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
import os
from contextlib import closing
from tempfile import gettempdir

import AppKit as ak
import Foundation as fn
from mocker import Mocker, MockerTestCase, expect, ANY, MATCH
from nose.tools import *
from editxt.test.util import TestConfig, untested, check_app_state, test_app

import editxt.constants as const
import editxt.errorlog as mod
from editxt.errorlog import ErrorLog, create_error_log_document

log = logging.getLogger(__name__)

# log.debug("""TODO
#     implement TextDocumentView.pasteboard_data()
# """)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ErrorConsoleView tests

#def test_ErrorLog_log():
#    el = ErrorLog.log()
#    assert ErrorLog.log() is el

def test_ErrorLog_init():
    app = type("App", (), {})()
    el = ErrorLog(app)
    assert isinstance(el.text, ak.NSTextStorage), repr(el.text)
    eq_(el._document, None)
    eq_(el.app, app)

def test_ErrorLog_document():
    from editxt.application import Application
    from editxt.document import TextDocument
    def test(c):
        m = Mocker()
        app = m.mock(Application)
        el = ErrorLog(app)
        doc_factory = m.replace(mod, "create_error_log_document")
        doc = m.mock(TextDocument)
        if not c.created:
            doc_factory(app, ANY) >> doc
            doc.text_storage = el.text
            doc.file_path = const.LOG_NAME
        else:
            el._document = doc
        with m:
            eq_(el.document, doc)
    c = TestConfig(created=False)
    yield test, c
    yield test, c(created=True)

def test_ErrorLog_write():
    from editxt.application import Application
    from editxt.document import TextDocument
    def test(c):
        m = Mocker()
        value = "some text"
        app = m.mock(Application)
        el = ErrorLog(app)
        el.text = ts = m.mock(ak.NSTextStorage)
        ts.length() >> 42
        range = fn.NSRange(42, 0)
        ts.replaceCharactersInRange_withString_(range, value)
        if c.has_doc:
            el._document = doc = m.mock(TextDocument)
            doc.clear_dirty()
        with m:
            el.write(value)
    c = TestConfig(has_doc=False)
    yield test, c
    yield test, c(has_doc=True)

def test_ErrorLog_flush():
    el = ErrorLog(None)
    el.flush() # no op

def test_ErrorLog_unexpected_error():
    def test(c):
        m = Mocker()
        el = ErrorLog(None)
        log = m.replace(mod, 'root_log')
        log.error("unexpected error", exc_info=True)
#        open_error = app.open_error_log(set_current=False)
#        if c.open_fail:
#            expect(open_error).throw(Exception)
#            log.warn("cannot open error log", exc_info=True)
        with m:
            assert el.unexpected_error()
    c = TestConfig()
    yield test, c(open_fail=False)
    yield test, c(open_fail=True)

def test_create_error_log_document():
    from editxt.document import TextDocument
    with test_app() as app:
        doc = create_error_log_document(app, lambda:None)
        try:
            eq_(type(doc).__name__, "ErrorLogDocument")
            eq_(doc.app, app)
            assert isinstance(doc, TextDocument)
            doc2 = create_error_log_document(app, lambda:None)
            try:
                assert doc is not doc2
                assert type(doc) is type(doc2)
                eq_(doc2.app, app)
            finally:
                doc2.close()
        finally:
            doc.close()
