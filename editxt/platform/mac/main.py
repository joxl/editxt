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

import objc
from PyObjCTools import AppHelper, Debugging

from editxt.platform.mac.app import AppDelegate
from editxt.platform.mac.errors import install_exception_handler
# TODO move Cocoa specific part of valuetrans (all of it?) into platform.mac
from editxt.valuetrans import register_value_transformers

log = logging.getLogger(__name__)

def init(use_pdb):

    # prevent NSLog("PyObjC: Converting exception to Objective-C")
    # See pyobjc-core/Modules/objc/objc_util.m
    objc.setVerbose(0)

    if use_pdb:
        # make PyObjC use our exception handler
        Debugging.installExceptionHandler = install_exception_handler
    else:
        install_exception_handler()

    fix_PyObjCTools_path()

    # HACK monkey-patch pyobc exception handler to use our logger
    def log_error(template, message=None):
        log.error(template if message is None else message)
    #AppHelper.NSLog = log_error
    Debugging.NSLog = log_error


def run(app, argv, unexpected_error_callback, use_pdb):
    # initialize class definitions
    import editxt.controls.cells
    import editxt.controls.linenumberview
    import editxt.controls.splitview
    import editxt.controls.textview

    register_value_transformers()
    AppDelegate.app = app # HACK global. Would prefer to set an instance variable
    if not use_pdb:
        AppDelegate.updater = load_sparkle()

    AppHelper.runEventLoop(argv, unexpected_error_callback, pdb=use_pdb)


def fix_PyObjCTools_path():
    try:
        import PyObjCTools.KeyValueCoding
    except ImportError:
        # HACK fix path of namespace package
        # I thought this was supposed to be handled by PEP 420
        # http://www.python.org/dev/peps/pep-0420/
        import PyObjCTools
        assert len(PyObjCTools.__path__) == 1, PyObjCTools.__path__
        head, tail = os.path.split(PyObjCTools.__path__[0])
        assert tail == "PyObjCTools", PyObjCTools.__path__
        PyObjCTools.__path__.append(os.path.join(head, "PyObjC", tail))


def load_sparkle():
    from os.path import abspath, dirname, join
    base_path = join(dirname(os.environ['RESOURCEPATH']), 'Frameworks')
    bundle_path = abspath(join(base_path, 'Sparkle.framework'))
    objc.loadBundle('Sparkle', globals(), bundle_path=bundle_path)
    swizzle_SUWindowController()
    return SUUpdater.sharedUpdater()


def swizzle_SUWindowController():
    def swizzle(old):
        def swizzleWithNewMethod_(f):
            # http://permalink.gmane.org/gmane.comp.python.pyobjc.devel/5446
            cls = old.definingClass
            oldSelectorName = old.__name__.replace(b"_", b":")
            oldIMP = cls.instanceMethodForSelector_(oldSelectorName)
            newSelectorName = f.__name__.encode('ascii').replace(b"_", b":")

            newSEL = objc.selector(
                f,
                selector=newSelectorName,
                signature=old.signature
            )
            oldSEL = objc.selector(
                lambda self, *args: oldIMP(self, *args),
                selector=newSelectorName,
                signature=old.signature
            )

            # Swap the two methods
            objc.classAddMethod(cls, newSelectorName, oldSEL)
            objc.classAddMethod(cls, oldSelectorName, newSEL)
            log.debug("Swizzled %s.%s <-> %s",
                cls.__name__,
                oldSelectorName.decode('ascii'),
                newSelectorName.decode('ascii'),
            )
            return f

        return swizzleWithNewMethod_

    @swizzle(SUWindowController.initWithHost_windowNibName_)
    def initWithHost_windowNibName_(self, host, nibName):
        return self.initWithWindowNibName_owner_(nibName, self)
