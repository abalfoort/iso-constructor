#!/usr/bin/env python3

# Make sure the right versions are loaded
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Vte', '2.91')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, GLib, Vte, Gdk, Gio
from os import environ
import time

# Reference: https://lazka.github.io/pgi-docs/Vte-2.91/classes/Terminal.html
class Terminal(Vte.Terminal):
    def __init__(self):
        super(Terminal, self).__init__()

        # Signals
        self.connect_after('child-exited', self.on_child_exited)
        self.connect("key_press_event", self.on_key_press)
        self.connect('contents-changed', self.on_contents_changed)

        # Properties
        self.log_file = None
        self.enable_copy_paste = True
        self.set_scroll_on_output(True)
        self.set_input_enabled(True)
        self._cancellable = Gio.Cancellable()
        self._last_row = 0
        self._cmd_is_running = False
        
        # Colors
        fg = Gdk.RGBA()
        bg = Gdk.RGBA()
        fg.parse('#ffffff')
        bg.parse('#1c1f22')
        self.set_color_foreground(fg)
        self.set_color_background(bg)
        
        # Create child
        self.create_child()
            
    def create_child(self):
        self.spawn_async(
            Vte.PtyFlags.DEFAULT,                 #pty flags
            environ['HOME'],                      #working directory
            ["/bin/bash"],                        #argmument vector
            [],                                   #list with environment variables
            GLib.SpawnFlags.DO_NOT_REAP_CHILD,    #spawn flags
            None,                                 #setup function
            None,                                 #child_setup data (gpointer)
            -1,                                   #timeout
            self._cancellable,                    #cancellable
            None,                                 #callback
            None                                  #callback data
            )
           
    def feed(self, command, wait_until_done=False):
        if self._cmd_is_running:
            return
        self._cancellable.reset()
        self.grab_focus()
        command += '\n'
        self.feed_child(command.encode())

        def sleep(seconds=0.1):
            time.sleep(seconds)
            # Update the parent window
            while Gtk.events_pending():
                Gtk.main_iteration()

        # Unfortunately, there is no built-in way to notify the parent
        # that a command has finished or to wait for the command 
        # until it is finished.
        if wait_until_done:
            self._cmd_is_running = True
            # This won't work if the user scrolls up.
            # So, disable scrolling while running the command
            parent_is_sensitive = False
            try:
                parent_is_sensitive = self.get_parent().get_sensitive()
                self.get_parent().set_sensitive(False)
            except:
                pass
            # First, wait until the last character is not a prompt sign
            while self.get_text(None, None)[0].strip()[-1:] in '$#':
                sleep()
            # Finally, the command is executing - wait until the last
            # character is a prompt sign
            while self.get_text(None, None)[0].strip()[-1:] not in '$#':
                sleep()
            # Make the terminal scrollable again if it was at the start
            if parent_is_sensitive: self.get_parent().set_sensitive(True)
            # Command is done
            self._cmd_is_running = False
        
    def cancel(self):
        self._cancellable.cancel()
        
    def get_last_line(self):
        text = self.get_text(None, None)[0].strip()
        text = text.split('\n')
        ii = len(text) - 1
        while text[ii] == '':
            ii = ii - 1
        text = text[ii]
        return text
        
    def on_contents_changed(self, terminal):
        # Log the content of the terminal
        if self.log_file != None:
            column, row = self.get_cursor_position()
            if self._last_row != row:
                text = self.get_text_range(self._last_row, 0, row, -1)[0]
                text = text.strip()
                self._last_row = row
                with open(self.log_file, 'a') as f:
                    f.write(text + '\n')
            
    def on_key_press(self, widget, event):
        # Handle Ctrl-Shift-C and Ctrl-Shift-V
        if self.enable_copy_paste:
            ctrl = (event.state & Gdk.ModifierType.CONTROL_MASK)
            shift = (event.state & Gdk.ModifierType.SHIFT_MASK)
            if ctrl and shift:
                keyval = Gdk.keyval_to_upper(event.keyval)
                if keyval == Gdk.KEY_C and self.get_has_selection():
                    self.copy_clipboard()
                    return True
                elif keyval == Gdk.KEY_V:
                    self.paste_clipboard()
                    return True
            
    def on_child_exited(self, terminal, status):
        # Create a new child if the user ended the current one
        # with Ctrl-D or typing exit.
        self.create_child()
