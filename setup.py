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
import glob
import os
import re
import shutil
import sys
import time
from os.path import join

from datetime import datetime
from setuptools import setup
from subprocess import check_output, Popen, PIPE

import CommonMark as commonmark


if hasattr(sys, 'real_prefix'):
    # HACK fixes for py2app + virtualenv
    if sys.prefix.endswith("/.."):
        sys.prefix = os.path.normpath(sys.prefix)
    if sys.exec_prefix.endswith("/.."):
        sys.exec_prefix = os.path.normpath(sys.exec_prefix)

import py2app

from editxt import __version__ as version
build_date = datetime.now()
revision = build_date.strftime("%Y%m%d%H%M")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Fix modulegraph 0.12 bug : http://stackoverflow.com/q/25394320/10840

def _fix_modulegraph():
    import modulegraph.modulegraph as mod
    mod.ModuleGraph.scan_code = mod.ModuleGraph._scan_code
    mod.ModuleGraph.load_module = mod.ModuleGraph._load_module
_fix_modulegraph()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# handle -A switch (dev build)
if "-A" in sys.argv:
    dev = True
    appname = "EditXTDev"
else:
    dev = False
    appname = "EditXT"

package = ('--package' in sys.argv)
if package:
    assert not dev, 'cannot package dev build'
    sys.argv.remove('--package')

# get git revision information
def proc_out(cmd):
    proc = Popen(cmd, stdout=PIPE, close_fds=True)
    for line in proc.stdout:
        yield line.decode("utf8") # HACK
gitrev = next(proc_out(["git", "rev-parse", "HEAD"]))[:7]
changes = 0
for line in proc_out(["git", "status"]):
    if line.startswith("# Changed but not updated"):
        changes += 1
    if line.startswith("# Changes to be committed"):
        changes += 1
if changes:
    gitrev += "+"
    if not dev:
        response = input("Build with uncommitted changes? [Y/n] ").strip()
        if response and response.lower() not in ["y", "yes"]:
            print("aborted.")
            sys.exit()
print("building %s %s %s.%s" % (appname, version, revision, gitrev))

thisdir = os.path.dirname(os.path.abspath(__file__))

def clean():
    # remove old build
    if "--noclean" in sys.argv:
        sys.argv.remove("--noclean")
    else:
        def rmtree(path):
            print("removing", path)
            if os.path.exists(path):
                shutil.rmtree(path)
        rmtree(join(thisdir, "build"))
        rmtree(join(thisdir, "dist", appname + ".app"))

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
setup_args = {}
def prepare_build(**kw):
    setup_args.update(kw)

prepare_build(
    name=appname,
    app=['boot.py'],
    version=version,
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3'
    ],
    options=dict(py2app=dict(
        # argv_emulation causes the app to launch in a strange mode that does
        # not play nicely with Exposé (the window does not come to the front
        # when switching to EditXT with Exposé). Luckily everything seems to
        # work as expected without it!!
        argv_emulation=True,
        packages=["editxt"],
        frameworks=["resources/Sparkle-1.8.0/Sparkle.framework"],
        plist=dict(
            CFBundleGetInfoString = "%s %s.%s" % (version, revision, gitrev),
            CFBundleShortVersionString = version,
            CFBundleVersion = revision + "." + gitrev,
            NSHumanReadableCopyright = '© Daniel Miller',
            CFBundleIdentifier = "org.editxt." + appname,
            CFBundleIconFile = "PythonApplet.icns",
            SUPublicDSAKeyFile = "dsa_pub.pem",
            SUFeedURL = "https://github.com/editxt/editxt/raw/master/resources/updater/updates.xml",
            CFBundleDocumentTypes = [
                dict(
                    CFBundleTypeName="All Documents",
                    CFBundleTypeRole="Editor",
                    NSDocumentClass="TextDocument",
                    LSHandlerRank="Alternate",
                    LSIsAppleDefaultForType=False,
                    LSItemContentTypes=["public.data"],
                    LSTypeIsPackage=False,
                    CFBundleTypeExtensions=["*"],
                    CFBundleTypeOSTypes=["****"],
                ),
                dict(
                    CFBundleTypeName="Text Document",
                    CFBundleTypeRole="Editor",
                    NSDocumentClass="TextDocument",
                    LSHandlerRank="Owner",
                    LSItemContentTypes=["public.plain-text", "public.text"],
                    CFBundleTypeExtensions=["txt", "text"],
                    CFBundleTypeOSTypes=["TEXT"],
                ),
#               dict(
#                   CFBundleTypeName="EditXT Project",
#                   CFBundleTypeRole="Editor",
#                   #NSDocumentClass="Project",
#                   LSHandlerRank="Owner",
#                   LSItemContentTypes=["org.editxt.project"],
#                   CFBundleTypeExtensions=["edxt"],
#               ),
            ],
#           UTExportedTypeDeclarations = [
#               dict(
#                   UTTypeIdentifier="org.editxt.project",
#                   UTTypeDescription="EditXT project format",
#                   UTTypeConformsTo=["public.plain-text"],
#                   #UTTypeIconFile=???,
#                   UTTypeTagSpecification={
#                       "public.finename-extension": ["edxt"]
#                   },
#               ),
#           ],
        ),
    )),
    data_files=[
        'resources/PythonApplet.icns',
        'resources/MainMenu.nib',
        'resources/EditorWindow.nib',
        'resources/FindPanel.nib',
        'resources/OpenPath.nib',
        'resources/SortLines.nib',
        'resources/WrapLines.nib',
        'resources/ChangeIndentation.nib',
        'resources/images/close-hover.png',
        'resources/images/close-normal.png',
        'resources/images/close-pressed.png',
        'resources/images/close-selected.png',
        'resources/images/close-dirty-hover.png',
        'resources/images/close-dirty-normal.png',
        'resources/images/close-dirty-pressed.png',
        'resources/images/close-dirty-selected.png',
        'resources/images/docsbar-blank.png',
        'resources/images/docsbar-menu.png',
        'resources/images/docsbar-plus.png',
        'resources/images/docsbar-props-down.png',
        'resources/images/docsbar-props-up.png',
        'resources/images/docsbar-sizer.png',
        'resources/images/popout-button.png',
        'resources/images/popout-button-alt.png',
        'resources/mytextcommand.py',
        'resources/updater/dsa_pub.pem',
        ("syntax", glob.glob("resources/syntax/*")),
        #("../Frameworks", ("lib/Frameworks/NDAlias.framework",)),
    ],
    entry_points={
        'nose.plugins': [
            'skip-slow = editxt.test.noseplugins:SkipSlowTests',
            'list-slowest = editxt.test.noseplugins:ListSlowestTests',
        ]
    },
)

if dev and hasattr(sys, 'real_prefix'):
    # HACK patch __boot__.py to work with virtualenv
    bootfile = join("dist", appname + ".app",
        "Contents/Resources/__boot__.py")
    with open(bootfile, "rb") as file:
        original = file.read()
    sitepaths = [p for p in sys.path if p.startswith(sys.real_prefix)]
    bootfunc = "import sys; sys.path[:0] = %r\n\n" % sitepaths
    with open(bootfile, "wb") as file:
        file.write(bootfunc.encode('utf-8') + original)

def prepare_sparkle_update(zip_path):
    sig = check_output([
        join(thisdir, "resources/Sparkle-1.8.0/bin/sign_update.sh"),
        zip_path,
        join(thisdir, "resources/updater/dsa_priv.pem"),
    ], universal_newlines=True).strip()

    with open(join(thisdir, "resources/updater/item-template.xml")) as fh:
        template = fh.read()
    item = template.format(
        title="Version {}".format(version),
        changesHTML=get_latest_changes(version),
        pubDate=build_date.strftime("%a, %d %b %Y %H:%M:%S " + timezone(build_date)),
        url="https://github.com/editxt/editxt/releases/download/{}/{}".format(
                version, os.path.basename(zip_path)),
        version=revision + "." + gitrev,
        shortVersion=version,
        dsaSignature=sig,
        length=os.stat(zip_path).st_size,
    )

    with open(join(thisdir, "resources/updater/updates.xml")) as fh:
        updates = fh.read()
    i = updates.rfind("  </channel>")
    assert i > 0, updates
    with open(join(thisdir, "resources/updater/updates.xml"), "w") as fh:
        fh.write(updates[:i])
        fh.write(item)
        fh.write(updates[i:])

    update_change_log_html()


def timezone(local_datetime):
    """Get timezone in +HHMM format"""
    ts = time.mktime(local_datetime.replace(microsecond=0).timetuple())
    utc_offset = local_datetime - datetime.utcfromtimestamp(ts)
    assert -1 <= utc_offset.days <= 0, utc_offset
    assert utc_offset.seconds % 900 == 0, utc_offset
    total_minutes = (utc_offset.days * 24 * 3600 + utc_offset.seconds) // 60
    assert total_minutes % 15 == 0, (utc_offset, total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    assert minutes >= 0, (hours, minutes, total_minutes)
    if hours < 0 and minutes > 0:
        hours += 1
        minutes = 60 - minutes
    assert 0 <= abs(hours) <= 14, (utc_offset, hours, minutes)
    assert 0 <= minutes < 60, (utc_offset, hours, minutes)
    return "%+03i%02i" % (hours, minutes)


def get_latest_changes(version):
    regex = re.compile((
        r"\n20\d\d-..-.. - {}\n" # date/version tag for current version
        r"([\s\S]+?)"           # changes
        r"\n20\d\d-..-.. - "    # older version tag
    ).format(re.escape(version)))
    with open(join(thisdir, "changelog.txt")) as fh:
        data = fh.read()
    match = regex.search(data)
    if not match:
        print("recent changes not found in changelog.txt")
        return ""
    value = match.group(1)
    parser = commonmark.DocParser()
    renderer = commonmark.HTMLRenderer()
    return renderer.render(parser.parse(value))


def update_change_log_html():
    regex = re.compile(r"20\d\d-..-.. - ")
    lines = []
    with open(join(thisdir, "changelog.txt")) as fh:
        for line in fh:
            if lines:
                if regex.match(line):
                    line = "## " + line
                lines.append(line)
            elif line == "## Change Log\n":
                lines.append("")
    if not lines:
        print("Change Log header not found in changelog.txt")
        return False
    value = "".join(lines)
    parser = commonmark.DocParser()
    renderer = commonmark.HTMLRenderer()
    updates_html = renderer.render(parser.parse(value))
    with open(join(thisdir, "resources/updater/updates-template.html")) as fh:
        template = fh.read()
    html = template % {"body": updates_html}
    with open(join(thisdir, "resources/updater/updates.html"), "w") as fh:
        fh.write(html)
    return True


def build_zip():
    from contextlib import closing
    from zipfile import ZipFile, ZIP_DEFLATED
    distpath = join(thisdir, 'dist')
    zip_file = '%s-v%s-%s.zip' % (appname, version, gitrev)
    print('packaging for distribution: %s' % zip_file)
    zip_path = join(distpath, zip_file)
    zip = ZipFile(zip_path, "w", ZIP_DEFLATED)
    with closing(zip):
        zip.write(join(thisdir, 'changelog.txt'), 'changelog.txt')
        zip.write(join(thisdir, 'COPYING'), 'COPYING')
        zip.write(join(thisdir, 'README.txt'), 'README.txt')
        zip.write(join(thisdir, 'bin/xt.py'), 'xt')
        app_path = join(thisdir, 'dist', appname + '.app')
        trimlen = len(distpath) + 1
        for dirpath, dirnames, filenames in os.walk(app_path):
            zpath = dirpath[trimlen:]
            for filename in filenames:
                zip.write(join(dirpath, filename), join(zpath, filename))
    return zip_path


if "--html-only" in sys.argv:
    update_change_log_html()
    sys.exit()

clean()
setup(**setup_args)
if package:
    zip_path = build_zip()
    prepare_sparkle_update(zip_path)
