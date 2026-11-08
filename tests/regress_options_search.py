"""Regression: .tmp SettingsSearchController ported into the Options
dialog sidebar.

Upstream: a search field above the page list; typing filters a lazily
built index of every page's SettingEntry (label/section/hint/page
match), hits list with a "page › section" path, choosing one navigates
and anchors the control; empty query restores the tree; a query with
no hits names the query back. PluginsPanel is deliberately unindexed.

The port collects entries by scanning each freshly built page (the
same outcome upstream's instrumented addCheckbox/addRow helpers
produce), keeps the query across the per-page chrome rebuilds, and
flashes the anchor widget on activation.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if cond:
        print("  ok %s" % name)
    else:
        fail.append("%s -- %s" % (name, detail))
        print("  FAIL %s -- %s" % (name, detail))


from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

_qapp = QApplication.instance() or QApplication([])

import qtranslate.config as C  # noqa: E402

_tmp = tempfile.mktemp(suffix=".json")
C.DEFAULT_PATH = _tmp
C.save(C.default_config())

from qtranslate.qt.options import OptionsDialog, PAGES  # noqa: E402

d = OptionsDialog(None)
d.show()

# 1. The field exists in the sidebar chrome.
ck("search field present", hasattr(d, "_search")
   and d._search.placeholderText() == "Search settings")

# 2. Empty query: page rows visible, results hidden.
ck("empty query shows page rows",
   all(r.isVisible() for r in d._rows)
   and not d._search_results.isVisible())

# 3. Index builds lazily on first query, once per dialog.
d._search.setText("proxy")
_qapp.processEvents()
idx = d._search_idx
ck("index built on first query", idx is not None and len(idx) > 50,
   "entries: %s" % (len(idx) if idx else 0))
again = d._search_index()
ck("index is cached, not rebuilt", again is idx)

# 4. Hits: proxy settings are findable (hint-registered controls).
labels = [it.text() for it in
          (d._search_results.item(i)
           for i in range(d._search_results.count()))]
ck("proxy query hits proxy settings",
   any("Proxy" in t for t in labels), str(labels[:5]))
ck("hit carries page › section path",
   all("›" in (d._search_results.item(i).toolTip() or "")
       for i in range(d._search_results.count())),
   "tooltips carry the path")

# 5. Section names are searchable (upstream matches pageLabel too).
d._search.setText("Retries")
_qapp.processEvents()
ck("section name matches",
   d._search_results.count() >= 1
   and any("retr" in (d._search_results.item(i).text() or "")
           .lower() or "Retry" in (d._search_results.item(i).text()
                                   or "")
           for i in range(d._search_results.count())),
   "count=%d" % d._search_results.count())

# 6. No-hit query names the query back (.tmp NAV_EMPTY card).
d._search.setText("zzzz-no-such-setting")
_qapp.processEvents()
ck("no hits shows the query back",
   d._search_empty.isVisible()
   and "zzzz-no-such-setting" in d._search_empty.text(),
   d._search_empty.text())
ck("no hits hides results list",
   not d._search_results.isVisible())

# 7. Clearing restores the page rows.
d._search.setText("")
_qapp.processEvents()
ck("clearing restores page rows",
   all(r.isVisible() for r in d._rows)
   and not d._search_results.isVisible()
   and not d._search_empty.isVisible())

# 8. Activation navigates to the hit's page and clears the search.
d._search.setText("dictionary")
_qapp.processEvents()
ck("dictionary query has hits", d._search_results.count() > 0,
   "%d" % d._search_results.count())
target_page = (d._search_results.item(0).data(Qt.UserRole)
               or {}).get("page")
d._search_activate(d._search_results.item(0))
_qapp.processEvents()
ck("hit activation navigates to its page",
   d._page_name == target_page, "%s != %s" % (d._page_name, target_page))
ck("activation clears the query",
   d._search.text() == "" and all(r.isVisible() for r in d._rows))

# 9. Every indexed page name is a real sidebar page; Extensions is
#    excluded like upstream's PluginsPanel.
pages_in_idx = {h["page"] for h in idx}
ck("indexed pages are real pages",
   pages_in_idx <= set(PAGES), str(pages_in_idx - set(PAGES)))
ck("Extensions page unindexed (manager, like PluginsPanel)",
   "Extensions" not in pages_in_idx)

# 10. Entries carry anchors for the flash-on-activate path.
ck("entries carry geometry anchors",
   all(isinstance(h.get("x"), int) and isinstance(h.get("y"), int)
       for h in idx))

# 11. _paint_rows keys on the stored page name, not the caption text:
#     with a non-English UI pack the sidebar captions are localized and
#     q.text() never equals the English _page_name -- the highlight
#     must still land on the current page's row.
def _sel_rows():
    return [r for r in d._rows
            if "background:transparent" not in (r.styleSheet() or "")]

sel = _sel_rows()
ck("exactly one sidebar row highlighted", len(sel) == 1,
   "%d" % len(sel))
if sel:
    row = sel[0]
    row.setText("zz-localized-caption")
    d._paint_rows()
    sel = _sel_rows()
    ck("highlight survives a localized caption",
       len(sel) == 1 and sel[0] is row, "%d" % len(sel))
    ck("row carries its page name",
       row.property("qt_page") == d._page_name,
       repr(row.property("qt_page")))

try:
    os.remove(_tmp)
except OSError:
    pass

if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_options_search: all checks ok (%d assertions)" % n[0])
