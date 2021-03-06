# -*- coding: utf-8 -*-
# EditXT
# Copyright 2007-2014 Daniel Miller <millerdev@gmail.com>
#
# This file is part of EditXT, a programmer's text editor for Mac OS X,
# which can be found at http://editxt.org/.
#
# EditXT is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# EditXT is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EditXT.  If not, see <http://www.gnu.org/licenses/>.
import logging
import os

import AppKit as ak
import Foundation as fn
# from NDAlias import NDAlias

import editxt.constants as const
import editxt.platform.constants as platform_const

from editxt.command.find import Finder, FindOptions
from editxt.command.util import change_indentation, replace_newlines
from editxt.constants import LARGE_NUMBER_FOR_TEXT
from editxt.controls.alert import Alert
from editxt.document import DocumentController, Error as DocumentError
from editxt.platform.document import setup_main_view, teardown_main_view
from editxt.platform.kvo import KVOList, KVOProxy, KVOLink
from editxt.util import register_undo_callback, user_path, WeakProperty

log = logging.getLogger(__name__)


def document_property(do):
    name = do.__name__
    def fget(self):
        if self.document is None:
            return None
        return getattr(self.document, name)
    def fset(self, value):
        old = getattr(self.document, name)
        if value != old:
            do(self, value, old)
    return property(fget, fset)


class Editor(object):
    """Editor

    Reference graph:
        strong:
            app -> window -> KVOProxy(project) -> KVOProxy(self)
        weak:
            self -> project -> window -> app
    """

    id = None # will be overwritten (put here for type api compliance for testing)
    _project = WeakProperty()
    is_leaf = True

    def __init__(self, project, *, document=None, path=None, state=None):
        if state is not None:
            if "internal" in state:
                app = project.window.app
                document = app.get_internal_document(state["internal"])
            else:
                assert document is None, (state, document)
                assert path is None, (state, path)
                path = state["path"]
        if path is not None:
            assert document is None, (path, document)
        if document is None:
            document = project.window.app.document_with_path(path)
            assert document is not None, (project, path, state)
        self.editors = KVOList.alloc().init()
        self.id = next(DocumentController.id_gen)
        self._project = project
        self.document = document
        self.proxy = KVOProxy(self)
        self.main_view = None
        self.text_view = None
        self.scroll_view = None
        self.command_view = None
        self._goto_line = None
        props = document.props
        self.kvolink = KVOLink([
            (self.proxy, "icon", self.proxy, "summary_info"),
            (self.proxy, "name", self.proxy, "summary_info"),
            (self.proxy, "is_dirty", self.proxy, "summary_info"),
            (props, "is_dirty", self.proxy, "is_dirty"),
            (props, "indent_mode", self.proxy, "indent_mode"),
            (props, "indent_size", self.proxy, "indent_size"),
            (props, "newline_mode", self.proxy, "newline_mode"),
            (props, "syntaxdef", self.proxy, "syntaxdef"),
            (props, "character_encoding", self.proxy, "character_encoding"),
            (props, "highlight_selected_text", self.proxy, "highlight_selected_text"),
        ])
        if state is not None:
            self.edit_state = state

    def icon(self):
        return self.document.icon()

    @property
    def app(self):
        return self.project.window.app

    @property
    def project(self):
        """Get/set this editor's project

        The setter will remove this editor from it's previous project's
        editors if it is found there.
        """
        return self._project
    @project.setter
    def project(self, new):
        old = getattr(self, "_project", None)
        if old is not None:
            old.remove(self)
        self._project = new

    @property
    def name(self):
        return self.document.name

    @property
    def summary_info(self):
        """Returns a 4-tuple: ``icon, name, is_dirty, self``"""
        return (self.icon, self.name, self.is_dirty, self)

    @property
    def undo_manager(self):
        return self.document.undo_manager

    def window(self):
        """Return the native window of this view (NOT a editxt.window.Window)"""
        if self.scroll_view is not None:
            return self.scroll_view.window()
        return None

    @property
    def file_path(self):
        return self.document.file_path
    @file_path.setter
    def file_path(self, value):
        self.document.file_path = value

    @property
    def selection(self):
        if self.text_view is None:
            return None
        return self.text_view.selectedRange()

    @property
    def is_dirty(self):
        return self.document.is_dirty()

    def short_path(self, name=True):
        path = self.file_path
        if not name:
            path = os.path.dirname(path)
        if self.project.path and path.startswith(self.project.path + os.path.sep):
            path = path[len(self.project.path) + 1:]
        return user_path(path)

    def dirname(self):
        """Return a tuple: (directory, filename or None)"""
        if self.file_path and os.path.isabs(self.file_path):
            return os.path.dirname(self.file_path)
        return self.project.dirname()

    def save(self, prompt=False, callback=(lambda saved:None)):
        """Save the document to disk

        Possible UI interactions:
        - get file path if the file has not been saved.
        - ask to overwrite existing file if file has not been opened from or
          saved to its current file_path before.
        - ask to overwrite if the file has changed on disk and there has been
          no subsequent prompt to reload.

        :param prompt: Optional boolean argument, defaults to False.
        Unconditionally prompt for new save location if True.
        :param callback: Optional callback to be called with the save result
        of the save operation (True if successful else False).
        """
        document = self.document
        window = self.project.window
        def save_with_path(path):
            saved = False
            try:
                if path is not None:
                    if document.file_path != path:
                        document.file_path = path
                    document.save()
                    saved = True
                    if self.text_view is not None:
                        self.text_view.breakUndoCoalescing()
            except DocumentError as err:
                log.error(err)
            except Exception:
                log.exception("cannot save %s", path)
            finally:
                callback(saved)
        if prompt or not document.has_real_path():
            window.save_document_as(self, save_with_path)
        elif document.file_changed_since_save():
            window.prompt_to_overwrite(self, save_with_path)
        else:
            save_with_path(document.file_path)

    def should_close(self, callback):
        """Check if the document can be closed

        Prompt for save, discard, or cancel if the document is dirty and call
        ``callback(<should close>)`` once the appropriate action has been
        performed. Otherwise call ``callback(True)``. The callback may raise an
        exception; if it does it must be allowed to propagate to continue the
        termination sequence.
        """
        if not self.is_dirty:
            callback(True)
            return
        def save_discard_or_cancel(save):
            """Save, discard, or cancel the current operation

            :param save: True => save, False => discard, None => cancel
            """
            if save:
                self.save(callback=callback)
            else:
                callback(save is not None)
        document = self.document
        save_as = not document.has_real_path()
        self.project.window.prompt_to_close(self, save_discard_or_cancel, save_as)

    def set_main_view_of_window(self, view, window):
        frame = view.bounds()
        if self.scroll_view is None:
            self.main_view = setup_main_view(self, frame)
            self.scroll_view = self.main_view.top
            self.command_view = self.main_view.bottom
            self.text_view = self.scroll_view.documentView() # HACK deep reach
            self.soft_wrap = self.document.app.config["soft_wrap"]
            self.reset_edit_state()
            if self._goto_line is not None:
                self.text_view.goto_line(self._goto_line)
        else:
            self.main_view.setFrame_(frame)
        view.addSubview_(self.main_view)
        window.makeFirstResponder_(self.text_view)
        self.document.update_syntaxer()
        self.scroll_view.verticalRulerView().invalidateRuleThickness()
        self.document.check_for_external_changes(window)

    def _get_soft_wrap(self):
        if self.text_view is None or self.text_view.textContainer() is None:
            return None
        wrap = self.text_view.textContainer().widthTracksTextView()
        return const.WRAP_WORD if wrap else const.WRAP_NONE
    def _set_soft_wrap(self, value):
        wrap = value != const.WRAP_NONE
        tv = self.text_view
        tc = tv.textContainer()
        if wrap:
            mask = ak.NSViewWidthSizable
            size = self.scroll_view.contentSize()
            width = size.width
        else:
            mask = ak.NSViewWidthSizable | ak.NSViewHeightSizable
            width = LARGE_NUMBER_FOR_TEXT
        # TODO
        # if selection is visible:
        #     get position of selection
        # else:
        #     get position top visible line
        tc.setContainerSize_(fn.NSMakeSize(width, LARGE_NUMBER_FOR_TEXT))
        tc.setWidthTracksTextView_(wrap)
        tv.setHorizontallyResizable_(not wrap)
        tv.setAutoresizingMask_(mask)
        if wrap:
            #tv.setConstrainedFrameSize_(size) #doesn't seem to work
            tv.setFrameSize_(size)
            tv.sizeToFit()
        # TODO
        # if selection was visible:
        #     put selection as near to where it was as possible
        # else:
        #     put top visible line at the top of the scroll view
    soft_wrap = property(_get_soft_wrap, _set_soft_wrap)

    @document_property
    def indent_size(self, new, old):
        mode = self.document.indent_mode
        if mode == const.INDENT_MODE_TAB:
            self.change_indentation(mode, old, mode, new, True)
        elif new != old:
            self.document.props.indent_size = new

    @document_property
    def indent_mode(self, new, old):
        if new != old:
            self.document.props.indent_mode = new

    @document_property
    def newline_mode(self, new, old):
        undoman = self.undo_manager
        if not (undoman.isUndoing() or undoman.isRedoing()):
            replace_newlines(self.text_view, const.EOLS[new])
        self.document.props.newline_mode = new
        def undo():
            self.proxy.newline_mode = old
        register_undo_callback(undoman, undo)

    @document_property
    def syntaxdef(self, new, old):
        self.document.syntaxdef = new

    @document_property
    def character_encoding(self, new, old):
        self.document.character_encoding = new

    @document_property
    def highlight_selected_text(self, new, old):
        if not new:
            self.finder.mark_occurrences("")
        self.document.highlight_selected_text = new

    def change_indentation(self, old_mode, old_size, new_mode, new_size, convert_text):
        if convert_text:
            old_indent = "\t" if old_mode == const.INDENT_MODE_TAB else (" " * old_size)
            new_indent = "\t" if new_mode == const.INDENT_MODE_TAB else (" " * new_size)
            change_indentation(self.text_view, old_indent, new_indent, new_size)
        if old_mode != new_mode:
            self.document.props.indent_mode = new_mode
        if old_size != new_size:
            self.document.props.indent_size = new_size
        if convert_text or convert_text is None:
            def undo():
                self.change_indentation(new_mode, new_size, old_mode, old_size, None)
            register_undo_callback(self.undo_manager, undo)

    def _get_edit_state(self):
        if self.text_view is not None:
            sel = self.selection
            sp = self.scroll_view.contentView().bounds().origin
            state = dict(
                selection=[sel.location, sel.length],
                scrollpoint=[sp.x, sp.y],
                soft_wrap=self.soft_wrap,
            )
        else:
            state = dict(getattr(self, "_state", {}))
        if self.document is self.app.errlog.document \
                and not self.document.has_real_path():
            state["internal"] = "errlog"
        else:
            assert self.file_path is not None, repr(self)
            state["path"] = str(self.file_path)
            state.pop("internal", None)
        return state
    def _set_edit_state(self, state):
        if self.text_view is not None:
            point = state.get("scrollpoint", [0, 0])
            sel = state.get("selection", [0, 0])
            self.proxy.soft_wrap = state.get("soft_wrap", const.WRAP_NONE)
            length = self.document.text_storage.length() - 1
            if length > 0:
                # HACK next line does not seem to work without this
                self.text_view.setSelectedRange_(fn.NSRange(length, 0))
            self.scroll_view.documentView().scrollPoint_(fn.NSPoint(*point))
            if sel[0] < length:
                if sel[0] + sel[1] > length:
                    sel = (sel[0], length - sel[0])
                self.text_view.setSelectedRange_(fn.NSRange(*sel))
        else:
            self._state = state
    edit_state = property(_get_edit_state, _set_edit_state)

    def reset_edit_state(self):
        state = getattr(self, "_state", None)
        if state is not None:
            self.edit_state = state
            del self._state

    def message(self, msg, msg_type=const.INFO):
        """Display a message in the command view"""
        self.command_view.message(msg, self.text_view, msg_type)

    def goto_line(self, line):
        if self.text_view is None:
            self._goto_line = line
        else:
            self.text_view.goto_line(line)

    def interactive_close(self, do_close):
        """Close this editor if the user agrees to do so

        :param do_close: A function to be called to close the document.
        """
        def last_editor_of_document():
            return all(editor is self
                for editor in self.app.iter_editors_of_document(self.document))
        if self.is_dirty and last_editor_of_document():
            def callback(should_close):
                if should_close:
                    do_close()
            self.should_close(callback)
        else:
            do_close()

    def close(self):
        project = self.project
        doc = self.document
        self.project = None # removes editor from project.editors
        if self.text_view is not None and doc.text_storage is not None:
            doc.text_storage.removeLayoutManager_(self.text_view.layoutManager())
        if all(e is self for e in doc.app.iter_editors_of_document(doc)):
            doc.close()
        self.document = None
        if self.main_view is not None:
            teardown_main_view(self.main_view)
            self.main_view = None
        self.text_view = None
        self.scroll_view = None
        self.command_view = None
        self.proxy = None

    def __repr__(self):
        name = 'N/A' if self.document is None else self.name
        return '<%s 0x%x name=%s>' % (type(self).__name__, id(self), name)

    # TextView delegate ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    @property
    def finder(self):
        try:
            finder = self._finder
        except Exception:
            finder = self._finder = Finder(
                (lambda:self.text_view),
                FindOptions(ignore_case=False, wrap_around=False),
                self.document.app,
            )
        return finder

    def on_do_command(self, command):
        if command == platform_const.ESCAPE and self.command_view is not None:
            if self.command_view:
                self.command_view.dismiss()
            else:
                self.command_view.show_last_message()
            return True
        return False

    def on_selection_changed(self, textview):
        text = textview.string()
        range = textview.selectedRange()
        index = range.location if range.location < text.length() else (text.length() - 1)
        line = self.scroll_view.verticalRulerView().line_number_at_char_index(index)
        i = index
        while i > 0 and text[i - 1] != "\n":
            i -= 1
        col = (index - i)
        sel = range.length
        self.scroll_view.status_view.updateLine_column_selection_(line, col, sel)

        if self.document.highlight_selected_text:
            ftext = text.substringWithRange_(range)
            if len(ftext.strip()) < 3 or " " in ftext:
                ftext = ""
            self.finder.mark_occurrences(ftext)

