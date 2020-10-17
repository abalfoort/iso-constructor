#!/usr/bin/env python3

import os
import shutil
import glob
import errno
import stat
import apt
import subprocess
import re
import threading
from os.path import expanduser, exists
from fuzzywuzzy import fuzz
from distutils.dir_util import copy_tree
from distutils.errors import DistutilsFileError

def shell_exec_popen(command, kwargs={}):
    print(('Executing:', command))
    return subprocess.Popen(command, shell=True,
                            stdout=subprocess.PIPE, **kwargs)


def shell_exec(command):
    print(('Executing:', command))
    return subprocess.call(command, shell=True)


def getoutput(command):
    #return shell_exec(command).stdout.read().strip()
    try:
        output = subprocess.check_output(command, shell=True).decode('utf-8').strip().replace('\r\n', '\n').replace('\r', '\n').split('\n')
    except:
        output = []
    return output


def chroot_exec(command):
    command = command.replace('"', "'").strip()  # FIXME
    return shell_exec('chroot /target/ /bin/sh -c "%s"' % command)


# Read keys from file
def get_config_dict(file, key_value=re.compile(r'^\s*(\w+)\s*=\s*["\']?(.*?)["\']?\s*(#.*)?$')):
    """Returns POSIX config file (key=value, no sections) as dict.
    Assumptions: no multiline values, no value contains '#'. """
    d = {}
    with open(file) as f:
        for line in f:
            try:
                key, value, _ = key_value.match(line).groups()
            except AttributeError:
                continue
            d[key] = value
    return d


# Get the package version number
def get_package_version(package, candidate=False):
    version = ''
    try:
        cache = apt.Cache()
        pkg = cache[package]
        if candidate:
            version = pkg.candidate.version
        elif pkg.installed is not None:
            version = pkg.installed.version
    except:
        pass
    return version


# Convert string to number
def str_to_nr(stringnr, toInt=False):
    nr = 0
    # Might be a int or float: convert to str
    stringnr = str(stringnr).strip()
    try:
        if toInt:
            nr = int(stringnr)
        else:
            nr = float(stringnr)
    except ValueError:
        nr = 0
    return nr


def get_logged_user():
    return os.getlogin()


def get_user_home():
    return expanduser("~%s" % get_logged_user())


def silent_remove(path, tree=True):
    try:
        for f in glob.glob(path):
            os.system("chmod -f u+w '%s'" % f)
            os.remove(f)
            print(("Removed: %s" % f))
    except:
        try:
            if tree:
                shutil.rmtree(path)
            else:
                os.rmdir(path)
            print(("Removed: %s" % path))
        except OSError as e:
            if e.errno != errno.ENOENT:
                print(("ERROR: silent_remove - %s" % e))


# Get the host's installed EFI architecture (x86_64 or i386)
def get_host_efi_arch():
    return getoutput("ls /usr/lib/grub/ 2> /dev/null | grep efi | cut -d'-' -f1")[0]


# Get the possible EFI architecture of the target environment (x86_64 or i386)
def get_guest_efi_arch(rootPath):
    ret = ''
    if exists(rootPath):
        ret = 'i386'
        output = getoutput("file {}/bin/ls".format(rootPath))[0]
        if 'x86-64' in output:
            ret = 'x86_64'
    return ret


# Get lsb-release information
# lsb_parameter: DISTRIB_ID (default), DISTRIB_RELEASE, DISTRIB_CODENAME, DISTRIB_DESCRIPTION
def get_lsb_release_info(root_dir=None):
    lsb_dict = {}
    lsb_release_path = '/etc/*release'
    if exists(root_dir):
       lsb_release_path = '{rootdir}/etc/*release'.format(rootdir=root_dir) 
    try:
        lsb_dict['name'] = getoutput("egrep '^DISTRIB_DESCRIPTION|^PRETTY_NAME' {lrp} | head -n 1 | cut -d'=' -f 2  | tr -d '\"'".format(lrp=lsb_release_path))[0]
        lsb_dict['id'] = getoutput("egrep '^DISTRIB_ID|^ID' {lrp} | head -n 1 | cut -d'=' -f 2  | tr -d '\"'".format(lrp=lsb_release_path))[0]
        lsb_dict['codename'] = getoutput("egrep '^DISTRIB_CODENAME|^VERSION_CODENAME' {lrp} | head -n 1 | cut -d'=' -f 2  | tr -d '\"'".format(lrp=lsb_release_path))[0]
        lsb_dict['version'] = getoutput("egrep '^DISTRIB_RELEASE|^VERSION_ID|^VERSION' {lrp} | head -n 1 | cut -d'=' -f 2  | tr -d '\"'".format(lrp=lsb_release_path))[0]
       
    except Exception as detail:
        print("ERROR (functions.get_lsb_release_info: %(detail)s" % {"detail": detail})
    return lsb_dict


def copy(src, dst, debug=False):
    if exists(src):
        try:
            verbose = 1 if debug else 0
            copy_tree(src, dst, verbose=verbose)
        except DistutilsFileError:
            # Not a directory, copy as file
            try:
                shutil.copy2(src, dst)
            except DistutilsFileError as e:
                print(('ERROR - Cannot copy %s > %s: %s' % (src, dst, e)))
                return False
        if debug: print(('DEBUG - Successfuly copied %s > %s' % (src, dst)))
    else:
        print(('ERROR - Cannot copy %s > %s: source does not exist' % (src, dst)))
        return False
    return True


# shutil.copytree does not recursively copy into an existing destination directory
# We need an improved copytree
# Contrary to shutil.copytree, this version copies symlinks as symlinks by default
def copytree(src, dst, symlinks=True, ignore=None):
    if not exists(dst):
        os.makedirs(dst)
        shutil.copystat(src, dst)
    lst = os.listdir(src)
    if ignore:
        excl = ignore(src, lst)
        lst = [x for x in lst if x not in excl]
    for item in lst:
        s = join(src, item)
        d = join(dst, item)
        if symlinks and islink(s):
            # Copy symbolic link only if copy will not point to itself
            s_lnk = os.readlink(s)
            if s_lnk != d[-len(s_lnk):]:
                # lexists will also remove broken symlinks
                if lexists(d):
                    os.remove(d)
                os.symlink(s_lnk, d)
                try:
                    st = os.lstat(s)
                    mode = stat.S_IMODE(st.st_mode)
                    os.lchmod(d, mode)
                except:
                    pass # lchmod not available
        elif isdir(s):
            copytree(s, d, symlinks, ignore)
        else:
            # copy does not seem to overwrite symlinks when pointing to the source file
            if lexists(d):
                os.remove(d)
            shutil.copy2(s, d)


# Fuzzy string comparison
# fuzzy_level: 1 = no string pre-processing (differnce in character case)
#              2 = optimal partial logic
#              3 = includes string pre-processing (remove punctuation, lower case, etc)
#              4 = ptakes out the common tokens (the intersection) and then makes a pairwise comparisons
def get_fuzzy_ratio(string1, string2, fuzzy_level=1):
    if fuzzy_level == 2:
        ratio = fuzz.partial_ratio(string1,string2)
    elif fuzzy_level == 3:
        ratio = fuzz.token_sort_ratio(string1,string2)
    elif fuzzy_level == 4:
        ratio = fuzz.token_set_ratio(string1,string2)
    else:
        ratio = fuzz.ratio(string1,string2)
    return ratio


# Class to run commands in a thread and return the output in a queue
class ExecuteThreadedCommands(threading.Thread):

    def __init__(self, commandList, theQueue=None, returnOutput=False):
        super(ExecuteThreadedCommands, self).__init__()
        self.commands = commandList
        self.queue = theQueue
        self.returnOutput = returnOutput

    def run(self):
        if isinstance(self.commands, (list, tuple)):
            for cmd in self.commands:
                self.exec_cmd(cmd)
        else:
            self.exec_cmd(self.commands)

    def exec_cmd(self, cmd):
        if self.returnOutput:
            ret = getoutput(cmd)
        else:
            ret = shell_exec(cmd)
        if self.queue is not None:
            self.queue.put(ret)
