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
import re

import editxt.constants as const
from editxt.command.base import command, CommandError
from editxt.command.parser import (CommandParser, Choice, CompleteWord,
    Conditional, Int, Regex, String, Error)
from editxt.command.util import has_editor
from editxt.editor import Editor
from editxt.platform.app import beep
from editxt.platform.constants import KEY

log = logging.getLogger(__name__)


class EditorTreeItem(String):

    NO_MATCH = const.Constant("no match")

    def __init__(self, *args, editor=None, **kw):
        super().__init__(*args, **kw)
        self.editor = editor
        self.completions = {} if editor is not None else None

    def with_context(self, editor):
        return EditorTreeItem(self.name, default=self.default, editor=editor)

    def sorted_projects(self):
        def key(item):
            primary = 0 if item[1] is current_project else 1
            return (primary, item[0])
        current_project = self.editor.project
        enum = enumerate(self.editor.project.window.projects)
        for i, project in sorted(enum, key=key):
            yield project

    @staticmethod
    def full_name(editor):
        parts = [editor.name, editor.short_path(name=False)]
        if isinstance(editor, Editor):
            parts.append(editor.project.name)
        return "::".join(p for p in parts if p is not None)

    def cached_completions(self, arg):
        key = (arg.text, arg.start)
        try:
            items = self.completions[key]
        except KeyError:
            items = self.completions[key] = self.get_completions(arg)
        return items

    def value_of(self, consumed, arg):
        if self.completions is not None and consumed:
            starts = []
            for comp in self.cached_completions(arg):
                if comp == consumed:
                    return comp.value
                if comp.startswith(consumed):
                    starts.append(comp.value)
            if starts:
                return starts[0]
            name = self.full_name
            for project in self.sorted_projects():
                if name(project) == consumed:
                    return project
                for editor in project.editors:
                    if name(editor) == consumed:
                        return editor
        if consumed:
            return self.NO_MATCH
        return self.default

    def parse_completions(self, text, index, args):
        items, end = super().parse_completions(text, index, args)
        if self.completions is not None:
            self.completions[(text, index)] = items
        return items, end

    def get_completions(self, arg):
        if self.editor is None:
            return []
        def add_completion(editor):
            word = editor.name
            if word in itemset:
                word += "::" + editor.short_path(name=False)
            if isinstance(editor, Editor) and word in itemset:
                word += "::" + editor.project.name
            if word in itemset:
                return # ignore exact match
            itemset.add(word)
            if ' ' in word:
                word = word.replace(" ", "\\ ")
            items.append(CompleteWord(word, start=0, value=editor))
        try:
            token = self.consume(arg.text, arg.start)[0] or ""
        except Error:
            return ""
        items = []
        itemset = set()
        for project in self.sorted_projects():
            if project.name.startswith(token):
                add_completion(project)
            for editor in project.editors:
                if editor.name.startswith(token):
                    add_completion(editor)
        return items

    def get_placeholder(self, arg):
        if not arg:
            return str(self)
        token = self.consume(arg.text, arg.start)[0] or ""
        comps = [word for word in self.cached_completions(arg)
                      if word.startswith(token)]
        if len(comps) == 1:
            return comps[0][len(token):]
        return ""

    def arg_string(self, value):
        if value is not None:
            value = self.full_name(value)
        return super().arg_string(value)


def no_editor(arg):
    return arg.preceding.editor is None


@command(arg_parser=CommandParser(
    EditorTreeItem("editor"),
    Conditional(no_editor, Choice(
        ("previous", const.PREVIOUS),
        ("next", const.NEXT),
        ("up", const.UP),
        ("down", const.DOWN),
        name="direction"
    )),
    Conditional(no_editor, Int("offset", default=1)),
), title="Navigate Document Tree", is_enabled=has_editor)
def doc(editor, sender, args):
    """Navigate the document tree"""
    if args is None:
        from editxt.commands import show_command_bar
        show_command_bar(editor, sender, doc.name + " ")
        return
    if args.editor is not None:
        if args.editor is not EditorTreeItem.NO_MATCH and \
                editor.project.window.focus(args.editor):
            return
    elif editor.project.window.focus(args.direction, args.offset):
        return
    beep()
