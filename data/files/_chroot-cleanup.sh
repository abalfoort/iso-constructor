#!/bin/bash

KEEPPACKAGES=$1

# Make this script unattended
# https://debian-handbook.info/browse/stable/sect.automatic-upgrades.html
export DEBIAN_FRONTEND=noninteractive
APT="yes '' | apt-get -y -o DPkg::options::=--force-confdef -o DPkg::options::=--force-confold" 

# Check for old debian release
DISTRIB_RELEASE=$(egrep '^DISTRIB_RELEASE|^VERSION_ID|^VERSION' /etc/*release | head -n 1 | cut -d'=' -f 2  | tr -d '"')
if [ "$DISTRIB_RELEASE" -lt 8 ]; then
    APT='apt-get --force-yes'
fi

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

echo '> Make sure all firmware drivers are installed but do not install from backports'
FIRMWARE=$(apt list --all-versions 2>/dev/null | grep -v -E 'backports|installed|micropython' | grep ^firmware | cut -d'/' -f 1)
for F in $FIRMWARE; do
    eval $APT install $F
done

echo '> Cleanup'
apt-get clean
eval $APT --purge autoremove

# Remove old kernel and headers
VERSION=$(ls -al / | grep -e "\svmlinuz\s" | cut -d'/' -f2 | cut -d'-' -f2,3)
if [ ! -z "$VERSION" ]; then
    OLDKERNEL=$(dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' 'linux-image-[0-9]*' 'linux-headers-[0-9]*' | grep ^i | grep -v "$VERSION" | egrep -v "[a-z]-486|[a-z]-686|[a-z]-586" | awk '{print $2}')
    if [ ! -z "$OLDKERNEL" ]; then
        echo "> Remove old kernel packages:\n$OLDKERNEL"
        eval $APT purge $OLDKERNEL
        KBCNT=$(dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' 'linux-kbuild*' | grep ^i | wc -l)
        if [ $KBCNT -gt 1 ]; then
            eval $APT purge $(dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' 'linux-kbuild*' | grep ^i | egrep -v ${VERSION%-*} | awk '{print $2}')
        fi
    fi
fi

echo '> Remove unavailable packages only when not manually held back'
for PCK in $(env LANG=C apt list --installed 2>/dev/null | grep installed,local | cut -d'/' -f 1); do
    # Check if the locally installed packages are not available in a repository
    if [ -z "$(apt-cache show $PCK | grep -i filename)" ]; then
        REMOVE=true
        for HELDPCK in $(env LANG=C dpkg --get-selections | grep hold$ | awk '{print $1}'); do
            if [ "$PCK" == "$HELDPCK" ]; then
                REMOVE=false
            fi
        done
        if $REMOVE; then
            if [[ "$KEEPPACKAGES" =~ "$PCK" ]] || [ "$KEEPPACKAGES" == '*' ]; then
                echo "Not available but keep installed: $PCK"
            else
                eval $APT purge $PCK
            fi
        fi
    fi
done

if [ "$KEEPPACKAGES" != '*' ] && [ ! -z "$(which deborphan)" ]; then
    echo '> Removing orphaned packages, except the ones listed in KEEPPACKAGES'
    Exclude=${KEEPPACKAGES//,/\/d;/}
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
    if [ ! -z "$LIVE_USERNAME" ]; then
        sed -i -r -e "s|^#.*autologin-user=.*\$|autologin-user=$LIVE_USERNAME|" \
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

# Update pixbuf cache
PB='/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders'
if [ ! -e $PB ]; then
    PB='/usr/lib/i386-linux-gnu/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders'
fi
if [ -e $PB ]; then
    echo '> Update pixbuf cache'
    $PB --update-cache
fi

UFW=$(which ufw)
if [ ! -z "$UFW" ]; then
    echo '> Setup ufw'
    eval $UFW --force reset
    rm /etc/ufw/*.rules.* 2>/dev/null
    rm /lib/ufw/*.rules.* 2>/dev/null
    eval $UFW default deny incoming
    eval $UFW default allow outgoing
    eval $UFW allow to any app CIFS 2>/dev/null
    eval $UFW allow from any app CIFS 2>/dev/null
    eval $UFW allow to any app CUPS 2>/dev/null
    eval $UFW allow from any app CUPS 2>/dev/null
    # msdn port
    eval $UFW allow 5353/udp 2>/dev/null
    eval $UFW allow out 5353/udp 2>/dev/null
    eval $UFW enable
fi

FWD='/etc/firewalld/zones/public.xml'
if [ -d /etc/firewalld/zones/ ]; then
    echo '> Setup firewalld'
    if [ -f "$FWD" ]; then
        if ! grep -q mdns "$FWD"; then
            # Allow mDNS (ping, etc)
            sed -i '/\/zone/i <service name="mdns"\/>' "$FWD" 
        fi
        if ! grep -q ipp "$FWD"; then
            # Allow CUPS
            sed -i '/\/zone/i <service name="ipp"\/>' "$FWD" 
        fi
    else
        # Create initial file
        cat > "$FWD" << EOF
<?xml version="1.0" encoding="utf-8"?>
<zone>
  <short>Public</short>
  <description>For use in public areas.</description>
  <service name="ssh"/>
  <service name="dhcpv6-client"/>
  <service name="mdns"/>
  <service name="ipp"/>
</zone>
EOF
    fi
fi

# Cleanup root history
rm /root/.nano_history 2>/dev/null
rm /root/.bash_history 2>/dev/null
rm /root/.wget-hsts 2>/dev/null
rm /root/.aptitude 2>/dev/null
rm /root/.nano 2>/dev/null
rm /root/.cache 2>/dev/null

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

if [ -e "/etc/resolv.conf" ] && [ ! -L "/etc/resolv.conf" ]; then
    echo '> Remove /etc/resolv.conf'
    rm -f /etc/resolv.conf
fi

# Removing redundant kernel module structure(s) from /lib/modules (if any)
VersionPlusArch=$(ls -l /vmlinuz | sed 's/.*\/vmlinuz-\(.*\)/\1/')
L=${#VersionPlusArch}
for I in /lib/modules/*; do
    if [ ${I: -$L} != $VersionPlusArch ] && [ ! -d $I/kernel ]; then
        echo "> Removing redundant kernel module structure: $I"
        rm -fr $I
    fi
done
