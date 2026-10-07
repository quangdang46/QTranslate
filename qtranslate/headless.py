"""Headless-browser fetch helper (Playwright + Chromium).

Used for providers whose pages are JS-challenge walled (Anubis bot-wall
on WordReference) or need browser TLS fingerprinting — cases plain
urllib cannot reach. Mirrors what the native app does with its embedded
Chakra engine + libcurl cookie jar, but with a real browser.

Run: uv run --with playwright python -I qtranslate/headless.py <url>
Requires one-time: uv run --with playwright python -m playwright
install chromium --only-shell
"""
import sys

sys.path.insert(0, ".")

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def fetch_html(url: str, wait_ms: int = 10000, timeout: int = 30000) -> str:
    """Load url in headless Chromium (stealth flags), return rendered HTML.

    Tries in-process playwright first; falls back to
    `uv run --with playwright` subprocess when playwright is not
    installed in the current interpreter (it is only provisioned via
    `uv run` in this repo).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return _fetch_via_uv(url, wait_ms, timeout)
    with sync_playwright() as p:
        b = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(user_agent=_UA, locale="en-US")
        pg = ctx.new_page()
        pg.goto(url, timeout=timeout)
        pg.wait_for_timeout(wait_ms)
        html = pg.content()
        b.close()
    return html


def _fetch_via_uv(url: str, wait_ms: int, timeout: int) -> str:
    import os
    import subprocess
    import tempfile
    helper = (
        "import sys; sys.path.insert(0, '.');"
        "from qtranslate.headless import fetch_html;"
        f"open(r'{tempfile.gettempdir()}/wr_fetch.html','w',encoding='utf-8')"
        f".write(fetch_html({url!r}, {wait_ms}, {timeout}))"
    )
    subprocess.run(
        ["uv", "run", "--with", "playwright", "python", "-I", "-c", helper],
        capture_output=True, timeout=timeout // 1000 + 60)
    out = os.path.join(tempfile.gettempdir(), "wr_fetch.html")
    with open(out, encoding="utf-8") as f:
        return f.read()


def wordreference_html(word: str, sl: str = "en", tl: str = "ru") -> str:
    """Fetch a WordReference entry page through the Anubis wall.

    Retries with longer waits until the article marker appears
    (Anubis JS-challenge solve time varies run to run).
    """
    import urllib.parse
    url = (f"https://www.wordreference.com/{sl}{tl}/"
           f"{urllib.parse.quote(word)}")
    for wait in (10000, 20000, 30000):
        html = fetch_html(url, wait_ms=wait)
        if "articleWRD" in html or 'id="article"' in html:
            return html
    return html


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else \
        "https://www.wordreference.com/enru/hello"
    html = fetch_html(url)
    print(f"len={len(html)} "
          f"article={'articleWRD' in html or 'id=\"article\"' in html}")
