"""Dictionary multi-service HTML renderer — port of RT_HTML id 192.

The native DictionaryWindow renders every provider's HTML fragment into
this shell template (qt-s{id}/qt-h{id}/qt-d{id}/qt-l{id} cards + nav
menu + toggle/fullEntry/checkEntry JS). This module reproduces it so
`app.py` dict mode shows collapsible per-service cards like the original.
"""
import html as _html
import os

_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "dict_template.html")

# Native's empty-result message, verbatim from the recovered image at file
# offset 0x11dbc8 (26 chars, VA 0x51ebc8) — single quotes are the native
# literal's, not a placeholder repr, so this is formatted with % and not
# with %r, which would double-quote and escape differently.
#   docs/review/DICT_CARD_BUILDER_2026-10-10.md 2b
NO_RESULTS = "No results found for '%s'."

# Native's slot-2 wrapper, verbatim (the literal is at VA 0x51e868):
#   <a href="%s" class="qt-link-browser" title="Open in browser">%s</a>
# whose first %s is the service's home page and second is the title. When the
# service has NO home page, native falls back to `FUN_00401ec9(&local_78,
# piVar2)` — the bare title — settled from the pushes at 0x00425551..0x00425568
# (the `<a ...>` branch) and 0x0042556a..0x0042556f (the else), which are the
# two arms of one conditional on `[ESP+0x14] != 0 && [EAX-0xc] != 0 &&
# FUN_00403897(obj)`.
_LINK_WRAP = ('<a href="%s" class="qt-link-browser" '
              'title="Open in browser">%s</a>')

# Per-service browser link, ported from each `services/*/Service.js`. The
# shape is `serviceHost()` + `buildUri()` in `serviceDictionaryResponse`
# (`d = serviceHost(...); b = buildUri(...); d += b`), which is exactly the
# `*_link` family in dictionary.py — so the value is a resolved URL, not a
# constant table. `sources` below pins each entry to the JS line it came from.
#
# Lexical by display name, because app.py builds cards with the display name
# as the title and never has the numeric service id at the point it renders.
SERVICE_LINKS = {
    "Google Search": "https://www.google.com",
    "Wikipedia": "https://www.wikipedia.org/",
    "Multitran": "https://www.multitran.com",
    "ImTranslator": "http://dictionary.imtranslator.net/",
    "WordReference": "https://www.wordreference.com",
    "Babylon Dictionary": "https://dictionary.babylon-software.com",
    "Reverso": "http://dictionary.reverso.net",
    "Urban Dictionary": "https://www.urbandictionary.com",
    "ABBYY Lingvo Live": "https://www.lingvolive.com",
    "Oxford Learner Dictionary":
        "https://www.oxfordlearnersdictionaries.com",
}


def service_link(title: str) -> str:
    """The browser link for a service, or ``""`` when native has none.

    A service with no home page renders the bare title instead of an <a>
    (`FUN_00401ec9` branch), so `""` is a meaningful value here and not a
    missing entry: an unknown name means "native would not link it".
    """
    return SERVICE_LINKS.get(title, "")



def load_template() -> str:
    with open(_TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


def render_cards(results: list, query: str = "") -> str:
    """results: [(service_id, title, html_fragment)]. Returns full page."""
    tpl = load_template()
    cards = []
    menu_calls = []
    for i, (sid, title, frag) in enumerate(results):
        # Card markup is native FUN_004253cc's format string, verbatim
        # (docs/review/DICT_CARD_BUILDER_2026-10-10.md): one wide literal at
        # file offset 0x11d8f0, 298 chars / 596 bytes, with NINE substitutions
        # in order:  %u %u %u | %s %s | %u %u %u | %s
        #              s   h   t    icon title   d   l   full   frag
        # The four things a port most easily gets wrong are pinned here:
        #   ondblclick, not onclick, on the header
        #   onselectstart="return false;" on the header
        #   qt-l is an <input type="button"> reading "READ MORE", not an <a>
        #   no inline display:none -- native lets checkEntry decide
        #
        # KNOWN GAP, now measured rather than guessed. Native's header is TWO
        # substitution slots, "%s%s", and the port emits only the title:
        #   slot 1 = the service icon, as
        #          <img src="%s" style="vertical-align: middle"></img>&nbsp;
        #          whose %s is "file:///%s" over <config>/Services/<name>/
        #          Service.ico, or a default when that file is absent
        #   slot 2 = <a href="%s" class="qt-link-browser" title="Open in
        #          browser">%s</a> when the service has a home page, else the
        #          bare title
        # Settled from FUN_004253cc's own dataflow: local_8c (icon html) is
        # built first, local_78 (link-or-title) second, and the card format
        # takes them in that order. ADD ESP,0x2c after the call confirms 9
        # varargs for the 9 specifiers, so no argument is unaccounted for.
        # The port leaves slot 1 empty and never emits the browser link --
        # nothing here has an icon to put there, and inventing one would be a
        # guess. docs/review/DICT_CARD_BUILDER_2026-10-10.md §2 records it.
        #
        # SLOT 1 (icon). Measured 2026-10-12 from the disassembly of
        # FUN_004253cc's own branch at 0x0042546a..0x004254de: the function
        # pushes 0x522b00 (the wide "Service.ico") at 0x0042546a, builds
        # Services/<name>/Service.ico, calls GetFileAttributesW
        # (CALL dword ptr [0x0050d3b4]) at 0x004254c3, and on
        # CMP EAX,-0x1 / JZ 0x004254e3 skips the file:/// format
        # (PUSH 0x51e7d4) entirely -- jumping straight past the <img src>
        # build. So an absent .ico yields NO <img> in slot 1, not a
        # Default.ico reference: 0x522a78 ("Default.ico") is referenced from
        # a different function (file 0x5a903) and never appears on this path.
        # On this host the file never exists, so the faithful port emits the
        # same empty slot native would.
        icon_html = ""
        #
        # SLOT 2 (link-or-title). service_link() above returns native's
        # serviceLink(); when it is "" the bare title is emitted, matching
        # the FUN_00401ec9 else-branch. The title is escaped because it is
        # service metadata reaching HTML, and the href is a constant from
        # the recovered JS -- never user input -- so it is not escaped.
        link = service_link(title)
        header = (_LINK_WRAP % (link, _html.escape(title)) if link
                  else _html.escape(title))
        cards.append(
            f'<div id="qt-s{sid}" class="qt-card">'
            f'<div id="qt-h{sid}" class="qt-header" '
            f'ondblclick="toggle({sid});" onselectstart="return false;">'
            f'{icon_html}{header}</div>'
            f'<div id="qt-d{sid}" class="qt-data">'
            f'<input type="button" id="qt-l{sid}" '
            f'onclick="fullEntry({sid});return false;" '
            f'class="qt-read-more" value="READ MORE"></input>'
            f'{frag}</div></div>')
        menu_calls.append(
            f"appendMenuItem({sid}, {title!r}, '');checkEntry({sid});")
    # FUN_00425767's zero-result state. The card counter at +0x180 is the SAME
    # counter that gates showNavigation() below, so "no cards" is one branch
    # in native, not a case the renderer forgets. The query word is substituted
    # in, and it is escaped because it is user input reaching HTML.
    body = "\n".join(cards) if cards else (
        NO_RESULTS % _html.escape(query or ""))
    page = tpl.replace(
        '<div id="qt-content" class="qt-content"></div>',
        '<div id="qt-content" class="qt-content">' + body + "</div>")
    page = page.replace(
        "</body>",
        "<script>window.onload=function(){" + "".join(menu_calls)
        + "if(document.querySelectorAll('.qt-card').length>1)showNavigation();"
        + "}</script></body>")
    return page


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from qtranslate.services import dictionary as D
    frags = [("oxford", "Oxford", D.oxford_lookup("hello")[:2000])]
    open("dict_demo.html", "w", encoding="utf-8").write(render_cards(frags))
    print("wrote dict_demo.html")
