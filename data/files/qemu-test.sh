#!/bin/bash

HDIMG="$HOME/.iso-constructor/qemu.img"
DISTPATH=$1

if [ $UID -eq 0 ]; then
  echo "Run this script as $(logname), not as root"
  exit 1
fi

if [ ! -z "$DISTPATH" ]; then
    TISO=$(ls "$DISTPATH"/*.iso | head -n 1)
fi

if [ -z "$(which qemu-system-x86_64)" ]; then
    echo "qemu-system-x86_64 not installed - exiting"
    exit 3
fi

OVMF=$(dpkg -S OVMF.fd | head -n 1 | cut -d' ' -f 2)
if [ -z "$OVMF" ]; then
    echo "Cannot find OVMF.fd - exiting"
    exit 4
fi

# Get memory to use
MEM=2
MEMKB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
MEMGB=$(($MEMKB/1024/1024))
if [ $MEMGB -lt 4 ]; then
    echo "Not enough RAM (at least 4GB) - exiting"
    exit 5
fi
if [ $MEMGB -gt 8 ]; then
    MEM=4
fi
if [ $MEMGB -gt 16 ]; then
    MEM=8
fi

# Check audio device
HDA=$(qemu-system-x86_64 -device help | grep hda)
AUDIODEV=$(qemu-system-x86_64 -device help | grep -i audio | head -n 1 | cut -d'"' -f 2)
if [ ! -z "$AUDIODEV" ]; then
    #SRV=$(pactl info 2>/dev/null | grep -i 'Server String:' | cut -d' ' -f 3)
    SRV="/run/user/$UID/pulse/native"
    if [ -e "$SRV" ]; then
        #-device intel-hda -device hda-duplex,audiodev=pa1
        AUDIO="-audiodev id=pa1,driver=pa,server=$SRV -device $AUDIODEV,audiodev=pa1"
    fi
fi

# Create raw image
if [ ! -e "$HDIMG" ]; then
    # Check if 25G space available for 20G hd image
    AVAIL=$(df -k --output=avail "/tmp" | tail -n 1)
    if [ $AVAIL -gt 26214400 ]; then
        qemu-img create -f raw $HDIMG 20G
    fi
fi
if [ -e "$HDIMG" ]; then
    HD="-drive file=$HDIMG,format=raw,if=virtio"
fi

if [ ! -z "$TISO" ]; then
    CDROM="-cdrom \"$TISO\""
fi

if [ -z "$HD" ] && [ -z "$CDROM" ]; then
    echo "Cannot find ISO or $HDIMG"
    exit 0
fi

# List VGA devices:
# qemu-system-x86_64 -device help | grep -i vga
echo "Test ISO command: qemu-system-x86_64 -m ${MEM}G -enable-kvm $AUDIO -display gtk -vga virtio -full-screen -bios $OVMF $CDROM $HD"
eval "qemu-system-x86_64 -m ${MEM}G -enable-kvm $AUDIO -display gtk -vga virtio -full-screen -bios $OVMF $CDROM $HD" 
