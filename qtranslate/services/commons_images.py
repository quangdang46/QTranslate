"""Wikimedia Commons image search -- the .tmp ``wikimedia-reference``
plugin's CommonsImageSearchService port.

Reference: .tmp/QTranslate/plugins/wikimedia-reference
(WikimediaClient.searchImages + CommonsImageSearchService). Commons is
ONE wiki shared by every language edition, so the request takes no
language; ``generator=search`` + ``gsrnamespace=6`` restricts hits to
the File: namespace, ``filetype:bitmap|drawing`` keeps audio/video/PDF
out of a thumbnail grid, and ``iiurlwidth`` asks Commons for a
thumbnail instead of the original (some files run to tens of MB).

formatversion=2 returns ``query.pages[]`` with ``imageinfo[0]``
carrying ``thumburl``/``url``/``descriptionurl`` and ``extmetadata``
(Artist, LicenseShortName -- both HTML, stripped to text). Pages with
no thumbnail are dropped like the Kotlin ``toResult`` does.

No key, no account: the only outbound data is the search term.
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request

from qtranslate import common

API = "https://commons.wikimedia.org/w/api.php"
_UA = {"User-Agent": "QTranslate/6.10 (image search)"}
THUMBNAIL_WIDTH = 480          # Kotlin THUMBNAIL_WIDTH
DEFAULT_LIMIT = 12

_MEDIA_FILETYPES = {"BOTH": "bitmap|drawing", "PHOTOS": "bitmap",
                    "DIAGRAMS": "drawing"}

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_markup(value):
    """extmetadata credits arrive as HTML (usually a link around the
    name); Jsoup.parseBodyFragment(...).text() in Kotlin."""
    if not value:
        return ""
    text = _TAG_RE.sub(" ", str(value))
    return html.unescape(text).strip()


def _params(query, limit, media):
    return {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "generator": "search",
        "gsrsearch": "%s filetype:%s"
                     % (query, _MEDIA_FILETYPES.get(
                         (media or "BOTH").upper(), "bitmap|drawing")),
        # Namespace 6 is File: -- without it search returns article
        # pages, which have no image to show.
        "gsrnamespace": 6,
        "gsrlimit": max(1, min(int(limit or DEFAULT_LIMIT), 50)),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": THUMBNAIL_WIDTH,
    }


def search_images(query, limit=DEFAULT_LIMIT, media="BOTH", opener=None):
    """Return [{title, thumbnail, url, source, attribution, license}].

    ``opener`` is forwarded to ``common.http_open`` so tests can stub
    the transport, same contract the other service modules carry.
    """
    query = (query or "").strip()
    if not query:
        return []
    url = API + "?" + urllib.parse.urlencode(_params(query, limit, media))
    req = urllib.request.Request(url, headers=_UA)
    with common.http_open(req, opener) as r:
        obj = json.loads(r.read().decode("utf-8", errors="replace"))
    pages = ((obj.get("query") or {}).get("pages")) or []
    out = []
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        # Kotlin: thumbnailUrl ?: return null -- a page with only the
        # original URL is dropped, not shown at full size.
        thumb = info.get("thumburl")
        full = info.get("url")
        if not thumb or not full:
            # Commons returns no thumbnail for formats it cannot
            # rasterize -- drop the file like Kotlin's toResult.
            continue
        meta = info.get("extmetadata") or {}
        title = str(page.get("title") or "")
        title = title[5:] if title.startswith("File:") else title
        title = title.rsplit(".", 1)[0].strip()
        out.append({
            "title": title or str(page.get("title") or ""),
            "thumbnail": thumb,
            "url": full,
            "source": info.get("descriptionurl") or "",
            "attribution": _strip_markup(
                (meta.get("Artist") or {}).get("text")),
            "license": _strip_markup(
                (meta.get("LicenseShortName") or {}).get("text")),
        })
    return out
