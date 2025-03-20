# ISO CONSTRUCTOR

iso-constructor - Tool to build and maintain custom Debian Live ISOs.

# SYNOPSIS

Usage: iso-constructor [OPTIONS] [DISTRIBUTION_PATH]

DISTRIBUTION_PATH contains the unpacked distribution with a boot and root directory.

# DESCRIPTION

Without parameters the GUI is started.

Options for terminal use (no GUI):

-b
:   Build the distribution

-e
:   Edit the distribution

-h
:   Help screen

-u
:   Upgrade the distribution

-U [iso_path]
:   Unpack the ISO

Options for the GUI (all other parameters will be ignored):

-v
:   Prints debug information while running the GUI.

# GUI

## Add distribution
Here you can either unpack an ISO to a new work directory or select an exsiting previously removed work directory.

## Remove distribution
When removing a distribution the work directory will NOT be removed.

## Edit distribution
Creates a chrooted environment where you can change the system.

## Upgrade distribution
Simply runs "apt-get dist-upgrade" but taking into account that some services need to be handled before and after the upgrade.

## Build ISOs
Builds the ISO and creates a sha256 file.

If you installed packages that are not in the repository but you want to keep installed you can edit the keep-packages file:

cp -v /usr/share/iso_constructor/keep-packages ~/.iso-constructor/

Note: to keep all packages you can simply write an asterisk (*) in the keep-packages file.

# REPOSITORY

You can create a pool directory structure as in the live Debian ISOs. Any .deb are updated automatically during build. Release information in the dists directory is generated during build.

Note: ISO Constructor is not able to update the .udeb packages. These need to be updated manually.

# GRUB AND ISOLINUX

To customize/translate the Grub and Isolinux boot menus you can create and edit the templates in ~/.iso-constructor/:

cp -v /usr/share/iso_constructor/grub-template ~/.iso-constructor/

cp -v /usr/share/iso_constructor/isolinux-template ~/.iso-constructor/


# FILES

~/.iso-constructor/iso-constructor.conf
:   Configuration file

~/.iso-constructor/iso-constructor.log
:   Log file.

~/.iso-constructor/keep-packages (optional)
:   List of packages not in repository. Use /usr/share/iso_constructor/keep-packages as base.

~/.iso-constructor/grub-template (optional)
:   Custom template for grub.cfg. Use /usr/share/iso_constructor/grub-template as base.

~/.iso-constructor/isolinux-template (optional)
:   Custom template for isolinux.cfg. Use /usr/share/iso_constructor/isolinux-template as base.

# AUTHOR

Written by Arjen Balfoort

# BUGS

https://github.com/abalfoort/iso-constructor/issues

# TRANSLATIONS

https://www.transifex.com/abalfoort/iso-constructor

# TODO

Find out how to update/customize the pool packages in Debian live ISOs.
