#!/usr/bin/env python3
""" Module to provide a Vte.Terminal object """

import time
from os import environ
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Vte', '2.91')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, GLib, Vte, Gdk, Gio


# Reference: https://lazka.github.io/pgi-docs/#Vte-3.91/classes/Terminal.html
class Terminal(Vte.Terminal):
    ''' Terminal class. '''

    def __init__(self):
        super().__init__()

        # Signals
        self.connect_after('child-exited', self.on_child_exited)
        self.connect("key_press_event", self.on_key_press)
        self.connect('contents-changed', self.on_contents_changed)

        # Properties
        self.pause_logging = False
        self.log_file = None
        self.enable_copy_paste = True
        self.set_scroll_on_output(True)
        self.set_input_enabled(True)
        self._cancellable = Gio.Cancellable()
        self._last_row = 0
        self._cmd_is_running = False

        # Colors
        fg_color = Gdk.RGBA()
        bg_color = Gdk.RGBA()
        fg_color.parse('#ffffff')
        bg_color.parse('#1c1f22')
        self.set_color_foreground(fg_color)
        self.set_color_background(bg_color)

        # Create child
        self.create_child()

    def create_child(self):
        ''' Create a terminal object. '''
        # Use async from version 0.48
        self.spawn_async(
            Vte.PtyFlags.DEFAULT,  # pty flags
            environ['HOME'],  # working directory
            ["/bin/bash"],  # argmument vector
            [],  # list with environment variables
            GLib.SpawnFlags(Vte.SPAWN_NO_PARENT_ENVV),  # spawn flags
            None,  # child_setup function
            None,  # child_setup data (gpointer)
            -1,  # timeout
            self._cancellable,  # cancellable
            None,  # callback
            None  # callback data
        )

    def terminal_feed(self, command, wait_until_done=False,
                      disable_scrolling=True, pause_logging=False):
        """Feed a command to the terminal

        Args:
            command (string): command to execute
            wait_until_done (bool, optional): wait for the command to finish.
                                              Defaults to False.
            disable_scrolling (bool, optional): disable user scrolling while command is running.
                                                Defaults to True.
            pause_logging (bool, optional): pause logging while command is running.
                                            Defaults to False.
        """
        if self._cmd_is_running:
            return

        def sleep(seconds=0.1):
            time.sleep(seconds)
            # Update the parent window
            while Gtk.events_pending():
                Gtk.main_iteration()

        self._cancellable.reset()
        self.grab_focus()
        self.pause_logging = pause_logging
        command += '\n'
        self.feed_child(command.encode())
        # We need to wait until the command is complete fed
        sleep()

        # Unfortunately, there is no built-in way to notify the parent
        # that a command has finished or to wait for the command
        # until it is finished.
        if wait_until_done:
            self._cmd_is_running = True
            # This won't work if the user scrolls up.
            # So, disable scrolling while running the command
            parent_is_sensitive = False
            try:
                if disable_scrolling:
                    parent_is_sensitive = self.get_parent().get_sensitive()
                    self.get_parent().set_sensitive(False)
            except Exception:
                pass
            # First, wait until the last character is not a prompt sign

            # TODO: vte_terminal_get_text: Passing a GArray to retrieve attributes is deprecated.
            # TODO: In a future version, passing non-NULL as attributes array will make the function return NULL
            while self.get_text()[0].strip()[-1:] in '$#':
                sleep()
            # Finally, the command is executing - wait until the last
            # character is a prompt sign
            while self.get_text()[0].strip()[-1:] not in '$#':
                sleep()

            # Make the terminal scrollable again if it was at the start
            if parent_is_sensitive:
                self.get_parent().set_sensitive(True)
            # Command is done
            self._cmd_is_running = False

        # Reset pause on logging
        self.pause_logging = False

    def cancel(self):
        ''' Set terminal cancellable. '''
        self._cancellable.cancel()

    def get_last_line(self):
        ''' Get the last line in the terminal. '''
        text = self.get_text(None, None)[0].strip()
        text = text.split('\n')
        i_pos = len(text) - 1
        while text[i_pos] == '':
            i_pos = i_pos - 1
        text = text[i_pos]
        return text

    def get_vte_version(self):
        ''' Return tuple of vte version. '''
        return Vte.get_major_version(), Vte.get_minor_version(), Vte.get_micro_version()

    def on_contents_changed(self, terminal):
        ''' Log the content of the terminal. '''
        if self.log_file and not self.pause_logging:
            column, row = self.get_cursor_position()
            if self._last_row != row:
                text = self.get_text_range(self._last_row, 0, row, -1)[0]
                text = text.strip()
                self._last_row = row
                with open(file=self.log_file, mode='a', encoding='utf-8') as log_file:
                    log_file.write(text + '\n')

    def on_key_press(self, widget, event):
        ''' Handle Ctrl-Shift-C and Ctrl-Shift-V. '''
        if self.enable_copy_paste:
            ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
            shift = event.state & Gdk.ModifierType.SHIFT_MASK
            if ctrl and shift:
                keyval = Gdk.keyval_to_upper(event.keyval)
                if keyval == Gdk.KEY_C and self.get_has_selection():
                    self.copy_clipboard()
                    return True
                if keyval == Gdk.KEY_V:
                    self.paste_clipboard()
                    return True
        return False

    def on_child_exited(self, terminal, status):
        '''
        Create a new child if the user ended the current one
        with Ctrl-D or typing exit.
        '''
        self.create_child()
