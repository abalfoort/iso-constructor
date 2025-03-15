#!/bin/bash

MACHINE_NAME="SolydXK"
HDQCOW="$HOME/.iso-constructor/${MACHINE_NAME}.qcow2"
OVMF_CODE="/usr/share/OVMF/OVMF_CODE_4M.ms.fd"
OVMF_VARS_ORIG="/usr/share/OVMF/OVMF_VARS_4M.ms.fd"
OVMF_VARS="$HOME/.iso-constructor/$(basename "${OVMF_VARS_ORIG}")"
DISTPATH=$1

if [ $UID -eq 0 ]; then
  echo "Run this script as $(logname), not as root"
  exit 1
fi

if [ ! -z "$DISTPATH" ]; then
    TISO=$(ls "$DISTPATH"/*.iso | head -n 1)
    if [ ! -e "${TISO}" ]; then
        echo "Cannot find ISO file ${TISO}"
        exit 2
    fi
fi

if [ -z "$(which qemu-system-x86_64)" ]; then
    echo "qemu-system-x86_64 not installed - exiting"
    exit 3
fi

if [ ! -e "${OVMF_VARS}" ] && [ -e "${OVMF_VARS_ORIG}" ]; then
    cp "${OVMF_VARS_ORIG}" "${OVMF_VARS}"
fi

if [ ! -e "${OVMF_CODE}" ] || [ ! -e ${OVMF_VARS} ]; then
    echo "Cannot find OVMF files - exiting"
    exit 4
fi

# Get memory to use
MEM=2
MEMKB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
MEMGB=$((${MEMKB}/1024/1024))
if ((${MEMGB}<=4)); then
    echo "Not enough RAM (at least 4GB) - exiting"
    exit 5
fi
((${MEMGB}>=8)) && MEM=4
((${MEMGB}>=16)) && MEM=8
((${MEMGB}>=32)) && MEM=16

# Get nr of CPUs to use
CPU=1
TCPU=$(grep -c ^processor /proc/cpuinfo)
UCPU=$(($TCPU/2))
if ((${UCPU}<2)); then
    echo "Just one CPU available - exiting"
    exit 6
fi
((${UCPU}>=4)) && CPU=2
((${UCPU}>=8)) && CPU=4
((${UCPU}>=16)) && CPU=8

# Create image
if [ ! -e "${HDQCOW}" ]; then
    # Check if 25G space available for 20G hd image
    AVAIL=$(df -k --output=avail "/tmp" | tail -n 1)
    if [ ${AVAIL} -gt 26214400 ]; then
        qemu-img create -f qcow2 ${HDQCOW} 20G
    fi
    if [ ! -e "${HDQCOW}" ]; then
        echo "Cannot create ${HDQCOW}"
        exit 7
    fi
fi

# Build the connected USB paramater
USBS=$(lsblk -p -S -o NAME,TRAN | grep usb | awk '{print $1}')
for USB in $USBS; do
    IDSARRAY=( $(udevadm info --query=property --name=$USB --property=ID_VENDOR_ID --property=ID_MODEL_ID --value) )
    if [ ${#IDSARRAY[@]} -eq 2 ]; then
        USBDEVICE+="-device usb-host,vendorid=0x${IDSARRAY[1]},productid=0x${IDSARRAY[0]},id=usb${IDSARRAY[1]}${IDSARRAY[0]} "
    fi
done
if [ ! -z "$USBDEVICE" ]; then
    USBDEVICE="-device qemu-xhci $USBDEVICE"
fi


CMD="qemu-system-x86_64 \
 -enable-kvm \
 -name \"${MACHINE_NAME}\" \
 -cpu host \
 -machine q35,accel=kvm \
 -vga virtio -full-screen \
 -netdev user,id=net0 \
 -m ${MEM}G \
 -smp cores=${CPU} \
 -drive if=pflash,format=raw,readonly=on,file=${OVMF_CODE},index=0 \
 -drive if=pflash,format=raw,file=${OVMF_VARS},index=1 \
 -drive file=\"${HDQCOW}\",id=disk,format=qcow2,index=2,if=virtio \
 -drive file=\"${TISO}\",format=raw,index=3,media=cdrom \
 -chardev qemu-vdagent,id=ch1,name=vdagent,clipboard=on \
 -device virtio-balloon \
 -device virtio-net-pci,netdev=net0 \
 -device intel-hda \
 -device hda-output,audiodev=audio0 \
 -device virtio-serial-pci \
 -device virtserialport,chardev=ch1,id=ch1,name=com.redhat.spice.0 \
 -audiodev sdl,id=audio0 \
 -virtfs local,path=${HOME},mount_tag=hostshare,security_model=passthrough,id=hostshare \
 $USBDEVICE"
 
 echo $CMD
 
 eval $CMD
 
exit 0
