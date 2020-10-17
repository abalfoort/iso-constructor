#! /bin/bash

ISOPATH=$1
TARGETDIR=$2

# Global variables
ISONAME=$(basename $ISOPATH)
MOUNTDIR="/tmp/${ISONAME%.*}"

# Check before continue
if [ -z "$ISOPATH" ] || [ ! -e "$ISOPATH" ]; then
    echo "Cannot find ISO file $ISOPATH - exiting"
    exit 1
fi
# Mount ISO 
mkdir -p "$MOUNTDIR"
modprobe loop
mount -o loop "$ISOPATH" "$MOUNTDIR"
if [ ! -d "$MOUNTDIR/isolinux" ]; then
    umount --force "$MOUNTDIR"
    echo "Cannot find isolinux directory in ISO file $ISONAME - exiting"
    exit 2
fi
SQUASHFS=$(find "$MOUNTDIR" -type f -name "filesystem.squashfs")
if [ -z "$SQUASHFS" ]; then
    echo "Cannot find filesystem.squashfs in ISO file $ISONAME - exiting"
    exit 3
fi

# Create directories
mkdir -p "$TARGETDIR/root" "$TARGETDIR/boot"

# Rsync the ISO to targetdir/boot
echo "> Unpack $ISONAME to $TARGETDIR/boot"
rsync -at --del --info=progress2 "$MOUNTDIR/" "$TARGETDIR/boot"
umount --force "$MOUNTDIR"

# Make sure the squashfs file is in the live directory
SQUASHFS=$(find "$TARGETDIR/boot" -type f -name "filesystem.squashfs")
SQUASHDIR=$(dirname $SQUASHFS)
BN=$(basename $SQUASHDIR)
if [ "$BN" != 'live' ]; then
    LIVEDIR="$TARGETDIR/boot/live"
    SQUASHFS="$LIVEDIR/filesystem.squashfs"
    mv "$SQUASHDIR" "$LIVEDIR"
    sed -i "s#/$BN#/live#g" "$TARGETDIR/boot/isolinux/isolinux.cfg"
fi

# Unpack filesystem.squashfs
mkdir -p "${MOUNTDIR}_FS"
mount -t squashfs -o loop "$SQUASHFS" "${MOUNTDIR}_FS"
echo "> Unpack $SQUASHFS to $TARGETDIR/root"
rsync -at --del --info=progress2 "${MOUNTDIR}_FS/" "$TARGETDIR/root"
umount --force "${MOUNTDIR}_FS"

# Set proper permissions
chmod 6755 "$TARGETDIR/root/usr/bin/sudo"
chmod 0440 "$TARGETDIR/root/etc/sudoers"

echo
echo 'Unpacking ISO finished'

