---
layout: page
title: ISO-CONSTRUCTOR
section: 1
footer: "ISO Constructor"
header: "ISO Constructor"
date: September 2020
---

# NAME

iso-constructor - Tool to build and maintain Debian isos

# SYNOPSIS

**iso-constructor** \[**-d**|**--debug**]

# DESCRIPTION

Tool to build and maintain Debian isos.
ISO Constructor opens in a terminal where you can follow the building output.

-d, --debug
:   Prints debug information.

# Files

~/.iso-constructor/distributions.list
:   List with distribution directories

/usr/share/iso-constructor/grubgen.sh
:   Generates boot/boot/grub/grub.cfg (with grub-template).

/usr/share/iso-constructor/isolinuxgen.sh
:   Generates boot/isolinux/isolinux.cfg (with isolinux-template).

/usr/share/iso-constructor/cleanup.sh
:   This script cleans up prior to building the ISO.

/usr/share/iso-constructor/setlocale.sh
:   Sets the locale of the ISO. Default is: en_US.

/usr/share/iso-constructor/excludes
:   List with directories excluded from the ISO build.

# Author

Written by Arjen Balfoort

# BUGS

https://gitlab.com/abalfoort/iso-indicator/-/issues


