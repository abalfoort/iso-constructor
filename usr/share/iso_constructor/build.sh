#! /bin/bash

DISTPATH=$1
SHAREDIR='/usr/share/iso_constructor'

DESKTOPENV='kde'
if [ -e /usr/bin/startxfce4 ]; then
    DESKTOPENV='xfce'
fi

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
# Packages that must NOT be treated as obsolete - comma separated list
# Set to '*' to keep everything
KEEPPACKAGES=$(cat "$SHAREDIR/keep-packages" | sed -z 's/\n/,/g;s/,$//;s/ //')
if [ -f "$USERDIR/keep-packages" ]; then
    KEEPPACKAGES=$(cat "$USERDIR/keep-packages" | sed -z 's/\n/,/g;s/,$//;s/ //')
    echo "> Using custom keep-packages file: $USERDIR/keep-packages"
fi

# Run configuration script
cp -v "$SHAREDIR/_chroot-configure.sh" "$DISTPATH/root/"
bash $SHAREDIR/chroot-dir.sh "$DISTPATH/root" "bash /_chroot-configure.sh"
rm -f "$DISTPATH/root/_chroot-configure.sh"
echo

# Run cleanup script
cp -v "$SHAREDIR/_chroot-cleanup.sh" "$DISTPATH/root/"
bash $SHAREDIR/chroot-dir.sh "$DISTPATH/root" "bash /_chroot-cleanup.sh \"$KEEPPACKAGES\""
rm -f "$DISTPATH/root/_chroot-cleanup.sh"
echo

# Global variables
ARCH=$(file "$DISTPATH/root/bin/ls" | egrep -oh 'x86-64|i386' | head -n 1 | tr - _)
case $ARCH in
    i386|i686) DEBARCH="i386" ;;
    x86_64) DEBARCH="amd64" ;;
esac
DESCRIPTION=$(egrep '^DISTRIB_DESCRIPTION|^PRETTY_NAME' "$DISTPATH/root/etc/"*release | head -n 1 | cut -d'=' -f 2  | sed s'/(.*)//g;s/gnu//I;s/linux//I;s/bit//I;s/[/"\-]//g;s/ \+/ /g')
CODENAME=$(egrep '^DISTRIB_CODENAME|^VERSION_CODENAME' "$DISTPATH/root/etc/"*release | head -n 1 | cut -d'=' -f 2  | tr -d ' "_\-')
SHORTDATE=$(date +"%Y%m")
ISODATE=$(date +"%FT%T")
MODDATE=$(date +"%Y%m%d%H%M%S00")
ISOFILENAME=$(echo $DESCRIPTION | tr ' ' '_' | cut -d'-' -f 1 | tr '[:upper:]' '[:lower:]')"_$SHORTDATE"
LOCALIZED=$(grep -oP '(?<=LANG=).*?(?=_)' "$DISTPATH/root/etc/default/locale" | grep -v 'en')
if [ ! -z "$LOCALIZED" ]; then
    ISOFILENAME="$ISOFILENAME_$LOCALIZED"
fi
ISOFILENAME="$ISOFILENAME.iso"
# deb822-proof debian release command
DEBRELEASE=$(find "$DISTPATH/root/var/lib/apt/lists/" -maxdepth 1 -regex ".*/deb.debian.org_debian_dists_[a-z]+_InRelease" | grep -oP '(?<=dists_)([a-z]+)')
#DEBRELEASE=$(grep -oP '(?<=/debian )\w+(?= )' "$DISTPATH/root/etc/apt/sources.list" | head -n 1)

# Update offline packages
if [ -d "$DISTPATH/boot/offline" ]; then
    cd "$DISTPATH/boot"
    # Download packages
    DEBS=$(find offline -name "*.deb")
    for DEB in $DEBS; do
        DEBPATH=${DEB%/*}
        DEBNAME=${DEB##*/}
        PCKNAME=${DEBNAME%%_*}
        # Copy resolv.conf
        if [ ! -L "$DISTPATH/root/etc/resolv.conf" ] && [ -e "/etc/resolv.conf" ]; then
            if [ -f "$DISTPATH/root/etc/resolv.conf" ]; then
                mv -f "$DISTPATH/root/etc/resolv.conf" "$DISTPATH/root/etc/resolv.conf.bak"
            fi
            cat "/etc/resolv.conf" > "$DISTPATH/root/etc/resolv.conf"
        fi
        # Download package
        chroot "$DISTPATH/root" apt-get download $PCKNAME
        # Replace resolv.conf
        if [ -f "$DISTPATH/root/etc/resolv.conf.bak" ]; then
            mv -f "$DISTPATH/root/etc/resolv.conf.bak" "$DISTPATH/root/etc/resolv.conf"
        fi
        # Remove old deb
        rm -v "$DEBPATH/$PCKNAME"*.deb
        # Get downloaded deb
        mv -v "$DISTPATH/root/"*.deb "$DEBPATH"
    done
elif [ -d "$DISTPATH/boot/pool" ]; then
    cd "$DISTPATH/boot"
    # Fix _apt permission
    chroot "$DISTPATH/root" chown -R _apt:root /var/lib/apt/lists
    # Save system's apt information in a file
    echo "> Apt lists:"
    ls "$DISTPATH/root/var/lib/apt/lists/"*"debian"*"$DEBRELEASE"*"${DEBARCH}_Packages"
    cat $(ls "$DISTPATH/root/var/lib/apt/lists/"*"debian"*"$DEBRELEASE"*"${DEBARCH}_Packages") > apt.lst
    # Update deb files (not udeb)
    DEBS=$(find pool -name "*.deb")
    for DEB in $DEBS; do
        DEBPATH=${DEB%/*}
        DEBNAME=${DEB##*/}
        PCKNAME=${DEBNAME%%_*}
        # Get package version information
        DEBVERSION=$(dpkg-deb -I $DEB | grep -i version: | awk '{print $2}')
        NEWDEBVERSION=$(sed -n "/Package:\s*${PCKNAME}$/I,/\/*${PCKNAME}_/p" apt.lst | grep -i version: | awk '{print $2}' | head -n 1)
        echo "> Check $PCKNAME versions: $DEBVERSION > $NEWDEBVERSION"
        if [ ! -z "$DEBVERSION" ] && [ ! -z "$NEWDEBVERSION" ] && [ "$DEBVERSION" != "$NEWDEBVERSION" ]; then
            # Download new package
            if [ ! -L "$DISTPATH/root/etc/resolv.conf" ] && [ -e "/etc/resolv.conf" ]; then
                if [ -f "$DISTPATH/root/etc/resolv.conf" ]; then
                    mv -f "$DISTPATH/root/etc/resolv.conf" "$DISTPATH/root/etc/resolv.conf.bak"
                fi
                cat "/etc/resolv.conf" > "$DISTPATH/root/etc/resolv.conf"
            fi
            chroot "$DISTPATH/root" apt-get download $PCKNAME
            if [ -f "$DISTPATH/root/etc/resolv.conf.bak" ]; then
                mv -f "$DISTPATH/root/etc/resolv.conf.bak" "$DISTPATH/root/etc/resolv.conf"
            fi
            rm -v "$DEBPATH/${PCKNAME}_"*.deb
            mv -v "$DISTPATH/root/"*.deb "$DEBPATH"
        fi
    done
    rm -f apt.lst
    # Create configuration for dists files
    CONFDEB='Dir { ArchiveDir "."; }; TreeDefault { Directory "pool/"; };'
    COMPONENTS=$(ls pool)
    for COMP in $COMPONENTS; do
        mkdir -p "dists/$DEBRELEASE/$COMP/binary-$DEBARCH"
        CONFDEB="$CONFDEB BinDirectory \"pool/$COMP\" { Packages \"dists/$DEBRELEASE/$COMP/binary-$DEBARCH/Packages\"; };"
    done
    CONFDEB="$CONFDEB Default { Packages { Extensions \".deb .udeb\"; }; }; "
    echo "$CONFDEB" | tee config-deb
    # Create dists files
    apt-ftparchive generate config-deb
    rm config-deb
    # Remove Release file
    rm -f "dists/$DEBRELEASE/Release"
    # Update Release file
    OPTIONS="-o APT::FTPArchive::Release::Origin=Debian -o APT::FTPArchive::Release::Label=Debian -o APT::FTPArchive::Release::Codename=$DEBRELEASE -o APT::FTPArchive::Release::Architectures=$DEBARCH -o APT::FTPArchive::Release::Components=$(echo $COMPONENTS | tr ' ' ',') -o APT::FTPArchive::Release::Suite=stable"
    apt-ftparchive $OPTIONS release "dists/$DEBRELEASE" >> "dists/$DEBRELEASE/Release"
    # Update md5sum.txt
    md5sum `find ! -name "md5sum.txt" ! -path "./isolinux/*" -follow -type f` > md5sum.txt
fi

# Create disk info directories/files
mkdir -p "$DISTPATH/boot/live"
mkdir -p "$DISTPATH/boot/.disk"
touch "$DISTPATH/boot/.disk/base_installable"
touch "$DISTPATH/boot/.disk/udeb_include"
echo "$DESCRIPTION Live $(date +"%Y%m") $DESKTOPENV $ISODATE" > "$DISTPATH/boot/.disk/info"
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
cp -vf "$SHAREDIR/isolinux/"* "$DISTPATH/boot/isolinux/"

# copy grub files
if [ -d "$DISTPATH/root/usr/lib/grub/x86_64-efi" ]; then
    mkdir -p "$DISTPATH/boot/boot/grub/x86_64-efi"
    rm -rf "$DISTPATH/boot/boot/grub/x86_64-efi/"*
    echo "Copy /usr/lib/grub/x86_64-efi to $DISTPATH/boot/boot/grub/"
    cp -f "$DISTPATH/root/usr/lib/grub/x86_64-efi/"* "$DISTPATH/boot/boot/grub/x86_64-efi/"
fi
cp -vf "$SHAREDIR/grub/"* "$DISTPATH/boot/boot/grub/"

# Copy the signed efi files
rm -rf "$DISTPATH/boot/EFI"
mkdir -p "$DISTPATH/boot/EFI/boot"
cp -av $DISTPATH/root/usr/lib/shim/shim*.efi.signed $DISTPATH/boot/EFI/boot/bootx64.efi
cp -av $DISTPATH/root/usr/lib/grub/x86_64-efi-signed/gcdx64.efi.signed $DISTPATH/boot/EFI/boot/grubx64.efi

# Create img file
if [ -f $DISTPATH/boot/EFI/boot/grubx64.efi ]; then
    cat > $DISTPATH/grub.cfg << EOF
search --set=root --file /.disk/info
if [ -e (\$root)/boot/grub/grub.cfg ]; then
    set prefix=(\$root)/boot/grub
    configfile \$prefix/grub.cfg
else
    echo 'Could not find /boot/grub/grub.cfg!'
fi
EOF
    dd if=/dev/zero of=$DISTPATH/boot/boot/grub/efi.img bs=1M count=5
    mkfs.vfat $DISTPATH/boot/boot/grub/efi.img 
    mmd -i $DISTPATH/boot/boot/grub/efi.img EFI EFI/boot boot boot/grub
    mcopy -vi $DISTPATH/boot/boot/grub/efi.img "$DISTPATH/boot/EFI/boot/bootx64.efi" ::EFI/boot/
    mcopy -vi $DISTPATH/boot/boot/grub/efi.img "$DISTPATH/boot/EFI/boot/grubx64.efi" ::EFI/boot/
    mcopy -vi $DISTPATH/boot/boot/grub/efi.img "$DISTPATH/grub.cfg" ::boot/grub/
    rm $DISTPATH/grub.cfg
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

# build iso
cd "$DISTPATH"
CMD="xorriso -as mkisofs -R -r -J -joliet-long -l -iso-level 3 -isohybrid-mbr ${ISOHDPFX} -partition_offset 16 -A \"${CODENAME} Live\" -publisher \"${CODENAME} Live project; https://solydxk.com\" -V \"${CODENAME^^}\" --modification-date=${MODDATE} -b isolinux/isolinux.bin -c isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table -eltorito-alt-boot -e boot/grub/efi.img -no-emul-boot -isohybrid-gpt-basdat -isohybrid-apm-hfsplus -o \"${ISOFILENAME}\" boot"
echo $CMD
eval $CMD

# Save the xorriso command to mkisofs file
echo "$CMD" > "./boot/.disk/mkisofs"

# Create sha256 file
sha256sum "$ISOFILENAME" > "$ISOFILENAME.sha256"

echo
echo "Building $ISOFILENAME finished"
