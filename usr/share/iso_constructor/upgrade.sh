#!/bin/bash

# Need to find current path
# Because current directory is user home directory
SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

# Create an upgrade script in the root directory
cat > "$1/root/upgrade.sh" << EOF

# Make this script unattended
# https://debian-handbook.info/browse/stable/sect.automatic-upgrades.html
export DEBIAN_FRONTEND=noninteractive
APT="yes '' | apt-get -y -o DPkg::options::=--force-confdef -o DPkg::options::=--force-confold" 

# Check for old debian release
DISTRIB_RELEASE=\$(egrep '^DISTRIB_RELEASE|^VERSION_ID|^VERSION' /etc/*release | head -n 1 | cut -d'=' -f 2  | tr -d '"')
if [ "\$DISTRIB_RELEASE" -lt 8 ]; then
    APT='apt-get --force-yes'
fi

echo 'Fix debconf database'
FIXDB='/usr/share/debconf/fix_db.pl'; [ -f "\$FIXDB" ] && perl "\$FIXDB"

function start_stop_services () {
    echo "\$1 services"
    [ -f '/etc/apache2/apache2.conf' ] && eval service apache2 \$1
    [ -f '/etc/mysql/debian.cnf' ] && eval service mysql \$1
}

apt-get update
start_stop_services start
eval \$APT dist-upgrade
eval \$APT autopurge
eval \$APT clean
start_stop_services stop

echo
echo 'Upgrade finished'
EOF

# Execute and remove the script when done
"${SCRIPTPATH}"/chroot-dir.sh "$1/root" "bash /upgrade.sh"
rm -f "$1/root/upgrade.sh" 
