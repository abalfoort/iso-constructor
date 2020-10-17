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

-l
:   Localize the distribution

-u
:   Upgrade the distribution

-U
:   Unpack the ISO

Options for the GUI (all other parameters will be ignored):

-v
:   Prints debug information while running the GUI.


# GUI

## Add distribution
Here you can either unpack an ISO to a new work directory or select an exsiting previously removed work directory.

## Remove distribution
When removing a distribution the work directory will NOT be removed.

## Upgrade distribution
Simply runs "apt-get dist-upgrade" but taking into account that some services need to be handled before and after the upgrade.

## Localize the ISOs
ISO Constructor by default generates a boot menu where the user can select their own locale when starting a live session. This will localize your live system permanently to your selected locale. Do not forget to translate the Grub and Isolinux menu. See the section below on editing the Grub and Isolinux templates.

## Build ISOs
Builds the ISO and creates a sha256 file.

# GRUB AND ISOLINUX

To customize/translate the Grub and Isolinux boot menus you can create and edit the templates in ~/.iso-constructor/:

cp -v /usr/share/iso-constructor/grub-template ~/.iso-constructor/

cp -v /usr/share/iso-constructor/isolinux-template ~/.iso-constructor/

# FILES

~/.iso-constructor/distributions.list
:   List with distribution directories

~/.constructor/iso-constructor.log
:   Log file.

~/.constructor/grub-template (optional)
:   Custom template for grub.cfg. Use /usr/share/iso-constructor/grub-template as base.

~/.constructor/isolinux-template (optional)
:   Custom template for isolinux.cfg. Use /usr/share/iso-constructor/isolinux-template as base.

# AUTHOR

Written by Arjen Balfoort

# BUGS

https://gitlab.com/abalfoort/iso-indicator/-/issues

# TRANSLATIONS

https://www.transifex.com/abalfoort/iso-constructor

# TODO

Find out how to update/customize the pool packages in Debian live ISOs.
