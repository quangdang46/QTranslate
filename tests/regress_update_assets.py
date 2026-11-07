"""Regression: update dialog platform-asset download (GAP_AUDIT_2 item 2).

Ports the Kotlin contract end to end:

  * ``ReleaseAssets.selectDownload`` -> ``update_check.select_download_asset``
    picks the platform-appropriate release asset BY NAME, never "first
    asset" (GitHub lists alphabetically, so first has always meant a plugin
    JAR upstream).
  * ``Updater.downloadUrlFor`` -> ``check_for_update`` fills
    ``download_url`` from the asset's ``browser_download_url``; an
    unrecognised release yields "" so the dialog falls back to the release
    page.
  * ``UpdateDialog``'s Download button -> ``show_update_result`` offers
    "Download" (opens the asset URL via ``QDesktopServices.openUrl``) next
    to "Open release page". Nothing is downloaded or executed -- the URL
    is only opened.

The release fetch is mocked through ``qtranslate.common.http_open``; the
dialog runs under QT_QPA_PLATFORM=offscreen with ``QMessageBox.exec`` and
``QDesktopServices.openUrl`` replaced by recording fakes.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append(name + (" -- " + detail if detail else ""))


from qtranslate import update_check as U  # noqa: E402

# --- 1. select_download_asset: per-platform name matching -------------------

MIXED = [
    "ai-plugin-6.11.0.jar",                      # alphabetically first, NOT the app
    "QTranslate-6.11.0-linux-x86_64.AppImage",
    "QTranslate-6.11.0-macos-arm64.dmg",
    "QTranslate-6.11.0-windows-x64.zip",
    "QTranslate-6.11.0.zip",                     # portable archive
    "QTranslate-App-6.11.0.jar",                 # bare app JAR (last resort)
]

ck("darwin picks the macOS package over the portable zip",
   U.select_download_asset(MIXED, platform="darwin")
   == "QTranslate-6.11.0-macos-arm64.dmg")
ck("windows picks the windows package over the portable zip",
   U.select_download_asset(MIXED, platform="windows")
   == "QTranslate-6.11.0-windows-x64.zip")
ck("linux picks the linux package",
   U.select_download_asset(MIXED, platform="linux")
   == "QTranslate-6.11.0-linux-x86_64.AppImage")
ck("platform hints normalise (macos/osx/win32)",
   U.select_download_asset(MIXED, platform="macos")
   == "QTranslate-6.11.0-macos-arm64.dmg"
   and U.select_download_asset(MIXED, platform="osx")
   == "QTranslate-6.11.0-macos-arm64.dmg"
   and U.select_download_asset(MIXED, platform="win32")
   == "QTranslate-6.11.0-windows-x64.zip")

ck("portable zip is the fallback when no platform package exists",
   U.select_download_asset(["QTranslate-6.11.0.zip", "ai-plugin-6.11.0.jar"],
                           platform="darwin") == "QTranslate-6.11.0.zip")
ck("bare app JAR is the last resort on every platform",
   all(U.select_download_asset(["QTranslate-App-6.11.0.jar"], platform=p)
       == "QTranslate-App-6.11.0.jar"
       for p in ("darwin", "windows", "linux")))
ck("plugin JARs and unknown files are never offered",
   U.select_download_asset(["ai-plugin-6.11.0.jar", "notes.txt",
                            "QTranslate-6.11.0-windows-x64.zip"],
                           platform="darwin") is None,
   "a windows package must not leak onto darwin")
ck("plugin-only release selects nothing",
   U.select_download_asset(["ai-plugin-6.11.0.jar", "README.md"],
                           platform="windows") is None)
ck("empty/None asset list selects nothing",
   U.select_download_asset([], platform="darwin") is None
   and U.select_download_asset(None, platform="darwin") is None)

# --- 2. check_for_update: download_url comes from the release assets --------

class _Resp:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def _release(assets):
    return {"tag_name": "v6.11.0", "name": "QTranslate 6.11.0",
            "body": "release notes",
            "html_url": "https://example.invalid/releases/tag/v6.11.0",
            "assets": [{"name": name,
                        "browser_download_url":
                            "https://example.invalid/dl/" + name}
                       for name in assets]}


def _check(assets, platform):
    import qtranslate.common as C
    orig = C.http_open
    C.http_open = lambda req, opener=None: _Resp(_release(assets))
    try:
        return U.check_for_update(platform=platform)
    finally:
        C.http_open = orig


res = _check(["ai-plugin-6.11.0.jar", "QTranslate-6.11.0-macos-arm64.dmg",
              "QTranslate-6.11.0.zip"], "darwin")
ck("update status with a newer tag", res["status"] == "update",
   str(res))
ck("darwin download_url is the macOS asset's browser_download_url",
   res["download_url"]
   == "https://example.invalid/dl/QTranslate-6.11.0-macos-arm64.dmg",
   res["download_url"])
ck("release page url is still reported",
   res["url"] == "https://example.invalid/releases/tag/v6.11.0")

res = _check(["ai-plugin-6.11.0.jar", "QTranslate-6.11.0-windows-x64.zip",
              "QTranslate-6.11.0.zip"], "windows")
ck("windows download_url is the windows package",
   res["download_url"]
   == "https://example.invalid/dl/QTranslate-6.11.0-windows-x64.zip",
   res["download_url"])

res = _check(["ai-plugin-6.11.0.jar", "notes.txt"], "darwin")
ck("unrecognised assets -> empty download_url (release-page fallback)",
   res["status"] == "update" and res["download_url"] == "",
   str(res))
ck("release page url survives the fallback",
   res["url"] == "https://example.invalid/releases/tag/v6.11.0")

res = _check(["QTranslate-6.11.0.zip"], "linux")
ck("linux falls back to the portable zip",
   res["download_url"] == "https://example.invalid/dl/QTranslate-6.11.0.zip",
   res["download_url"])

# error path keeps the new key so callers never KeyError
import qtranslate.common as _C  # noqa: E402
_orig_open = _C.http_open
_C.http_open = lambda req, opener=None: (_ for _ in ()).throw(
    OSError("no network"))
try:
    err = U.check_for_update()
finally:
    _C.http_open = _orig_open
ck("error result carries download_url", err["status"] == "error"
   and err["download_url"] == "", str(err))

# --- 3. show_update_result: Download button opens the asset URL --------------

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
import PySide6.QtWidgets as _W  # noqa: E402
import PySide6.QtGui as _G  # noqa: E402

_app = QApplication.instance() or QApplication([])

opened = []


class _FakeDesktop:
    @staticmethod
    def openUrl(url):
        opened.append(url.toString())


class _FakeBox(QMessageBox):
    """QMessageBox whose exec() clicks the button named in CLICK instead of
    blocking -- the offscreen stand-in for a user pressing it."""
    CLICK = None

    def exec(self):
        for b in self.buttons():
            if b.text() == type(self).CLICK:
                b.click()
                break
        return 0


class _FakeMsg(QMessageBox):
    pass


def _run_dialog(res, click):
    """Show the update dialog offscreen; return (button texts, opened)."""
    opened.clear()
    _FakeBox.CLICK = click
    real_box, real_desk = _W.QMessageBox, _G.QDesktopServices
    _W.QMessageBox = _FakeBox
    _G.QDesktopServices = _FakeDesktop
    texts = []
    try:
        # Capture the button row by wrapping addButton on the instance the
        # dialog builds -- simplest reliable hook is a recording subclass.
        class _RecBox(_FakeBox):
            def addButton(self, *a, **kw):
                btn = super().addButton(*a, **kw)
                texts.append(btn.text())
                return btn
        _W.QMessageBox = _RecBox
        U.show_update_result(None, res)
    finally:
        _W.QMessageBox = real_box
        _G.QDesktopServices = real_desk
    return texts, list(opened)


DL = "https://example.invalid/dl/QTranslate-6.11.0-macos-arm64.dmg"
PG = "https://example.invalid/releases/tag/v6.11.0"

texts, urls = _run_dialog(
    {"status": "update", "version": "v6.11.0", "notes": "n",
     "url": PG, "download_url": DL, "error": ""}, "Download")
ck("dialog offers Download, release page, and Close",
   texts == ["Download", "Open release page", "Close"], str(texts))
ck("Download opens the asset URL via QDesktopServices.openUrl",
   urls == [DL], str(urls))

texts, urls = _run_dialog(
    {"status": "update", "version": "v6.11.0", "notes": "n",
     "url": PG, "download_url": DL, "error": ""}, "Open release page")
ck("release-page button still opens the release page",
   urls == [PG], str(urls))

texts, urls = _run_dialog(
    {"status": "update", "version": "v6.11.0", "notes": "n",
     "url": PG, "download_url": "", "error": ""}, "Open release page")
ck("no recognisable asset -> no Download button (release page is the "
   "fallback)", texts == ["Open release page", "Close"], str(texts))
ck("fallback still opens the release page", urls == [PG], str(urls))

texts, urls = _run_dialog(
    {"status": "update", "version": "v6.11.0", "notes": "n",
     "url": "", "download_url": "", "error": ""}, "Close")
ck("neither url nor asset -> only Close", texts == ["Close"], str(texts))
ck("Close opens nothing", urls == [], str(urls))

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_update_assets: all checks ok (%d assertions)" % n[0])
