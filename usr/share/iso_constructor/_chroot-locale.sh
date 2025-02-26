#!/bin/bash

# Extra locale specific packages
# When adding locales: change code at the bottom of this script
zh_TW='libthai0 fonts-thai-tlwg im-config fcitx fcitx-table-thai fcitx-sunpinyin fcitx-libpinyin fcitx-googlepinyin fcitx-frontend-gtk3 fcitx-ui-classic fcitx-config-gtk'
zh_SG='fonts-arphic-ukai fonts-arphic-uming im-config fcitx fcitx-sunpinyin fcitx-libpinyin fcitx-googlepinyin fcitx-frontend-gtk3 fcitx-ui-classic fcitx-config-gtk'
zh_HK='fonts-arphic-ukai fonts-arphic-uming im-config fcitx fcitx-table-cantonhk fcitx-sunpinyin fcitx-libpinyin fcitx-googlepinyin fcitx-frontend-gtk3 fcitx-ui-classic fcitx-config-gtk'
zh_CN='fonts-arphic-ukai fonts-arphic-uming im-config fcitx fcitx-sunpinyin fcitx-libpinyin fcitx-googlepinyin fcitx-frontend-gtk3 fcitx-ui-classic fcitx-config-gtk'
ko_KR='fonts-unfonts* im-config fcitx fcitx-hangul fcitx-frontend-gtk3 fcitx-ui-classic fcitx-config-gtk'
ja_JP='fonts-vlgothic fonts-takao im-config fcitx fcitx-mozc fcitx-frontend-gtk3 fcitx-ui-classic fcitx-config-gtk mozc-utils-gui'

# Check for old debian release
APT="yes '' | apt-get -y -o DPkg::options::=--force-confdef -o DPkg::options::=--force-confold" 
DISTRIB_RELEASE=$(egrep '^DISTRIB_RELEASE|^VERSION_ID|^VERSION' /etc/*release | head -n 1 | cut -d'=' -f 2  | tr -d '"')
if [ "$DISTRIB_RELEASE" -lt 8 ]; then
    APT='apt-get --force-yes'
fi

# Change live configuration
function localizeLive() {
    LIVE='/etc/live/config.conf'
    if [ -f $LIVE ]; then
        PRM=$1
        VAL=$2
        if grep -q $PRM "$LIVE"; then
            sed -i -e "s#.*$PRM.*#export $PRM=\"$VAL\"#" "$LIVE"
        else
            echo "export $PRM=\"$VAL\"" >> "$LIVE"
        fi
    fi
}

# Set locale
#echo "$LOC.UTF-8 UTF-8" >> /etc/locale.gen
#locale-gen
#update-locale LANG="$LOC.UTF-8"
dpkg-reconfigure locales

# Set timezone
dpkg-reconfigure  tzdata
TIMEZONE=$(cat /etc/timezone)
rm /etc/localtime
ln -sf /usr/share/zoneinfo/$TIMEZONE /etc/localtime

# Get language
. /etc/default/locale
LOCALE=$(echo $LANG | cut -d'.' -f 1)
BASELAN=${LOCALE:0:2}
EXTLANU=${LOCALE:3:5}
EXTLANL=${EXTLANU,,}

# Exit if user set en_US as the default locale
if [ "$LOCALE" == 'en_US' ]; then exit 0; fi

# Live configuration
localizeLive 'LIVE_LOCALES' "$LANG,en_US.UTF-8"
localizeLive 'LIVE_KEYBOARD_LAYOUTS' "us,$BASELAN"
localizeLive 'LIVE_TIMEZONE' "$TIMEZONE"
localizeLive 'LIVE_UTC' 'no'
if [ -e '/etc/live/live-hooks.sh' ]; then
  localizeLive 'LIVE_HOOKS' '/etc/live/live-hooks.sh'
fi

# Localize Grub2
LOCALEDIR='/boot/grub/locale'
DEFGRUB='/etc/default/grub'
if [ -f "$DEFGRUB" ]; then
    # Get all translation files
    mkdir -p $LOCALEDIR
    for F in $(find /usr/share/locale -name "grub.mo"); do 
        MO="$LOCALEDIR/$(echo $F | cut -d'/' -f 5).mo"
        cp -afuv $F $MO
    done
    sed -i '/^LANG=/d' $DEFGRUB
    sed -i '/^LANGUAGE=/d' $DEFGRUB
    sed -i '/^GRUB_LANG=/d' $DEFGRUB
    sed -i '/^# Set locale$/d' $DEFGRUB
    # Update grub
    update-grub
fi

# Update cache before installing packages
apt-get update

# Install language packages for several applications
CHKLAN="$BASELAN$EXTLANL"
if dpkg -l | grep -q ' kde-runtime '; then
    LAN=$BASELAN
    apt-cache -q show kde-l10n-$CHKLAN >/dev/null 2>&1 && LAN=$CHKLAN
    eval $APT install kde-l10n-$LAN
fi
if dpkg -l | grep -q ' calligra '; then
    LAN=$BASELAN
    apt-cache -q show calligra-l10n-$CHKLAN >/dev/null 2>&1 && LAN=$CHKLAN
    eval $APT install calligra-l10n-$LAN
fi

CHKLAN="$BASELAN-$EXTLANL"
LAN=$BASELAN
apt-cache -q show hunspell-$CHKLAN >/dev/null 2>&1 && LAN=$CHKLAN
eval $APT install hunspell-$LAN

FF=false
if dpkg -l | grep -q ' firefox '; then
    FF=true
    LAN=$BASELAN
    apt-cache -q show firefox-l10n-$CHKLAN >/dev/null 2>&1 && LAN=$CHKLAN
    eval $APT install firefox-l10n-$LAN
fi
if dpkg -l | grep -q ' firefox-esr '; then
    FF=true
    LAN=$BASELAN
    apt-cache -q show firefox-esr-l10n-$CHKLAN >/dev/null 2>&1 && LAN=$CHKLAN
    eval $APT install firefox-esr-l10n-$LAN
fi

if dpkg -l | grep -q ' thunderbird '; then
    LAN=$BASELAN
    apt-cache -q show thunderbird-l10n-$CHKLAN >/dev/null 2>&1 && LAN=$CHKLAN
    eval $APT install thunderbird-l10n-$LAN
    # lightning-l10n is now integrated in thunderbird-l10n
    #if dpkg -l | grep -q ' lightning '; then
    #  apt-cache -q show lightning-l10n-$CHKLAN >/dev/null 2>&1 && LAN=$CHKLAN
    #  eval $APT install lightning-l10n-$LAN
    #fi
fi

if dpkg -l | grep -q ' libreoffice '; then
    LAN=$BASELAN
    apt-cache -q show libreoffice-l10n-$CHKLAN >/dev/null 2>&1 && LAN=$CHKLAN
    eval $APT install libreoffice-l10n-$LAN
    LAN=$BASELAN
    apt-cache -q show libreoffice-help-$CHKLAN >/dev/null 2>&1 && LAN=$CHKLAN
    eval $APT install libreoffice-help-$LAN
fi

if dpkg -l | grep -q ' icedove '; then
    LAN=$BASELAN
    apt-cache -q show icedove-l10n-$CHKLAN >/dev/null 2>&1 && LAN=$CHKLAN
    eval $APT install icedove-l10n-$LAN
fi

if dpkg -l | grep -q ' iceowl '; then
    LAN=$BASELAN
    apt-cache -q show iceowl-l10n-$CHKLAN >/dev/null 2>&1 && LAN=$CHKLAN
    eval $APT install iceowl-l10n-$LAN
fi

if dpkg -l | grep -q ' iceweasel '; then
    LAN=$BASELAN
    apt-cache -q show iceweasel-l10n-$CHKLAN >/dev/null 2>&1 && LAN=$CHKLAN
    eval $APT install iceweasel-l10n-$LAN
fi

# Mozilla locale configuration
. /etc/default/locale
LOCALE=$(echo $LANG | cut -d'.' -f 1)
if [ "$LOCALE" == 'en_US' ]; then
    LOCALE=''
fi
MOZLAN=$(echo $LOCALE | sed 's/_/-/')
for INI in $(dpkg -S distribution.ini 2>/dev/null | egrep 'firefox|thunderbird' | awk '{print $2}'); do
    echo "> Change Mozilla $INI"
    if [ -f "$INI" ]; then
        sed -i "s/^intl.locale.requested.*/intl.locale.requested=\"$LOCALE\"/" "$INI"
        sed -i "s/^spellchecker.dictionary.*/spellchecker.dictionary=\"$MOZLAN\"/" "$INI"
    fi
done

# Install locale specific packages
if [ "$LOCALE" == "zh_TW" ]; then eval $APT install $zh_TW; fi
if [ "$LOCALE" == "zh_SG" ]; then eval $APT install $zh_SG; fi
if [ "$LOCALE" == "zh_HK" ]; then eval $APT install $zh_HK; fi
if [ "$LOCALE" == "zh_CN" ]; then eval $APT install $zh_CN; fi
if [ "$LOCALE" == "ko_KR" ]; then eval $APT install $ko_KR; fi
if [ "$LOCALE" == "ja_JP" ]; then eval $APT install $ja_JP; fi

