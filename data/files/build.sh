#! /bin/bash

DISTPATH=$1
SHAREDIR='/usr/share/iso-constructor'

# Check before continue
if [ -z "$DISTPATH" ] || [ ! -d "$DISTPATH/boot" ] || [ ! -d "$DISTPATH/root" ]; then
    echo 'Current path must contain root and boot directories - exiting'
    exit 1
fi
HOSTEFIARCH=$(ls /usr/lib/grub/ 2>/dev/null | grep efi | cut -d'-' -f1)
if [ -z "$HOSTEFIARCH" ]; then
    echo 'Cannot find host EFI architecture in /usr/lib/grub - exiting'
    exit 2
fi
ISOHDPFX=$(dpkg -S isohdpfx.bin | awk '{print $2}')
if [ -z "$ISOHDPFX" ]; then
    echo 'Cannot find path to isohdpfx.bin - install isolinux - exiting'
    exit 3
fi

# Chroot into distribution root directory and cleanup first
USERDIR="/home/$(logname)/.iso-constructor"
# Packages that deborphan must NOT treat as orphans - comma separated list
# Set to '*' to keep everything
KEEPPACKAGES=$(cat "$SHAREDIR/keep-packages" | sed -z 's/\n/,/g;s/,$//;s/ //')
if [ -f "$USERDIR/keep-packages" ]; then
    KEEPPACKAGES=$(cat "$USERDIR/keep-packages" | sed -z 's/\n/,/g;s/,$//;s/ //')
    echo "> Using custom keep-packages file: $USERDIR/keep-packages"
fi
cp -v "$SHAREDIR/_chroot-cleanup.sh" "$DISTPATH/root/"
bash $SHAREDIR/chroot-dir.sh "$DISTPATH/root" "bash /_chroot-cleanup.sh \"$KEEPPACKAGES\"; rm /_chroot-cleanup.sh"
echo

# Move offline packages for live-installer-3
if [ -d "$DISTPATH/root/offline" ]; then
    rm -r "$DISTPATH/boot/offline" 2>/dev/null
    mv "$DISTPATH/root/offline" "$DISTPATH/boot/offline"
fi

# Global variables
ARCH=$(file "$DISTPATH/root/bin/ls" | egrep -oh 'x86-64|i386' | head -n 1 | tr - _)
DESCRIPTION=$(egrep '^DISTRIB_DESCRIPTION|^PRETTY_NAME' "$DISTPATH/root/etc/"*release | head -n 1 | cut -d'=' -f 2  | sed s'/(.*)//g;s/gnu//I;s/linux//I;s/bit//I;s/[/"\-]//g;s/ \+/ /g')
VOLID=$(echo $DESCRIPTION | tr ' ' '_'  | tr '[:lower:]' '[:upper:]')
CODENAME=$(egrep '^DISTRIB_CODENAME|^VERSION_CODENAME' "$DISTPATH/root/etc/"*release | head -n 1 | cut -d'=' -f 2  | tr -d ' "_\-')
CODENAME=${CODENAME^^}
SHORTDATE=$(date +"%Y%m")
ISODATE=$(date +"%FT%T")
ISOFILENAME=$(echo $DESCRIPTION | tr ' ' '_' | cut -d'-' -f 1 | tr '[:upper:]' '[:lower:]')"_$SHORTDATE"
LOCALIZED=$(grep -oP '(?<=LANG=).*?(?=_)' "$DISTPATH/root/etc/default/locale" | grep -v 'en')
if [ ! -z "$LOCALIZED" ]; then
    ISOFILENAME="$ISOFILENAME_$LOCALIZED"
fi
ISOFILENAME="$ISOFILENAME.iso"

# Create disk info directories/files
mkdir -p "$DISTPATH/boot/live"
mkdir -p "$DISTPATH/boot/.disk"
touch "$DISTPATH/boot/.disk/base_installable"
touch "$DISTPATH/boot/.disk/udeb_include"
if [ ! -e "$DISTPATH/boot/.disk/base_components" ]; then
    echo 'main' > "$DISTPATH/boot/.disk/base_components"
fi
if [ ! -e "$DISTPATH/boot/.disk/base_components" ]; then
    echo 'live' > "$DISTPATH/boot/.disk/cd_type"
fi
cat >"$DISTPATH/boot/.disk/udeb_include" <<EOF
netcfg
ethdetect
pcmciautils-udeb
live-installer
EOF

# Copy system boot files (initrd, vmlinuz, etc) to live directory 
rm -r "$DISTPATH/boot/live/"*
cp -vf "$DISTPATH/root/boot/"* "$DISTPATH/boot/live/" 2>/dev/null

# Generate grub.cfg / isolinux.cfg
cp "$SHAREDIR/_grubgen.sh" "$DISTPATH/boot/"
cp "$SHAREDIR/_isolinuxgen.sh" "$DISTPATH/boot/"
cd "$DISTPATH/boot"
bash _grubgen.sh
bash _isolinuxgen.sh
rm *.sh

# check for custom mksquashfs (for multi-threading, new features, etc.)
if [ -z "$MKSQUASHFS" ] || [ "$MKSQUASHFS" == 'mksquashfs' ]; then
    # Use half of the cpu cores
    NRCORES=$(egrep '^cpu cores.*([0-9])' /proc/cpuinfo | head -n 1 | cut -d':' -f 2 | tr -d ' ')
    AVCORES=$((NRCORES / 2))
    if [ -z "$AVCORES" ] || [ "$AVCORES" -lt 1 ]; then
        AVCORES=1
    fi
    # Create squashfs file
    CMD="mksquashfs \"$DISTPATH/root/\" \"$DISTPATH/boot/live/filesystem.squashfs\" -comp xz -processors $AVCORES -wildcards -ef \"$SHAREDIR/excludes\""
    echo $CMD
    eval $CMD
else
    eval "$MKSQUASHFS \"$DISTPATH/root\" \"$DISTPATH/boot/live/filesystem.squashfs\""
fi

# Update isolinux files
chmod -R +w "$DISTPATH/boot/isolinux"
cp -vf "/usr/lib/syslinux/modules/bios/"{chain.c32,hdt.c32,libmenu.c32,libgpl.c32,reboot.c32,vesamenu.c32,poweroff.c32,ldlinux.c32,libcom32.c32,libutil.c32} "$DISTPATH/boot/isolinux/"
cp -vf '/usr/lib/ISOLINUX/isolinux.bin' "$DISTPATH/boot/isolinux"
cp -vf '/usr/lib/syslinux/memdisk' "$DISTPATH/boot/isolinux"

# copy efi mods
if [ -d '/usr/lib/grub/x86_64-efi' ]; then
    rm -r "$DISTPATH/boot/boot/grub/x86_64-efi"
    cp -rvf '/usr/lib/grub/x86_64-efi' "$DISTPATH/boot/boot/grub/"
fi

# Build EFI image
GRUBEFI="bootx64"
if [ "$ARCH" == 'i386' ]; then GRUBEFI='bootia32'; fi

rm -r "$DISTPATH/boot/EFI" 2>/dev/null
mkdir -p "$DISTPATH/boot/EFI/boot" 2>/dev/null

# Create embedded.cfg
# Check contents with: strings bootx64.efi | grep "set=root"
cat >"embedded.cfg" <<EOF
search --file --set=root /md5sum.txt
if [ -e (\$root)/boot/grub/grub.cfg ]; then
    set prefix=(\$root)/boot/grub
    configfile \$prefix/grub.cfg
else
    echo 'Could not find /boot/grub/grub.cfg!'
fi
EOF

echo -e "embedded.cfg content:\n$(cat embedded.cfg)"

# Now we can actually create the EFI file
MODS="part_gpt part_msdos ntfs ntfscomp hfsplus fat ext2 chain boot configfile linux multiboot iso9660 gfxmenu gfxterm loadenv efi_gop efi_uga loadbios fixvideo png loopback search minicmd cat cpuid appleldr elf usb videotest halt help ls reboot echo test normal sleep memdisk tar font video_fb video gettext true video_bochs video_cirrus multiboot2 acpi gfxterm_background gfxterm_menu"

CMD="grub-mkimage --prefix '' --config \"embedded.cfg\" -O $ARCH-efi -o \"$DISTPATH/boot/EFI/boot/$GRUBEFI.efi\" $MODS"
echo $CMD
eval $CMD
rm -v embedded.cfg

# Create img file
if [ -f "$DISTPATH/boot/EFI/boot/$GRUBEFI.efi" ]; then
    rm "$DISTPATH/boot/boot/grub/efi.img" 2>/dev/null
    CMD="mkdosfs -F 12 -n \"$CODENAME\" -C \"$DISTPATH/boot/boot/grub/efi.img\" 2048"
    echo $CMD
    eval $CMD
fi

# remove existing iso
rm "$DISTPATH/"*.iso* 2>/dev/null

# Create an md5sum file for the isolinux/grub integrity check
cat >'md5sum.txt' <<EOF
## This file contains the list of md5 checksums of all files on this medium.
## You can verify them automatically with the 'verify-checksums' boot parameter
## or manually with: 'md5sum -c md5sum.txt'.
EOF
for F in $(find . -type f ! -name "md5sum.txt" ! -name "isolinux.bin" ! -name "boot.cat"); do
    md5sum "$F" >> 'md5sum.txt'
done

# build iso according to architecture
cd "$DISTPATH"
CMD="xorriso -outdev \"$ISOFILENAME\" -volid $VOLID -padding 0 -compliance no_emul_toc -map ./boot / -chmod 0755 / -- -boot_image isolinux dir=/isolinux  -boot_image isolinux system_area=$ISOHDPFX -boot_image any next -boot_image any efi_path=boot/grub/efi.img -boot_image isolinux partition_entry=gpt_basdat"
echo $CMD
eval $CMD

# Save the xorriso command to mkisofs file
echo "$CMD" > "./boot/.disk/mkisofs"

# Create sha256 file
sha256sum "$ISOFILENAME" > "$ISOFILENAME.sha256"

echo
echo "Building $ISOFILENAME finished"
