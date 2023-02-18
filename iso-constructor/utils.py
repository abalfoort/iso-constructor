""" Module providing general purpose functions """

#!/usr/bin/env python3

import os
import subprocess
import re
from os.path import expanduser, exists
import apt


def shell_exec_popen(command, kwargs={}):
    ''' Execute command with subprocess arguments. '''
    print(('Executing:', command))
    return subprocess.Popen(command, shell=True,
                            stdout=subprocess.PIPE, **kwargs)


def shell_exec(command, wait=False):
    ''' Execute command in shell '''
    print(('Executing:', command))
    if wait:
        return subprocess.check_call(command, shell=True)
    return subprocess.call(command, shell=True)


def getoutput(command):
    ''' Get output from command. '''
    try:
        output = (subprocess.check_output(command, shell=True)
                            .decode('utf-8')
                            .strip()
                            .replace('\r\n', '\n')
                            .replace('\r', '\n')
                            .split('\n'))
    except Exception:
        output = []
    return output


def chroot_exec(command, chroot_path):
    ''' Run command in chroot environment'''
    command = command.replace('"', "'").strip()  # FIXME
    return shell_exec(f'chroot {chroot_path} /bin/sh -c "{command}"')


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


def get_package_version(package, candidate=False):
    ''' Get the package version number.'''
    version = ''
    try:
        cache = apt.Cache()
        pkg = cache[package]
        if candidate:
            version = pkg.candidate.version
        elif pkg.installed is not None:
            version = pkg.installed.version
    except Exception:
        pass
    return version


def str_to_nr(stringnr, to_int=False):
    ''' Convert string to number.'''
    number = 0
    # Might be a int or float: convert to str
    stringnr = str(stringnr).strip()
    try:
        if to_int:
            number = int(stringnr)
        else:
            number = float(stringnr)
    except ValueError:
        number = 0
    return number


def get_logged_user():
    ''' Return current user.'''
    return os.getlogin()


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
