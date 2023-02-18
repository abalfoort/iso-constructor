""" Module to provide dialogs """

#!/usr/bin/env python3

from os.path import exists
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GdkPixbuf, GLib, Gtk


DIALOG_TYPES = {
    Gtk.MessageType.INFO: 'MessageDialog',
    Gtk.MessageType.ERROR: 'ErrorDialog',
    Gtk.MessageType.WARNING: 'WarningDialog',
    Gtk.MessageType.QUESTION: 'QuestionDialog',
}


class Dialog(Gtk.MessageDialog):
    '''
    Show message dialog
    Usage:
    MessageDialog(_("My Title"), "Your message here")
    Use safe=False when calling from a thread
    '''

    def __init__(self, message_type, buttons, title, text, text2=None,
                 parent=None, safe=True, icon=None):
        parent = parent or next(
            (w for w in Gtk.Window.list_toplevels() if w.get_title()), None)
        Gtk.MessageDialog.__init__(self,
                                   parent=None,
                                   modal=True,
                                   destroy_with_parent=True,
                                   message_type=message_type,
                                   buttons=buttons,
                                   text=text)
        self.set_position(Gtk.WindowPosition.CENTER)
        if parent is not None:
            self.set_icon(parent.get_icon())
        elif icon is not None:
            if exists(icon):
                self.set_icon_from_file(icon)
            else:
                self.set_icon_name(icon)
        self.set_title(title)
        self.set_markup(text)
        self.desc = text[:30] + ' ...' if len(text) > 30 else text
        self.dialog_type = DIALOG_TYPES[message_type]
        if text2:
            self.format_secondary_markup(text2)
        self.safe = safe
        if not safe:
            self.connect('response', self._handle_clicked)

    def _handle_clicked(self, *args):
        self.destroy()

    def show(self):
        if self.safe:
            return self._do_show_dialog()
        else:
            return GLib.timeout_add(0, self._do_show_dialog)

    def _do_show_dialog(self):
        """ Show the dialog.
            Returns True if user response was confirmatory.
        """
        # print(('Showing {0.dialog_type} ({0.desc})'.format(self)))
        try:
            return self.run() in (Gtk.ResponseType.YES,
                                  Gtk.ResponseType.APPLY,
                                  Gtk.ResponseType.OK,
                                  Gtk.ResponseType.ACCEPT)
        finally:
            if self.safe:
                self.destroy()
                while Gtk.events_pending():
                    Gtk.main_iteration()
            else:
                return False


def show_message_dialog(*args):
    '''
    Show message dialog
    '''
    return Dialog(Gtk.MessageType.INFO, Gtk.ButtonsType.OK, *args).show()


def show_question_dialog(*args):
    '''
    Show question dialog
    '''
    return Dialog(Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO, *args).show()


def show_warning_dialog(*args):
    '''
    Show warning dialog
    '''
    return Dialog(Gtk.MessageType.WARNING, Gtk.ButtonsType.OK, *args).show()


def show_error_dialog(*args):
    '''
    Show error dialog
    '''
    return Dialog(Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, *args).show()


class CustomQuestionDialog(Gtk.Dialog):
    '''
    Create a custom question dialog
    Usage:
    dialog = CustomQuestionDialog(_("My Title"), myCustomObject, 600, 450, parentWindow))
       if (dialog.show()):
    CustomQuestionDialog can NOT be called from a working thread, only from main (UI) thread
    '''

    def __init__(self, title, my_object, width=500, height=300, parent=None):
        self.title = title
        self.my_object = my_object
        self.parent = parent
        self.width = width
        self.height = height

    def show(self):
        dialog = Gtk.Dialog(title=self.title,
                            parent=self.parent,
                            modal=True,
                            destroy_with_parent=True)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                           Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialog.set_position(Gtk.WindowPosition.CENTER)
        dialog.set_default_size(self.width, self.height)
        if self.parent is not None:
            dialog.set_icon(self.parent.get_icon())

        buttonbox = dialog.get_action_area()
        buttons = buttonbox.get_children()
        dialog.set_focus(buttons[0])

        dialog.vbox.pack_start(self.my_object, True, True, 0)
        dialog.show_all()

        answer = dialog.run()
        return_value = bool(answer == Gtk.ResponseType.OK)
        dialog.destroy()
        return return_value


class SelectFileDialog(object):
    '''
    You can pass a Gtk.FileFilter object.
    Use add_mime_type, and add_pattern.
    Get the mime type of a file: $ mimetype [file]
    e.g.: $ mimetype debian.iso
            debian.iso: application/x-cd-image
    '''

    def __init__(self, title, start_directory=None, parent=None, gtk_file_filter=None):
        self.title = title
        self.start_directory = start_directory
        self.parent = parent
        self.gtk_file_filter = gtk_file_filter
        self.is_images = False
        if gtk_file_filter is not None:
            if gtk_file_filter.get_name() == "Images":
                self.is_images = True

    def show(self):
        '''
        Show File Chooser Dialog and return selected file.
        '''
        file_path = None
        image = Gtk.Image()

        # Image preview function
        def image_preview_cb(dialog):
            filename = dialog.get_preview_filename()
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    filename, 128, 128)
                image.set_from_pixbuf(pixbuf)
                valid_preview = True
            except:
                valid_preview = False
            dialog.set_preview_widget_active(valid_preview)

        dialog = Gtk.FileChooserDialog(title=self.title,
                                       parent=self.parent,
                                       action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                           Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        if self.start_directory is not None:
            dialog.set_current_folder(self.start_directory)
        if self.gtk_file_filter is not None:
            dialog.add_filter(self.gtk_file_filter)

        if self.is_images:
            # Add a preview widget:
            dialog.set_preview_widget(image)
            dialog.connect("update-preview", image_preview_cb)

        answer = dialog.run()
        if answer == Gtk.ResponseType.OK:
            file_path = dialog.get_filename()
        dialog.destroy()
        return file_path


class SelectImageDialog(object):
    '''
    Dialog to select images from file.
    '''

    def __init__(self, title, start_directory=None, parent=None):
        self.title = title
        self.start_directory = start_directory
        self.parent = parent

    def show(self):
        '''
        Show a File Chooser Dialog and limit to images.
        '''
        file_filter = Gtk.FileFilter()
        file_filter.set_name("Images")
        file_filter.add_mime_type("image/png")
        file_filter.add_mime_type("image/jpeg")
        file_filter.add_mime_type("image/gif")
        file_filter.add_pattern("*.png")
        file_filter.add_pattern("*.jpg")
        file_filter.add_pattern("*.gif")
        file_filter.add_pattern("*.tif")
        file_filter.add_pattern("*.xpm")
        fdg = SelectFileDialog(
            self.title, self.start_directory, self.parent, file_filter)
        return fdg.show()


class SelectDirectoryDialog(object):
    '''
    Dialog to select a directory.
    '''

    def __init__(self, title, start_directory=None, parent=None):
        self.title = title
        self.start_directory = start_directory
        self.parent = parent

    def show(self):
        '''
        Show a File Chooser Dialog and limit to directories.
        '''
        directory = None
        dialog = Gtk.FileChooserDialog(title=self.title,
                                       parent=self.parent,
                                       action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                           Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        if self.start_directory is not None:
            dialog.set_current_folder(self.start_directory)
        answer = dialog.run()
        if answer == Gtk.ResponseType.OK:
            directory = dialog.get_filename()
        dialog.destroy()
        return directory


class InputDialog(Gtk.MessageDialog):
    '''
    Dialog to ask for user input.
    '''

    def __init__(self, title, text, text2=None, parent=None, default_value='', is_password=False):
        parent = parent or next(
            (w for w in Gtk.Window.list_toplevels() if w.get_title()), None)

        Gtk.MessageDialog.__init__(self, parent=parent,
                                   modal=True,
                                   destroy_with_parent=True,
                                   message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.OK,
                                   text=text)
        self.set_position(Gtk.WindowPosition.CENTER)
        if parent is not None:
            self.set_icon(parent.get_icon())
        self.set_title(title)
        self.set_markup(text)
        if text2:
            self.format_secondary_markup(text2)

        # Add entry field
        entry = Gtk.Entry()
        if is_password:
            entry.set_visibility(False)
        entry.set_text(default_value)
        entry.connect("activate",
                      lambda ent, dlg, resp: dlg.response(resp),
                      self, Gtk.ResponseType.OK)
        self.vbox.pack_end(entry, True, True, 0)
        self.vbox.show_all()
        self.entry = entry

        self.set_default_response(Gtk.ResponseType.OK)

    def set_value(self, text):
        '''
        Set a default value of the entry field.
        '''
        self.entry.set_text(text)

    def show(self):
        '''
        Show the message dialog with the custom entry field.
        '''
        try:
            result = self.run()
            if result == Gtk.ResponseType.OK:
                return self.entry.get_text().strip()
            else:
                return ''
        except Exception as detail:
            print((f">> InputDialog error: {detail}"))
            return ''
        finally:
            self.destroy()
