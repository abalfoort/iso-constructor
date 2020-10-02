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

echo 'Fix debconf database'
FIXDB='/usr/share/debconf/fix_db.pl'; [ -f "$FIXDB" ] && perl "$FIXDB"

function start_stop_services () {
    echo "$1 services"
    [ -f '/etc/apache2/apache2.conf' ] && eval service apache2 $1
    [ -f '/etc/mysql/debian.cnf' ] && eval service mysql $1
}

apt-get update
start_stop_services start
eval $APT dist-upgrade
start_stop_services stop
