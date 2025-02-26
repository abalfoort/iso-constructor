#!/usr/bin/env python3 -OO
# -OO: Turn on basic optimizations.  Given twice, causes docstrings to be discarded.

import sys
import traceback
from dialogs import error_dialog
from construcor import Constructor

# Make sure the right Gtk version is loaded
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk


# i18n: http://docs.python.org/3/library/gettext.html
import gettext
_ = gettext.translation('iso-constructor', fallback=True).gettext


def uncaught_excepthook(*args):
    sys.__excepthook__(*args)
    if not __debug__:
        details = '\n'.join(traceback.format_exception(*args)).replace('<', '').replace('>', '')
        title = _('Unexpected error')
        msg = _('ISO Constructor has failed with the following unexpected error. Please submit a bug report!')
        error_dialog(title, f"<b>{msg}</b>", f"<tt>{details}</tt>", None, True, 'solydxk')

    sys.exit(1)

sys.excepthook = uncaught_excepthook

if __name__ == '__main__':
    # Create an instance of our GTK application
    try:
        Constructor()
        Gtk.main()
    except KeyboardInterrupt:
        pass
