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
from __future__ import absolute_import

import inspect
import logging
import os
import re
import shutil
import tempfile
from collections import defaultdict
from contextlib import contextmanager
from nose import with_setup
import nose.tools

from editxt.util import untested

try:
    basestring
except NameError:
    basestring = str

log = logging.getLogger(__name__)


def todo_remove(obj):
    log.debug("TODO remove %r", obj)
    return obj

def unittest_print_first_failures_last():
    """monkeypatch unittest to print errors in reverse order
    which is more convenient for viewing in the console
    """
    import unittest
    old_printErrorList = unittest._TextTestResult.printErrorList
    def printErrorList(self, flavor, errors):
        return old_printErrorList(self, flavor, reversed(errors))
    unittest._TextTestResult.printErrorList = printErrorList


def eq_(a, b, text=None):
    if a != b:
        if callable(text):
            text = text()
        if isinstance(a, basestring) or len(repr(a)) > 20:
            if text is None:
                text = "not equal"
            err = "%s\n%r\n%r" % (text, a, b)
        else:
            text = (str(text) + " : ") if text is not None else ""
            err = "%s%r != %r" % (text, a, b)
        raise AssertionError(err)


def do_method_pass_through(attr, inner_obj_class, outer_obj, token, method,
        ext_args=(), int_args=None, returns=None):
    from mocker import Mocker # late import so mockerext is installed
    def inject_wc(args):
        return [(outer_obj if a is token else a) for a in args]
    if int_args is None:
        int_args = ext_args
    ext_args = inject_wc(ext_args)
    int_args = inject_wc(int_args)
    m = Mocker()
    if isinstance(method, basestring):
        method = (method, method)
    outer_method, inner_method = method
    inner_obj = m.replace(outer_obj, attr, spec=inner_obj_class)
    setattr(outer_obj, attr, inner_obj)
    getattr(inner_obj, inner_method)(*int_args) >> returns
    with m:
        rval = getattr(outer_obj, outer_method)(*ext_args)
        eq_(rval, returns)

class TestConfig(object):
    def __init__(self, *args, **kw):
        self.__dict__.update(*args, **kw)
    def __iter__(self):
        return iter(self.__dict__.items())
    def __call__(self, **kw):
        return TestConfig(self.__dict__, **kw)
    def __contains__(self, name):
        return name in self.__dict__
    def __getitem__(self, name):
        return self.__dict__[name]
    def _get(self, name, default):
        return getattr(self, name, default)
    def __len__(self):
        return len(self.__dict__)
    def __repr__(self):
        val = ", ".join("%s=%r" % kv for kv in sorted(self.__dict__.items()))
        return "(%s)" % val

@contextmanager
def replattr(*args, **kw):
    sigchk = kw.pop('sigcheck', True)
    dict_replace = kw.pop('dict', False)
    if kw:
        raise ValueError('unrecognized keyword arguments: %s' % ', '.join(kw))
    if len(args) == 3 and isinstance(args[1], basestring):
        args = [args]
    errors = []
    temps = []
    for obj, attr, value in args:
        try:
            temp = obj[attr] if dict_replace else getattr(obj, attr)
            if sigchk and (inspect.isfunction(temp) or inspect.ismethod(temp)):
                as0 = inspect.getargspec(temp)
                as1 = inspect.getargspec(value)
                if as0 != as1:
                    errors.append("%s%s != %s%s" % (
                        temp.__name__, inspect.formatargspec(*as0),
                        value.__name__, inspect.formatargspec(*as1),
                    ))
            temps.append(temp)
            if dict_replace:
                obj[attr] = value
            else:
                setattr(obj, attr, value)
        except Exception as ex:
            rtype = 'key' if dict_replace else 'attribute'
            log.error("cannot replace %s: %s", rtype, attr, exc_info=True)
            errors.append(str(ex))
    try:
        yield
    finally:
        for (obj, attr, value), temp in zip(args, temps):
            if dict_replace:
                obj[attr] = temp
                if obj[attr] is not temp:
                    errors.append("%r is not %r" % (obj[attr], temp))
            else:
                setattr(obj, attr, temp)
                if getattr(obj, attr) is not temp:
                    errors.append("%r is not %r" % (getattr(obj, attr), temp))
    assert not errors, "\n".join(errors)


def assert_raises(*args, **kw):
    if len(args) == 1:
        msg = kw.pop('msg', None)
        if kw:
            raise AssertionError('invalid kwargs: {!r}'.format(kwargs))
        @contextmanager
        def raises():
            if args[0] is None:
                yield
                return
            try:
                yield
                raise AssertionError('{} not raised'.format(args[0]))
            except args[0] as err:
                if isinstance(msg, basestring):
                    eq_(str(err), msg)
                elif isinstance(msg, BaseException):
                    eq_(err, msg)
                elif hasattr(msg, 'search'):
                    assert msg.search(str(err)), \
                        '{!r} does not match {!r}'.foramt(msg.pattern, str(err))
                elif msg is not None:
                    msg(err)
            except Exception as err:
                log.error("unexpected error", exc_info=True)
                raise AssertionError("{} != {}".format(
                    type(err).__name__, args[0].__name__))
        return raises()
    else:
        nose_assert_raises(*args, **kw)

nose_assert_raises = nose.tools.assert_raises


class CaptureLog(object):

    def __init__(self, module):
        self.log = module.log
        self.module = module
        self.data = defaultdict(list)

    def __getattr__(self, name):
        def log(message, *args, **kw):
            getattr(self.log, name)(message, *args, **kw)
            exc_info = kw.pop("exc_info", None)
            assert not kw, "unrecognized keyword args: {}".format(kw)
            if args:
                message = message % args
            if exc_info is not None:
                message += "\nexc_info = {!r}".format(exc_info)
            self.data[name].append(message)
        log.__name__ = name
        return log

    def __enter__(self):
        self.context = replattr(self.module, "log", self)
        self.context.__enter__()
        return self

    def __exit__(self, *args):
        self.context.__exit__(*args)


class Regex(object):

    def __init__(self, expression, *args, **kw):
        self.repr = kw.pop("repr", None)
        self.expr = re.compile(expression, *args, **kw)
        self.expression = expression

    def __repr__(self):
        if self.repr is not None:
            return self.repr
        return "Regex({!r})".format(self.expression)

    def __str__(self):
        return self.expression

    def __eq__(self, other):
        return self.expr.search(other)

    def __ne__(self, other):
        return not self.__eq__(other)


@nose.tools.nottest
@contextmanager
def test_app(config=None):
    """Create an Application object for testing purposes

    :param config: A string with details about the app configuration.
    The string is a space-delimited list of the following names:

        window project editor

    These names can be used to pre-configure the application with
    windows, projects, and editors to minimize the amount of setup
    needed in the test. Editors can be suffixed with parens containing a
    name to configure multiple views of the same document. For example:

        window
            project
                editor(doc1)
                editor
            project
                editor(doc1)

    In this case the first and third editor are editing the same
    document. By default each unnamed editor will contain a new,
    untitled document.

    A window or project omitted from the config is implied since it is
    not possible to have an editor without a project or a project
    without a window. For example, the following two configs result in
    identical configurations:

        window project editor

        editor

    """
    from editxt.application import Application, DocumentController
    from editxt.document import Editor
    from editxt.project import Project
    from editxt.window import Window
    def setup(app, config):
        docs_by_name = {}
        app._test_app__items = items = {}
        app._test_app__news = 0
        if config is None:
            return
        window = project = None
        for i, item in enumerate(config.split()):
            match = test_app.editor_re.match(item)
            assert match and (
                    match.group(2) == "project" or not match.group(1)
                ), "unknown config item: {}".format(item)
            collapsed, item, name, current = match.groups()
            if not name:
                name = "<{}>".format(i)
            if item == "window" or window is None:
                window = Window(app)
                project = None
                app.windows.append(window)
                if item == "window":
                    items[window] = "window" + name
                    continue
                else:
                    items[window] = "window<{}>".format(i)
            if item == "project" or project is None:
                project = Project(window)
                if collapsed:
                    project.expanded = False
                window.projects.append(project)
                if item == "project":
                    items[project] = "project" + name
                    if current:
                        window.current_editor = project
                    continue
                else:
                    items[project] = "project<{}>".format(i)
            document = docs_by_name.get(name)
            if document is None:
                document = app.document_with_path(None)
                docs_by_name[name] = document
            editor = Editor(project, document=document)
            items[editor] = "editor" + name
            items[document] = "document" + name
            project.editors.append(editor)
            if current:
                window.current_editor = editor
    with tempdir() as tmp:
        app = Application(tmp)
        try:
            setup(app, config)
            yield app
        finally:
            controller = DocumentController.sharedDocumentController()
            for document in controller.documents():
                document.close()
            assert not controller.documents(), controller.documents()

test_app.editor_re = re.compile("(-?)(window|project|editor)((?:\([a-zA-Z0-9-]+\))?)(\*?)$")

def _test_app_config(app):
    """Get a string representing the app window/project/editor/document config

    Documents that were created after the app was initialized are
    delimited with square brackets rather than parens. For example:

        window project editor[Untitled 0]

    Documents not associated with any window (this is a bug) are listed
    at the end of the config string after a pipe (|) character. Example:

        window project editor | editor[Untitled 0]
    """
    from editxt.application import DocumentController
    name_re = re.compile("(window|project|editor)<")
    def iter_items(app):
        def name(item):
            name = _test_app_item_name(item, app)
            match = name_re.match(name)
            return match.group(1) if match else name
        seen = set()
        for window in app.windows:
            yield name(window)
            current = window.current_editor
            for project in window.projects:
                star = "*" if project is current else ""
                collapsed = "" if project.expanded else "-"
                yield collapsed + name(project) + star
                for editor in project.editors:
                    star = "*" if editor is current else ""
                    yield name(editor) + star
                    seen.add(editor.document)
        controller = DocumentController.sharedDocumentController()
        documents = set(controller.documents()) - seen
        if documents:
            # documents not associated with any window (should not get here)
            yield "|"
            for document in documents:
                yield _test_app_item_name(document, app)
    return " ".join(iter_items(app))
test_app.config = _test_app_config

def _test_app_item_name(item, app):
    """Get the name of a window, project, or editor/document"""
    from editxt.document import Editor, TextDocument
    from editxt.project import Project
    from editxt.window import Window
    name = app._test_app__items.get(item)
    if name is None:
        if isinstance(item, (Window, Project)):
            name = "[{}]".format(app._test_app__news)
        else:
            name = "[{} {}]".format(item.name, app._test_app__news)
        ident = name
        prefix = "document" if isinstance(item, TextDocument) \
                            else type(item).__name__.lower()
        name = prefix + name
        app._test_app__news += 1
        app._test_app__items[item] = name
        if isinstance(item, Editor):
            app._test_app__items[item.document] = "document" + ident
    return name
test_app.name = _test_app_item_name

def _test_app_get_item(name, app):
    """Get the item for the given name

    :param name: The name of the item to get. Example: ``"editor(1)"``
    """
    items_by_name = {v: k for k, v in app._test_app__items.items()}
    print(items_by_name)
    return items_by_name[name]
test_app.get = _test_app_get_item

def check_app_state(test):
    def checker(when):
        def check_app_state():
            from editxt.application import DocumentController
            dc = DocumentController.sharedDocumentController()
            assert not dc.documents(), "app state was dirty %s %s: %r" \
                % (when, test.__name__, dc.documents())
        return check_app_state
    return with_setup(checker("before"), checker("after"))(test)


def profile(test, *args):
    import cProfile
    import sys
    def prof_test(test=test, args=args):
        stdout = sys.stdout
        sys.stdout = sys.__stdout__
        try:
            print("\n%s%r" % (test.__name__, args))
            cProfile.runctx("test(*args)", {}, dict(test=test, args=args))
        finally:
            sys.stdout = stdout
    return (prof_test, test, args)


@contextmanager
def tempdir(*args, **kw):
    delete = kw.pop("delete", True)
    path = tempfile.mkdtemp(*args, **kw)
    try:
        yield path
    finally:
        if delete and os.path.exists(path):
            shutil.rmtree(path)


def patch_nose_tools():
    nose.tools.eq_ = eq_
    nose.tools.assert_raises = assert_raises

    import pdb
    import sys
    def set_trace():
        """nose-compatible trace function

        uses default stdout, which is not consumed by nose
        """
        pdb.Pdb(stdout=sys.__stdout__).set_trace(sys._getframe().f_back)
    pdb.set_trace = set_trace
