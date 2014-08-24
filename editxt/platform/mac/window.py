# -*- coding: utf-8 -*-
# EditXT
# Copyright 2007-2013 Daniel Miller <millerdev@gmail.com>
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

import objc
import AppKit as ak
import Foundation as fn
from PyObjCTools import AppHelper

from editxt.controls.alert import Alert
from editxt.editor import Editor
from editxt.platform.views import BUTTON_STATE_NORMAL
from editxt.util import untested, representedObject, user_path, WeakProperty

log = logging.getLogger(__name__)


class WindowController(ak.NSWindowController):

    # 2013-11-23 08:56:28.994 EditXTDev[47194:707] An instance 0x10675fc30 of
    # class _KVOList was deallocated while key value observers were still
    # registered with it. Observation info was leaked, and may even become
    # mistakenly attached to some other object. Set a breakpoint on
    # NSKVODeallocateBreak to stop here in the debugger.
    #window_ = WeakProperty()

    docsController = objc.IBOutlet()
    docsScrollview = objc.IBOutlet()
    docsView = objc.IBOutlet()
    mainView = objc.IBOutlet()
    splitView = objc.IBOutlet()
    plusButton = objc.IBOutlet()
    propsView = objc.IBOutlet()
    propsViewButton = objc.IBOutlet()
    #propCharacterEncoding = objc.IBOutlet()
    #propLanguageSelector = objc.IBOutlet()
    #propLineEndingType = objc.IBOutlet()
    #propTabSpacesInput = objc.IBOutlet()
    #propTabSpacesSelector = objc.IBOutlet()
    #propWrapLines = objc.IBOutlet()

    def __new__(cls, window):
        wc = cls.alloc().initWithWindowNibName_("EditorWindow")
        wc.window_ = window
        wc.save_as_caller = None
        return wc

    def windowDidLoad(self):
        self.window_.window_did_load()

    def characterEncodings(self):
        return fn.NSValueTransformer.valueTransformerForName_("CharacterEncodingTransformer").names

    def setCharacterEncodings_(self, value):
        pass

    def syntaxDefNames(self):
        return [d.name for d in self.window_.app.syntaxdefs]

    def setSyntaxDefNames_(self, value):
        pass

    def projects(self):
        return self.window_.projects

    def save_(self, sender):
        self.window_.save()

    def saveAs_(self, sender):
        self.window_.save_as()

    def newProject_(self, sender):
        self.window_.new_project()

    def togglePropertiesPane_(self, sender):
        self.window_.toggle_properties_pane()

    def outlineViewSelectionDidChange_(self, notification):
        self.window_.selected_editor_changed()

    def outlineViewItemDidCollapse_(self, notification):
        representedObject(notification.userInfo()["NSObject"]).expanded = False

    def outlineViewItemDidExpand_(self, notification):
        representedObject(notification.userInfo()["NSObject"]).expanded = True

    def outlineView_shouldSelectItem_(self, outlineview, item):
        return self.window_.should_select_item(outlineview, item)

    def outlineView_willDisplayCell_forTableColumn_item_(self, view, cell, col, item):
        if col.identifier() == "name":
            cell.setImage_(representedObject(item).icon())

    def outlineView_shouldEditTableColumn_item_(self, view, col, item):
        return self.window_.should_edit_item(col, item)

    def outlineView_toolTipForCell_rect_tableColumn_item_mouseLocation_(
        self, view, cell, rect, col, item, mouseloc):
        return self.window_.tooltip_for_item(view, item), rect

    def hoverButton_rowClicked_(self, cell, row):
        self.window_.close_button_clicked(row)

    @untested
    def hoverButtonCell_imageForState_row_(self, cell, state, row):
        from editxt.window import BUTTON_STATE_SELECTED
        if state is BUTTON_STATE_NORMAL and self.docsView.isRowSelected_(row):
            state = BUTTON_STATE_SELECTED
        if row >= 0 and row < self.docsView.numberOfRows():
            item = self.docsView.itemAtRow_(row)
            doc = self.docsView.realItemForOpaqueItem_(item)
            if doc is not None and doc.is_dirty:
                return self.dirtyImages[state]
        return self.cleanImages[state]

    def setup_current_editor(self, editor):
        """Setup the current editor in the window

        :returns: True if the editor was setup, otherwise False.
        """
        main_view = self.mainView
        if editor is not None:
            sel = self.docsController.selected_objects
            if not sel or sel[0] is not editor:
                self.docsController.selected_objects = [editor]
            if isinstance(editor, Editor): # TODO eliminate isinstance call
                if editor.main_view not in main_view.subviews():
                    for subview in main_view.subviews():
                        subview.removeFromSuperview()
                    editor.set_main_view_of_window(main_view, self.window())
                    #self.setDocument_(editor.document)
                    return True
        #else:
        #    self.window().setTitle_(editor.name)
        #    log.debug("self.window().setTitle_(%r)", editor.name)
        for subview in main_view.subviews():
            subview.removeFromSuperview()
        self.setDocument_(None)
        return False

    def undo_manager(self):
        return self.window_.undo_manager()

    def windowTitleForDocumentDisplayName_(self, name):
        editor = self.window_.current_editor
        if editor is not None and editor.file_path is not None:
            return user_path(editor.file_path)
        return name

    def windowDidBecomeKey_(self, notification):
        self.window_.window_did_become_key(notification.object())

    def windowShouldClose_(self, window):
        return self.window_.window_should_close(window)

    def windowWillClose_(self, notification):
        self.window_.window_will_close()

    def save_document_as(self, directory, filename, save_with_path):
        panel = NSSavePanel.alloc().init()
        panel.setShowsHiddenFiles_(True)
        panel.setExtensionHidden_(False)
        panel.setTreatsFilePackagesAsDirectories_(True)
        assert self.save_as_caller == None, "window cannot save two files at once"
        def callback(sheet, code):
            if code == ak.NSOKButton:
                path = sheet.URL().fileSystemRepresentation()
                save_with_path(path)
            self.save_as_caller = None
        self.save_as_caller = SaveAsCaller.alloc().init(callback)
        panel.beginSheetForDirectory_file_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
            directory, filename, window,
            self.save_as_caller, "savePanelDidEnd:returnCode:contextInfo:", 0)

    def prompt_to_overwrite(self, file_path, save_with_path, save_as, diff_with_original):
        self.alert = alert = Alert.alloc().init()
        alert.setAlertStyle_(ak.NSInformationalAlertStyle)
        message = ("Replace “{}”?").format(file_path)
        alert.setMessageText_("The file has been modified by another program.")
        alert.setInformativeText_(infotext)
        alert.addButtonWithTitle_("Save As...")
        alert.addButtonWithTitle_("Replace")
        # may need to use .objectAtIndex_(1) instead of [1]
        # http://stackoverflow.com/questions/16627894/how-to-make-the-nsalerts-2nd-button-the-return-button
        alert.buttons()[1].setKeyEquivalent_(" ") # space bar -> replace
        diff = diff_with_original is not None
        if diff:
            alert.addButtonWithTitle_("Diff")
            alert.buttons()[2].setKeyEquivalent_("d")
        alert.addButtonWithTitle_("Cancel")
        def respond(response):
            if response == ak.NSAlertFirstButtonReturn:
                save_as()
            elif response == ak.NSAlertSecondButtonReturn:
                save_with_path(file_path)
            elif diff and response == ak.NSAlertThirdButtonReturn:
                diff_with_original()
        alert.beginSheetModalForWindow_withCallback_(window, respond)

    # outlineview datasource methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def outlineView_writeItems_toPasteboard_(self, view, items, pboard):
        return self.window_.write_items_to_pasteboard(view, items, pboard)

    def outlineView_acceptDrop_item_childIndex_(self, view, info, item, index):
        parent = None if item is None else representedObject(item)
        return self.window_.accept_drop(
            view, info.draggingPasteboard(), parent, index)

    def outlineView_validateDrop_proposedItem_proposedChildIndex_(self, view, info, item, index):
        return self.window_.validate_drop(view, info, item, index)

    # def outlineView_namesOfPromisedFilesDroppedAtDestination_forDraggedItems_(
    #   self, view, names, items):
    #   item = representedObject(item)
    #   raise NotImplementedError

    # the following are dummy implementations since we are using bindings (they
    # are required since we are using NSOutlineView's drag/drop datasource methods)
    # see: http://theocacao.com/document.page/130

    def outlineView_child_ofItem_(self, view, index, item):
        return None

    def outlineView_isItemExpandable_(self, view, item):
        return False

    def outlineView_numberOfChildrenOfItem_(self, view, item):
        return 0

    def outlineView_objectValueForTableColumn_byItem_(self, view, col, item):
        return None


class SaveAsCaller(fn.NSObject):

    @objc.namedSelector(b"init:")
    def init(self, callback):
        self = super(SaveAsCaller, self).init()
        self.callback = callback
        return self

    @objc.typedSelector(b'v@:@ii')
    def savePanelDidEnd_returnCode_contextInfo_(self, sheet, code, context):
        self.callback(sheet, code)
