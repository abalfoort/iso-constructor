#!/bin/bash

# Generates a template grub.cfg with a list of languages
# Depends upon uni2ascii

# Set variables
SHAREDIR='/usr/share/iso-constructor'
USERDIR="/home/$(logname)/.iso-constructor"
GRUBTEMPLATE="$SHAREDIR/grub-template"
if [ -f "$USERDIR/grub-template" ]; then
    GRUBTEMPLATE="$USERDIR/grub-template"
    echo "> Using custom Grub template: $GRUBTEMPLATE"
fi
GRUB='boot/grub/grub.cfg'
LARRAY=()
ROOTDIR=$1
TITLE=$(egrep 'DISTRIB_DESCRIPTION|PRETTY_NAME' ../root/etc/*release | head -n 1 | cut -d'=' -f 2  | tr -d '"')

echo '> Start creating grub boot configuration'

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
            MENU="menuentry \"Start $TITLE\" {\n    linux   /$VMLINUZFLE boot=live components quiet splash \"\$\{loopback\}\"\n    initrd  /$INITRDFLE\n}"
        else
            # Extra kernels
            [ ! -z "$VER" ] && VERSTR=" (kernel ${VER%-*})"
            MENUPLUS="$MENUPLUS\n    menuentry \"Start $TITLE$VERSTR\" {\n        linux   /$VMLINUZFLE boot=live components quiet splash \"\$\{loopback\}\"\n        initrd  /$INITRDFLE\n    }"
        fi
    fi
done

# Exit on failure
[ -z "$MENU" ] && echo "ERROR: failed to generate grub.cfg" && exit 1

# Use the template to generate grub.cfg
sed "s|\[MENU\]|$MENU|" "$GRUBTEMPLATE" > "$GRUB"
sed -i "s|\[TITLE\]|$TITLE|g" "$GRUB"
sed -i "s|\[MENUPLUS\]|$MENUPLUS|" "$GRUB"

# Get grub font
BOOTFONT=$(ls boot/grub/*.pf2 | head -n 1)
if [ -z "$BOOTFONT" ]; then
    UNIFONT=$(ls ../root/boot/grub/*.pf2 | head -n 1)
    cp "$UNIFONT" boot/grub/
    BOOTFONT=$(ls boot/grub/*.pf2 | head -n 1)
fi
sed -i "s|\[BOOTFONT\]|/$BOOTFONT|" "$GRUB"

# Get theme
ROOTTHEME=$(find ../root/boot/grub/themes -name "theme.txt" 2>/dev/null)
THEME=''
if [ ! -z "$ROOTTHEME" ]; then
    # Copy the theme to boot directory
    RTDN=$(dirname $ROOTTHEME)
    THEMENAME=${RTDN##*/}
    if [ ! -d "boot/grub/themes/$THEMENAME" ]; then
        mkdir -p boot/grub/themes/
        cp -r "$RTDN" boot/grub/themes/
    fi
    # Configure theme
    for FONT in "boot/grub/themes/$THEMENAME/"*.pf2; do
        THEME="$THEME\n    loadfont /$FONT"
    done
    THEME="$THEME\n    set theme=/boot/grub/themes/$THEMENAME/theme.txt"
    THEME="$THEME\n    export theme"
    # Copy flags
    mkdir -p "boot/grub/themes/$THEMENAME/icons/"
    cp -r "$SHAREDIR/flags" "boot/grub/themes/$THEMENAME/icons/"
fi
sed -i "s|\[THEME\]|$THEME|" "$GRUB"

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
            LNAME=$(egrep '^lang_name' "$LPATH" | grep -oP '(?<=").*?(?=")' | sed 's/<U/\\u/g' | sed 's/>//g' | ascii2uni -a U -q)
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

    #Generate language menus
    IFS=$'\n' SARRAY=($(sort <<<"${LARRAY[*]}"))
    # printf "%s\n" "${SARRAY[@]}"
    for ITEM in ${SARRAY[@]}; do
        IFS='|' read -ra ADDR <<< "$ITEM"
        CNTR=${ADDR[1]#*_}
        LOCALES="$LOCALES\n    menuentry \"${ADDR[0]} (${ADDR[1]})\" --class flags/${CNTR,,} \{\n        linux  $VMLINUZDEFAULT boot=live components locales=${ADDR[1]}.UTF-8 keyboard-layouts=${CNTR,,},us quiet splash \"\$\{loopback\}\"\n        initrd $INITRDDEFAULT\n    \}"
    done
    
    # Build the menu
    if [ ! -z "$LOCALES" ]; then
        LOCALES="submenu \"Start $TITLE with Localisation Support\" {$LOCALES\n}"
    fi
fi

# Debian Installer
if [ -d "d-i" ]; then
    if [ -f "d-i/gtk/vmlinuz" ]; then
        DEBINSTALLER="$DEBINSTALLER\n    menuentry \"Graphical Debian Installer\" {\n        linux  /d-i/gtk/vmlinuz append video=vesa:ywrap,mtrr vga=788 \"\$\{loopback\}\"\n        initrd /d-i/gtk/initrd.gz\n    }"
    fi
    if [ -f "d-i/vmlinuz" ]; then
        DEBINSTALLER="$DEBINSTALLER\n    menuentry \"Debian Installer\" {\n        linux  /d-i/vmlinuz  \"\$\{loopback\}\"\n        initrd /d-i/initrd.gz\n    }"
    fi
    if [ -f "d-i/gtk/vmlinuz" ]; then
        DEBINSTALLER="$DEBINSTALLER\n    menuentry \"Debian Installer with Speech Synthesis\" {\n        linux  /d-i/gtk/vmlinuz speakup.synth=soft \"\$\{loopback\}\"\n        initrd /d-i/gtk/initrd.gz\n    }"
    fi
    
    # Build the menu
    if [ ! -z "$DEBINSTALLER" ]; then
        DEBINSTALLER="submenu \"Debian Installer\" {$DEBINSTALLER\n}"
    fi
fi

# Update grub.cfg
sed -i "s|\[LOCALES\]|$LOCALES\n|" "$GRUB"
sed -i "s|\[DEBINSTALLER\]|$DEBINSTALLER\n|" "$GRUB"
sed -i "s|\[VMLINUZ\]|$VMLINUZDEFAULT|" "$GRUB"
sed -i "s|\[INITRD\]|$INITRDDEFAULT|" "$GRUB"

echo "Grub gen successfuly generated: $GRUB"
exit 0
