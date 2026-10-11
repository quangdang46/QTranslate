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
        cards.append(
            f'<div id="qt-s{sid}" class="qt-card">'
            f'<div id="qt-h{sid}" class="qt-header" '
            f'ondblclick="toggle({sid});" onselectstart="return false;">'
            f'{_html.escape(title)}</div>'
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
