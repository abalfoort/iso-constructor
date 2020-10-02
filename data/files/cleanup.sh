#!/bin/bash

# Make this script unattended
# https://debian-handbook.info/browse/stable/sect.automatic-upgrades.html
export DEBIAN_FRONTEND=noninteractive
APT="yes '' | apt-get -y -o DPkg::options::=--force-confdef -o DPkg::options::=--force-confold" 

# Check for old debian release
. /etc/lsb-release
if [ "$DISTRIB_RELEASE" -lt 8 ]; then
    APT='apt-get --force-yes'
fi

# Offline packages
OFFLINEPCKS="grub-efi efivar broadcom-sta-dkms"
SKIPOFFLINEPCKS='grub-efi'

# Packages that deborphan must NOT treat as orphans - comma separated list
# Set to '*' to keep everything
NOTORPHAN='baloo,virtualbox-guest-x11,virtualbox-guest-dkms,virtualbox-guest-utils'

if [ -e /usr/share/mime/packages/kde.xml ]; then
    echo '> Remove fake mime types in KDE'
    sed -i -e /\<.*fake.*\>/,/^$/d /usr/share/mime/packages/kde.xml
fi

if which gconftool-2 >/dev/null; then
    echo '> Set gconf default settings'
    gconftool-2 --direct --config-source xml:readwrite:/etc/gconf/gconf.xml.defaults --type bool --set /apps/gksu/sudo-mode true
    gconftool-2 --direct --config-source xml:readwrite:/etc/gconf/gconf.xml.defaults --type bool --set /apps/gksu/display-no-pass-info false
    gconftool-2 --direct --config-source xml:readwrite:/etc/gconf/gconf.xml.defaults --type string --set /apps/blueman/transfer/browse_command 'thunar --browser obex://[%d]'
fi

echo '> Download offline packages'
if [ -d offline ]; then
    rm -r offline
fi
mkdir offline
cd offline
[ "$(dpkg --print-architecture)" == "amd64" ] && F=i386 || F=amd64
DEPS=$(LANG=C apt-cache depends $OFFLINEPCKS | sed -r '/.+:'$F'|Breaks:|Conflicts:|Enhances:|Provides:|Replaces:|Suggests|Recommends|PreDepends:.+/d; s/^ .*: //')
for DEP in $DEPS; do
    SKIP=false
    for SPCK in $SKIPOFFLINEPCKS; do
        if [ "$DEP" == "$SPCK" ]; then
            SKIP=true
            break
        fi
    done
    if ! $SKIP; then
        if [ "${DEP: -4}" != '-dbg' ] && [ "${DEP: -4}" != '-dev' ]; then
            if [ $(LANG=C dpkg-query -W -f='${Status}' $DEP 2>/dev/null | grep -c "ok installed") -eq 0 ]; then
                apt-get download $DEP 2>/dev/null
            fi
        fi
    fi
done
cd ../

echo '> Make sure all firmware drivers are installed but do not install from backports'
FIRMWARE=$(aptitude search ^firmware | grep ^p | egrep -v 'adi|ralink|-dl|-doc|-dbgsym|micropython|qcom-media' | awk '{print $2}')
for F in $FIRMWARE; do
    STABLE=$(apt-cache policy $F | grep 500 2>/dev/null)
    if [ "$STABLE" != "" ]; then
        eval $APT install $F
    fi
done

echo '> Cleanup'
apt-get clean
eval $APT autoremove
aptitude -y purge ~c

# Remove old kernel and headers
VERSION=$(ls -al / | grep -e "\svmlinuz\s" | cut -d'/' -f2 | cut -d'-' -f2,3)
if [ "$VERSION" != "" ]; then
    OLDKERNEL=$(aptitude search linux-image-[0-9] linux-headers-[0-9] | grep ^i | grep -v "$VERSION" | egrep -v "[a-z]-486|[a-z]-686|[a-z]-586" | cut -d' ' -f 3)
    if [ "$OLDKERNEL" != "" ]; then
        echo "> Remove old kernel packages:\n$OLDKERNEL"
        eval $APT purge $OLDKERNEL
        KBCNT=$(aptitude search linux-kbuild | grep ^i | wc -l)
        if [ $KBCNT -gt 1 ]; then
            eval $APT purge $(aptitude search linux-kbuild | grep ^i | egrep -v ${VERSION%-*} | cut -d' ' -f 3 | head -n 1)
        fi
    fi
fi

echo '> Remove unavailable packages only when not manually held back'
for PCK in $(env LANG=C apt-show-versions | grep 'available' | cut -d':' -f1); do
    REMOVE=true
    for HELDPCK in $(env LANG=C dpkg --get-selections | grep hold$ | awk '{print $1}'); do
        if [ $PCK == $HELDPCK ]; then
            REMOVE=false
        fi
    done
    if $REMOVE; then
        if [[ "$NOTORPHAN" =~ "$PCK" ]] || [ "$NOTORPHAN" == '*' ]; then
            echo "Not available but keep installed: $PCK"
        else
            eval $APT purge $PCK
        fi
    fi
done

if [ "$NOTORPHAN" != '*' ]; then
    echo '> Removing orphaned packages, except the ones listed in NOTORPHAN'
    Exclude=${NOTORPHAN//,/\/d;/}
    Orphaned=$(deborphan | sed '/'$Exclude'/d')
    while [ "$Orphaned" ]; do
        eval $APT purge $Orphaned
        RC=$(dpkg-query -l | sed -n 's/^rc\s*\(\S*\).*/\1/p')
        [ "$RC" ] && eval $APT purge $RC
        Orphaned=$(deborphan | sed '/'$Exclude':/d')
    done
fi

if [ -f /initrd.img ] && [ -f /initrd.img.old ]; then
    echo '> Remove /initrd.img.old'
    rm /initrd.img.old
fi
if [ -f /vmlinuz ] && [ -f /vmlinuz.old ]; then
    echo '> Remove /vmlinuz.old'
    rm /vmlinuz.old
fi

if [ -f /etc/grub.d/20_memtest86+ ]; then
    echo '> Disable memtest in Grub'
    chmod -x /etc/grub.d/20_memtest86+
fi

echo '> Configure LightDM'    
CONF='/etc/lightdm/lightdm.conf'
XSESSION='/etc/lightdm/Xsession'
if [ -e "$CONF" ]; then
    for F in $(find etc/live/ -type f -name "*.conf"); do source "$F"; done
    if [ ! -z $LIVE_HOSTNAME ]; then
        sed -i -r -e "s|^#.*autologin-user=.*\$|autologin-user=$LIVE_HOSTNAME|" \
                      -e "s|^#.*autologin-user-timeout=.*\$|autologin-user-timeout=0|" \
                      "$CONF"
    fi
    sed -i -r -e "s|^#.*allow-user-switching=.*\$|allow-user-switching=true|" \
                  -e "s|^#.*greeter-hide-users=.*\$|greeter-hide-users=false|" \
                  "$CONF"
    if [ -e "$XSESSION" ]; then
        sed -i -r -e "s|^#.*session-wrapper=.*\$|session-wrapper=$XSESSION|"    "$CONF"
    else
        # Comment the line if not already commented
        sed -i -r -e '/^session-wrapper=.*/ s/^#*/#/' "$CONF"
    fi
fi

if [ -e /usr/sbin/policy-rc.d ]; then
    echo '> Remove unneeded policy-rc.d'
    rm -r /usr/sbin/policy-rc.d
fi

if which update-apt-xapian-index >/dev/null; then
    echo '> Refresh xapian database'
    update-apt-xapian-index
fi

if which updatedb >/dev/null; then
    echo '> Update database for mlocate'
    updatedb
fi

if which geoipupdate >/dev/null; then
    echo '> Update GeoIP database'
    geoipupdate -v
fi

# Update pixbuf cache
PB='/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders'
if [ ! -e $PB ]; then
    PB='/usr/lib/i386-linux-gnu/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders'
fi
if [ -e $PB ]; then
    echo '> Update pixbuf cache'
    $PB --update-cache
fi

echo '> Setup the firewall'
/usr/sbin/ufw --force reset
rm /etc/ufw/*.rules.* 2>/dev/null
rm /lib/ufw/*.rules.* 2>/dev/null
/usr/sbin/ufw default deny incoming
/usr/sbin/ufw default allow outgoing
/usr/sbin/ufw allow to any app CIFS
/usr/sbin/ufw allow from any app CIFS
/usr/sbin/ufw allow to any app CUPS
/usr/sbin/ufw allow from any app CUPS
/usr/sbin/ufw enable

echo '> Change Mozilla distribution.ini'
. /etc/default/locale
LOCALE=$(echo $LANG | cut -d'.' -f 1)
if [ "$LOCALE" == 'en_US' ]; then
    LOCALE=''
fi
MOZLAN=$(echo $LOCALE | sed 's/_/-/')
INI='/usr/lib/firefox-esr/distribution/distribution.ini'
if [ -f "$INI" ]; then
    sed -i "s/^intl.locale.requested.*/intl.locale.requested=\"$LOCALE\"/" "$INI"
    sed -i "s/^spellchecker.dictionary.*/spellchecker.dictionary=\"$MOZLAN\"/" "$INI"
fi
INI='/usr/lib/firefox/distribution/distribution.ini'
if [ -f "$INI" ]; then
    sed -i "s/^intl.locale.requested.*/intl.locale.requested=\"$LOCALE\"/" "$INI"
    sed -i "s/^spellchecker.dictionary.*/spellchecker.dictionary=\"$MOZLAN\"/" "$INI"
fi
INI='/usr/lib/thunderbird/distribution/distribution.ini'
if [ -f "$INI" ]; then
    sed -i "s/^intl.locale.requested.*/intl.locale.requested=\"$LOCALE\"/" "$INI"
    sed -i "s/^spellchecker.dictionary.*/spellchecker.dictionary=\"$MOZLAN\"/" "$INI"
fi

echo '> Cleanup temporary files'
rm -rf /media/*
rm -rf /tmp/*
rm -rf /tmp/.??*
rm -rf /var/backups/*
rm -rf /var/cache/fontconfig/*
rm -rf /var/cache/samba/*
rm -rf /var/mail/*
rm -rf /var/spool/exim4/input/*
rm -rf /var/spool/exim4/msglog/*
rm -rf /var/tmp/*
rm -rf /var/tmp/.??*

echo '> Cleanup all log files'
find /var/log -type f -delete

echo '> Delete __pycache__ directories'
find . -type d -name "__pycache__" -exec rm -r {} 2>/dev/null \;

echo '> Cleanup backup files'
find / \( -name "*.bak*" -o -name "*.dpkg" -o -name "*.dpkg-old" -o -name "*.dpkg-dist" -o -name "*.old" -o -name "*.tmp" \) -delete

echo '> Remove alternatives that do not link anywhere'
find -L /etc/alternatives -type l -exec rm -v {} \;

echo '> Delete grub.cfg: it will be generated during install'
rm -rf /boot/grub/grub.cfg

echo '> Remove deb files left from development'
find / -maxdepth 1 -name "*.deb" -delete

# Removing redundant kernel module structure(s) from /lib/modules (if any)
VersionPlusArch=$(ls -l /vmlinuz | sed 's/.*\/vmlinuz-\(.*\)/\1/')
L=${#VersionPlusArch}
for I in /lib/modules/*; do
    if [ ${I: -$L} != $VersionPlusArch ] && [ ! -d $I/kernel ]; then
        echo "> Removing redundant kernel module structure: $I"
        rm -fr $I
    fi
done
