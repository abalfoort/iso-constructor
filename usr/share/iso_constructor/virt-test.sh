#!/bin/bash
# Test ISOs from ISO Constructor

DISTPATH=$1
if [ ! -z "$DISTPATH" ]; then
    ISO=$(ls "$DISTPATH"/*.iso | head -n 1)
fi
if [ -z "${ISO}" ]; then
    notify-send -u critical -a "ISO Constructor" -i iso-constructor "Cannot find the ISO - exiting"
    exit 1
fi

NAME="${ISO##*/}"
NAME="${NAME%.*}"
HDQCOW="$HOME/.iso-constructor/iso-constructor.qcow2"

if [ $UID -eq 0 ]; then
  notify-send -u critical -a "ISO Constructor" -i iso-constructor "Run this script as $(logname), not as root - exiting"
  exit 2
fi

VINST=$(which virt-install)
if [ -z "$VINST" ]; then
    notify-send -u critical -a "ISO Constructor" -i iso-constructor "virt-install not installed - exiting"
    exit 3
fi

# Get memory to use
MEMKB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
MEMMB=$((${MEMKB}/1000))
if ((${MEMMB}<=4000)); then
    notify-send -u critical -a "ISO Constructor" -i iso-constructor "Not enough RAM (at least 4GB) - exiting"
    exit 4
fi
((${MEMMB}>=8000)) && MEM=4000
((${MEMMB}>=16000)) && MEM=8000
((${MEMMB}>=32000)) && MEM=16000

# Get nr of CPUs to use
CPU=1
TCPU=$(grep -c ^processor /proc/cpuinfo)
UCPU=$(($TCPU/2))
if ((${UCPU}<2)); then
    notify-send -u critical -a "ISO Constructor" -i iso-constructor "Just one CPU available - exiting"
    exit 5
fi
((${UCPU}>=4)) && CPU=2
((${UCPU}>=8)) && CPU=4
((${UCPU}>=16)) && CPU=8

# Create image
if [ ! -e "${HDQCOW}" ]; then
    # Check if 25G space available for 20G hd image
    AVAIL=$(df -k --output=avail "/tmp" | tail -n 1)
    if [ ${AVAIL} -gt 26214400 ]; then
        HDQCOW="--disk ${HDQCOW},size=20,format=qcow2"
    else
        notify-send -u critical -a "ISO Constructor" -i iso-constructor "Missing hard drive" "${HDQCOW} cannot be created.\n${ISO} will boot, but cannot be installed."
        HDQCOW=""
    fi
else
    HDQCOW="--disk=${HDQCOW}"
fi

ARGS=(
 --name ${NAME}
 --vcpus ${CPU}
 --memory ${MEM}
 --memorybacking source.type=memfd,access.mode=shared
 --arch x86_64
 --machine q35
 --network type=user,model=virtio
 --cpu host
 --video virtio
 --virt-type kvm
 --sound ich9
 ${HDQCOW}
 --cdrom ${ISO}
 --os-variant debiantesting
 --boot cdrom,hd,menu=on,firmware=efi
 --noreboot
 --filesystem $HOME,hostshare
 --controller type=virtio-serial
 --controller type=usb,model=none
 --controller type=scsi,model=virtio-scsi
 --input type=keyboard,bus=virtio
 --input type=tablet,bus=virtio
 --rng /dev/urandom,model=virtio
 --check all=off
 --destroy-on-exit
)

echo
echo "$VINST ${ARGS[@]}"
echo
eval "$VINST ${ARGS[@]}"

# Delete the guest: this is only for testing ISOs
virsh undefine --nvram ${NAME}

exit 0
