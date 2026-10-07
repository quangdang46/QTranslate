"""Dictionary multi-service HTML renderer — port of RT_HTML id 192.

The native DictionaryWindow renders every provider's HTML fragment into
this shell template (qt-s{id}/qt-h{id}/qt-d{id}/qt-l{id} cards + nav
menu + toggle/fullEntry/checkEntry JS). This module reproduces it so
`app.py` dict mode shows collapsible per-service cards like the original.
"""
import html as _html
import os

_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "dict_template.html")


def load_template() -> str:
    with open(_TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


def render_cards(results: list) -> str:
    """results: [(service_id, title, html_fragment)]. Returns full page."""
    tpl = load_template()
    cards = []
    menu_calls = []
    for i, (sid, title, frag) in enumerate(results):
        cards.append(
            f'<div class="qt-card" id="qt-s{sid}">'
            f'<div class="qt-header" id="qt-h{sid}" '
            f'onclick="toggle({sid})">{_html.escape(title)}</div>'
            f'<div class="qt-data" id="qt-d{sid}">{frag}'
            f'<a class="qt-read-more" id="qt-l{sid}" '
            f'href="javascript:void(0)" onclick="fullEntry({sid})" '
            f'style="display:none">more...</a></div></div>')
        menu_calls.append(
            f"appendMenuItem({sid}, {title!r}, '');checkEntry({sid});")
    page = tpl.replace(
        '<div id="qt-content" class="qt-content"></div>',
        '<div id="qt-content" class="qt-content">' + "\n".join(cards) + "</div>")
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
