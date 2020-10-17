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


# Files

~/.iso-constructor/distributions.list
:   List with distribution directories

~/.constructor/iso-constructor.log
:   Log file.

~/.constructor/grub-template (optional)
:   Custom template for grub.cfg. Use /usr/share/iso-constructor/grub-template as base.

~/.constructor/isolinux-template (optional)
:   Custom template for isolinux.cfg. Use /usr/share/iso-constructor/isolinux-template as base.

# Author

Written by Arjen Balfoort

# BUGS

https://gitlab.com/abalfoort/iso-indicator/-/issues

# TRANSLATIONS

https://www.transifex.com/abalfoort/iso-constructor

# TODO

Find out how to update/customize the pool packages in Debian live ISOs.
