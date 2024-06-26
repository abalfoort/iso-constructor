#!/bin/bash

KEEPPACKAGES=$1

function obsolete_packages() {
    if [ ! -z "$(which deborphan)" ]; then
        deborphan
    elif [ ! -z "$(which aptitude)" ]; then
        # Alternative for deborphan
        aptitude -F%p search '~o (~slibs|~soldlibs|~sintrospection) !~Rdepends:.*'
    fi
}

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

echo '> Cleanup'
apt-get clean
eval $APT --purge autoremove

# Remove old kernel and headers
VERSION=$(readlink -s /vmlinuz | grep -o -P '(?<=vmlinuz-).*(?=-amd64)')
if [ ! -z "$VERSION" ]; then
    OLDKERNEL=$(dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' 'linux-image-[0-9]*' 'linux-headers-[0-9]*' | grep ^i | grep -v "$VERSION" | egrep -v "[a-z]-486|[a-z]-686|[a-z]-586" | awk '{print $2}')
    if [ ! -z "$OLDKERNEL" ]; then
        echo "> Remove old kernel packages: $OLDKERNEL"
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

if [ "$KEEPPACKAGES" != '*' ] && [ ! -z "$(which aptitude)" ]; then
    echo '> Removing obsolete packages, except the ones listed in KEEPPACKAGES'
    Exclude=${KEEPPACKAGES//,/\/d;/}
    
    Obsolete=$(obsolete_packages | sed '/'$Exclude'/d')
    while [ "$Obsolete" ]; do
        eval $APT purge $Obsolete
        RC=$(dpkg-query -l | sed -n 's/^rc\s*\(\S*\).*/\1/p')
        [ "$RC" ] && eval $APT purge $RC
        Obsolete=$(obsolete_packages | sed '/'$Exclude'/d')
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

if [ -e /usr/sbin/policy-rc.d ]; then
    echo '> Remove unneeded policy-rc.d'
    rm -r /usr/sbin/policy-rc.d
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
find / \( -name "*.bak*" -o -name "*.dpkg" -o -name "*.dpkg-old" -o -name "*.dpkg-dist" -o -name "*.old" -o -name "*.tmp" -o -name "*.ucf-dist" \) -delete

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
