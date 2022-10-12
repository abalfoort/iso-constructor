#!/usr/bin/env python3

import os
# Make sure the right Gtk version is loaded
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, GdkPixbuf


class TreeViewHandler(GObject.GObject):
    '''
    Treeview needs subclassing of gobject
    http://www.pygtk.org/articles/subclassing-gobject/sub-classing-gobject-in-python.htm

    def myCallback(self, obj, path, col_nr, toggle_value, data=None):
        print str(toggle_value)
    self.myTreeView = TreeViewHandler(self.myTreeView, self.myLogObject)
    self.myTreeView.connect('checkbox-toggled', self.myCallback)
    '''

    __gsignals__ = {
        'checkbox-toggled': (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
                            (GObject.TYPE_STRING, GObject.TYPE_INT, GObject.TYPE_BOOLEAN,))
        }

    def __init__(self, tree_view, logger_object=None):
        GObject.GObject.__init__(self)
        self.log = logger_object
        self.treeview = tree_view

    def clear_tree_view(self):
        ''' Clear treeview. '''
        liststore = self.treeview.get_model()
        if liststore is not None:
            liststore.clear()
            self.treeview.set_model(liststore)

    def fill_treeview(self, content_list, column_types_list, set_cursor=0,
                      set_cursor_weight=400, first_item_is_col_name=False,
                      append_to_existing=False, append_to_top=False, font_size=10000,
                      fixed_img_height=None):
        '''
        General function to fill a treeview
        Set set_cursor_weight to 400 if you don't want bold font
        '''
        # Check if this is a multi-dimensional array
        multi_cols = self.is_list_of_lists(content_list)
        col_name_list = []

        if len(content_list) == 0:
            # Empty treeview
            self.clear_tree_view()
        else:
            liststore = self.treeview.get_model()
            if liststore is None:
                # Dirty but need to dynamically create a list store
                dyn_list_store = 'Gtk.ListStore('
                for i, i_val in enumerate(column_types_list):
                    dyn_list_store += i_val + ', '
                dyn_list_store += 'int, int)'
                msg = f"Create list store eval string: {dyn_list_store}"
                print(msg)
                if self.log:
                    self.log.write(msg, 'self.treeview.fill_treeview', 'debug')
                liststore = eval(dyn_list_store)
            else:
                if not append_to_existing:
                    # Existing list store: clear all rows and columns
                    msg = "Clear existing list store"
                    print(msg)
                    if self.log:
                        self.log.write(msg, 'self.treeview.fill_treeview', 'debug')
                    liststore.clear()
                    for col in self.treeview.get_columns():
                        self.treeview.remove_column(col)

            # Create list with column names
            if multi_cols:
                for i, i_val in enumerate(content_list[0]):
                    if first_item_is_col_name:
                        msg = f"First item is column name (multi-column list): {i_val}"
                        print(msg)
                        if self.log:
                            self.log.write(msg, 'self.treeview.fill_treeview', 'debug')
                        col_name_list.append(i_val)
                    else:
                        col_name_list.append('Column ' + str(i))
            else:
                if first_item_is_col_name:
                    msg = f"First item is column name (single-column list): {content_list[0][0]}"
                    print(msg)
                    if self.log:
                        self.log.write(msg, 'self.treeview.fill_treeview', 'debug')
                    col_name_list.append(content_list[0])
                else:
                    col_name_list.append('Column 0')

            msg = f"Create column names: {str(col_name_list)}"
            print(msg)
            if self.log:
                self.log.write(msg, 'self.treeview.fill_treeview', 'debug')

            # Add data to the list store
            for i, i_val in enumerate(content_list):
                # Skip first row if that is a column name
                skip = False
                if first_item_is_col_name and i == 0:
                    msg = "First item is column name: skip first item"
                    print(msg)
                    if self.log:
                        self.log.write(msg, 'self.treeview.fill_treeview', 'debug')
                    skip = True

                if not skip:
                    weight = 400
                    weight_row = set_cursor
                    if first_item_is_col_name:
                        weight_row += 1
                    if i == weight_row:
                        weight = set_cursor_weight
                    if multi_cols:
                        # Dynamically add data for multi-column list store
                        if append_to_top:
                            dyn_list_store_append = 'liststore.insert(0, ['
                        else:
                            dyn_list_store_append = 'liststore.append(['
                        for j, val in enumerate(i_val):
                            if str(column_types_list[j]) == 'str':
                                # Make sure it's a single line
                                val = ('"' + val.replace('\n', ' ')
                                                .replace('\r', '')
                                                .replace('"', '\\"') + '"')
                            if str(column_types_list[j]) == 'GdkPixbuf.Pixbuf':
                                if os.path.isfile(val):
                                    if fixed_img_height:
                                        pb = GdkPixbuf.Pixbuf.new_from_file(val)
                                        nw = pb.get_width() * (fixed_img_height / pb.get_height())
                                        val = f'GdkPixbuf.Pixbuf.new_from_file("{val}").scale_simple({nw}, {fixed_img_height}, GdkPixbuf.InterpType.BILINEAR)'
                                    else:
                                        val = f'GdkPixbuf.Pixbuf.new_from_file("{val}")'
                                else:
                                    val = None
                            dyn_list_store_append += f'{val}, '
                        dyn_list_store_append += f'{str(weight)}, {font_size}])'

                        msg = f"Add data to list store: {dyn_list_store_append}"
                        print(msg)
                        if self.log:
                            self.log.write(msg, 'self.treeview.fill_treeview', 'debug')
                        eval(dyn_list_store_append)
                    else:
                        if append_to_top:
                            msg = f"Add data to top of list store: {str(i_val)}"
                            print(msg)
                            if self.log:
                                self.log.write(msg, 'self.treeview.fill_treeview', 'debug')
                            liststore.insert(0, [i_val, weight, font_size])
                        else:
                            msg = f"Add data to bottom of list store: {str(i_val)}"
                            print(msg)
                            if self.log:
                                self.log.write(msg, 'self.treeview.fill_treeview', 'debug')
                            liststore.append([i_val, weight, font_size])

            # Create columns
            for i, i_val in enumerate(col_name_list):
                # Create a column only if it does not exist
                col_found = ''
                cols = self.treeview.get_columns()
                for col in cols:
                    if col.get_title() == i_val:
                        col_found = col.get_title()
                        break

                if col_found == '':
                    # Build renderer and attributes to define the column
                    # Possible attributes for text: text, foreground, background, weight
                    attr = (', text=' + str(i) + ', weight=' + str(len(col_name_list)) +
                            ', size=' + str(len(col_name_list) + 1))
                    # an object that renders text into a Gtk.TreeView cell
                    renderer = 'Gtk.CellRendererText()'
                    if str(column_types_list[i]) == 'bool':
                        # an object that renders a toggle button into a TreeView cell
                        renderer = 'Gtk.CellRendererToggle()'
                        attr = ', active=' + str(i)
                    if str(column_types_list[i]) == 'GdkPixbuf.Pixbuf':
                        # an object that renders a pixbuf into a Gtk.TreeView cell
                        renderer = 'Gtk.CellRendererPixbuf()'
                        attr = ', pixbuf=' + str(i)
                    dyn_col = 'Gtk.TreeViewColumn("' + str(i_val) + '", ' + renderer + attr + ')'

                    msg = f"Create column: {dyn_col}"
                    print(msg)
                    if self.log:
                        self.log.write(msg, 'self.treeview.fill_treeview', 'debug')
                    col = eval(dyn_col)

                    # Get the renderer of the column and add type specific properties
                    rend = col.get_cells()[0]
                    #if str(column_types_list[i]) == 'str':
                        # TODO: Right align text in column - add parameter to function
                        #rend.set_property('xalign', 1.0)
                    if str(column_types_list[i]) == 'bool':
                        # If checkbox column, add toggle function
                        msg = "Check box found: add toggle function"
                        print(msg)
                        if self.log:
                            self.log.write(msg, 'self.treeview.fill_treeview', 'debug')
                        rend.connect('toggled', self.tvchk_on_toggle, liststore, i)

                    # Let the last colum fill the treeview
                    if i == len(col_name_list):
                        msg = f"Last column fills treeview: {i}"
                        print(msg)
                        if self.log:
                            self.log.write(msg, 'self.treeview.fill_treeview', 'debug')
                        col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)

                    # Finally add the column
                    self.treeview.append_column(col)
                    msg = f"Column added: {col.get_title()}"
                    print(msg)
                    if self.log:
                        self.log.write(msg, 'self.treeview.fill_treeview', 'debug')
                else:
                    msg = f"Column already exists: {col_found}"
                    print(msg)
                    if self.log:
                        self.log.write(msg, 'self.treeview.fill_treeview', 'debug')

            # Add liststore, set cursor and set the headers
            self.treeview.set_model(liststore)
            if set_cursor >= 0:
                self.treeview.set_cursor(set_cursor)
            self.treeview.set_headers_visible(first_item_is_col_name)
            if self.log:
                self.log.write("Add Liststore to Treeview", 'self.treeview.fill_treeview', 'debug')

            # Scroll to selected cursor
            selection = self.treeview.get_selection()
            tm, tree_iter = selection.get_selected()
            if tree_iter:
                path = tm.get_path(tree_iter)
                self.treeview.scroll_to_cell(path)
                msg = f"Scrolled to selected row: {set_cursor}"
                print(msg)
                if self.log:
                    self.log.write(msg, 'self.treeview.fill_treeview', 'debug')

    def tvchk_on_toggle(self, cell, path, liststore, col_nr, *ignore):
        '''
        Raise trigger checkbox-toggled when checkbox is clicked.
        Parameters: path, column number, toggle value
        '''
        if path is not None:
            itr = liststore.get_iter(path)
            toggled = liststore[itr][col_nr]
            liststore[itr][col_nr] = not toggled
            self.emit('checkbox-toggled', path, col_nr, not toggled)

    def get_selected_value(self, col_nr=0):
        '''
        Get the selected value in a treeview.
        Assume single row selection
        '''
        val = None
        (model, pathlist) = self.treeview.get_selection().get_selected_rows()
        if model is not None and pathlist:
            val = model.get_value(model.get_iter(pathlist[0]), col_nr)
        return val

    def get_selected_rows(self):
        '''
        Get the selected rows.
        Assume single row selection
        '''
        rows = []
        cols_nr = self.get_column_count()
        (model, pathlist) = self.treeview.get_selection().get_selected_rows()
        if model is not None:
            for path in pathlist:
                row = []
                for n in range(0, cols_nr):
                    row.append(model.get_value(model.get_iter(path), n))
                rows.append([path, row])
        return rows

    def get_value(self, path, col_nr=0):
        ''' Get the value for a specific path (= row number). '''
        val = None
        model = self.treeview.get_model()
        path = int(path)
        if model is not None and path >= 0:
            val = model.get_value(model.get_iter(path), col_nr)
        return val

    def select_value(self, value, col_nr=0):
        ''' Select the row with a specific value. '''
        if value is not None:
            value = value.strip()
            model = self.treeview.get_model()
            if model is not None:
                i = 0
                itr = model.get_iter_first()
                while itr is not None:
                    if model.get_value(itr, col_nr).strip() == value:
                        self.treeview.set_cursor(i)
                        break
                    i += 1
                    itr = model.iter_next(itr)

    def get_column_values(self, col_nr=0):
        ''' Return all the values in a given column. '''
        cv = []
        model = self.treeview.get_model()
        if model is not None:
            itr = model.get_iter_first()
            while itr is not None:
                cv.append(model.get_value(itr, col_nr))
                itr = model.iter_next(itr)
        return cv

    def get_row_count(self, startIter=None):
        '''
        Return the number of rows counted from iter
        If iter is None, all rows are counted
        '''
        nr = 0
        model = self.treeview.get_model()
        if model is not None:
            nr = model.iter_n_children(startIter)
        return nr

    def get_column_count(self):
        ''' Return the number of columns. '''
        return self.treeview.get_model().get_n_columns()

    def del_row(self, row_nr=None):
        ''' Delete row by number from treeview. '''
        if row_nr is None:
            (model, path_list) = self.treeview.get_selection().get_selected_rows()
            for path in path_list:
                it = model.get_iter(path)
                model.remove(it)
        else:
            model = self.treeview.get_model()
            it = model.get_iter(row_nr)
            model.remove(it)

    def add_row(self, row_list):
        ''' Add row list to treeview. '''
        model = self.treeview.get_model()
        model.append(row_list)
        self.treeview.set_model(model)

    def get_toggled_values(self, toggle_col_nr=0, value_col_nr=1):
        ''' Return checkbox values of treeview. '''
        values = []
        model = self.treeview.get_model()
        if model is not None:
            itr = model.get_iter_first()
            while itr is not None:
                if model[itr][toggle_col_nr]:
                    values.append(model[itr][value_col_nr])
                itr = model.iter_next(itr)
        return values

    def treeview_toggle_rows(self, toggle_col_nr_list, path_list=None):
        ''' Toggle check box in row. '''
        if path_list is None:
            (model, path_list) = self.treeview.get_selection().get_selected_rows()
        else:
            model = self.treeview.get_model()
        # Toggle the check boxes in the given column in the selected rows (=path_list)
        if model is not None:
            for path in path_list:
                for col_nr in toggle_col_nr_list:
                    it = model.get_iter(path)
                    model[it][col_nr] = not model[it][col_nr]

    def treeview_toggle_all(self, toggle_col_nr_list, toggle_value=False,
                            exclude_col_nr=-1, exclude_value=''):
        '''
        Toggle all given rows in treeview
        '''
        model = self.treeview.get_model()
        if model is not None:
            itr = model.get_iter_first()
            while itr is not None:
                for col_nr in toggle_col_nr_list:
                    if exclude_col_nr >= 0:
                        excl_val = model.get_value(itr, exclude_col_nr)
                        if excl_val != exclude_value:
                            model[itr][col_nr] = toggle_value
                    else:
                        model[itr][col_nr] = toggle_value
                    itr = model.iter_next(itr)

    def is_list_of_lists(self, lst):
        ''' Check if list contains lists. '''
        return len(lst) == len([x for x in lst if isinstance(x, list)])

# Register the class
GObject.type_register(TreeViewHandler)


# TODO - implement clickable image in TreeViewHandler
# http://www.daa.com.au/pipermail/pygtk/2010-March/018355.html
#class CellRendererPixbufXt(Gtk.CellRendererPixbuf):
    #"""docstring for CellRendererPixbufXt"""
    #__gproperties__ = {'active-state':
                        #(GObject.TYPE_STRING, 'pixmap/active widget state',
                        #'stock-icon name representing active widget state',
                        #None, GObject.PARAM_READWRITE)}
    #__gsignals__ = {'clicked':
                        #(GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, ()), }
    #states = [None, Gtk.STOCK_APPLY, Gtk.STOCK_CANCEL]

    #def __init__(self):
        #Gtk.CellRendererPixbuf.__init__(self)

    #def do_get_property(self, property):
        #"""docstring for do_get_property"""
        #if property.name == 'active-state':
            #return self.active_state
        #else:
            #raise AttributeError('unknown property %s' % property.name)

    #def do_set_property(self, property, value):
        #if property.name == 'active-state':
            #self.active_state = value
        #else:
            #raise AttributeError('unknown property %s' % property.name)
