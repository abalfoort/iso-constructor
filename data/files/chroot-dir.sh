#!/bin/bash

TARGET=$1
COMMANDS=$2

if [ -z "${TARGET}" ]; then
    echo 'Missing target directory to chroot into - exiting'
    exit 1
fi

if ! $(ls ${TARGET}{/run,/sys,/proc,/dev} >/dev/null 2>&1); then
    echo "Missing ${TARGET}/{dev,proc,sys,run} - exiting"
    exit 2
fi

if [ -d "${TARGET}/etc/" ] && [ -f "/etc/resolv.conf" ]; then
    cp -f "/etc/resolv.conf" "${TARGET}/etc/"
fi

# Make nodes and bind directories
{
    mount -vt devtmpfs devtmpfs ${TARGET}/dev
    mount -vt devpts devpts ${TARGET}/dev/pts
    mount -vt proc proc ${TARGET}/proc
    mount -vt sysfs sysfs ${TARGET}/sys
    mount -vt tmpfs tmpfs ${TARGET}/run
    if [ -d /sys/firmware/efi/efivars ] && 
    [ -d ${TARGET}/sys/firmware/efi/efivars ]; then
        mount -vt efivarfs efivarfs ${TARGET}/sys/firmware/efi/efivars
    fi
    if [ -h ${TARGET}/dev/shm ]; then mkdir -pv ${TARGET}/$(readlink ${TARGET}/dev/shm); fi
    if [ -h ${TARGET}/var/lock ]; then mkdir -pv ${TARGET}/$(readlink ${TARGET}/var/lock); fi
} &> /dev/null

# Chroot into dir
echo
echo "Chroot: ${TARGET}"
if [ ! -z "${COMMANDS}" ]; then
    echo "Commands: ${COMMANDS}"
    COMMANDS="-c \"${COMMANDS}\""
else
    echo 'Run your commands and exit with Ctrl-D when done.'
fi
echo

eval "chroot \"${TARGET}\" /usr/bin/env -i \
    HOME=/root \
    TERM=\"$TERM\" \
    PS1=\"\\[$(tput rev)\\](chroot):\w#\\[$(tput sgr0)\\] \" \
    PATH=/bin:/usr/bin:/sbin:/usr/sbin \
    /bin/bash --noprofile --login +h \
    ${COMMANDS}"

# Remove flag
rm -f "${TARGET}/.tmp"
   
# Unmount when done
umount -v ${TARGET}/{run,sys/firmware/efi/efivars,sys,proc,dev/pts,dev} &> /dev/null
