#!/usr/bin/env python3

# Password settings
# http://docs.python.org/2/library/spwd.html#module-spwd
# User settings
# http://docs.python.org/2/library/pwd.html

# Make sure the right Gtk version is loaded
import gi
gi.require_version('Gtk', '3.0')

# sudo apt-get install python3-gi
# from gi.repository import Gtk, GdkPixbuf, GObject, Pango, Gdk
from gi.repository import Gtk, GLib
from os import makedirs, system, listdir, environ, rename
from shutil import copy
import threading
import operator
from queue import Queue
# abspath, dirname, join, expanduser, exists, basename
from os.path import join, abspath, dirname, exists, isdir

# Local imports
from .execcmd import ExecCmd
from .iso import IsoUnpack, EditDistro, BuildIso, DistroGeneral
from .treeview import TreeViewHandler
from .dialogs import MessageDialog, ErrorDialog, SelectFileDialog, \
                    SelectDirectoryDialog, QuestionDialog
from .functions import pushMessage, get_user_home_dir, getUserLoginName, \
                      getPackageVersion, repaintGui, silent_remove

# i18n: http://docs.python.org/3/library/gettext.html
import gettext
from gettext import gettext as _
gettext.textdomain('iso-constructor')


#class for the main window
class Constructor(object):

    def __init__(self):
        self.shareDir = '/usr/share/iso-constructor'
        self.userAppDir = join(get_user_home_dir(), ".iso-constructor")
        self.distroFile = join(self.userAppDir, "distributions.list")

        # Create the user's application directory if it doesn't exist
        if not isdir(self.userAppDir):
            old_dir = join(get_user_home_dir(), ".constructor")
            if exists(old_dir):
                rename(old_dir, self.userAppDir)
                if exists(join(self.userAppDir, 'distros.list')):
                    rename(join(self.userAppDir, 'distros.list'), self.distroFile)
            else:
                user_name = getUserLoginName()
                makedirs(self.userAppDir)
                system("chown -R %s:%s %s" % (user_name, user_name, self.userAppDir))

        # Load window and widgets
        self.builder = Gtk.Builder()
        self.builder.add_from_file(join(self.shareDir, 'iso-constructor.glade'))

        # Main window objects
        go = self.builder.get_object
        self.window = go('constructorWindow')
        self.tvDistros = go('tvDistros')
        self.lblOutput = go('lblOutput')
        self.statusbar = go('statusbar')
        self.btnAdd = go('btnAdd')
        self.chkSelectAll = go('chkSelectAll')
        self.btnRemove = go('btnRemove')
        self.btnEdit = go('btnEdit')
        self.btnUpgrade = go('btnUpgrade')
        self.btnLocalize = go('btnLocalize')
        self.btnBuildIso = go('btnBuildIso')

        # Add iso window objects
        self.windowAddDistro = go('addDistroWindow')
        self.txtIso = go('txtIso')
        self.txtDir = go('txtDir')
        self.btnDir = go('btnDir')
        self.btnSave = go('btnSave')
        self.btnHelp = go('btnHelp')
        self.lblIso = go('lblIso')
        self.boxIso = go('boxIso')
        self.lblDir = go('lblDir')
        self.chkFromIso = go('chkFromIso')

        # Main window translations
        self.window.set_title(_("ISO Constructor"))
        self.chkSelectAll.set_label(_("Select all"))
        self.btnAdd.set_label("_{}".format(_("Add")))
        self.btnRemove.set_label("_{}".format(_("Remove")))
        self.btnEdit.set_label("_{}".format(_("Edit")))
        self.btnUpgrade.set_label("_{}".format(_("Upgrade")))
        self.btnLocalize.set_label("_{}".format(_("Localize")))
        self.btnBuildIso.set_label("_{}".format(_("Build")))
        self.btnHelp.set_label("_{}".format(_("Help")))

        # Add iso window translations
        self.windowAddDistro.set_title(_("Add Distribution"))
        self.lblIso.set_text(_("ISO"))
        go('lblFromIso').set_label("Create from ISO")
        go('btnCancel').set_label("_{}".format(_("Cancel")))
  
        # Init
        self.ec = ExecCmd()
        self.ec.run("modprobe loop", False)
        self.queue = Queue()
        self.mountDir = "/mnt/constructor"
        self.distroAdded = False
        self.iso = None
        self.dir = None
        self.isoName = None
        self.doneWav = join(self.shareDir, 'done.wav')
        self.htmlDir = join(self.shareDir, "html")
        self.help = join(self.get_language_dir(), "help.html")
        self.chkFromIso.set_active(True)
        self.toggleGuiElements(False)

        # Treeviews
        self.tvHandlerDistros = TreeViewHandler(self.tvDistros)
        self.fillTreeViewDistros()

        # Version information
        ver = _("Version")
        self.version = "%s: %s" % (ver, getPackageVersion('iso-constructor'))
        self.showOutput(self.version)

        # Connect the signals and show the window
        self.builder.connect_signals(self)
        self.window.show()

    # ===============================================
    # Main Window Functions
    # ===============================================

    def on_btnAdd_clicked(self, widget):
        self.windowAddDistro.show()

    def on_btnRemove_clicked(self, widget):
        selected = self.tvHandlerDistros.getToggledValues(toggleColNr=0, valueColNr=2)
        for path in selected:
            answer = QuestionDialog(self.btnRemove.get_label().replace('_', ''), 
                                  _("Are you sure you want to remove the selected distribution from the list?\n" \
                                  "(This will not remove the directory and its data)"))
            if answer:
                self.saveDistroFile(distroPath=path, addDistro=False)
        self.fillTreeViewDistros()

    def on_btnEdit_clicked(self, widget):
        selected = self.tvHandlerDistros.getToggledValues(toggleColNr=0, valueColNr=2)
        for path in selected:
            services = []
            if exists(join(path, 'root/etc/apache2/apache2.conf')):
                services.append("apache2")
            if exists(join(path, 'root/etc/mysql/debian.cnf')):
                services.append("mysql")
            if services:
                msg = "If you need to update packages that depend on these services,\n" \
                      "you will need to manually start them:\n"
                for service in services:
                    msg += "\nservice %s start" % service
                msg += "\n\nWhen done:\n"
                for service in services:
                    msg += "\nservice %s stop" % service
                self.showInfo(_("Services detected"), msg, self.window)
                repaintGui()
            ed = EditDistro(path)
            ed.openTerminal()

    def on_btnUpgrade_clicked(self, widget):
        selected = self.tvHandlerDistros.getToggledValues(toggleColNr=0, valueColNr=2)
        upgraded = False
        for path in selected:
            rootPath = "%s/root" % path
            script = "upgrade.sh"
            scriptSource = join(self.shareDir, script)
            scriptTarget = join(rootPath, script)
            if exists(scriptSource):
                copy(scriptSource, scriptTarget)
                self.ec.run("chmod a+x '%s'" % scriptTarget)
                ed = EditDistro(path)
                ed.openTerminal("/bin/bash '%s'" % script)
                silent_remove(scriptTarget)
                upgraded = True

        if upgraded:
            self.showInfo("", _("Upgrade done"), self.window)

    def on_btnLocalize_clicked(self, widget):
        # Set locale
        selected = self.tvHandlerDistros.getToggledValues(toggleColNr=0, valueColNr=2)
        for path in selected:
            rootPath = "%s/root" % path
            script = "setlocale.sh"
            scriptSource = join(self.shareDir, script)
            scriptTarget = join(rootPath, script)
            if exists(scriptSource):
                copy(scriptSource, scriptTarget)
                self.ec.run("chmod a+x '%s'" % scriptTarget)
                ed = EditDistro(path)
                ed.openTerminal("/bin/bash %s" % script)
                silent_remove(scriptTarget)
            
            # Copy Grub locale files to ISO boot directory and configure grub.cfg
            grub_path = "%s/boot/boot/grub/" % path
            grubcfg_path = "%s/grub.cfg" % grub_path
            locale_path = "%s/root/boot/grub/locale" % path
            default_path = "%s/root/etc/default" % path
            locale = self.ec.run(r"grep -oP '(?<=LANG=).*?(?=\.)' %s/locale" % default_path)[0]
            if exists(locale_path) and \
               exists(grubcfg_path) and \
               locale:
                self.ec.run("cp -rf %s %s" % (locale_path, grub_path))
                self.ec.run("sed -i 's/set lang=.*/set lang=%s/' %s" % (locale, grubcfg_path))

    def on_btnBuildIso_clicked(self, widget):
        selected = self.tvHandlerDistros.getToggledValues(toggleColNr=0, valueColNr=2)
        if selected:
            # Loop through selected distributions
            msg = ""
            for path in selected:
                self.toggleGuiElements(True)
                self.showOutput("Start building ISO in: %s" % path)
                repaintGui()

                # Start building the ISO in a thread
                t = BuildIso(path, self.queue)
                t.start()
                self.queue.join()

                # Thread is done
                # Get the data from the queue
                ret = self.queue.get()
                self.queue.task_done()

                if ret is not None:
                    self.showOutput(ret)
                    if "error" in ret.lower():
                        self.showError("Error", ret, self.window)
                    else:
                        msg += "%s\n" % ret

        if msg != "":
            self.showInfo("", msg, self.window)
        self.toggleGuiElements(False)

    def on_chkSelectAll_toggled(self, widget):
        self.tvHandlerDistros.treeviewToggleAll(toggleColNrList=[0], toggleValue=widget.get_active())

    def on_tvDistros_row_activated(self, widget, path, column):
        self.tvHandlerDistros.treeviewToggleRows(toggleColNrList=[0])

    def on_btnHelp_clicked(self, widget):
        system("open-as-user %s" % self.help)

    def on_btnOpenDir_clicked(self, widget):
        selected = self.tvHandlerDistros.getToggledValues(toggleColNr=0, valueColNr=2)
        for path in selected:
            system("open-as-user %s" % path)

    def fillTreeViewDistros(self, selectDistros=[]):
        contentList = [[_("Select"), _("Distribution"), _("Working directory")]]
        distros = self.getDistros()
        for distro in distros:
            select = False
            for selectDistro in selectDistros:
                if distro[0] == selectDistro:
                    select = True
            contentList.append([select, distro[0], distro[1]])
        self.tvHandlerDistros.fillTreeview(contentList=contentList, columnTypesList=['bool', 'str', 'str'], firstItemIsColName=True)

    def getDistros(self):
        distros = []
        if exists(self.distroFile):
            with open(self.distroFile, 'r') as f:
                lines = f.readlines()
            for line in lines:
                line = line.strip().rstrip('/')
                print(line)
                if exists(line):
                    dg = DistroGeneral(line)
                    isoName = dg.description
                    distros.append([isoName, line])
            # Sort on iso name
            if distros:
                distros = sorted(distros, key=operator.itemgetter(0))
        return distros

    # ===============================================
    # Add ISO Window Functions
    # ===============================================

    def on_btnIso_clicked(self, widget):
        fleFilter = Gtk.FileFilter()
        fleFilter.set_name("ISO")
        fleFilter.add_mime_type("application/x-cd-image")
        fleFilter.add_pattern("*.iso")

        startDir = None
        if exists(dirname(self.txtIso.get_text())):
            startDir = dirname(self.txtIso.get_text())

        filePath = SelectFileDialog(title=_('Select ISO file'), start_directory=startDir, parent=self.window, gtkFileFilter=fleFilter).show()
        if filePath is not None:
            self.txtIso.set_text(filePath)

    def on_btnDir_clicked(self, widget):
        startDir = None
        if exists(self.txtDir.get_text()):
            startDir = self.txtDir.get_text()
        dirText = SelectDirectoryDialog(title=_('Select directory'), start_directory=startDir, parent=self.window).show()
        if dirText is not None:
            self.txtDir.set_text(dirText)

    def on_btnSave_clicked(self, widget):
        self.iso = ""
        if self.chkFromIso.get_active():
            self.iso = self.txtIso.get_text()
        self.dir = self.txtDir.get_text()

        title = _("Save existing working directory")
        if self.iso != "":
            title = _("Unpack ISO and save")

        if not exists(self.dir):
            makedirs(self.dir)

        if not exists(self.dir):
            self.showError(title, _("Could not create directory %(dir)s: exiting" % {"dir": self.dir}), self.window)
        else:
            self.windowAddDistro.hide()
            if self.iso != "":
                if not exists(self.iso):
                    self.showInfo(self.btnSave.get_label(), _("The path to the ISO file does not exist:\n{}".format(self.iso)), self.window)
                    return
                if listdir(self.dir):
                    answer = QuestionDialog(self.btnSave.get_label(),
                                          _("The destination directory is not empty.\n"
                                          "Are you sure you want to overwrite all data in {}?".format(self.dir)))
                    if not answer:
                        return

                self.showOutput("Start unpacking the ISO...")
                self.toggleGuiElements(True)
                t = IsoUnpack(self.mountDir, self.iso, self.dir, self.queue)
                t.start()
                self.queue.join()
                GLib.timeout_add(1000, self.checkThread, True)
            else:
                self.saveDistroFile(self.dir, True)
                self.fillTreeViewDistros()
                self.showOutput(_("Existing working directory added"))
                #self.toggleGuiElements(False)

    def on_btnCancel_clicked(self, widget):
        self.windowAddDistro.hide()

    def on_addDistroWindow_delete_event(self, widget, data=None):
        self.windowAddDistro.hide()
        return True

    def on_txtIso_changed(self, widget):
        path = self.txtIso.get_text()
        if exists(path):
            self.txtDir.set_sensitive(True)
            self.btnDir.set_sensitive(True)
            if exists(self.txtDir.get_text()):
                self.btnSave.set_sensitive(True)
        else:
            self.txtDir.set_sensitive(False)
            self.btnDir.set_sensitive(False)
            self.btnSave.set_sensitive(False)

    def on_txtDir_changed(self, widget):
        blnFromIso = self.chkFromIso.get_active()
        isoPath = self.txtIso.get_text()
        dirText = self.txtDir.get_text()
        self.btnSave.set_sensitive(False)
        if exists(dirText):
            if blnFromIso:
                if exists(isoPath):
                    self.btnSave.set_sensitive(True)
            else:
                self.btnSave.set_sensitive(True)

    def on_chkFromIso_toggled(self, widget):
        if widget.get_active():
            self.lblIso.set_visible(True)
            self.boxIso.set_visible(True)
            self.txtDir.set_sensitive(False)
            self.btnDir.set_sensitive(False)
            self.btnSave.set_sensitive(False)
            self.lblDir.set_text(_("Unpack ISO to directory"))
            self.btnSave.set_label(_("Unpack & Save"))
        else:
            self.txtIso.set_text("")
            self.lblIso.set_visible(False)
            self.boxIso.set_visible(False)
            self.txtDir.set_sensitive(True)
            self.btnDir.set_sensitive(True)
            self.btnSave.set_sensitive(True)
            self.lblDir.set_text(_("Work directory"))
            self.btnSave.set_label(_("Save"))

    # ===============================================
    # General functions
    # ===============================================

    def showInfo(self, title, message, parent=None):
        MessageDialog(title, message)

    def showError(self, title, message, parent=None):
        ErrorDialog(title, message)

    def showOutput(self, message):
        print(message)
        pushMessage(self.statusbar, message)

    def checkThread(self, addDistro=None):
        #print 'Thread count = ' + str(threading.active_count())
        # As long there's a thread active, keep spinning
        if threading.active_count() > 1:
            return True

        # Thread is done
        # Get the data from the queuez
        ret = self.queue.get()
        self.queue.task_done()

        # Thread is done
        if addDistro is not None:
            self.saveDistroFile(self.dir, addDistro)
            self.fillTreeViewDistros(self.isoName)
        self.toggleGuiElements(False)
        if ret is not None:
            self.showOutput(ret)
            if "error" in ret.lower():
                self.showError("Error", ret, self.window)
            else:
                self.showInfo("", ret, self.window)
        return False

    def toggleGuiElements(self, startThread):
        if startThread:
            self.chkSelectAll.set_sensitive(False)
            self.tvDistros.set_sensitive(False)
            self.btnAdd.set_sensitive(False)
            self.btnBuildIso.set_sensitive(False)
            self.btnEdit.set_sensitive(False)
            self.btnRemove.set_sensitive(False)
            self.btnUpgrade.set_sensitive(False)
            self.btnLocalize.set_sensitive(False)
            self.btnDir.set_sensitive(False)
            self.btnHelp.set_sensitive(False)
        else:
            self.chkSelectAll.set_sensitive(True)
            self.tvDistros.set_sensitive(True)
            self.btnAdd.set_sensitive(True)
            self.btnBuildIso.set_sensitive(True)
            self.btnEdit.set_sensitive(True)
            self.btnRemove.set_sensitive(True)
            self.btnUpgrade.set_sensitive(True)
            self.btnLocalize.set_sensitive(True)
            self.btnDir.set_sensitive(True)
            self.btnHelp.set_sensitive(True)

    def saveDistroFile(self, distroPath, addDistro=True):
        newCont = []
        dg = DistroGeneral(distroPath)
        self.isoName = dg.description

        cfg = []
        if exists(self.distroFile):
            with open(self.distroFile, 'r') as f:
                cfg = f.readlines()
            for line in cfg:
                line = line.strip()
                if distroPath != line and exists(line):
                    newCont.append(line)

        if addDistro:
            newCont.append(distroPath)

        with open(self.distroFile, 'w') as f:
            f.write('\n'.join(newCont))

        self.iso = ""
        self.dir = ""

    # Close the gui
    def on_constructorWindow_destroy(self, widget):
        # Close the app
        Gtk.main_quit()
        
    # ===============================================
    # Language specific functions
    # ===============================================

    def get_language_dir(self):
        # First test if full locale directory exists, e.g. html/pt_BR,
        # otherwise perhaps at least the language is there, e.g. html/pt
        # and if that doesn't work, try html/pt_PT
        lang = self.get_current_language()
        path = join(self.htmlDir, lang)
        if not isdir(path):
            base_lang = lang.split('_')[0].lower()
            path = join(self.htmlDir, base_lang)
            if not isdir(path):
                path = join(self.htmlDir, "{}_{}".format(base_lang, base_lang.upper()))
                if not isdir(path):
                    path = join(self.htmlDir, 'en')
        return path

    def get_current_language(self):
        lang = environ.get('LANG', 'US').split('.')[0]
        if lang == '':
            lang = 'en'
        return lang

def main():
    # Create an instance of our GTK application
    try:
        Constructor()
        Gtk.main()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
