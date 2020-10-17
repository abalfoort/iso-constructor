#! /bin/bash

DISTPATH=$1
SHAREDIR='/usr/share/iso-constructor'

# Check before continue
if [ -z "$DISTPATH" ] || [ ! -d "$DISTPATH/boot" ] || [ ! -d "$DISTPATH/root" ]; then
    echo 'Current path must contain root and boot directories - exiting'
    exit 1
fi

# Chroot into distribution root directory and set the locale
cp -v "$SHAREDIR/_chroot-locale.sh" "$DISTPATH/root/"
$SHAREDIR/chroot-dir.sh "$DISTPATH/root" "bash -c /_chroot-locale.sh; rm /_chroot-locale.sh"

# Copy Grub locale files to ISO boot directory and configure grub.cfg
GRUBDIR="$DISTPATH/boot/boot/grub/"
GRUBCFG="$GRUBDIR/grub.cfg"
LOCALEDIR="$DISTPATH/root/boot/grub/locale"
DEFAULTDIR="$DISTPATH/root/etc/default"
LOCALE=$(grep -oP '(?<=LANG=).*?(?=\.)' "$DEFAULTDIR/locale")
if [ -d "$LOCALEDIR" ] && [ -f "$GRUBCFG" ] && [ ! -z "$LOCALE" ]; then
    cp -rvf "$LOCALEDIR" "$GRUBDIR"
    sed -i "s/set lang=.*/set lang=$LOCALE/" $GRUBCFG
fi

echo
echo 'Localizing finished'
