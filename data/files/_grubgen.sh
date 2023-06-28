#!/bin/bash

# Generates a template grub.cfg with a list of languages
# Depends upon uni2ascii

# Set variables
SHAREDIR='/usr/share/iso-constructor'
USERDIR="/home/$(logname)/.iso-constructor"

TMPLADVANCED="$SHAREDIR/grub-template-advanced"
TMPLCONFIG="$SHAREDIR/grub-template-config"
TMPLGRUB="$SHAREDIR/grub-template-grub"
TMPLTHEME="$SHAREDIR/grub-template-theme"

ADVANCEDCFG='boot/grub/advanced.cfg'
CONFIGCFG='boot/grub/config.cfg'
GRUBCFG='boot/grub/grub.cfg'
THEMECFG='boot/grub/theme.cfg'
LOCALESCFG='boot/grub/locales.cfg'
FONT='boot/grub/unicode.pf2'
LOOPBACK='boot/grub/loopback.cfg'

LARRAY=()
ROOTDIR=$1
TITLE=$(egrep 'DISTRIB_DESCRIPTION|PRETTY_NAME' ../root/etc/*release | head -n 1 | cut -d'=' -f 2  | tr -d '"')

echo '> Start creating grub boot configuration'

mkdir -p boot/grub
echo "source /boot/grub/grub.cfg" > "$LOOPBACK"
cp -vf "$TMPLCONFIG" "$CONFIGCFG"

# Get installed kernels and generate menus
VMLINUZFLE=$(ls live/vmlinuz* | head -n 1)
VER=${VMLINUZFLE#*-}
[ ! -z "$VER" ] && VMLINUZVER="-${VER}"
INITRDFLE="live/initrd.img${VMLINUZVER}"
if [ -f "$INITRDFLE" ]; then
    echo "KERNEL: $VMLINUZFLE - $INITRDFLE - $VER"
    sed "s|\[TITLE\]|$TITLE|" "$TMPLGRUB" > "$GRUBCFG"
    sed -i "s|\[VMLINUZ\]|\/$VMLINUZFLE|" "$GRUBCFG"
    sed -i "s|\[INITRD\]|\/$INITRDFLE|g" "$GRUBCFG"
    sed "s|\[TITLE\]|$TITLE|" "$TMPLADVANCED" > "$ADVANCEDCFG"
    sed -i "s|\[VMLINUZ\]|\/$VMLINUZFLE|" "$ADVANCEDCFG"
    sed -i "s|\[INITRD\]|\/$INITRDFLE|g" "$ADVANCEDCFG"
fi

# Get grub font
if [ ! -e $FONT ] && [ -e ../root/usr/share/grub/unicode.pf2 ]; then
    cp -vf ../root/usr/share/grub/unicode.pf2 $FONT
fi

# Get theme
ROOTTHEME=$(grep -E GRUB_THEME= ../root/etc/default/grub | cut -d'=' -f 2)
RTDN=$(dirname $ROOTTHEME)
if [ -d "../root${RTDN}" ]; then
    # Copy the theme to boot directory
    THEMENAME=${RTDN##*/}
    rm -rf boot/grub/themes
    mkdir -p boot/grub/themes
    cp -vfr "../root${RTDN}" boot/grub/themes/
    # Configure theme
    THEME="/boot/grub/themes/$THEMENAME/theme.txt"
    # Copy flags
    mkdir -p "boot/grub/themes/$THEMENAME/icons/"
    cp -rf "$SHAREDIR/flags" "boot/grub/themes/$THEMENAME/icons/"
fi
sed "s|\[THEME\]|$THEME|" "$TMPLTHEME" > "$THEMECFG"

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
            
            # Add to array if language name was found (lower case)
            if [ ! -z "$LNAME" ]; then
                LARRAY+=("${LNAME,,}|$LOCALE")
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
        LOCALES="$LOCALES\nmenuentry \"${ADDR[0]} (${ADDR[1]})\" --class flags/${CNTR,,} {\n    linux  /$VMLINUZFLE boot=live components locales=${ADDR[1]}.UTF-8 keyboard-layouts=${CNTR,,},us quiet splash \"\${loopback}\"\n    initrd /$INITRDFLE\n}"
    done
    
    # Build the menu
    if [ ! -z "$LOCALES" ]; then
        printf "$LOCALES\n" > $LOCALESCFG
    fi
fi

echo "Grub gen successfuly generated: $GRUBCFG"
exit 0
