"""CSV Dictionary -- a private glossary, abbreviations, error codes.

Port of the .tmp ``csv-services`` plugin: the file's language is whatever
the user put in it, and the lookup is local -- nothing leaves the
machine. The file is read into memory on each lookup batch rather than
watched: a term list is small and re-reading per keystroke would be
slower and no more correct.

Configure it in Options -> Extensions -> CSV Dictionary -> Settings:
the CSV path, the delimiter (``\\t`` for tab-separated), which columns
hold the term / definition / optional notes (a header name, or a
1-based number when the file has no header row), case sensitivity, and
the label shown beside each result.
"""

import csv
import io
import os

_NAME = "csv-dictionary"

# Settings keys, mirroring the manifest's settings_schema.
_K_FILE = "file.path"
_K_DELIM = "file.delimiter"
_K_TERM = "columns.term"
_K_DEF = "columns.definition"
_K_NOTES = "columns.notes"
_K_CASE = "matching.case_sensitive"
_K_LABEL = "matching.label"


def _settings(api):
    return {
        "path": api.get_setting(_K_FILE, "") or "",
        "delimiter": api.get_setting(_K_DELIM, ",") or ",",
        "term": api.get_setting(_K_TERM, "1") or "1",
        "definition": api.get_setting(_K_DEF, "2") or "2",
        "notes": api.get_setting(_K_NOTES, "") or "",
        "case": bool(api.get_setting(_K_CASE, False)),
        "label": api.get_setting(_K_LABEL, "term") or "term",
    }


def _delimiter(configured):
    """``\\t`` in a text field is the two characters, not a tab."""
    configured = str(configured or "")
    if configured == "\\t":
        return "\t"
    return (configured or ",")[:1] or ","


def _resolve_column(configured, header):
    """A column setting is a header name or a 1-based number; None when
    it is neither -- guessing a column would produce plausible-looking
    wrong answers."""
    wanted = str(configured or "").strip()
    if not wanted:
        return None
    for i, cell in enumerate(header):
        if cell.strip().lower() == wanted.lower():
            return i
    try:
        n = int(wanted) - 1
    except ValueError:
        return None
    return n if 0 <= n < len(header) else None


def _read_index(api):
    """The file keyed by normalised term -> [(term, definition, note)].

    Rows missing the asked-for columns are skipped rather than failing
    the file: a stray blank line should not cost every other term.
    Returns {} when the file is absent or unreadable -- a miss is an
    empty result, not an error, so the dictionary panel can say
    "nothing found" for the ordinary case.
    """
    s = _settings(api)
    path = s["path"].strip()
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            rows = [r for r in csv.reader(fh, delimiter=_delimiter(s["delimiter"]))
                    if any(c.strip() for c in r)]
    except (OSError, csv.Error):
        return {}
    if not rows:
        return {}

    header = rows[0]
    term_i = _resolve_column(s["term"], header)
    def_i = _resolve_column(s["definition"], header)
    note_i = (_resolve_column(s["notes"], header)
              if s["notes"].strip() else None)
    if term_i is None or def_i is None:
        return {}

    # A column named rather than numbered means the first row describes
    # the columns and is not itself data (.tmp CsvIndex.read).
    def _numeric(v):
        try:
            int(str(v).strip())
            return True
        except (TypeError, ValueError):
            return False
    has_header = (not _numeric(s["term"]) or not _numeric(s["definition"]))
    body = rows[1:] if has_header else rows

    def norm(t):
        t = t.strip()
        return t if s["case"] else t.lower()

    index = {}
    for cells in body:
        term = cells[term_i].strip() if term_i < len(cells) else ""
        definition = cells[def_i].strip() if def_i < len(cells) else ""
        if not term or not definition:
            continue
        note = ""
        if note_i is not None and note_i < len(cells):
            note = cells[note_i].strip()
        index.setdefault(norm(term), []).append(
            (term, definition, note))
    return index


def _lookup(word, src, tgt, api):
    """fn(word, src, tgt) -> the entry's HTML fragment.

    A miss returns "" -- the same contract every DICTS provider keeps:
    the renderer shows its no-results literal, and an error would put a
    red status in front of the user for a word simply absent from their
    own glossary.
    """
    index = _read_index(api)
    if not index:
        return ""
    s = _settings(api)
    matches = index.get((word or "").strip()
                        if s["case"]
                        else (word or "").strip().lower()) or []
    if not matches:
        return ""

    label = s["label"].strip() or "term"
    parts = ['<div class="csv-entry"><b>%s</b> <i>(%s)</i><ul>'
             % (_esc(matches[0][0]), _esc(label))]
    for _term, definition, note in matches:
        item = "<li>%s" % _esc(definition)
        if note:
            item += ' <span class="csv-note">— %s</span>' % _esc(note)
        parts.append(item + "</li>")
    parts.append("</ul></div>")
    return "".join(parts)


def _esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def register(api):
    api.register_dictionary(_NAME, lambda w, s, t: _lookup(w, s, t, api))
