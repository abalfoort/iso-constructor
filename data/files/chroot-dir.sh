#!/bin/bash

TARGET=$1
COMMANDS=$2

if [ -z "$TARGET" ]; then
    echo 'Missing target directory to chroot into - exiting'
    exit 1
fi

if [ ! -d "$TARGET"/dev ] || [ ! -d "$TARGET"/proc ] || [ ! -d "$TARGET"/sys ] || [ ! -d "$TARGET"/run ]; then
    echo "Missing $TARGET/{dev,proc,sys,run} - exiting"
    exit 2
fi

if [ -d "$TARGET/etc/" ] && [ -f "/etc/resolv.conf" ]; then
    cp -f "/etc/resolv.conf" "$TARGET/etc/"
fi

# Make nodes and bind directories
{
    mknod -m 600 "$TARGET"/dev/console c 5 1
    mknod -m 666 "$TARGET"/dev/null c 1 3 2
    mount -v --bind /dev "$TARGET"/dev
    mount -vt devpts devpts "$TARGET"/dev/pts -o gid=5,mode=620
    mount -vt proc proc "$TARGET"/proc
    mount -vt sysfs sysfs "$TARGET"/sys
    mount -vt tmpfs tmpfs "$TARGET"/run
    if [ -h "$TARGET"/dev/shm ]; then mkdir -pv "$TARGET"/$(readlink "$TARGET"/dev/shm); fi
    if [ -h "$TARGET"/var/lock ]; then mkdir -pv "$TARGET"/$(readlink "$TARGET"/var/lock); fi
} &> /dev/null

# Chroot into dir
echo
echo "Chroot: $TARGET"
if [ ! -z "$COMMANDS" ]; then
    echo "Commands: $COMMANDS"
    COMMANDS="-c \"$COMMANDS\""
else
    echo 'Run your commands and exit with Ctrl-D when done.'
fi
echo

eval "chroot \"$TARGET\" /usr/bin/env -i \
    HOME=/root \
    TERM=\"$TERM\" \
    PS1=\"\\[$(tput rev)\\](chroot):\w#\\[$(tput sgr0)\\] \" \
    PATH=/bin:/usr/bin:/sbin:/usr/sbin \
    /bin/bash --noprofile --login +h \
    $COMMANDS"

# Remove flag
rm -f "$TARGET/.tmp"
   
# Unmount when done
umount -v "$TARGET"/{run,sys,proc,dev/pts,dev} &> /dev/null
