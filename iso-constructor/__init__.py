#!/usr/bin/env python3

from os import makedirs, system, listdir, \
               environ, rename, remove, sysconf
import operator
from os.path import join, dirname, exists, isdir

# i18n: http://docs.python.org/3/library/gettext.html
import gettext
_ = gettext.translation('iso-constructor', fallback=True).gettext

# Make sure the right versions are loaded
import gi
gi.require_version('Gtk', '3.0')
# from gi.repository import Gtk, GdkPixbuf, GObject, Pango, Gdk, Vte
from gi.repository import Gtk

# Local imports
from .treeview import TreeViewHandler
from .terminal import Terminal
from .dialogs import show_message_dialog, show_error_dialog, SelectFileDialog, \
                     SelectDirectoryDialog, show_question_dialog
from .utils import get_user_home, get_logged_user, \
                   get_package_version, get_lsb_release_info, \
                   getoutput, shell_exec


class Constructor():
    '''
    ISO Constructor main class.
    '''
    def __init__(self):
        self.share_dir = '/usr/share/iso-constructor'
        self.chroot_script = join(self.share_dir, "chroot-dir.sh")
        self.user_app_dir = join(get_user_home(), ".iso-constructor")
        self.distro_file = join(self.user_app_dir, "distributions.list")
        self.log_file = join(self.user_app_dir, 'iso-constructor.log')

        # Remove old log file
        if exists(self.log_file):
            remove(self.log_file)

        # Create the user's application directory if it doesn't exist
        if not isdir(self.user_app_dir):
            old_dir = join(get_user_home(), ".constructor")
            if exists(old_dir):
                rename(old_dir, self.user_app_dir)
                if exists(join(self.user_app_dir, 'distros.list')):
                    rename(join(self.user_app_dir, 'distros.list'), self.distro_file)
            else:
                user_name = get_logged_user()
                makedirs(self.user_app_dir)
                system(f"chown -R {user_name}:{user_name} {self.user_app_dir}")

        # Load window and widgets
        self.builder = Gtk.Builder()
        self.builder.add_from_file(join(self.share_dir, 'iso-constructor.glade'))

        # Main window objects
        go = self.builder.get_object
        self.window = go('constructor_window')
        self.tv_distros = go('tv_distros')
        self.btn_add = go('btn_add')
        self.btn_log = go('btn_log')
        self.chk_selectall = go('chk_select_all')
        self.btn_remove = go('btn_remove')
        self.btn_edit = go('btn_edit')
        self.btn_upgrade = go('btn_upgrade')
        self.btn_buildiso = go('btn_build_iso')
        self.btn_qemu = go('btn_qemu')

        # Add iso window objects
        self.window_adddistro = go('add_distro_window')
        self.txt_iso = go('txt_iso')
        self.txt_dir = go('txt_dir')
        self.btn_dir = go('btn_dir')
        self.btn_save = go('btn_save')
        self.btn_help = go('btn_help')
        self.lbl_iso = go('lbl_iso')
        self.box_iso = go('box_iso')
        self.lbl_dir = go('lbl_dir')
        self.chk_fromiso = go('chk_from_iso')

        # Main window translations
        self.remove_text = _("Remove")
        self.window.set_title("ISO Constructor")
        self.chk_selectall.set_label(_("Select all"))
        self.btn_add.set_tooltip_text(_("Add"))
        self.btn_log.set_tooltip_text(_("View log file"))
        self.btn_remove.set_tooltip_text(self.remove_text)
        self.btn_edit.set_tooltip_text(_("Edit"))
        self.btn_upgrade.set_tooltip_text(_("Upgrade"))
        self.btn_buildiso.set_tooltip_text(_("Build"))
        self.btn_help.set_tooltip_text(_("Help"))
        self.btn_qemu.set_tooltip_text(_("Test ISO"))

        # Add iso window translations
        self.window_adddistro.set_title(_("Add Distribution"))
        self.lbl_iso.set_text(_("ISO"))
        go('lbl_from_iso').set_label("Create from ISO")
        cancel = _("Cancel")
        go('btn_cancel').set_label(f"_{cancel}")

        # Terminal
        self.terminal = Terminal()
        go('sw_tve').add(self.terminal)
        self.terminal.log_file = self.log_file
        self.terminal.set_input_enabled(False)

        # Init
        self.iso = None
        self.dir = None
        self.html_dir = join(self.share_dir, "html")
        self.help = join(self.get_language_dir(), "help.html")
        self.chk_fromiso.set_active(True)

        # Treeviews
        self.tv_handlerdistros = TreeViewHandler(self.tv_distros)
        self.fill_tv_dists()

        # Version information
        ver = get_package_version('iso-constructor')
        self.log(f'> ISO Constructor {ver}')

        # Connect the signals and show the window
        self.builder.connect_signals(self)
        self.window.show_all()

        # Check if qemu is installed and show the qemu button if it is.
        self.btn_qemu.set_visible(False)
        qemu_ver = get_package_version('qemu-system-x86')
        ovmf_ver = get_package_version('ovmf')
        # Get RAM in GB
        mem_bytes = sysconf('SC_PAGE_SIZE') * sysconf('SC_PHYS_PAGES')
        mem_gib = int(mem_bytes/(1024.**3))
        if qemu_ver and ovmf_ver and mem_gib >= 4:
            self.btn_qemu.set_visible(True)

    # ===============================================
    # Main Window Functions
    # ===============================================

    def on_btn_add_clicked(self, widget):
        '''
        Add distribution from ISO file.
        '''
        self.window_adddistro.show()

    def on_btn_remove_clicked(self, widget):
        '''
        Remove selected distribution(s).
        '''
        selected = self.tv_handlerdistros.get_toggled_values(toggle_col_nr=0, value_col_nr=2)
        for path in selected:
            answer = show_question_dialog(self.remove_text,
                                  _("Are you sure you want to remove "
                                    "the selected distribution from the list?\n"
                                    "(This will not remove the directory and its data)"))
            if answer:
                self.save_dist_file(distro_path=path, add_distro=False)
        self.fill_tv_dists()

    def on_btn_edit_clicked(self, widget):
        '''
        Edit selected distribution(s)
        '''
        self.enable_gui_elements(False)
        selected = self.tv_handlerdistros.get_toggled_values(toggle_col_nr=0, value_col_nr=2)
        for path in selected:

            self.log(f'> Start editing {path}')

            # Edit the distribution in a chroot session
            self.terminal.feed(command=f'iso-constructor -e "{path}"')

            # Check if chrooted and wait until user is done
            while getoutput(f'pgrep -f "chroot-dir.sh {path}"'):
                # Update the parent window
                while Gtk.events_pending():
                    Gtk.main_iteration()
        self.enable_gui_elements(True)

    def on_btn_upgrade_clicked(self, widget):
        '''
        Apt upgrade selected distribution(s).
        '''
        self.enable_gui_elements(False)
        selected = self.tv_handlerdistros.get_toggled_values(toggle_col_nr=0, value_col_nr=2)
        for path in selected:
            self.log(f'> Start upgrading {path}')

            # Upgrade the distribtution
            self.terminal.feed(command=f'iso-constructor -u "{path}"', wait_until_done=True)
        self.enable_gui_elements(True)

    def on_btn_build_iso_clicked(self, widget):
        '''
        Build ISOs from selected distribution(s).
        '''
        self.enable_gui_elements(False)
        selected = self.tv_handlerdistros.get_toggled_values(toggle_col_nr=0, value_col_nr=2)
        if selected:
            # Loop through selected distributions
            for path in selected:
                self.log(f'> Start building ISO in: {path}')

                # Build the ISO
                self.terminal.feed(command=f'iso-constructor -b "{path}"', wait_until_done=True)
        self.enable_gui_elements(True)

    def on_btn_qemu_clicked(self, widget):
        '''
        Test ISOs from selected distribution(s) in Qemu.
        '''
        self.enable_gui_elements(False)
        selected = self.tv_handlerdistros.get_toggled_values(toggle_col_nr=0, value_col_nr=2)
        if selected:
            # Loop through selected distributions
            for path in selected:
                for iso_path in listdir(path):
                    if iso_path.endswith(".iso"):
                        self.log(f'> Start testing ISO: {path}/{iso_path}')

                        # Start qemu to test the selected ISO
                        shell_exec(command=f'iso-constructor -t "{path}"', wait=True)
        self.enable_gui_elements(True)

    def on_chk_select_all_toggled(self, widget):
        '''
        Select/Deselect all listed distributions.
        '''
        self.tv_handlerdistros.treeview_toggle_all(toggle_col_nr_list=[0],
                                                   toggle_value=widget.get_active())

    def on_tv_distros_row_activated(self, widget, path, column):
        '''
        Toggle checkbox in row when row is activated.
        '''
        self.tv_handlerdistros.treeview_toggle_rows(toggle_col_nr_list=[0])

    def on_btn_help_clicked(self, widget):
        '''
        Show help.
        '''
        self.enable_gui_elements(False)
        command = 'man iso-constructor'
        self.terminal.feed(command=command, wait_until_done=True,
                           disable_scrolling=False, pause_logging=True)
        self.enable_gui_elements(True)

    def on_btn_log_clicked(self, widget):
        '''
        Show log file.
        '''
        self.enable_gui_elements(False)
        self.terminal.feed(command=f'sensible-editor {self.log_file}', wait_until_done=True,
                           disable_scrolling=False, pause_logging=True)
        self.enable_gui_elements(True)

    def on_constructor_window_destroy(self, widget):
        '''
        Close the app
        '''
        Gtk.main_quit()

    # ===============================================
    # Add ISO Window Functions
    # ===============================================

    def on_btn_iso_clicked(self, widget):
        '''
        Select ISO file.
        '''
        fle_filter = Gtk.FileFilter()
        fle_filter.set_name("ISO")
        fle_filter.add_mime_type("application/x-cd-image")
        fle_filter.add_pattern("*.iso")

        start_dir = None
        if exists(dirname(self.txt_iso.get_text())):
            start_dir = dirname(self.txt_iso.get_text())

        file_path = SelectFileDialog(title=_('Select ISO file'),
                                     start_directory=start_dir,
                                     parent=self.window,
                                     gtk_file_filter=fle_filter).show()
        if file_path is not None:
            self.txt_iso.set_text(file_path)

    def on_btn_dir_clicked(self, widget):
        '''
        Select target directory to unpack ISO into.
        '''
        start_dir = None
        if exists(self.txt_dir.get_text()):
            start_dir = self.txt_dir.get_text()
        dir_text = SelectDirectoryDialog(title=_('Select directory'),
                                        start_directory=start_dir,
                                        parent=self.window).show()
        if dir_text is not None:
            self.txt_dir.set_text(dir_text)

    def on_btn_save_clicked(self, widget):
        '''
        Unpack ISO to target directory.
        '''
        self.iso = ""
        if self.chk_fromiso.get_active():
            self.iso = self.txt_iso.get_text()
        self.dir = self.txt_dir.get_text()

        title = _("Save existing working directory")
        if self.iso != "":
            title = _("Unpack ISO and save")

        if not exists(self.dir):
            makedirs(self.dir)

        if not exists(self.dir):
            show_error_dialog(title=title,
                              text=_(f"Could not create directory {self.dir}: exiting"),
                              parent=self.window)
        else:
            self.window_adddistro.hide()
            if self.iso != "":
                if not exists(self.iso):
                    show_message_dialog(title=self.btn_save.get_label(),
                                        text=_(f"The path to the ISO file does not exist:\n{self.iso}"),
                                        parent=self.window)
                    return
                if listdir(self.dir):
                    answer = show_question_dialog(self.btn_save.get_label(),
                                          _(f"The destination directory is not empty.\nAre you sure you want to overwrite all data in {self.dir}?"))
                    if not answer:
                        return

                self.enable_gui_elements(False)

                self.log(f'> Start unpacking {self.iso} to {self.dir}')

                # Start unpacking the ISO
                self.terminal.feed(command=f'iso-constructor -U "{self.iso}" "{self.dir}"',
                                   wait_until_done=True)

                self.save_dist_file(self.dir)
                self.fill_tv_dists()

                self.enable_gui_elements(True)
            else:
                self.save_dist_file(self.dir)
                self.fill_tv_dists()
                self.log(f'> Added existing working directory {self.dir}')

    def on_btn_cancel_clicked(self, widget):
        '''
        Cancel unpacking ISO.
        '''
        self.window_adddistro.hide()

    def on_add_distro_window_delete_event(self, widget, data=None):
        '''
        Hide the Add Distro window.
        '''
        self.window_adddistro.hide()
        return True

    def on_txt_iso_changed(self, widget):
        '''
        Set objects sensitivity when txt_iso is changed.
        '''
        path = self.txt_iso.get_text()
        if exists(path):
            self.txt_dir.set_sensitive(True)
            self.btn_dir.set_sensitive(True)
            if exists(self.txt_dir.get_text()):
                self.btn_save.set_sensitive(True)
        else:
            self.txt_dir.set_sensitive(False)
            self.btn_dir.set_sensitive(False)
            self.btn_save.set_sensitive(False)

    def on_txt_dir_changed(self, widget):
        '''
        Set objects sensitivity when txt_dir is changed.
        '''
        bln_from_iso = self.chk_fromiso.get_active()
        iso_path = self.txt_iso.get_text()
        dir_text = self.txt_dir.get_text()
        self.btn_save.set_sensitive(False)
        if exists(dir_text):
            if bln_from_iso:
                if exists(iso_path):
                    self.btn_save.set_sensitive(True)
            else:
                self.btn_save.set_sensitive(True)

    def on_chk_from_iso_toggled(self, widget):
        '''
        When checked: unpack ISO.
        When unchecked: use target directory as-is.
        '''
        if widget.get_active():
            self.lbl_iso.set_visible(True)
            self.box_iso.set_visible(True)
            self.txt_dir.set_sensitive(False)
            self.btn_dir.set_sensitive(False)
            self.btn_save.set_sensitive(False)
            self.lbl_dir.set_text(_("Unpack ISO to directory"))
            self.btn_save.set_label(_("Unpack & Save"))
        else:
            self.txt_iso.set_text("")
            self.lbl_iso.set_visible(False)
            self.box_iso.set_visible(False)
            self.txt_dir.set_sensitive(True)
            self.btn_dir.set_sensitive(True)
            self.btn_save.set_sensitive(True)
            self.lbl_dir.set_text(_("Work directory"))
            self.btn_save.set_label(_("Save"))

    # ===============================================
    # General functions
    # ===============================================

    def fill_tv_dists(self, select_distros=[]):
        '''
        Fill the TreeView with distributions.
        '''
        content_list = [[_("Select"), _("Distribution"), _("Working directory")]]
        distros = self.get_dists()
        for distro in distros:
            select = False
            for select_distro in select_distros:
                if distro[0] == select_distro:
                    select = True
            content_list.append([select, distro[0], distro[1]])
        self.tv_handlerdistros.fill_treeview(content_list=content_list,
                                             column_types_list=['bool', 'str', 'str'],
                                             first_item_is_col_name=True)

    def get_dists(self):
        '''
        Return a list with distributions,
        filled from the save file.
        '''
        distros = []
        if exists(self.distro_file):
            with open(file=self.distro_file, mode='r', encoding='utf-8') as f:
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
        '''
        Enable/Disable GUI elements.
        '''
        if not enable:
            self.terminal.set_input_enabled(True)
            self.chk_selectall.set_sensitive(False)
            self.tv_distros.set_sensitive(False)
            self.btn_add.set_sensitive(False)
            self.btn_log.set_sensitive(False)
            self.btn_buildiso.set_sensitive(False)
            self.btn_edit.set_sensitive(False)
            self.btn_remove.set_sensitive(False)
            self.btn_upgrade.set_sensitive(False)
            self.btn_qemu.set_sensitive(False)
            self.btn_dir.set_sensitive(False)
            self.btn_help.set_sensitive(False)
        else:
            self.terminal.set_input_enabled(False)
            self.chk_selectall.set_sensitive(True)
            self.tv_distros.set_sensitive(True)
            self.btn_add.set_sensitive(True)
            self.btn_log.set_sensitive(True)
            self.btn_buildiso.set_sensitive(True)
            self.btn_edit.set_sensitive(True)
            self.btn_remove.set_sensitive(True)
            self.btn_upgrade.set_sensitive(True)
            self.btn_qemu.set_sensitive(True)
            self.btn_dir.set_sensitive(True)
            self.btn_help.set_sensitive(True)

    def save_dist_file(self, distro_path, add_distro=True):
        '''
        Save distribution to the save file.
        '''
        new_cont = []
        cfg = []
        if exists(self.distro_file):
            with open(file=self.distro_file, mode='r', encoding='utf-8') as f:
                cfg = f.readlines()
            for line in cfg:
                line = line.strip()
                if distro_path != line and exists(line):
                    new_cont.append(line)

        if add_distro:
            new_cont.append(distro_path)

        with open(file=self.distro_file, mode='w', encoding='utf-8') as f:
            f.write('\n'.join(new_cont))

        self.iso = ""
        self.dir = ""

    def log(self, text):
        '''
        Save text to the log file.
        '''
        if self.log_file and text:
            with open(file=self.log_file, mode='a', encoding='utf-8') as f:
                f.write(text + '\n')

    def get_language_dir(self):
        '''
        Get the language directory for the system's language.
        '''
        # First test if full locale directory exists, e.g. html/pt_BR,
        # otherwise perhaps at least the language is there, e.g. html/pt
        # and if that doesn't work, try html/pt_PT
        lang = self.get_current_language()
        path = join(self.html_dir, lang)
        if not isdir(path):
            base_lang = lang.split('_')[0].lower()
            path = join(self.html_dir, base_lang)
            if not isdir(path):
                path = join(self.html_dir, f"{base_lang}_{base_lang.upper()}")
                if not isdir(path):
                    path = join(self.html_dir, 'en')
        return path

    def get_current_language(self):
        '''
        Get the system's language.
        '''
        lang = environ.get('LANG', 'US').split('.')[0]
        if lang == '':
            lang = 'en'
        return lang


def main():
    '''
    Create an instance of our GTK application
    '''
    try:
        Constructor()
        Gtk.main()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
