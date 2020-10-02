#!/usr/bin/env python3

import re
import threading
import glob
import os
from os import makedirs, system, listdir, remove, symlink
from shutil import move, rmtree
from datetime import datetime
from os.path import join, exists, basename, abspath, dirname, isdir, islink

# Local imports
from .execcmd import ExecCmd
from .functions import get_config_dict, getHostEfiArchitecture, \
                      getGuestEfiArchitecture, silent_remove, \
                      get_lsb_release_info, copy, copytree


class IsoUnpack(threading.Thread):
    def __init__(self, mountDir, unpackIso, unpackDir, queue):
        threading.Thread.__init__(self)
        self.ec = ExecCmd()
        self.mountDir = mountDir
        self.unpackIso = unpackIso
        self.unpackDir = unpackDir
        self.queue = queue
        self.returnMessage = None

    def run(self):
        try:
            if not exists(self.mountDir):
                print(("Create mount directory: %s" % self.mountDir))
                makedirs(self.mountDir)

            rootDir = join(self.unpackDir, "root")
            if not exists(rootDir):
                print(("Create root directory: %s" % rootDir))
                makedirs(rootDir)

            isolinuxDir = join(self.unpackDir, "boot/isolinux")
            if not exists(isolinuxDir):
                print(("Create isolinux directory: %s" % isolinuxDir))
                makedirs(isolinuxDir)

            liveDir = join(self.unpackDir, "boot/live")
            if not exists(liveDir):
                print(("Create liveDir directory: %s" % liveDir))
                makedirs(liveDir)

            # Mount the ISO
            system("mount -o loop '%s' '%s'" % (self.unpackIso, self.mountDir))

            # Check isolinux directory
            mountIsolinux = join(self.mountDir, "isolinux")
            if not exists(mountIsolinux):
                self.ec.run("umount --force '%s'" % self.mountDir)
                self.returnMessage = "ERROR: Cannot find isolinux directory in ISO"

            fixCfgCmd = None
            dirs = []
            mountSquashfs = None
            if self.returnMessage is None:
                subdirs = self.getDirectSubDirectories(self.mountDir)
                for subdir in subdirs:
                    if self.hasSquashFs(join(self.mountDir, subdir)):
                        mountSquashfs = join(self.mountDir, subdir)
                        if subdir != "live":
                            fixCfgCmd = r"sed -i 's/\/%s/\/live/g' '%s/isolinux.cfg'" % (subdir, isolinuxDir)
                    elif subdir != "isolinux":
                        dirs.append(join(self.mountDir, subdir))

                if mountSquashfs is None:
                    self.ec.run("umount --force '%s'" % self.mountDir)
                    self.returnMessage = "ERROR: Cannot find squashfs directory in ISO"

            if self.returnMessage is None:
                # Copy files from ISO to unpack directory
                for d in dirs:
                    self.ec.run("rsync -at --del '%s' '%s'" % (d, join(self.unpackDir, "boot/")))
                self.ec.run("rsync -at --del '%s/' '%s'" % (mountIsolinux, isolinuxDir))
                self.ec.run("rsync -at --del '%s/' '%s'" % (mountSquashfs, liveDir))
                self.ec.run("umount --force '%s'" % self.mountDir)

                if fixCfgCmd is not None:
                    self.ec.run(fixCfgCmd)

                # rsync squashfs root
                squashfs = join(liveDir, "filesystem.squashfs")
                if exists(squashfs):
                    self.ec.run("mount -t squashfs -o loop '%s' '%s'" % (squashfs, self.mountDir))
                    self.ec.run("rsync -at --del '%s/' '%s/'" % (self.mountDir, rootDir))
                    self.ec.run("umount --force '%s'" % self.mountDir)

                # Cleanup
                silent_remove(self.mountDir, False)
                # set proper permissions
                self.ec.run("chmod 6755 '%s'" % join(rootDir, "usr/bin/sudo"))
                self.ec.run("chmod 0440 '%s'" % join(rootDir, "etc/sudoers"))

                self.returnMessage = "DONE - ISO unpacked to: %s" % self.unpackDir

            self.queue.put(self.returnMessage)

        except Exception as detail:
            self.ec.run("umount --force '%s'" % self.mountDir)
            silent_remove(self.mountDir, False)
            self.returnMessage = "ERROR: IsoUnpack: %(detail)s" % {"detail": detail}
            self.queue.put(self.returnMessage)

    def getDirectSubDirectories(self, directory):
        subdirs = []
        names = listdir(directory)
        for name in names:
            if isdir(join(directory, name)):
                subdirs.append(name)
        return subdirs

    def hasSquashFs(self, directory):
        names = listdir(directory)
        for name in names:
            if name == "filesystem.squashfs":
                return True
        return False


class BuildIso(threading.Thread):
    def __init__(self, distroPath, queue):
        threading.Thread.__init__(self)
        self.ec = ExecCmd()
        self.dg = DistroGeneral(distroPath)
        self.ed = EditDistro(distroPath)
        self.queue = queue

        self.returnMessage = None
        
        self.md5sum_fle = 'md5sum.txt'

        # Paths
        distroPath = distroPath.rstrip('/')
        if basename(distroPath) == "root":
            distroPath = dirname(distroPath)
        self.distroPath = distroPath
        self.rootPath = join(distroPath, "root")
        self.bootPath = join(distroPath, "boot")
        self.diskPath = join(self.bootPath, ".disk")
        self.livePath = join(self.bootPath, "live")
        self.shareDir = '/usr/share/iso-constructor'
        
        # Create dir if it does not exist
        if not exists(self.diskPath):
            makedirs(self.diskPath)
        if not exists(self.livePath):
            makedirs(self.livePath)
        if not exists(self.bootPath):
            makedirs(self.bootPath)
            
        # Get live desktop environment
        self.desktop_env = ''
        files = [file for file in glob.glob(join(self.rootPath, 'usr/bin/*-session'))] + \
                [file for file in glob.glob(join(self.rootPath, 'usr/bin/kdeinit*'))]
        for file in files:
            if 'xfce' in file:
                self.desktop_env = 'xfce'
                break
            elif 'kde' in file:
                self.desktop_env = 'kde'
                break
            elif 'gnome' in file:
                self.desktop_env = 'gnome'
                break
            elif 'mate' in file:
                self.desktop_env = 'mate'
                break

        # Create disk info files
        with open(join(self.diskPath, 'base_components'), 'w') as f:
            f.write('main')
        system("touch \"%s\"" % join(self.diskPath, 'base_installable'))
        system("touch \"%s\"" % join(self.diskPath, 'udeb_include'))
        with open(join(self.diskPath, 'cd_type'), 'w') as f:
            f.write('live')
        
        # We are not using a udeb repository. So, disable for now
        #udeb_include = "netcfg\n" \
        #               "ethdetect\n" \
        #               "pcmciautils-udeb\n" \
        #               "live-installer\n"
        #with open(join(self.diskPath, 'udeb_include'), 'w') as f:
        #    f.write(udeb_include)

        # ISO Name
        self.isoName = self.dg.description

        # ISO distribution
        self.isoBaseName = self.dg.getIsoFileName()
        self.isoFileName = join(self.distroPath, self.isoBaseName)
   
    def run(self):
        try:
            if not exists(self.rootPath):
                self.returnMessage = "ERROR: Cannot find root directory: %s" % self.rootPath

            if not exists(self.bootPath):
                self.returnMessage = "ERROR: Cannot find boot directory: %s" % self.bootPath
                
            isohdpfx = self.ec.run("dpkg -S isohdpfx.bin | awk '{print $2}'", returnAsList=False).strip()
            if not isohdpfx:
                self.returnMessage = "ERROR: Cannot find path to isohdpfx.bin - install isolinux"
                
            if self.returnMessage is None:
                print("======================================================")
                print("INFO: Cleanup and prepare ISO build...")
                print("======================================================")

                # Clean-up
                script = "cleanup.sh"
                scriptSource = join(self.shareDir, script)
                scriptTarget = join(self.rootPath, script)
                if exists(scriptSource):
                    copy(scriptSource, scriptTarget)
                    self.ec.run("chmod a+x '%s'" % scriptTarget)
                    self.ed.openTerminal("/bin/bash '%s'" % script)
                    silent_remove(scriptTarget)
                    
            # Move some directories and create symlinks if needed
            usr_dirs = ['bin', 'lib', 'lib32', 'lib64', 'libx32', 'sbin']
            for ud in usr_dirs:
                src_path = join(self.rootPath, ud)
                dst_path = join(self.rootPath, 'usr/{}'.format(ud))
                if isdir(src_path) and not islink(src_path):
                    # Copy the source dir into the destination dir even when destination dir exists
                    # shutil.copytree does not do that. So, an alternative copytree was needed
                    copytree(src_path, dst_path)
                    if exists(dst_path):
                        rmtree(src_path)
                if not exists(src_path):
                    if not exists(dst_path):
                        makedirs(dst_path)
                    symlink(src='usr/{}'.format(ud), dst=ud, dir_fd=os.open(self.rootPath, os.O_DIRECTORY))
                    
            # Copy system boot files (initrd, vmlinuz, etc) to live directory 
            if self.returnMessage is None:
                for fn in listdir(self.livePath):
                    f = join(self.livePath, fn)
                    if not isdir(f):
                        remove(f)
                root_boot = join(self.distroPath, 'root/boot/')
                for fn in listdir(root_boot):
                    f = join(root_boot, fn)
                    if not isdir(f):
                        copy(f, self.livePath)
            
            if self.returnMessage is None:
                # Offline files
                offlineSource = join(join(self.rootPath, "offline"))
                offlineTarget = join(join(self.rootPath, "../boot/offline"))
                if exists(offlineSource):
                    print(("%s exists" % offlineSource))
                    if exists(offlineTarget):
                        print((">> Remove %s" % offlineTarget))
                        silent_remove(offlineTarget)
                    print((">> Move %s to %s" % (offlineSource, offlineTarget)))
                    move(offlineSource, offlineTarget)
                    
                # Cleanup history
                rootHome = join(self.rootPath, "root")
                silent_remove(join(rootHome, ".nano_history"))
                silent_remove(join(rootHome, ".bash_history"))
                silent_remove(join(rootHome, ".wget-hsts"))
                silent_remove(join(rootHome, ".aptitude"))
                silent_remove(join(rootHome, ".nano"))
                silent_remove(join(rootHome, ".cache"))
                
                # Generate grub.cfg
                scriptSource = join(self.shareDir, "grubgen.sh")
                scriptTarget = join(self.bootPath, "grubgen.sh")
                if exists(scriptSource):
                    copy(scriptSource, scriptTarget)
                    self.ec.run("chmod a+x '%s'" % scriptTarget)
                    self.ec.run("/bin/bash -c 'grubgen.sh'", workingDir=self.bootPath)
                    silent_remove(scriptTarget)
                
                # Copy additional isolinux files
                isolinux_files = glob.glob(join(self.shareDir, "isolinux/*"))
                for file in isolinux_files:
                    copy(file, join(self.bootPath, "isolinux/"))
                
                # Generate isolinux.cfg
                scriptSource = join(self.shareDir, "isolinuxgen.sh")
                scriptTarget = join(self.bootPath, "isolinuxgen.sh")
                if exists(scriptSource):
                    copy(scriptSource, scriptTarget)
                    self.ec.run("chmod a+x '%s'" % scriptTarget)
                    self.ec.run("/bin/bash -c 'isolinuxgen.sh'", workingDir=self.bootPath)
                    silent_remove(scriptTarget)
                    

            if self.returnMessage is None:
                print("======================================================")
                print("INFO: Start building ISO...")
                print("======================================================")

                # build squash root
                print("Creating SquashFS root...")
                #print("Updating File lists...")
                #dpkgQuery = ' dpkg -l | awk \'/^ii/ {print $2, $3}\' | sed -e \'s/ /\t/g\' '
                #self.ec.run('chroot \"' + self.rootPath + '\"' + dpkgQuery + ' > \"' + join(self.livePath, "filesystem.packages") + '\"' )

                # check for existing squashfs root
                print("Removing existing SquashFS root...")
                silent_remove(join(self.livePath, "filesystem.squashfs"))
                print("Building SquashFS root...")
                # check for custom mksquashfs (for multi-threading, new features, etc.)
                mksquashfs = self.ec.run(command="echo $MKSQUASHFS", returnAsList=False).strip()
                rootPath = join(self.distroPath, "root/")
                squashfsPath = join(self.livePath, "filesystem.squashfs")
                if mksquashfs == '' or mksquashfs == 'mksquashfs':
                    cpus = 1
                    try:
                        with open('/proc/cpuinfo') as f:
                            match = re.search(r'^cpu cores.*([0-9])', f.read(), re.MULTILINE)
                            if match:
                                cpus = int(int(match.group(1)) / 2)
                                if cpus < 1: cpus = 1
                    except:
                        cpus = 1
                    # Get excluded dirs/files
                    excludes_lst = join(self.shareDir, "excludes")
                    squash_excl_str = '-wildcards -ef "{0}"'.format(excludes_lst) if exists(excludes_lst) else ''
                    cmd = "mksquashfs \"{0}\" \"{1}\" -comp xz -processors {2} {3}".format(rootPath, squashfsPath, cpus, squash_excl_str)
                    self.ec.run(cmd)
                else:
                    cmd = "{0} \"{1}\" \"{2}\"".format(mksquashfs, rootPath, squashfsPath)
                    self.ec.run(cmd)

                # Update isolinux files
                syslinuxPath = join(self.rootPath, "usr/lib/syslinux")
                modulesPath = join(syslinuxPath, "modules/bios")
                isolinuxPath = join(self.bootPath, "isolinux")
                self.ec.run("chmod -R +w '%s'" % isolinuxPath)
                copy(join(syslinuxPath, 'memdisk'), isolinuxPath)
                copy(join(modulesPath, "chain.c32"), isolinuxPath)
                copy(join(modulesPath, "hdt.c32"), isolinuxPath)
                copy(join(modulesPath, "libmenu.c32"), isolinuxPath)
                copy(join(modulesPath, "libgpl.c32"), isolinuxPath)
                copy(join(modulesPath, "reboot.c32"), isolinuxPath)
                copy(join(modulesPath, "vesamenu.c32"), isolinuxPath)
                copy(join(modulesPath, "poweroff.c32"), isolinuxPath)
                copy(join(modulesPath, "ldlinux.c32"), isolinuxPath)
                copy(join(modulesPath, "libcom32.c32"), isolinuxPath)
                copy(join(modulesPath, "libutil.c32"), isolinuxPath)
                copy("/usr/lib/ISOLINUX/isolinux.bin", isolinuxPath)
                
                # copy efi mods
                src = '/usr/lib/grub/x86_64-efi'
                dst = join(self.bootPath, "boot/grub/x86_64-efi")
                if exists(src):
                    if exists(dst):
                        rmtree(dst)
                    copytree(src, dst)

                # Build EFI image
                err = self.build_efi_images(self.distroPath)
                if err:
                    self.returnMessage = "ERROR: BuildIso: {}".format(err)

                # remove existing iso
                silent_remove(self.isoFileName)

                # Create an md5sum file for the isolinux/grub integrity check
                skip_fls = [self.md5sum_fle, 'isolinux.bin', 'boot.cat']
                md5sum_lst = []
                files = [file for file in glob.glob(self.bootPath + '/**', recursive=True)] + \
                        [file for file in glob.glob(self.bootPath +'/.**', recursive=True)]
                for file in files:
                    if not isdir(file) and not basename(file) in skip_fls:
                        md5 = self.ec.run("md5sum %s" % file, False, False)
                        if md5:
                            md5sum_lst.append(md5.replace(self.bootPath, '.'))
                if md5sum_lst:
                    md5_cont = "## This file contains the list of md5 checksums of all files on this medium.\n" \
                               "## You can verify them automatically with the 'verify-checksums' boot parameter\n" \
                               "## or manually with: 'md5sum -c {}'.\n".format(self.md5sum_fle)
                    md5_cont += '\n'.join(md5sum_lst) + '\n'
                    with open(join(self.bootPath, self.md5sum_fle), 'w') as f:
                        f.write(md5_cont)

                # build iso according to architecture
                print("Building ISO...")
                d = datetime.now()
                d = datetime(d.year, d.month, d.day, d.hour, d.minute)
                
                cmd = "xorriso " \
                      "-outdev {isoBaseName} " \
                      "-volid {volid} " \
                      "-padding 0 " \
                      "-compliance no_emul_toc " \
                      "-map ./boot / " \
                      "-chmod 0755 / -- " \
                      "-boot_image isolinux dir=/isolinux  " \
                      "-boot_image isolinux system_area={isohdpfx} " \
                      "-boot_image any next " \
                      "-boot_image any efi_path=boot/grub/efi.img " \
                      "-boot_image isolinux partition_entry=gpt_basdat".format(isoBaseName=self.isoBaseName,
                                                                                volid=self.get_volid(self.isoName), 
                                                                                isohdpfx=isohdpfx)

                # Save the xorriso command to mkisofs file
                with open(join(self.diskPath, 'mkisofs'), 'w') as f:
                    f.write(cmd)
                # Save info file
                with open(join(self.diskPath, 'info'), 'w') as f:
                    f.write("%s Live %s %s %s" % (self.isoName, d.strftime("%Y%m"), self.desktop_env, d.isoformat()))

                # Run the command
                self.ec.run(cmd, workingDir=self.distroPath)

                print("Create sha256 file...")
                oldmd5 = "%s.md5" % self.isoFileName
                silent_remove(oldmd5)
                self.ec.run("echo \"$(sha256sum \"%s\" | cut -d' ' -f 1)  %s\" > \"%s.sha256\"" % (self.isoFileName, self.isoBaseName, self.isoFileName))

                print("======================================================")
                if self.returnMessage is None:
                    self.returnMessage = "DONE - ISO Located at: %s" % self.isoFileName
                print((self.returnMessage))
                print("======================================================")

            self.queue.put(self.returnMessage)

        except Exception as detail:
            self.returnMessage = "ERROR: BuildIso: %(detail)s" % {"detail": detail}
            self.queue.put(self.returnMessage)

    def get_volid(self, name):
        name = name.upper().replace(" ", "_")
        volid = ""
        for c in name:
            matchObj = re.search(r"[A-Z0-9_]", c)
            if matchObj:
                volid += c
        return volid

    def build_efi_images(self, distro_path):
        hostEfiArchitecture = getHostEfiArchitecture()
        if hostEfiArchitecture == "":
            return None

        modules = "part_gpt part_msdos ntfs ntfscomp hfsplus fat ext2 chain boot configfile linux " \
                "multiboot iso9660 gfxmenu gfxterm loadenv efi_gop efi_uga loadbios fixvideo png " \
                "loopback search minicmd cat cpuid appleldr elf usb videotest " \
                "halt help ls reboot echo test normal sleep memdisk tar font video_fb video " \
                "gettext true video_bochs video_cirrus multiboot2 acpi gfxterm_background gfxterm_menu"

        rootPath = join(distro_path, "root")
        bootPath = join(distro_path, "boot")
        efiPath = join(bootPath, "EFI/boot")
        arch = getGuestEfiArchitecture(rootPath)

        grubEfiName = "bootx64"
        if arch != "x86_64":
            arch = "i386"
            grubEfiName = "bootia32"

        try:
            # Clean up old stuff and prepare for a new EFI image
            if not exists(efiPath):
                makedirs(efiPath)
            silent_remove(join(bootPath, "MD5SUMS"))
            silent_remove(join(bootPath, "boot/grub/i386-efi"))
            if exists(join(self.bootPath, "boot/grub/themes/")):
                silent_remove(join(bootPath, "boot/grub/font.pf2"))

            # Create embedded.cfg
            # Check contents with: strings bootx64.efi | grep "set=root"
            cont = "search --file --set=root /{}\n" \
                   "if [ -e ($root)/boot/grub/grub.cfg ]; then\n" \
                   "  set prefix=($root)/boot/grub\n" \
                   "  configfile $prefix/grub.cfg\n" \
                   "else\n" \
                   "  echo 'Could not find /boot/grub/grub.cfg!'\n" \
                   "fi\n".format(self.md5sum_fle)
            print(("\nembedded.cfg content:\n{}".format(cont)))
            with open('embedded.cfg', 'w') as f:
                f.write(cont)

            # Create the .efi image with the embedded.cfg file
            # --prefix is needed but can be left empty: it is set in embedded.cfg
            efifile = "{efiPath}/{grubEfiName}.efi".format(efiPath=efiPath, grubEfiName=grubEfiName)
            self.ec.run("grub-mkimage "
                        "--prefix '' "
                        "--config 'embedded.cfg' "
                        "-O {}-efi "
                        "-o '{}' "
                        "{}".format(arch, efifile, modules))
                        
            # Cleanup embedded.cfg
            silent_remove('embedded.cfg')

            if exists(efifile):
                # Create efi.img
                # Check contents with: mkdir /tmp/efi.img; mount -o loop efi.img /tmp/efi.img
                efibootPath = join(self.bootPath, "boot/grub/efi.img")
                label = self.dg.edition.upper().replace('-', '').replace('_', '')
                print(("Create %s" % efibootPath))
                cmd = "rm {efibootPath}; " \
                      "mkdosfs -F 12 -n \"{label}\" -C '{efibootPath}' 2048; " \
                      "mcopy -si {efibootPath} {efidir} ::".format(efibootPath=efibootPath, label=label, efidir=join(bootPath, "EFI"))
                self.ec.run(cmd)

            return None

        except Exception as detail:
            return detail


# Class to create a chrooted terminal for a given directory
# https://wiki.debian.org/chroot
class EditDistro(object):
    def __init__(self, distroPath):
        self.ec = ExecCmd()
        self.dg = DistroGeneral(distroPath)
        distroPath = distroPath.rstrip('/')
        if basename(distroPath) == "root":
            distroPath = dirname(distroPath)
        self.rootPath = join(distroPath, "root")

        # ISO description
        self.description = self.dg.description

    def openTerminal(self, command=""):
        # Set some paths
        resolveCnfHost = "/etc/resolv.conf"
        resolveCnf = join(self.rootPath, "etc/resolv.conf")
        resolveCnfBak = "%s.bk" % resolveCnf
        wgetrc = join(self.rootPath, "etc/wgetrc")
        wgetrcBak = "%s.bk" % wgetrc
        terminal = "/tmp/constructor-terminal.sh"
        lockDir = join(self.rootPath, "run/lock/")
        proc = join(self.rootPath, "proc/")
        dev = join(self.rootPath, "dev/")
        pts = join(self.rootPath, "dev/pts/")
        sys = join(self.rootPath, "sys/")
        run = join(self.rootPath, "run/")
        policy = join(self.rootPath, "usr/sbin/policy-rc.d")
        ischroot = join(self.rootPath, "usr/bin/ischroot")
        ischrootTmp = join(self.rootPath, "usr/bin/ischroot.tmp")

        try:
            # temporary create /run/lock
            if not exists(lockDir):
                makedirs(lockDir)

            # setup environment
            # copy dns info
            if exists(resolveCnf):
                move(resolveCnf, resolveCnfBak)
            if exists(resolveCnfHost):
                copy(resolveCnfHost, resolveCnf)

            # umount /proc /dev /dev/pts /sys
            self.unmount([run, sys, proc, pts, dev])
            
            # Make nodes
            self.ec.run('mkdir -p {rootfs}/dev {rootfs}/proc {rootfs}/sys {rootfs}/run'.format(rootfs=self.rootPath))
            self.ec.run('mknod -m 600 {rootfs}/dev/console c 5 1'.format(rootfs=self.rootPath))
            self.ec.run('mknod -m 666 {rootfs}/dev/null c 1 3'.format(rootfs=self.rootPath))

            # mount /proc /dev /dev/pts /sys /run /sys
            cmd = 'mount -v --bind /dev {dev};' \
                  'mount -vt devpts devpts {pts} -o gid=5,mode=620;' \
                  'mount -vt proc proc {proc};' \
                  'mount -vt sysfs sysfs {sys};' \
                  'mount -vt tmpfs tmpfs {run}'.format(**locals())
            self.ec.run(cmd)
            self.ec.run('if [ -h {rootfs}/dev/shm ]; then mkdir -pv {rootfs}/$(readlink {rootfs}/dev/shm); fi'.format(rootfs=self.rootPath))
            self.ec.run('if [ -h {rootfs}/var/lock ]; then mkdir -pv {rootfs}/$(readlink {rootfs}/var/lock); fi'.format(rootfs=self.rootPath))

            # copy wgetrc
            move(wgetrc, wgetrcBak)
            copy("/etc/wgetrc", wgetrc)

            # Let dpkg only start daemons when desired
            scr = "#!/bin/sh\nexit 101\n"
            with open(policy, 'w') as f:
                f.write(scr)
            self.ec.run("chmod a+x '%s'" % policy)

            # Temporary fix ischroot
            if not exists(ischrootTmp):
                self.ec.run("mv '%s' '%s'" % (ischroot, ischrootTmp))
            if not exists(ischroot):
                self.ec.run("ln -s /bin/true '%s'" % ischroot)

            # HACK: create temporary script for chrooting
            silent_remove(terminal)
            cmd_str = '-c "{cmd}"'.format(cmd=command) if command else ''
            scr = '#!/bin/sh\nchroot "{rootfs}"' \
                  ' /usr/bin/env -i ' \
                  ' HOME=/root' \
                  ' TERM="$TERM"' \
                  ' PS1="(chroot) \\u:\w\$ "' \
                  ' PATH=/bin:/usr/bin:/sbin:/usr/sbin' \
                  ' /bin/bash --login +h' \
                  ' {cmd_str}'.format(rootfs=self.rootPath, cmd_str=cmd_str)
            with open(terminal, 'w') as f:
                f.write(scr)
            self.ec.run("chmod a+x '%s'" % terminal)
            if self.ec.run('which x-terminal-emulator'):
                # Default: x-terminal-emulator
                self.ec.run('x-terminal-emulator --title "{title}" -e {script}'.format(title=self.description, script=terminal))
            elif self.ec.run("which xterm"):
                # Fallback: xterm
                self.ec.run('xterm -xrm \'XTerm.vt100.allowTitleOps: false\' -rightbar -title "{title}" -e {script}'.format(title=self.description, script=terminal))
            else:
                print(('Error: no valid terminal found'))
                print(('Please install xterm'))

            # restore wgetrc
            move(wgetrcBak, wgetrc)

            # move dns info
            if exists(resolveCnfBak):
                move(resolveCnfBak, resolveCnf)
            else:
                silent_remove(resolveCnf)

            # umount /proc /dev /dev/pts /sys
            self.unmount([run, sys, proc, pts, dev])

            # remove temp script
            silent_remove(terminal)

            # remove policy script
            silent_remove(policy)

            # replace ischroot
            if exists("%s.tmp" % ischroot):
                self.ec.run("rm '%s'" % ischroot)
                self.ec.run("mv '%s.tmp' '%s'" % (ischroot, ischroot))

            # cleanup /run
            self.ec.run("rm -rf '%s/run/'*" % self.rootPath)

        except Exception as detail:
            # restore wgetrc
            move(wgetrcBak, wgetrc)

            # move dns info
            if exists(resolveCnfBak):
                move(resolveCnfBak, resolveCnf)
            else:
                silent_remove(resolveCnf)

            # umount /proc /dev /dev/pts /sys
            self.unmount([pts, dev, proc, sys])

            # remove temp script
            silent_remove(terminal)

            # remove policy script
            silent_remove(policy)

            # replace ischroot
            if exists("%s.tmp" % ischroot):
                self.ec.run("rm '%s'" % ischroot)
                self.ec.run("mv '%s.tmp' '%s'" % (ischroot, ischroot))

            # cleanup /run
            self.ec.run("rm -rf '%s/run/'*" % self.rootPath)

            errText = 'Error launching terminal: '
            print((errText, detail))

    def unmount(self, mounts=[]):
        for mount in mounts:
            self.ec.run("umount --force '%s'" % mount)
            self.ec.run("umount -l '%s'" % mount)


class DistroGeneral(object):
    def __init__(self, distroPath):
        self.ec = ExecCmd()
        distroPath = distroPath.rstrip('/')
        if basename(distroPath) == "root":
            distroPath = dirname(distroPath)
        self.distroPath = distroPath
        self.rootPath = join(distroPath, "root")
        lsb_release_path = join(self.rootPath, "etc/lsb-release")
        lsb_info = get_lsb_release_info(lsb_release_path)
        self.edition = lsb_info['codename']
        self.description = lsb_info['name']
        if len(self.edition) == 0: self.edition = basename(distroPath)
        if len(self.description) == 0: self.description = basename(distroPath)

    def getIsoFileName(self):
        # Get the date string
        d = datetime.now()
        serial = d.strftime("%Y%m")
        # Check for a localized system
        localePath = join(self.rootPath, "etc/default/locale")
        if exists(localePath):
            locale = self.ec.run(command="grep LANG= '%s'" % localePath, returnAsList=False).strip('"').replace(" ", "")
            matchObj = re.search(r"\=\s*([a-z]{2})", locale)
            if matchObj:
                language = matchObj.group(1)
                if language != "en":
                    serial += "_{}".format(language)
        isoFileName = "{}_{}.iso".format(self.description.lower().replace(' ', '_').split('-')[0], serial)
        return isoFileName
