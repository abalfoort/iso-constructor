#!/usr/bin/env python3

# Make sure the right versions are loaded
import gi
gi.require_version('Gtk', '3.0')

# from gi.repository import Gtk, GdkPixbuf, GObject, Pango, Gdk, Vte
from gi.repository import Gtk
from os import makedirs, system, listdir, \
               environ, rename, remove
from shutil import copy
import operator
import time
from os.path import join, dirname, exists, isdir

# Local imports
from .treeview import TreeViewHandler
from .terminal import Terminal
from .dialogs import MessageDialog, ErrorDialog, SelectFileDialog, \
                     SelectDirectoryDialog, QuestionDialog
from .utils import get_user_home, get_logged_user, \
                   get_package_version, get_lsb_release_info

# i18n: http://docs.python.org/3/library/gettext.html
import gettext
from gettext import gettext as _
gettext.textdomain('iso-constructor')


# class for the main window
class Constructor(object):
    def __init__(self):
        self.shareDir = '/usr/share/iso-constructor'
        self.chrootScript = join(self.shareDir, "chroot-dir.sh")
        self.userAppDir = join(get_user_home(), ".iso-constructor")
        self.distroFile = join(self.userAppDir, "distributions.list")
        self.log_file = join(self.userAppDir, 'iso-constructor.log')
        
        # Remove old log file
        if exists(self.log_file):
            remove(self.log_file)

        # Create the user's application directory if it doesn't exist
        if not isdir(self.userAppDir):
            old_dir = join(get_user_home(), ".constructor")
            if exists(old_dir):
                rename(old_dir, self.userAppDir)
                if exists(join(self.userAppDir, 'distros.list')):
                    rename(join(self.userAppDir, 'distros.list'), self.distroFile)
            else:
                user_name = get_logged_user()
                makedirs(self.userAppDir)
                system("chown -R %s:%s %s" % (user_name, user_name, self.userAppDir))

        # Load window and widgets
        self.builder = Gtk.Builder()
        self.builder.add_from_file(join(self.shareDir, 'iso-constructor.glade'))

        # Main window objects
        go = self.builder.get_object
        self.window = go('constructorWindow')
        self.tvDistros = go('tvDistros')
        self.btnAdd = go('btnAdd')
        self.btnLog = go('btnLog')
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
        self.remove_text = _("Remove")
        self.window.set_title("ISO Constructor")
        self.chkSelectAll.set_label(_("Select all"))
        self.btnAdd.set_tooltip_text(_("Add"))
        self.btnLog.set_tooltip_text(_("View log file"))
        self.btnRemove.set_tooltip_text(self.remove_text)
        self.btnEdit.set_tooltip_text(_("Edit"))
        self.btnUpgrade.set_tooltip_text(_("Upgrade"))
        self.btnLocalize.set_tooltip_text(_("Localize"))
        self.btnBuildIso.set_tooltip_text(_("Build"))
        self.btnHelp.set_tooltip_text(_("Help"))

        # Add iso window translations
        self.windowAddDistro.set_title(_("Add Distribution"))
        self.lblIso.set_text(_("ISO"))
        go('lblFromIso').set_label("Create from ISO")
        go('btnCancel').set_label("_{}".format(_("Cancel")))
      
        # Terminal
        self.terminal = Terminal()
        go("swTve").add(self.terminal)
        self.terminal.log_file = self.log_file
        self.terminal.set_input_enabled(False)
  
        # Init    
        self.iso = None
        self.dir = None
        self.htmlDir = join(self.shareDir, "html")
        self.help = join(self.get_language_dir(), "help.html")
        self.chkFromIso.set_active(True)

        # Treeviews
        self.tvHandlerDistros = TreeViewHandler(self.tvDistros)
        self.fill_tv_dists()

        # Version information
        self.log('> ISO Constructor {ver}'.format(ver=get_package_version('iso-constructor')))

        # Connect the signals and show the window
        self.builder.connect_signals(self)
        self.window.show_all()

    # ===============================================
    # Main Window Functions
    # ===============================================

    def on_btnAdd_clicked(self, widget):
        self.windowAddDistro.show()

    def on_btnRemove_clicked(self, widget):
        selected = self.tvHandlerDistros.getToggledValues(toggleColNr=0, valueColNr=2)
        for path in selected:
            answer = QuestionDialog(self.remove_text,
                                  _("Are you sure you want to remove the selected distribution from the list?\n" \
                                  "(This will not remove the directory and its data)"))
            if answer:
                self.save_dist_file(distroPath=path, addDistro=False)
        self.fill_tv_dists()

    def on_btnEdit_clicked(self, widget):
        self.enable_gui_elements(False)
        selected = self.tvHandlerDistros.getToggledValues(toggleColNr=0, valueColNr=2)
        for path in selected:
            
            self.log('> Start editing {path}'.format(path=path))

            # Edit the distribution in a chroot session
            command =  'iso-constructor -e "{path}"'.format(path=path)
            self.terminal.feed(command=command)
            
            # Check for flag file (created by chrootScript) and wait
            flag = '{path}/root/.tmp'.format(path=path)
            with open(flag, 'w') as f:
                f.write('')
            self.check_chroot(flag_fle=flag)
        self.enable_gui_elements(True)
            
    def on_btnUpgrade_clicked(self, widget):
        self.enable_gui_elements(False)
        selected = self.tvHandlerDistros.getToggledValues(toggleColNr=0, valueColNr=2)
        for path in selected:
            self.log('> Start upgrading {path}'.format(path=path))
            
            # Upgrade the distribtution
            command =  'iso-constructor -u "{path}"'.format(path=path)
            self.terminal.feed(command=command, wait_until_done=True)
        self.enable_gui_elements(True)

    def on_btnLocalize_clicked(self, widget):
        self.enable_gui_elements(False)
        selected = self.tvHandlerDistros.getToggledValues(toggleColNr=0, valueColNr=2)
        for path in selected:
            self.log('> Start localizing {path}'.format(path=path))
            
            # Localize the distribution
            command = 'iso-constructor -l "{path}"'.format(path=path)
            self.terminal.feed(command=command)
            
            # Check for flag file (created by chrootScript) and wait
            flag = '{path}/root/.tmp'.format(path=path)
            with open(flag, 'w') as f:
                f.write('')
            self.check_chroot(flag_fle=flag)
        self.enable_gui_elements(True)

    def on_btnBuildIso_clicked(self, widget):
        self.enable_gui_elements(False)
        selected = self.tvHandlerDistros.getToggledValues(toggleColNr=0, valueColNr=2)
        if selected:
            # Loop through selected distributions
            msg = ""
            for path in selected:
                self.log('> Start building ISO in: {path}'.format(path=path))
                
                # Build the ISO
                command = 'iso-constructor -b "{path}"'.format(path=path)
                self.terminal.feed(command=command, wait_until_done=True)
        self.enable_gui_elements(True)

    def on_chkSelectAll_toggled(self, widget):
        self.tvHandlerDistros.treeviewToggleAll(toggleColNrList=[0], toggleValue=widget.get_active())

    def on_tvDistros_row_activated(self, widget, path, column):
        self.tvHandlerDistros.treeviewToggleRows(toggleColNrList=[0])

    def on_btnHelp_clicked(self, widget):
        self.enable_gui_elements(False)
        command = 'man iso-constructor'
        self.terminal.feed(command=command, wait_until_done=True, disable_scrolling=False, pause_logging=True)
        self.enable_gui_elements(True)
        #system("bash {sharedir}/open-as-user {html}".format(sharedir=self.shareDir, html=self.help))
           
    def on_btnLog_clicked(self, widget):
        self.enable_gui_elements(False)
        command = 'sensible-editor {log}'.format(log=self.log_file)
        self.terminal.feed(command=command, wait_until_done=True, disable_scrolling=False, pause_logging=True)
        self.enable_gui_elements(True)
        #system("bash {sharedir}/open-as-user {log}".format(sharedir=self.shareDir, log=self.log_file))
    
    def on_constructorWindow_destroy(self, widget):
        # Close the app
        Gtk.main_quit()

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
            ErrorDialog(title=title,
                        text=_("Could not create directory %(dir)s: exiting" % {"dir": self.dir}),
                        parent=self.window)
        else:
            self.windowAddDistro.hide()
            if self.iso != "":
                if not exists(self.iso):
                    MessageDialog(title=self.btnSave.get_label(),
                                  text=_("The path to the ISO file does not exist:\n{}".format(self.iso)),
                                  parent=self.window)
                    return
                if listdir(self.dir):
                    answer = QuestionDialog(self.btnSave.get_label(),
                                          _("The destination directory is not empty.\n"
                                          "Are you sure you want to overwrite all data in {}?".format(self.dir)))
                    if not answer:
                        return

                self.enable_gui_elements(False)
                
                self.log('> Start unpacking {iso} to {target}'.format(iso=self.iso, target=self.dir))
                
                # Start unpacking the ISO
                command = 'iso-constructor -U "{iso}" "{target}"'.format(iso=self.iso, target=self.dir)
                self.terminal.feed(command=command, wait_until_done=True)
                
                self.save_dist_file(self.dir)
                self.fill_tv_dists()
                
                self.enable_gui_elements(True)
            else:
                self.save_dist_file(self.dir)
                self.fill_tv_dists()
                self.log('> Added existing working directory {dir}'.format(dir=self.dir))

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
    
    def fill_tv_dists(self, selectDistros=[]):
        contentList = [[_("Select"), _("Distribution"), _("Working directory")]]
        distros = self.get_dists()
        for distro in distros:
            select = False
            for selectDistro in selectDistros:
                if distro[0] == selectDistro:
                    select = True
            contentList.append([select, distro[0], distro[1]])
        self.tvHandlerDistros.fillTreeview(contentList=contentList, columnTypesList=['bool', 'str', 'str'], firstItemIsColName=True)

    def get_dists(self):
        distros = []
        if exists(self.distroFile):
            with open(self.distroFile, 'r') as f:
                lines = f.readlines()
            for line in lines:
                line = line.strip().rstrip('/')
                print(line)
                if exists(line):
                    lsb_info = get_lsb_release_info(line + '/root')
                    distros.append([lsb_info['name'], line])
            # Sort on iso name
            if distros:
                distros = sorted(distros, key=operator.itemgetter(0))
        return distros

    def enable_gui_elements(self, enable):
        if not enable:
            self.terminal.set_input_enabled(True)
            self.chkSelectAll.set_sensitive(False)
            self.tvDistros.set_sensitive(False)
            self.btnAdd.set_sensitive(False)
            self.btnLog.set_sensitive(False)
            self.btnBuildIso.set_sensitive(False)
            self.btnEdit.set_sensitive(False)
            self.btnRemove.set_sensitive(False)
            self.btnUpgrade.set_sensitive(False)
            self.btnLocalize.set_sensitive(False)
            self.btnDir.set_sensitive(False)
            self.btnHelp.set_sensitive(False)
        else:
            self.terminal.set_input_enabled(False)
            self.chkSelectAll.set_sensitive(True)
            self.tvDistros.set_sensitive(True)
            self.btnAdd.set_sensitive(True)
            self.btnLog.set_sensitive(True)
            self.btnBuildIso.set_sensitive(True)
            self.btnEdit.set_sensitive(True)
            self.btnRemove.set_sensitive(True)
            self.btnUpgrade.set_sensitive(True)
            self.btnLocalize.set_sensitive(True)
            self.btnDir.set_sensitive(True)
            self.btnHelp.set_sensitive(True)

    def save_dist_file(self, distroPath, addDistro=True):
        newCont = []
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
        
    def log(self, text):
        if self.log_file and text:
            with open(self.log_file, 'a') as f:
                f.write(text + '\n')

    def check_chroot(self, flag_fle):
        while exists(flag_fle):
            # Update the parent window
            while Gtk.events_pending():
                Gtk.main_iteration()
            time.sleep(0.1)

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
