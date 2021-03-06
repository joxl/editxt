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

from .treeview import (
    OutlineView,
    HoverButtonCell,
    BUTTON_STATE_HOVER,
    BUTTON_STATE_NORMAL,
    BUTTON_STATE_PRESSED,
)

from .commandview import CommandView
from .listview import ListView


def screen_rect(view, rect=None):
    """Convert view rect to screen coordinates"""
    if rect is None:
        rect = view.bounds()
    window_rect = view.convertRect_toView_(rect, None)
    return view.window().convertRectToScreen_(window_rect)
