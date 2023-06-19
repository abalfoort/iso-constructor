#!/bin/bash

# Generates a template isolinux.cfg with a list of languages
# Depends upon uni2ascii

# Set variables
SHAREDIR='/usr/share/iso-constructor'
USERDIR="/home/$(logname)/.iso-constructor"
ISOLINUXTEMPLATE="$SHAREDIR/isolinux-template"
if [ -f "$USERDIR/isolinux-template" ]; then
    ISOLINUXTEMPLATE="$USERDIR/isolinux-template"
    echo "> Using custom Isolinux template: $ISOLINUXTEMPLATE"
fi
ISOLINUX='isolinux/isolinux.cfg'
LARRAY=()
ROOTDIR=$1
TITLE=$(egrep 'DISTRIB_DESCRIPTION|PRETTY_NAME' ../root/etc/*release | head -n 1 | cut -d'=' -f 2  | tr -d '"')

echo '> Start creating isolinux boot configuration'

# Get installed kernels and generate menus
VMLINUZFILES=$(ls live/vmlinuz* | sort)
for VMLINUZFLE in $VMLINUZFILES; do
    VER=${VMLINUZFLE#*-}
    [ ! -z "$VER" ] && VMLINUZVER="-${VER}"
    INITRDFLE="live/initrd.img${VMLINUZVER}"
    
    if [ -f "$INITRDFLE" ]; then
        echo "KERNEL: $VMLINUZFLE - $INITRDFLE - $VER"
        # Save paths to first vmlinuz/initrd.img for Advanced Options
        if [ -z "$VMLINUZDEFAULT" ]; then
            VMLINUZDEFAULT="/$VMLINUZFLE"
            INITRDDEFAULT="/$INITRDFLE"
            # Build menu string
            MENU="LABEL live$VMLINUZVER\n    MENU LABEL Start $TITLE\n    MENU default\n    KERNEL /$VMLINUZFLE\n    APPEND initrd=/$INITRDFLE boot=live components quiet splash\n"
        else
            # Extra kernels
            [ ! -z "$VER" ] && VERSTR=" (kernel ${VER%-*})"
            MENUPLUS="$MENUPLUS\n    LABEL live$VMLINUZVER\n        MENU LABEL Start $TITLE$VERSTR\n        KERNEL /$VMLINUZFLE\n        APPEND initrd=/$INITRDFLE boot=live components quiet splash\n"
        fi
    fi
done

# Exit on failure
[ -z "$MENU" ] && echo "ERROR: failed to generate isolinux.cfg" && exit 1

# Use the template to generate isolinux.cfg
sed "s|\[MENU\]|$MENU\n|" "$ISOLINUXTEMPLATE" > "$ISOLINUX"
sed -i "s|\[TITLE\]|$TITLE|g" "$ISOLINUX"
sed -i "s|\[MENUPLUS\]|$MENUPLUS|" "$ISOLINUX"

# Check if supported languages file exists
LSUP='/usr/share/i18n/SUPPORTED'
if [ ! -f "$LSUP" ]; then
    echo "ERROR: Cannot find $LSUP - no localized menu items will be generated."
else
    # Loop through all supported languages and get the local language name
    for LOCALE in $(grep 'UTF-8' "$LSUP" | grep -oP '[a-z]*_[A-Z]*' | uniq); do
        LPATH="/usr/share/i18n/locales/$LOCALE"
        if [ -e "$LPATH" ]; then
            # When unicode code points (e.g.: <U00F1>): 
            # apt install uni2ascii
            LNAME=$(grep -E '^lang_name' "$LPATH" | grep -oP '(?<=").*?(?=")' | ascii2uni -a A -q)

            # Or English language name instead:
            #LNAME=$(egrep '^language' "$LPATH" | grep -oP '(?<=").*?(?=")')
            
            # Add to array if language name was found
            if [ ! -z "$LNAME" ]; then
                LARRAY+=("$LNAME|$LOCALE")
            fi
        fi
    done

    # Check if array was filled
    if [ ${#LARRAY[@]} -eq 0 ]; then
        echo 'ERROR: language array not filled - exiting'
        exit 2
    fi

    # Generate header
    # https://wiki.syslinux.org/wiki/index.php?title=Comboot/menu.c32
    #Generate language menus
    IFS=$'\n' SARRAY=($(sort <<<"${LARRAY[*]}"))
    # printf "%s\n" "${SARRAY[@]}"
    for ITEM in ${SARRAY[@]}; do
        IFS='|' read -ra ADDR <<< "$ITEM"
        CNTR=${ADDR[1]#*_}
        LOCALES="$LOCALES\n        LABEL ${ADDR[1]}\n            MENU LABEL ${ADDR[0]} (${ADDR[1]})\n            KERNEL $VMLINUZDEFAULT\n            APPEND initrd=$INITRDDEFAULT boot=live components locales=${ADDR[1]}.UTF-8 keyboard-layouts=${CNTR,,},us quiet splash"
    done
    
    # Build the menu
    if [ ! -z "$LOCALES" ]; then
        LOCALES="MENU BEGIN locales\n    MENU TITLE $TITLE with Localisation Support\n        $LOCALES\n        LABEL back\n            MENU LABEL ^Back...\n            MENU exit\nMENU end"
    fi
fi

# Debian Installer
if [ -d "d-i" ]; then
    if [ -f "d-i/gtk/vmlinuz" ]; then
        DEBINSTALLER="LABEL digui\n            MENU LABEL Graphical Debian Installer\n            KERNEL /d-i/gtk/vmlinuz\n            APPEND initrd=/d-i/gtk/initrd.gz append video=vesa:ywrap,mtrr vga=788"
    fi
    if [ -f "d-i/vmlinuz" ]; then
        DEBINSTALLER="$DEBINSTALLER\n        LABEL dinorm\n            MENU LABEL Debian Installer\n            KERNEL /d-i/vmlinuz\n            APPEND initrd=/d-i/initrd.gz"
    fi
    if [ -f "d-i/gtk/vmlinuz" ]; then
        DEBINSTALLER="$DEBINSTALLER\n        LABEL disynth\n            MENU LABEL Debian Installer with Speech Synthesis\n            KERNEL /d-i/gtk/vmlinuz\n            APPEND initrd=/d-i/gtk/initrd.gz speakup.synth=soft"
    fi
    
    # Build the menu
    if [ ! -z "$DEBINSTALLER" ]; then
        DEBINSTALLER="MENU BEGIN debinstaller\n    MENU TITLE Debian Installer\n        $DEBINSTALLER\n        LABEL back\n            MENU LABEL ^Back...\n            MENU exit\nMENU end"
    fi
fi

# Update isolinux.cfg
sed -i "s|\[LOCALES\]|$LOCALES|" "$ISOLINUX"
sed -i "s|\[DEBINSTALLER\]|$DEBINSTALLER|" "$ISOLINUX"
sed -i "s|\[VMLINUZ\]|$VMLINUZDEFAULT|" "$ISOLINUX"
sed -i "s|\[INITRD\]|$INITRDDEFAULT|" "$ISOLINUX"

echo "Isolinux gen successfuly generated: $ISOLINUX"
exit 0
