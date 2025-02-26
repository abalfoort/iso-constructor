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

TMP=$(mktemp)
trap 'rm -f ${TMP}' EXIT
chmod u+x "${TMP}"

set -e

# Create bash to mount temporary API filesystems
cat > "${TMP}"  <<END
#!/bin/bash
set -e ${X}
: Entered private mount namespace
if [ -h ${TARGET}/dev/shm ]; then mkdir -p ${TARGET}$(readlink ${TARGET}/dev/shm); fi
if [ -h ${TARGET}/var/lock ]; then mkdir -p ${TARGET}$(readlink ${TARGET}/var/lock); fi
mount -t devtmpfs devtmpfs ${TARGET}/dev
mount -t devpts devpts ${TARGET}/dev/pts
mount -t tmpfs tmpfs ${TARGET}/dev/shm
mount -t proc proc ${TARGET}/proc
mount -t sysfs sysfs ${TARGET}/sys
if [ -d /sys/firmware/efi/efivars ] && 
   [ -d ${TARGET}/sys/firmware/efi/efivars ]; then
    mount -t efivarfs efivarfs ${TARGET}/sys/firmware/efi/efivars
fi
export LANGUAGE=C
export LANG=C
export LC_ALL=C
END

# Enable networking in chroot environment
if [ ! -L "${TARGET}/etc/resolv.conf" ] && [ -e "/etc/resolv.conf" ]; then
    if [ -f "${TARGET}/etc/resolv.conf" ]; then
        mv -f "${TARGET}/etc/resolv.conf" "${TARGET}/etc/resolv.conf.bak"
    fi
    cat "/etc/resolv.conf" > "${TARGET}/etc/resolv.conf"
fi

echo
echo "Chroot: ${TARGET}"
if [ -z "${COMMANDS}" ]; then
    echo 'Run your commands and exit with Ctrl-D when done.'
    echo
    echo chroot "${TARGET}" >> "$TMP"
else
    echo "Commands: ${COMMANDS}"
    echo
    echo chroot "${TARGET}" "${COMMANDS}" >> "$TMP"
fi

# Run program in new namespaces
unshare -m -- "${TMP}"

if [ -f "${TARGET}/etc/resolv.conf.bak" ]; then
    mv -f "${TARGET}/etc/resolv.conf.bak" "${TARGET}/etc/resolv.conf"
fi
