#!/usr/bin/env python3
""" Module to provide a Vte.Terminal object """

import time
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Vte', '2.91')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, GLib, Vte, Gdk, Gio


# Reference: https://lazka.github.io/pgi-docs/#Vte-2.91/classes/Terminal.html
class Terminal(Vte.Terminal):
    ''' Terminal class. '''

    def __init__(self, colors=None):
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
        use_default_colors = False
        if not isinstance(colors, list):
            use_default_colors = True
        if not use_default_colors:
            if len(colors) not in [8, 16, 232, 256]:
                use_default_colors = True
        if use_default_colors:
            colors = ["#191919", "#c01c28", "#26a269", "#a2734c",
                      "#12488b", "#a347ba", "#2aa1b3", "#cfcfcf",
                      "#5d5d5d", "#f66151", "#33d17a", "#e9ad0c",
                      "#2a7bde", "#c061cb", "#33c7de", "#ffffff"]

        # Create the RGBA palette from the colors
        palette = [Gdk.RGBA() for c in colors]
        for p, c in zip(palette, colors):
            p.parse(c)

        fg_color = Gdk.RGBA()
        bg_color = Gdk.RGBA()

        # Check if a light or dark theme is used
        # Also check theme name:
        # when running as root, gtk-application-prefer-dark-theme is not relyable
        gtk_settings = Gtk.Settings.get_default()
        theme_name = gtk_settings.get_property("gtk-theme-name")
        app_dark = gtk_settings.get_property("gtk-application-prefer-dark-theme")

        if app_dark or "dark" in theme_name.lower():
            print(("Vte dark theme"))
            fg_color.parse(colors[len(colors) - 1])
            bg_color.parse(colors[0])
        else:
            print(("Vte light theme"))
            fg_color.parse(colors[0])
            bg_color.parse(colors[len(colors) - 1])

        # Set the colors
        self.set_colors(fg_color, bg_color, palette)

        # Create child
        self._create_child()

    def _create_child(self):
        ''' Create a terminal object. '''
        # Use async from version 0.48
        self.spawn_async(
            Vte.PtyFlags.DEFAULT,  # pty flags
            '/',  # working directory
            ["/bin/bash"],  # argmument vector
            [],  # list with environment variables
            GLib.SpawnFlags.DEFAULT,  # spawn flags
            None,  # child_setup function
            None,  # child_setup data (gpointer)
            -1,  # timeout
            self._cancellable,  # cancellable
            None,  # callback
            None  # callback data
        )

    def exec(self, command, wait_until_done=False,
             disable_scrolling=True, pause_logging=False):
        """Execute a command in the terminal

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
        command = command + '\n' if command else '\n'
        self.feed_child(command.encode('utf-8'))

        # We need to wait until the command is completely fed
        sleep()

        # Unfortunately, there is no built-in way to notify the parent
        # that a command has finished or to wait for the command
        # until it is finished.
        if wait_until_done:
            self._cmd_is_running = True
            # This won't work if the user scrolls up.
            # So, disable scrolling while running the command
            parent_is_sensitive = False
            if disable_scrolling:
                try:
                    parent_is_sensitive = self.get_parent().get_sensitive()
                    self.get_parent().set_sensitive(False)
                except Exception:
                    pass

            # First, wait until the last character is not a prompt sign
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

    def last_line(self):
        ''' Get the last line in the terminal. '''
        text = self.get_text()[0].strip()
        text = text.split('\n')
        i_pos = len(text) - 1
        while text[i_pos] == '':
            i_pos = i_pos - 1
        text = text[i_pos]
        return text

    def version(self):
        ''' Return tuple of vte version. '''
        return Vte.get_major_version(), Vte.get_minor_version(), Vte.get_micro_version()

    def on_contents_changed(self, terminal):
        ''' Log the content of the terminal. '''
        if self.log_file and not self.pause_logging:
            column, row = self.get_cursor_position()
            if self._last_row != row:
                text = self.get_text_range(self._last_row, column, row, column + 1)[0]
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
        self._create_child()
