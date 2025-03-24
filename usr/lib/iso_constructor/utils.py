#!/usr/bin/env python3
""" Module providing general purpose functions """

import os
import subprocess
import re
import numbers
import pwd
from os.path import expanduser, exists
import apt


def shell_exec_popen(command, kwargs=None):
    """ Execute a command with Popen (returns the returncode attribute) """
    if not kwargs:
        kwargs = {}
    print((f"Executing: {command}"))
    # return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, **kwargs)
    return subprocess.Popen(command,
                            shell=True,
                            bufsize=0,
                            stdout=subprocess.PIPE,
                            universal_newlines=True,
                            **kwargs)


def shell_exec(command, wait=False):
    """ Execute a command (returns the returncode attribute) """
    print((f"Executing: {command}"))
    if wait:
        return subprocess.check_call(command, shell=True)
    return subprocess.call(command, shell=True)


def getoutput(command, timeout=None):
    """ Return command output (list) """
    try:
        output = subprocess.check_output(
            command, shell=True, timeout=timeout).decode('utf-8').strip().split('\n')
    except Exception as detail:
        print((f'getoutput exception: {detail}'))
        output = ['']
    return output


def chroot_exec(command, target):
    """ Excecute command in chroot """
    command = command.replace('"', "'").strip()  # FIXME
    return shell_exec(f'chroot {target}/ /bin/bash -c "{command}"')


def get_config_dict(file, key_value=re.compile(r'^\s*(\w+)\s*=\s*["\']?(.*?)["\']?\s*(#.*)?$')):
    '''
    Read keys from file.
    Returns POSIX config file (key=value, no sections) as dict.
    Assumptions: no multiline values, no value contains '#'.
    '''
    config_dict = {}
    with open(file=file, mode='r', encoding='utf-8') as config_fle:
        for line in config_fle:
            try:
                key, value, _ = key_value.match(line).groups()
            except AttributeError:
                continue
            config_dict[key] = value
    return config_dict


def is_package_installed(package_name):
    """ Check if package is installed """
    cache = apt.Cache()
    if cache[package_name].is_installed:
        return True
    return False


def does_package_exist(package_name):
    """ Check if a package exists """
    try:
        return bool(apt.Cache()[package_name])
    except KeyError:
        return False


def get_package_version(package_name, candidate=False):
    """ Get package version (default=installed) """
    if not does_package_exist(package_name=package_name):
        return ''
    if candidate:
        return apt.Cache()[package_name].candidate.version
    return apt.Cache()[package_name].installed.version


def str_to_nr(value):
    """ Convert string to number """
    if isinstance(value, numbers.Number):
        # Already numeric
        return value

    number = None
    try:
        number = int(value)
    except ValueError:
        try:
            number = float(value)
        except ValueError:
            number = None
    return number


def is_numeric(value):
    """ Check if value is a number """
    return bool(str_to_nr(value))


def get_logged_user():
    """ Get user name """
    p = os.popen("logname", 'r')
    user_name = p.readline().strip()
    p.close()
    if user_name == "":
        user_name = pwd.getpwuid(os.getuid()).pw_name
    return user_name


def get_user_home():
    ''' Return current user's home dir.'''
    return expanduser(f"~{get_logged_user()}")


def get_host_efi_arch():
    ''' Get the host's installed EFI architecture (x86_64 or i386).'''
    return getoutput("ls /usr/lib/grub/ 2> /dev/null | grep efi | cut -d'-' -f1")[0]


def get_guest_efi_arch(root_path):
    ''' Get the possible EFI architecture of the target environment (x86_64 or i386).'''
    ret = ''
    if exists(root_path):
        ret = 'i386'
        output = getoutput(f"file {root_path}/bin/ls")[0]
        if 'x86-64' in output:
            ret = 'x86_64'
    return ret


def get_lsb_release_info(root_dir=None):
    '''
    Get lsb-release information
    lsb_parameter: DISTRIB_ID (default), DISTRIB_RELEASE, DISTRIB_CODENAME, DISTRIB_DESCRIPTION
    '''
    lsb_dict = {}
    lsb_release_path = '/etc/*release'
    if exists(root_dir):
        lsb_release_path = f'{root_dir}/etc/*release'
    try:
        lsb_dict['name'] = getoutput(f"egrep '^DISTRIB_DESCRIPTION|^PRETTY_NAME' {lsb_release_path}"
                                     " | head -n 1 | cut -d'=' -f 2  | tr -d '\"'")[0]
        lsb_dict['id'] = getoutput(f"egrep '^DISTRIB_ID|^ID' {lsb_release_path}"
                                   " | head -n 1 | cut -d'=' -f 2  | tr -d '\"'")[0]
        lsb_dict['codename'] = getoutput(f"egrep '^DISTRIB_CODENAME|^VERSION_CODENAME' {lsb_release_path}"
                                         " | head -n 1 | cut -d'=' -f 2  | tr -d '\"'")[0]
        lsb_dict['version'] = getoutput(f"egrep '^DISTRIB_RELEASE|^VERSION_ID|^VERSION' {lsb_release_path}"
                                        " | head -n 1 | cut -d'=' -f 2  | tr -d '\"'")[0]

    except Exception as detail:
        print(f"ERROR (functions.get_lsb_release_info: {detail}")
    return lsb_dict
