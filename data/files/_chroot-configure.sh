#!/bin/bash

DESKTOP_ENV='kde'
[ -e /usr/bin/startxfce4 ] && DESKTOP_ENV='xfce'
[ -e /usr/bin/startlxqt ] && DESKTOP_ENV='lxqt'

INFO='/usr/share/solydxk/info'
[ -f "$INFO" ] && . "$INFO"

# ==========================
# Start Manual Configuration
# ==========================

SKIP_FIRMWARE='firmware-tomu firmware-nvidia-gsp firmware-nvidia-tesla-gsp firmware-siano firmware-samsung firmware-microbit-micropython firmware-microbit-micropython-doc firmware-ivtv'

PLASMA_FAVORITES='preferred://browser,thunderbird.desktop,libreoffice-startcenter.desktop,org.kde.discover.desktop,systemsettings.desktop,org.kde.konsole.desktop'

# Make sure the default theme THEME_01 exists:
# /usr/share/desktop-base/${THEME_01}-theme/
# /usr/share/grub/themes/${THEME_01}/
# /usr/share/plymouth/themes/${THEME_01}/
THEME_01='solydk-light'
THEME_02='solydk-dark'
THEME_03='solydk-black'
ICON_THEME='evolvere-2-blue'
BREEZE_THEME='Breeze'
ROOT_FILES='.bashrc .profile .config/fontconfig/fonts.conf .config/gtk-3.0/settings.ini .config/gtk-4.0/settings.ini .local/share/dolphin/view_properties/global/.directory .local/share/kxmlgui5/dolphin/dolphinui.rc .gtkrc-2.0'

if [ "$DESKTOP_ENV" == 'xfce' ]; then
    THEME_01='solydx-light'
    THEME_02='solydx-dark'
    THEME_03='solydx-black'
    ICON_THEME='evolvere-2'
    BREEZE_THEME='Breeze-X'
    ROOT_FILES='.bashrc .profile .config/gtk-3.0/settings.ini .config/xfce4/terminal/terminalrc .config/Thunar/thunarrc .config/Thunar/uca.xml .config/Thunar/volmanrc .config/xfce4/xfconf/xfce-perchannel-xml/thunar.xml .config/mimeapps.list .gtkrc-2.0'
fi

if [ "$DESKTOP_ENV" == 'lxqt' ]; then
    THEME_01='solydl-light'
    THEME_02='solydl-dark'
    THEME_03='solydl-black'
    ICON_THEME='evolvere-2-blue'
    BREEZE_THEME='Breeze'
    ROOT_FILES='.bashrc .profile .config/fontconfig/fonts.conf gtk-3.0/settings.ini .config/pcmanfm-qt/lxqt/settings.conf .config/qterminal.org/qterminal.ini .config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml .config/lxqt-mimeapps.list .config/mimeapps.list .gtkrc-2.0'
fi

# ========================
# End Manual Configuration
# ========================

# =========
# Functions
# =========
function divert_file {
    FLE=$1
    ISDIVERTED=$(LANG=C dpkg-divert --list $FLE)
    if [ -f $FLE ] && [ ! "$ISDIVERTED" ]; then
        dpkg-divert --package iso-constructor --add --rename --divert $FLE.divert $FLE
        ISDIVERTED=$(LANG=C dpkg-divert --list $FLE)
    fi
    [ "$ISDIVERTED" ] && cp -f "$FLE.divert" "$FLE"
}

# When diverting essential files:
# # dpkg-divert: warning: diverting file '[file]' from an Essential package with rename is dangerous, use --no-rename
function divert_essential_file {
    FLE=$1
    ISDIVERTED=$(LANG=C dpkg-divert --list $FLE)
    if [ -f $FLE ] && [ ! "$ISDIVERTED" ]; then
        cp "$FLE" "$FLE.divert"
        dpkg-divert --package iso-constructor --add --no-rename --divert $FLE.divert $FLE
        ISDIVERTED=$(LANG=C dpkg-divert --list $FLE)
    fi
    [ "$ISDIVERTED" ] && cp -f "$FLE.divert" "$FLE"
}

# Function to remove all diversions of a package
function remove_divert {
    if [ ! -z "$1" ]; then
        for CMD in $(LANG=C dpkg-divert --list "$1" | awk '{print $3}'); do
            DIVERT=$(LANG=C dpkg-divert --list "$CMD" | awk '{print $5}')
            if [ -e "$DIVERT" ]; then
                if [ -e "$CMD" ]; then
                    mv "$CMD" "$CMD.bak"
                fi
                cp "$DIVERT" "$DIVERT.bak"
                dpkg-divert --remove --rename "$CMD"
                if [ ! -e "$CMD" ]; then
                    mv "$DIVERT.bak" "$CMD"
                else
                    if [ -e "$DIVERT.bak" ]; then
                        rm "$DIVERT.bak"
                    fi
                     if [ -e "$CMD.bak" ]; then
                        rm "$CMD.bak"
                    fi
                fi
            else
                dpkg-divert --remove "$CMD"
            fi
        done
    fi
}

# =====================
# Firmware Installation
# =====================
echo 'Install firmware drivers'
FIRMWARE=$(apt list --all-versions 2>/dev/null | grep -v -E 'backports|installed|micropython' | grep ^firmware | cut -d'/' -f 1)
for F in $FIRMWARE; do
    if [[ ! "$SKIP_FIRMWARE" =~ "$PCK" ]]; then
        eval $APT install $F
    fi
done

# ====================
# SolydK Configuration
# ====================
if [ "$DESKTOP_ENV" == 'kde' ]; then
    # Reconfigure EE packages if they are installed
    dpkg-reconfigure solydkee-info 2>/dev/null
    
    # Fix favorites in kickoff
    KICKOFF='/usr/share/plasma/plasmoids/org.kde.plasma.kickoff/contents/config/main.xml'
    divert_file "$KICKOFF"
    [ -e "$KICKOFF" ] && sed -i -e "s#preferred://browser,.*\.desktop#$PLASMA_FAVORITES#" "$KICKOFF"

    KICKER='/usr/share/plasma/plasmoids/org.kde.plasma.kicker/contents/config/main.xml'
    divert_file "$KICKER"
    [ -e "$KICKER" ] && sed -i -e "s#preferred://browser,.*\.desktop#$PLASMA_FAVORITES#" "$KICKER"
   
    DOLPHIN_DIR='/usr/share/kxmlgui5/dolphin'
    [ ! -d "$DOLPHIN_DIR" ] && mkdir -p "$DOLPHIN_DIR"
    
    # Create a link to kdesu in /usr/bin
    KDESU='/usr/bin/kdesu'
    KF5KDESU="$(kf5-config --path libexec)kf5/kdesu"
    KF5KDESUD=${KF5KDESU}d
    if [ ! -e "$KDESU" ] && [ -e "$KF5KDESU" ]; then
        ln -s "$KF5KDESU" "$KDESU"
    fi
    # Set sgid on kdesud
    [ -e "$KF5KDESUD" ] && chmod g+s "$KF5KDESUD"
    
    # This conf file sets user-session to kde-plasma-kf5. Unfortunately, the
    # file in /usr/share/xsessions is called plasma.desktop and not
    # kde-plasma-kf5.desktop. The default desktop file there still works, so...
    CONF='/usr/share/lightdm/lightdm.conf.d/40-kde-plasma-kf5.conf'
    if [ -e $CONF ]; then
        KF5DT='/usr/share/xsessions/kde-plasma-kf5.desktop'
        PDT='/usr/share/xsessions/plasma.desktop'
        if [ ! -e $KF5DT ]; then
            if [ -e $PDT ]; then
                ln -s $PDT $KF5DT
            else
                divert_file $CONF
            fi
        fi
    fi
fi

# ====================
# SolydX Configuration
# ====================
if [ "$DESKTOP_ENV" == 'xfce' ]; then
    # Reconfigure EE packages if they are installed
    dpkg-reconfigure solydxee-info 2>/dev/null

    FIREFOX='/usr/bin/firefox-esr'
    [ ! -e "$FIREFOX" ] && FIREFOX='/usr/bin/firefox'

    CONF='/etc/skel/.config/xfce4/panel/whiskermenu-9.rc'
    if [ -e "$FIREFOX" ] && [ -e $CONF ]; then
        echo "> Configure $CONF"
        sed -i -e "s/firefox[\"a-z-]*\./$(basename $FIREFOX)\./" "$CONF"
    fi

    CONF='/usr/lib/firefox-esr/distribution/distribution.ini'
    [ -e $CONF ] && echo "> Configure $CONF"; sed -i "s/\"Breeze\"/\"$BREEZE_THEME\"/g" "$CONF"
    
    CONF='/usr/lib/thunderbird/distribution/distribution.ini'
    [ -e $CONF ] && echo "> Configure $CONF"; sed -i "s/\"Breeze\"/\"$BREEZE_THEME\"/g" "$CONF"
    
    if which gconftool-2 >/dev/null; then
        echo 'Set gconf default settings'
        gconftool-2 --direct --config-source xml:readwrite:/etc/gconf/gconf.xml.defaults --type bool --set /apps/gksu/sudo-mode true
        gconftool-2 --direct --config-source xml:readwrite:/etc/gconf/gconf.xml.defaults --type bool --set /apps/gksu/display-no-pass-info false
        gconftool-2 --direct --config-source xml:readwrite:/etc/gconf/gconf.xml.defaults --type string --set /apps/blueman/transfer/browse_command 'thunar --browser obex://[%d]'
    fi
fi

# ====================
# SolydL Configuration
# ====================
if [ "$DESKTOP_ENV" == 'lxqt' ]; then
    # Desktop files   
    FLE='/usr/share/applications/xfce-wm-settings.desktop'
    divert_file "$FLE"
    if [ -f "$FLE" ]; then
        ! grep -q 'OnlyShowIn=LXQt;' "$FLE" && sed -i 's#OnlyShowIn=#OnlyShowIn=LXQt;#' "$FLE"
        ! grep -q 'Categories=Qt;LXQt;' "$FLE" && sed -i 's#Categories=#Categories=Qt;LXQt;#' "$FLE"
    fi

    FLE='/usr/share/applications/xfce-wmtweaks-settings.desktop'
    divert_file "$FLE"
    if [ -f "$FLE" ]; then
        ! grep -q 'OnlyShowIn=LXQt;' "$FLE" && sed -i 's#OnlyShowIn=#OnlyShowIn=LXQt;#' "$FLE"
        ! grep -q 'Categories=Qt;LXQt;' "$FLE" && sed -i 's#Categories=#Categories=Qt;LXQt;#' "$FLE"
    fi

    FLE='/usr/share/applications/qt5ct.desktop'
    divert_file "$FLE"
    if [ -f "$FLE" ]; then
        ! grep -q 'Categories=LXQt;' "$FLE" && sed -i 's#Categories=#Categories=LXQt;#' "$FLE"
    fi

    # Ugly, but found no other way to show b/w icon in systray
    FLE="/usr/share/icons/$ICON_THEME/devices/24/drive-removable-media.svg"
    [ -f "$FLE" ] && cp -f "$FLE" "/usr/share/icons/$ICON_THEME/devices/64/"

    FLE="/usr/share/icons/$ICON_THEME/apps/64/system-software-installer.svg"
    [ -f "$FLE" ] && cp -f "$FLE" "/usr/share/icons/$ICON_THEME/apps/16/system-software-update.svg"

    FLE="/usr/share/icons/$ICON_THEME/apps/24/system-software-update.svg"
    [ -f "$FLE" ] && cp -f "$FLE" "/usr/share/icons/$ICON_THEME/apps/64/"

    FLE="/usr/share/icons/$ICON_THEME/status/24/software-update-available.svg"
    [ -f "$FLE" ] && cp -f "$FLE" "/usr/share/icons/$ICON_THEME/status/64/"

    FLE="/usr/share/icons/$ICON_THEME/status/24/software-update-urgent.svg"
    [ -f "$FLE" ] && cp -f "$FLE" "/usr/share/icons/$ICON_THEME/status/64/"

    # These need to be colored
    FLE="/usr/share/icons/$ICON_THEME/places/64/folder-desktop.svg"
    if [ -f "$FLE" ]; then
        TRG="/usr/share/icons/$ICON_THEME/places/24/user-desktop.svg"
        [ -e "$TRG" ] && rm "$TRG"
        cp -f "$FLE" "$TRG"
    fi

    FLE="/usr/share/icons/$ICON_THEME/apps/64/config-users.svg"
    [ -f "$FLE" ] && cp -f "$FLE" "/usr/share/icons/$ICON_THEME/apps/16/"

    FLE="/usr/share/icons/$ICON_THEME/status/64/blueman.svg"
    [ -f "$FLE" ] && cp -f "$FLE" "/usr/share/icons/$ICON_THEME/status/16/"

    FLE="/usr/share/icons/$ICON_THEME/places/64/user-desktop.svg"
    if [ -f "$FLE" ]; then
        cp -f "$FLE" "/usr/share/icons/$ICON_THEME/places/16/"
        cp -f "$FLE" "/usr/share/icons/$ICON_THEME/places/24/"
    fi
    
    FLE="/usr/share/icons/$ICON_THEME/apps/64/preferences-desktop-locale.svg"
    [ -f "$FLE" ] && cp -f "$FLE" "/usr/share/icons/$ICON_THEME/apps/16/"
    
    FLE="/usr/share/icons/$ICON_THEME/devices/64/input-mouse.svg"
    [ -f "$FLE" ] && cp -f "$FLE" "/usr/share/icons/$ICON_THEME/devices/16/"
    
    # Missing symlinks
    FLE="/usr/share/icons/$ICON_THEME/apps/16/preferences.svg"
    [ -f "$FLE" ] && ln -sf 'preferences.svg' "/usr/share/icons/$ICON_THEME/apps/16/preferences-desktop.svg"
    
    update-icon-caches /usr/share/icons/$ICON_THEME
fi

# ===================
# Update alternatives
# ===================
DT_THEME='/usr/share/desktop-base/active-theme'
DT_GRUB='/usr/share/images/desktop-base/desktop-grub.png'

THEME_PATH="/usr/share/desktop-base/${THEME_01}-theme"
if [ -d "$THEME_PATH" ]; then
    update-alternatives --install $DT_THEME desktop-theme "$THEME_PATH" 100
    update-alternatives --install $DT_GRUB desktop-grub "$THEME_PATH/grub/grub-16x9.png" 30
    update-alternatives --install $DT_GRUB desktop-grub "$THEME_PATH/grub/grub-4x3.png" 30
fi

THEME_PATH="/usr/share/desktop-base/${THEME_02}-theme"
if [ -d "$THEME_PATH" ]; then
    update-alternatives --install $DT_THEME desktop-theme "$THEME_PATH" 100
    update-alternatives --install $DT_GRUB desktop-grub "$THEME_PATH/grub/grub-16x9.png" 30
    update-alternatives --install $DT_GRUB desktop-grub "$THEME_PATH/grub/grub-4x3.png" 30
fi

THEME_PATH="/usr/share/desktop-base/${THEME_03}-theme"
if [ -d "$THEME_PATH" ]; then
    update-alternatives --install $DT_THEME desktop-theme "$THEME_PATH" 100
    update-alternatives --install $DT_GRUB desktop-grub "$THEME_PATH/grub/grub-16x9.png" 30
    update-alternatives --install $DT_GRUB desktop-grub "$THEME_PATH/grub/grub-4x3.png" 30
fi

update-alternatives --auto desktop-theme
update-alternatives --auto desktop-grub

# =====================
# LightDM Configuration
# =====================

LIGHTDM_DIR='/usr/share/lightdm/lightdm-gtk-greeter.conf.d'
mkdir -p "$LIGHTDM_DIR"
CONF="$LIGHTDM_DIR/50_solydxk.conf"
echo "> Configure $CONF"
cat > "$CONF" << EOF
[greeter]
theme-name = $BREEZE_THEME
icon-theme-name = ${ICON_THEME}
font-name = Clear Sans 11
default-user-image = /usr/share/pixmaps/faces/user-generic.png
clock-format = %d %b, %H:%M
indicators = ~host;~spacer;~session;~language;~a11y;~clock;~power
position = 60%,center 40%,center
EOF

LIGHTDM_DIR='/usr/share/lightdm/lightdm.conf.d'
mkdir -p "$LIGHTDM_DIR"
CONF="$LIGHTDM_DIR/50_solydxk.conf"
echo "> Configure $CONF"
cat > "$CONF" << EOF
[Seat:*]
greeter-hide-users = false
allow-user-switching = true
EOF

LIGHTDM_DIR='/usr/share/lightdm/users.conf.d'
mkdir -p "$LIGHTDM_DIR"
CONF="$LIGHTDM_DIR/50_solydxk.conf"
echo "> Configure $CONF"
cat > "$CONF" << EOF
[UserList]
minimum-uid = 1000
EOF

# ===================
# Grub2 Configuration
# ===================
DEFAULT_GRUB='/etc/default/grub'
GRUB_THEME="/usr/share/grub/themes/${THEME_01}/theme.txt"
GRUB_TEMPLATE='/usr/share/grub/default/grub'
[ -e "$GRUB_TEMPLATE" ] && cp "$GRUB_TEMPLATE" "$DEFAULT_GRUB"
if [ -e "$GRUB_THEME" ]; then
    echo "> Set Grub2 theme: $GRUB_THEME"
    if grep -q '^GRUB_THEME=' $DEFAULT_GRUB; then
        # Change existing Grub theme
        sed -i "s|^GRUB_THEME=.*|GRUB_THEME=$GRUB_THEME|" $DEFAULT_GRUB
    else
        # Append Grub theme
        echo -e "\n# Check available themes in /usr/share/grub/themes\nGRUB_THEME=$GRUB_THEME" >> $DEFAULT_GRUB
    fi

    GRUB_DEFAULT='GRUB_DEFAULT=saved\nGRUB_SAVEDEFAULT=true\nGRUB_HIDDEN_TIMEOUT_QUIET=true'
    sed -i -e "s|^GRUB_DEFAULT=0|$GRUB_DEFAULT|" $DEFAULT_GRUB

    [ ! -z "$DESCRIPTION" ] && GRUB_DISTRIBUTOR=$DESCRIPTION || GRUB_DISTRIBUTOR='SolydXK'
    sed -i -e "s/GRUB_DISTRIBUTOR=.*/GRUB_DISTRIBUTOR=\"$GRUB_DISTRIBUTOR\"/" $DEFAULT_GRUB

    sed -i -e 's|"quiet"|"quiet splash"|' $DEFAULT_GRUB
fi

# Enable os-prober - hands off for now
#if grep -q 'GRUB_DISABLE_OS_PROBER=' $DEFAULT_GRUB; then
#    sed -i 's|.*GRUB_DISABLE_OS_PROBER.*|GRUB_DISABLE_OS_PROBER=false|' $DEFAULT_GRUB
#else
#    # Only append if GRUB_DISABLE_OS_PROBER= is not in DEFAULT_GRUB
#    echo -e '\n# Disable os-prober\nGRUB_DISABLE_OS_PROBER=false' >> $DEFAULT_GRUB
#fi

# Update Grub2
update-grub

# Fix os-prober not listing LUKS partitions
OS_PROBER='/usr/bin/os-prober'
divert_file "$OS_PROBER"
if [ -e "$OS_PROBER" ]; then
    if ! grep -q "cryptsetup" "$OS_PROBER"; then
        echo "> List LUKS partitions in $OS_PROBER"
        cat > tmp.txt << EOF
	# List connected LUKS devices
	if type cryptsetup >/dev/null 2>&1; then
		for device in \$(ls /dev/mapper); do
			if [ ! -z "\$(cryptsetup status /dev/mapper/\$device | grep LUKS)" ]; then
				echo "/dev/mapper/\$device"
			fi
		done
	fi

EOF
        sed -i -e "/partitions.*(.*).*{/r tmp.txt" "$OS_PROBER"
        rm tmp.txt
    fi
fi

# ======================
# Plymouth Configuration
# ======================
if [ ! -z "$(which plymouth-set-default-theme)" ]; then
    echo "> Set Plymouth theme $THEME_01"
    plymouth-set-default-theme -R "$THEME_01"
fi

# ====================
# Bashrc Configuration
# ====================
FLE='/etc/skel/.bashrc'
divert_essential_file "$FLE"
if [ -f "$FLE" ]; then
    # Fix multiple entries in .bashrc
    # - Search for start line until first empty line and delete that
    sed -i '/# Source the SolydXK info file/,/^$/{/^$/!d}' "$FLE"
    # Fix volume always set to 100%
    sed -i 's/;31m/;34m/' "$FLE"
    sed -i 's/;32m/;34m/' "$FLE"
    sed -i 's/#\s*alias\s/alias /g' "$FLE"
    # Check if already added
    if ! grep -Fq "$INFO" "$FLE" && [ -e "$INFO" ]; then
        cat >> "$FLE" << EOF

# Source SolydXK info file
if [ -f $INFO ]; then
. $INFO
fi
EOF
    fi
fi

# ==================
# Root Configuration
# ==================
for FILE in $ROOT_FILES; do
    [ -e "/etc/skel/$FILE" ] && cp -v --parents "/etc/skel/$FILE" "/root/"
done
XTRA_ROOT_FILES=$(find /usr/share/solydxk/root_files -type f)
for FILE in $XTRA_ROOT_FILES; do
    cp -v --parents "$FILE" "/root/"
done
echo 'SELECTED_EDITOR="/bin/nano"' > /root/.selected_editor
[ -e /root/.mozilla ] && rm -r /root/.mozilla
touch /root/.mozilla
[ -e /root/.thunderbird ] && rm -r /root/.thunderbird
touch /root/.thunderbird

# ===================
# Audio Configuration
# ===================
CONF='/etc/modprobe.d/alsa-base.conf'
[ -f "$CONF" ] && CONT=$(cat "$CONF")
CHK="options snd-hda-intel model"
[[ "$CONT" != *$CHK* ]] && echo "$CHK=auto" >> "$CONF"

CONF='/etc/modprobe.d/alsa-base-blacklist.conf'
[ -f "$CONF" ] && CONT=$(cat "$CONF")
CHK="blacklist pcspkr"
[[ "$CONT" != *$CHK* ]] && echo "$CHK" >> "$CONF"

# Pulsaudio files
PULSE_DIR='/etc/pulse/daemon.conf.d'
mkdir -p $PULSE_DIR
echo "flat-volumes = no" > "$PULSE_DIR/50_solydxk.conf"

# ======================
# Firewall Configuration
# ======================
UFW=$(which ufw)
if [ ! -z "$UFW" ]; then
    echo 'Setup UFW'
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

# firewalld: cannot use firewall-cmd in a chrooted environment:
# DBUS_ERROR: Failed to connect to socket /run/dbus/system_bus_socket: No such file or directory
#firewall-cmd --set-default-zone=home
#firewall-cmd --permanent --add-service=ipp
#firewall-cmd --reload
FWDCONF='/etc/firewalld/firewalld.conf'
if [ -f "$FWDCONF" ]; then
    echo 'Setup Firewalld'
    # Set default zone to home
    sed -i -e 's/^DefaultZone=.*/DefaultZone=home/' $FWDCONF
    mkdir -p /etc/firewalld/zones/
    
    # Setup home zone
    FWDHOME='/etc/firewalld/zones/home.xml'
    if [ ! -f "$FWDHOME" ]; then
        # Create initial file
        cat > "$FWDHOME" << EOF
<?xml version="1.0" encoding="utf-8"?>
<zone>
<short>Home</short>
<description>For use in home areas. You mostly trust the other computers on networks to not harm your computer. Only selected incoming connections are accepted.</description>
<service name="mdns"/>
<service name="samba-client"/>
<service name="dhcpv6-client"/>
<service name="ipp"/>
<forward/>
</zone>
EOF
    fi
fi

# ==============
# Refresh caches
# ==============
# Update cache
[ ! -z "$(which update-desktop-database)" ] && update-desktop-database -q

# Refresh xapian database
[ ! -z "$(which update-apt-xapian-index)" ] && update-apt-xapian-index

# Update database for mlocate
[ ! -z "$(which updatedb)" ] && updatedb

# Recreate pixbuf cache
PIX_CACHE=$(dpkg -S *x86_64*gdk-pixbuf-query-loaders | awk '{print $2}')
[ -x "$PIX_CACHE" ] && "$PIX_CACHE" --update-cache

# Compile all the GSettings XML schema files
[ ! -z "$(which glib-compile-schemas)" ] && glib-compile-schemas /usr/share/glib-2.0/schemas

# =================
# GPG Configuration
# =================
GPG='/etc/skel/.gnupg'
[ -e $GPG ] && chmod 700 $GPG

APT=/etc/apt
if [ -e $APT/trusted.gpg ]; then
    OBSOLETE=$APT/trusted.gpg.obsolete
    mv -f $APT/trusted.gpg $OBSOLETE
    echo "> $APT/trusted.gpg renamed to $OBSOLETE"
    L=1
    T=$(LANG=C apt-key list 2>/dev/null)
    while read -r R; do
        ((++L))
        if [ "${R:0:3}" == pub ]; then
            [ "${R#*expired:}" != "$R" ] && L=1 || L=0
        elif [ $L -eq 1 ]; then
            if grep -q "$R" <<<$T; then
                echo "> $R already present"
            else
                echo "> $R exported to trusted.gpg.d"
                R="${R// /}"
                apt-key --keyring $OBSOLETE export $R 2>/dev/null >$APT/trusted.gpg.d/$R.asc
            fi
        fi
    done < <(LANG=C apt-key --keyring $OBSOLETE list 2>/dev/null) 
fi

# ===========================
# Desktop Files Configuration
# ===========================
FLE='/usr/share/applications/org.kde.kate.desktop'
divert_file "$FLE"
[ -e "$FLE" ] && sed -i 's/;Development//' "$FLE"
    
FLE='/usr/share/applications/gdebi.desktop'
divert_file "$FLE"
[ -e "$FLE" ] && sed -i 's#Exec=.*#Exec=sh -c "gdebi-gtk %f"#' "$FLE"

FLE='/usr/share/applications/xfce4-mail-reader.desktop'
divert_file "$FLE"
[ -e "$FLE" ] && sed -i 's#OnlyShowIn=.*#NoDisplay=true#' "$FLE"

FLE='/usr/share/applications/xfce4-web-browser.desktop'
divert_file "$FLE"
[ -e "$FLE" ] && sed -i 's#OnlyShowIn=.*#NoDisplay=true#' "$FLE"

FLE='/usr/share/applications/hardinfo.desktop'
divert_file "$FLE"
[ -e "$FLE" ] && sed -i 's#Icon=.*#Icon=hardinfo#' "$FLE"

FLE='/usr/share/applications/luckybackup-su.desktop'
divert_file "$FLE"
[ -e "$FLE" ] && sed -i 's#Icon=.*#Icon=luckybackup#' "$FLE"

FLE='/usr/share/applications/luckybackup.desktop'
divert_file "$FLE"
[ -e "$FLE" ] && sed -i 's#Icon=.*#Icon=luckybackup#' "$FLE"

# ========================
# Additional Configuration
# ========================
# Fix ping
PING=$(which ping)
[ ! -z "$PING" ] && chmod u+s "$PING"

# Disable memtest in Grub
MEMTEST='/etc/grub.d/20_memtest86+'
[ -f "$MEMTEST" ] && chmod -x "$MEMTEST"

# If dpkg removed /usr/local/bin: recreate it
mkdir -p /usr/local/bin

# Change face icon
ICON='/usr/share/icons/hicolor/scalable/apps/solydk.svg'
[ "$DESKTOP_ENV" == 'xfce' ] && ICON='/usr/share/icons/hicolor/scalable/apps/solydx.svg'
[ "$DESKTOP_ENV" == 'lxqt' ] && ICON='/usr/share/icons/hicolor/scalable/apps/solydl.svg'
[ -f "$ICON" ] && cp "$ICON" /etc/skel/.face
