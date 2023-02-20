""" Module providing initialization of the ISO Constructor application """

#!/usr/bin/env python3

from os import makedirs, system, listdir, \
    environ, remove, sysconf
from os.path import join, dirname, exists, isdir
import gettext
from configparser import ConfigParser
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from .utils import get_user_home, get_logged_user, \
    get_package_version, getoutput, shell_exec, \
    get_lsb_release_info
from .dialogs import show_message_dialog, show_error_dialog, SelectFileDialog, \
    SelectDirectoryDialog, show_question_dialog
from .terminal import Terminal
from .treeview import TreeViewHandler

# i18n: http://docs.python.org/3/library/gettext.html
_ = gettext.translation('iso-constructor', fallback=True).gettext


class Constructor():
    '''
    ISO Constructor main class.
    '''
    def __init__(self):
        self.share_dir = '/usr/share/iso-constructor'
        self.chroot_script = join(self.share_dir, "chroot-dir.sh")
        self.user_app_dir = join(get_user_home(), ".iso-constructor")
        self.log_file = join(self.user_app_dir, 'iso-constructor.log')
        self.conf_file = join(self.user_app_dir, 'iso-constructor.conf')

        # Create the user's application directory if it doesn't exist
        user_name = get_logged_user()
        if not isdir(self.user_app_dir):
            makedirs(self.user_app_dir)
            system(f"chown -R {user_name}:{user_name} {self.user_app_dir}")

        # Load window and widgets
        self.builder = Gtk.Builder()
        self.builder.add_from_file(
            join(self.share_dir, 'iso-constructor.glade'))

        # Main window object
        builder_obj = self.builder.get_object
        self.window = builder_obj('constructor_window')
        self.dt_paned = builder_obj('dt_paned')

        # Instantiate the ConfigParser
        self.config = ConfigParser()

        # Hold a list with distribution paths
        self.distros = []

        # Create conf file if it does not exist
        if not exists(self.conf_file):
            self.save_settings()
            system(f"chown -R {user_name}:{user_name} {self.user_app_dir}")

        # Old file with distro paths
        distro_file = join(self.user_app_dir, "distributions.list")
        if exists(distro_file):
            with open(file=distro_file, mode='r', encoding='utf-8') as distro_fle:
                self.distros = [distro.strip() for distro in distro_fle.readlines()]
            self.save_distros()
            remove(distro_file)

        # Parse config file
        self.config.read(self.conf_file)
        self.distros = self.get_distros()

        # Set saved sizes
        window_width, window_height, distros_height = self.get_settings()
        self.window.set_default_size(window_width, window_height)
        self.dt_paned.set_position(distros_height)

        # Remove old log file
        if exists(self.log_file):
            remove(self.log_file)

        # Main window objects
        self.tv_distros = builder_obj('tv_distros')
        self.btn_add = builder_obj('btn_add')
        self.btn_log = builder_obj('btn_log')
        self.chk_selectall = builder_obj('chk_select_all')
        self.btn_remove = builder_obj('btn_remove')
        self.btn_edit = builder_obj('btn_edit')
        self.btn_upgrade = builder_obj('btn_upgrade')
        self.btn_buildiso = builder_obj('btn_build_iso')
        self.btn_qemu = builder_obj('btn_qemu')
        self.btn_qemu_img = builder_obj('btn_qemu_img')

        # Add iso window objects
        self.window_adddistro = builder_obj('add_distro_window')
        self.txt_iso = builder_obj('txt_iso')
        self.txt_dir = builder_obj('txt_dir')
        self.btn_dir = builder_obj('btn_dir')
        self.btn_save = builder_obj('btn_save')
        self.btn_help = builder_obj('btn_help')
        self.lbl_iso = builder_obj('lbl_iso')
        self.box_iso = builder_obj('box_iso')
        self.lbl_dir = builder_obj('lbl_dir')
        self.chk_fromiso = builder_obj('chk_from_iso')

        # Main window translations
        self.remove_text = _("Remove")
        self.test_iso_text = _("Test ISO in Qemu")
        self.test_qemo_text = _("Ctrl-Alt-F to exit full screen mode.")
        self.test_img_text = _("Test Qemu image")
        self.window.set_title("ISO Constructor")
        self.chk_selectall.set_label(_("Select all"))
        self.btn_add.set_tooltip_text(_("Add"))
        self.btn_log.set_tooltip_text(_("View log file"))
        self.btn_remove.set_tooltip_text(self.remove_text)
        self.btn_edit.set_tooltip_text(_("Edit"))
        self.btn_upgrade.set_tooltip_text(_("Upgrade"))
        self.btn_buildiso.set_tooltip_text(_("Build"))
        self.btn_help.set_tooltip_text(_("Help"))
        self.btn_qemu.set_tooltip_text(self.test_iso_text)
        self.btn_qemu_img.set_tooltip_text(self.test_img_text)

        # Add iso window translations
        self.window_adddistro.set_title(_("Add Distribution"))
        self.lbl_iso.set_text(_("ISO"))
        builder_obj('lbl_from_iso').set_label("Create from ISO")
        cancel = _("Cancel")
        builder_obj('btn_cancel').set_label(f"_{cancel}")

        # Terminal
        self.terminal = Terminal()
        builder_obj('sw_tve').add(self.terminal)
        self.terminal.log_file = self.log_file
        self.terminal.set_input_enabled(False)

        # Init
        self.iso = None
        self.dir = None
        self.html_dir = join(self.share_dir, "html")
        self.help = join(self.get_language_dir(), "help.html")
        self.chk_fromiso.set_active(True)
        self.skip_select_all = False

        # Treeviews
        self.tv_handlerdistros = TreeViewHandler(self.tv_distros)
        self.tv_handlerdistros.connect('checkbox-toggled', self.tv_dists_toggled)
        self.fill_tv_dists()

        # Connect the signals and show the window
        self.builder.connect_signals(self)
        self.window.show_all()

        # Version information
        ver = get_package_version('iso-constructor')
        self.log(f'> ISO Constructor {ver}')

        # Check if qemu is installed and show the qemu button if it is.
        self.show_qemu = False
        self.btn_qemu.set_visible(False)
        qemu_ver = get_package_version('qemu-system-x86')
        ovmf_ver = get_package_version('ovmf')
        # Get RAM in GB
        mem_bytes = sysconf('SC_PAGE_SIZE') * sysconf('SC_PHYS_PAGES')
        mem_gib = int(mem_bytes/(1024.**3))
        if qemu_ver and ovmf_ver and mem_gib >= 4:
            self.btn_qemu.set_visible(True)
            self.show_qemu = True

        self.btn_qemu_img.set_visible(False)
        self.qemu_img = join(self.user_app_dir, "qemu.qcow2")
        if self.show_qemu and exists(self.qemu_img):
            self.btn_qemu_img.set_visible(True)

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
        selected = self.tv_handlerdistros.get_toggled_values(
            toggle_col_nr=0, value_col_nr=2)
        if selected:
            for path in selected:
                answer = show_question_dialog(self.remove_text,
                                              _("Are you sure you want to remove "
                                                "the selected distribution from the list?\n"
                                                "(This will not remove the directory and its data)"))
                if answer:
                    self.save_distro(distro_path=path, add_distro=False)
            self.fill_tv_dists()

    def on_btn_edit_clicked(self, widget):
        '''
        Edit selected distribution(s)
        '''
        selected = self.tv_handlerdistros.get_toggled_values(
            toggle_col_nr=0, value_col_nr=2)
        if selected:
            self.enable_gui_elements(False)
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
        selected = self.tv_handlerdistros.get_toggled_values(
            toggle_col_nr=0, value_col_nr=2)
        if selected:
            self.enable_gui_elements(False)
            for path in selected:
                self.log(f'> Start upgrading {path}')

                # Upgrade the distribtution
                self.terminal.feed(
                    command=f'iso-constructor -u "{path}"', wait_until_done=True)
            self.enable_gui_elements(True)

    def on_btn_build_iso_clicked(self, widget):
        '''
        Build ISOs from selected distribution(s).
        '''
        selected = self.tv_handlerdistros.get_toggled_values(
            toggle_col_nr=0, value_col_nr=2)
        if selected:
            self.enable_gui_elements(False)
            # Loop through selected distributions
            for path in selected:
                self.log(f'> Start building ISO in: {path}')

                # Build the ISO
                self.terminal.feed(
                    command=f'iso-constructor -b "{path}"', wait_until_done=True)
            self.enable_gui_elements(True)

    def on_btn_qemu_clicked(self, widget):
        '''
        Test ISOs from selected distribution(s) in Qemu.
        '''
        selected = self.tv_handlerdistros.get_toggled_values(
            toggle_col_nr=0, value_col_nr=2)
        if selected:
            self.enable_gui_elements(False)
            show_message_dialog(self.test_iso_text,
                                f"\n{self.test_qemo_text}")
            # Loop through selected distributions
            for path in selected:
                for iso_path in listdir(path):
                    if iso_path.endswith(".iso"):
                        self.log(f'> Start testing ISO: {path}/{iso_path}')

                        # Start qemu to test the selected ISO
                        shell_exec(
                            command=f'iso-constructor -t "{path}"', wait=True)
            self.enable_gui_elements(True)

        if exists(self.qemu_img):
            self.btn_qemu_img.set_visible(True)

    def on_btn_qemu_img_clicked(self, widget):
        '''
        Test installed image in Qemu.
        '''
        if exists(self.qemu_img):
            self.enable_gui_elements(False)
            show_message_dialog(self.test_img_text,
                                f"\n{self.test_qemo_text}")
            # Start qemu to test the selected ISO
            shell_exec(command='iso-constructor -i')
            self.enable_gui_elements(True)

    def on_chk_select_all_toggled(self, widget):
        '''
        Select/Deselect all listed distributions.
        '''
        if self.skip_select_all:
            return
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

    def on_constructor_window_delete_event(self, widget, data):
        ''' Save Settings '''
        self.save_settings()

    def on_constructor_window_destroy(self, widget):
        ''' Close the app '''
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
            show_error_dialog(title,
                              _(f"Could not create directory {self.dir}: exiting"))
        else:
            self.window_adddistro.hide()
            if self.iso != "":
                if not exists(self.iso):
                    show_message_dialog(self.btn_save.get_label(),
                                        _(f"The path to the ISO file does not exist:\n{self.iso}"))
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

                self.save_distro(self.dir)
                self.fill_tv_dists()

                self.enable_gui_elements(True)
            else:
                self.save_distro(self.dir)
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
        content_list = [
            [_("Select"), _("Distribution"), _("Working directory")]]

        for distro in self.distros:
            select = False
            lsb_info = get_lsb_release_info(distro + '/root')
            for select_distro in select_distros:
                if distro == select_distro or distro == lsb_info['name']:
                    select = True
            content_list.append([select, lsb_info['name'], distro])
        self.tv_handlerdistros.fill_treeview(content_list=content_list,
                                             column_types_list=[
                                                 'bool', 'str', 'str'],
                                             first_item_is_col_name=True,
                                             columns_resizable=True)

    def tv_dists_toggled(self, obj, path, col_nr, toggle_value, data=None):
        ''' Callback function for toggled checkboxes in a treeview '''
        if not toggle_value:
            if self.chk_selectall.get_active():
                self.skip_select_all = True
                self.chk_selectall.set_active(False)
                self.skip_select_all = False
        else:
            toggled_rows = len(self.tv_handlerdistros.get_toggled_values())
            total_rows = self.tv_handlerdistros.get_row_count()
            if toggled_rows == total_rows:
                self.skip_select_all = True
                self.chk_selectall.set_active(True)
                self.skip_select_all = False

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
            self.btn_qemu_img.set_sensitive(False)
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
            if self.show_qemu:
                self.btn_qemu.set_sensitive(True)
                if exists(self.qemu_img):
                    self.btn_qemu_img.set_sensitive(True)
            self.btn_dir.set_sensitive(True)
            self.btn_help.set_sensitive(True)

    def get_distros(self):
        ''' Get list with distributions '''
        distros = self.config.get(
            'DISTROS', 'distro_paths', fallback='').split(';')
        for distro in distros:
            if not exists(distro):
                distros.remove(distro)
        return distros

    def save_distros(self):
        ''' Save distributions to the config file '''
        if 'DISTROS' not in self.config.sections():
            self.config.add_section('DISTROS')
        self.config.set('DISTROS', 'distro_paths', ';'.join(self.distros))
        self.save_config()

    def save_distro(self, distro_path, add_distro=True):
        ''' Add or remove distro_path '''
        if add_distro:
            self.distros.append(distro_path)
        else:
            self.distros.remove(distro_path)
        self.distros = sorted(self.distros)
        self.save_distros()

        self.iso = ""
        self.dir = ""

    def get_settings(self):
        ''' Get tupil with settings '''
        return (self.config.getint('SETTINGS', 'window_width', fallback=600),
                self.config.getint('SETTINGS', 'window_height', fallback=450),
                self.config.getint('SETTINGS', 'distros_height', fallback=100))

    def save_settings(self):
        ''' Save settings '''
        if 'SETTINGS' not in self.config.sections():
            self.config.add_section('SETTINGS')
        window_width, window_height = self.window.get_size()
        distros_height = self.dt_paned.get_position()
        self.config.set('SETTINGS', 'window_width', str(window_width))
        self.config.set('SETTINGS', 'window_height', str(window_height))
        self.config.set('SETTINGS', 'distros_height', str(distros_height))
        self.save_config()

    def save_config(self):
        ''' Save the current config object to file '''
        with open(file=self.conf_file, mode='w', encoding='utf-8') as conf_fle:
            self.config.write(conf_fle)

    def log(self, text):
        '''
        Save text to the log file.
        '''
        if self.log_file and text:
            with open(file=self.log_file, mode='a', encoding='utf-8') as log_fle:
                log_fle.write(text + '\n')

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
