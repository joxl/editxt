# -*- coding: utf-8 -*-
# EditXT
# Copywrite (c) 2007-2010 Daniel Miller <millerdev@gmail.com>
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

name = "EditXT Log"
filepatterns = ["EditXT Log"]
comment_token = "x"
word_groups = [
    ([RE("[a-zA-Z.]+ DEBUG - ")], "808080"),
    ([RE("[a-zA-Z.]+ INFO - ")], "008080"),
    ([RE("[a-zA-Z.]+ WARNING - ")], "E89E28"),
    ([RE("[a-zA-Z.]+ ERROR - ")], "FF0000"),
    ([RE("[a-zA-Z.]+ CRITICAL - ")], "FF0000"),
]
