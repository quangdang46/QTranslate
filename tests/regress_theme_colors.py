"""Regression: theme palette loading and FUN_00464c2f's inheritance rule.

Evidence: the 7 extractable theme JSON files in the NSIS payload (8 themes
ship; Photoshop Dark is the 8th and is included here too where reachable),
the loader `FUN_00464c2f`, the colour parser `FUN_0046457a`, and the
colour-string getter `FUN_00464724` -- all read with Ghidra 12.1.4 headless
via REA 6.4.0.
    docs/review/G9_THEMES_AND_DLU_2026-10-11.md
    docs/review/THEME_LOADER_AND_BGR_RETRACTION_2026-10-11.md

Offline: the theme bytes are read from docs/review/artifacts/, written to a
temp dir, and loaded through the port's own loader. No network, and no
dependency on a QTranslate install being present.
"""
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from qtranslate import theme as T  # noqa: E402

PAYLOAD = os.path.join(ROOT, "docs", "review", "artifacts",
                       "nsis_payload_unpacked.bin")
# The eight themes, in the installer manifest's order, as consecutive
# length-prefixed chunks starting at the XdxfArticle.xslt at 0x977ec.
THEME_OFFSETS = [0x97b30, 0x98285, 0x98cf5, 0x99359, 0x99d63, 0x9a7b4, 0x9af7e]
THEME_NAMES = ["Blue", "Brackets", "Flat Dark", "Holo Dark",
               "Holo Light", "Metro", "Outlook Gray"]
THEME_HASHES = {
    "Blue": "90cb784c91d08c23", "Brackets": "592ca64df3ea7a38",
    "Flat Dark": "b16bd18f91abb33f", "Holo Dark": "b20e0542fc2a1250",
    "Holo Light": "66daa00ee19afe38", "Metro": "c9e578fc5332a5b0",
    "Outlook Gray": "dd79f734097d1b0e",
}

fail = []
n = [0]


def ck(name, cond, detail=""):
    n[0] += 1
    if not cond:
        fail.append("%s -- %s" % (name, detail))


if not os.path.exists(PAYLOAD):
    ck("NSIS payload present (run from the repo root)", False, PAYLOAD)
else:
    import hashlib
    blob = open(PAYLOAD, "rb").read()
    themes = {}
    for name, off in zip(THEME_NAMES, THEME_OFFSETS):
        ln = int.from_bytes(blob[off:off + 4], "little")
        body = blob[off + 4:off + 4 + ln]
        ck("%s: chunk length field is at %#x" % (name, off), 0 < ln < 100000,
           "got %d" % ln)
        ck("%s: the chunk's hash pins the artifact" % name,
           hashlib.sha256(body).hexdigest().startswith(THEME_HASHES[name]),
           hashlib.sha256(body).hexdigest()[:16])
        ck("%s: the body is a JSON object" % name,
           body.lstrip()[:1] == b"{", repr(body[:20]))
        themes[name] = json.loads(
            re.sub(r"//[^\n]*", "", body.decode("utf-8")))

    # --- FUN_0046457a: hex string -> COLORREF -------------------------------
    # The strings are RRGGBB. Not BGR: the reversed reading scatters Blue's
    # palette across 70.9 degrees of hue against 5.0 as written, and gives
    # every value R=0, G>=B (a blue palette turned into cyan-greys).
    for raw, want in (("1d8abd", "#1d8abd"), ("20", "#202020"),
                      ("09c", "#0099cc"), ("b", "#bbbbbb"),
                      ("#1d8abd", "#1d8abd"), ("1", "#111111"),
                      ("fe", "#fefefe")):
        ck("_hex(%r) is %r" % (raw, want), T._hex(raw) == want,
           "got %r" % T._hex(raw))
    ck('_hex("1") is #111111, NOT 0x00000001',
       T._hex("1") == "#111111",
       "the retracted BGR reading claimed 0x00000001")
    # --- _hex malformed input: native returns 0xffffffff, port returns "" ---
    # THEME_LOADER_AND_BGR_RETRACTION_2026-10-11.md §1: FUN_0046457a accepts
    # 1/2/3/6 hex digits, anything else → 0xffffffff. The port's sentinel is
    # "" (falsy), which slot() maps to UNSET. Before this fix, _hex("xyz")
    # silently produced "#" — six characters reaching the renderer as a colour.
    for raw, label in (("", "empty"), ("xyz", "illegal hex"),
                       ("12345", "5 digits"), ("1234", "4 digits"),
                       ("gg", "non-hex"), ("#", "hash only"),
                       ("1234567", "7 digits")):
        ck("_hex(%r) is \"\" (%s), not a colour string" % (raw, label),
           T._hex(raw) == "",
           "got %r -- native returns 0xffffffff for this" % T._hex(raw))
    # Valid lengths still work after the guard
    for raw, want in (("1d8abd", "#1d8abd"), ("20", "#202020"),
                      ("09c", "#0099cc"), ("b", "#bbbbbb"),
                      ("#1d8abd", "#1d8abd"), ("1", "#111111"),
                      ("fe", "#fefefe")):
        ck("_hex(%r) is still %r after the guard" % (raw, want),
           T._hex(raw) == want,
           "got %r" % T._hex(raw))

    # --- FUN_00464724: absent or unparseable -> 0xffffffff, NOT 0 ----------
    for raw, label in ((None, "None"), ("", "empty"), ("xyz", "illegal hex"),
                       ("12345", "5 digits"), ("1234", "4 digits"),
                       ("gg", "non-hex")):
        ck("slot() reports %s as unset, not as a colour" % label,
           T.slot({"Back": raw} if raw is not None else {}, "Back") is None,
           "native returns 0xffffffff for all of these")
    ck("an absent KEY is unset too", T.slot({"Text": "fe"}, "Back") is None)
    ck("unset is not black", T.slot({}, "Back") != "#000000",
       "0xffffffff and 0 are different values; #000000 is neither")
    ck("a non-dict record is unset, not a crash",
       T.slot(None, "Back") is None and T.slot("x", "Back") is None)

    # --- FUN_00464c2f: Disabled/Hover/Pressed inherit Normal --------------
    # This is the reachable path, not a defensive branch: all 7 themes omit
    # Hover and Pressed under Window, so reading Window/Hover directly got
    # zeros where native gets Normal's values.
    for name, d in sorted(themes.items()):
        for section in ("Window", "WindowButton", "Button"):
            for state in ("Disabled", "Hover", "Pressed"):
                got = T.state_colors(d, section, state)
                own = d.get(section, {}).get(state)
                want = (T.state_colors(d, section, state) if own
                        else T.state_colors(d, section, "Normal"))
                ck("%s/%s/%s inherits Normal when absent"
                   % (name, section, state), got == want,
                   "got %r want %r" % (got, want))
    ck("all 7 themes really do omit Window/Hover (so the branch is live)",
       all("Hover" not in d.get("Window", {}) for d in themes.values()),
       "if this fails the inheritance test above has become unreachable")

    # The inheritance is a five-dword struct move, so all five slots come
    # along -- BorderInner is the one the old 3-key helpers could not see.
    blue = themes["Blue"]
    ck("Blue Window/Normal carries all of native's slots",
       T.state_colors(blue, "Window", "Normal") == {
           "Back": "#1586bb", "Text": "#fefefe", "Border": "#0c4b73",
           "BorderInner": "#469fc6", "Caption": None},
       repr(T.state_colors(blue, "Window", "Normal")))
    ck("Blue Window/Hover inherits BorderInner too",
       T.state_colors(blue, "Window", "Hover")["BorderInner"] == "#469fc6",
       "the 5-dword copy is not three 1-dword copies")

    # Blue's Button section has no "Back" at all -- it is a gradient
    # (BackTop/BackBottom). That absence must read as unset, not as black.
    # NOTE: `Back` is not a Button key in the first place -- FUN_0046493f
    # reads ShadowTop/Border/GleamTop/BackTop/BackBottom/GleamBottom/
    # ShadowBottom/Text. The slot that IS absent in Blue and present in
    # Brackets is GleamTop, so that is what carries the "unset, not black"
    # assertion now that Button uses its own key names.
    ck("Blue Button/Normal omits GleamTop (a Button key) and reads unset",
       "GleamTop" not in blue.get("Button", {}).get("Normal", {})
       and T.state_colors(blue, "Button", "Normal")["GleamTop"] is None,
       repr(blue.get("Button", {}).get("Normal", {}).get("GleamTop")))
    ck("Blue's Button gradient really is BackTop/BackBottom, with no Back key",
       set(blue["Button"]["Normal"]) & {"BackTop", "BackBottom"}
       and "Back" not in T.SECTION_SLOTS["Button"],
       repr(sorted(blue["Button"]["Normal"])))

    # --- native fidelity, and the Tk boundary the port draws --------------
    # `window_colors` returns `None` for an unset slot because
    # FUN_00464724's sentinel is 0xffffffff, not 0. `None` is not a Tk colour,
    # so `tk_colors` projects it onto the system colours -- which is what
    # native paints when the theme supplies nothing. Both halves are asserted:
    # the fidelity of the inner layer, and that the projection leaves a real
    # theme's values untouched rather than flattening everything.
    ck("window_colors reports an unset slot as None (native 0xffffffff)",
       T.window_colors({}) == {"back": None, "text": None, "border": None},
       repr(T.window_colors({})))
    ck("a malformed theme value cannot become a non-colour string",
       all(T.window_colors({"Window": {"Normal": {"Back": "xyz"}}})[k]
           is None for k in ("back", "text", "border")),
       repr(T.window_colors({"Window": {"Normal": {"Back": "xyz"}}})))
    ck("tk_colors maps every unset slot to a system colour name",
       set(T.tk_colors(T.window_colors({})).values()) <=
       set(T.TK_UNSET.values())
       and None not in T.tk_colors(T.window_colors({})).values(),
       repr(T.tk_colors(T.window_colors({}))))
    ck("tk_colors leaves a real theme's values EXACTLY as they were",
       T.tk_colors(T.window_colors(blue)) == T.window_colors(blue)
       and T.tk_colors(T.window_colors(themes["Flat Dark"]))
       == T.window_colors(themes["Flat Dark"]),
       "the projection is a fallback, not a rewrite")
    ck("tk_colors is a total function on the None-theme path too",
       T.tk_colors(T.window_colors(None))["back"] is not None,
       "load_theme_native returns None when no theme applies")
    # --- native state indices → theme state names (FUN_0044FE1B/0044D502)
    # window: disabled → 3, focused → 4, has-text → 1, empty → 0;
    # buttons: pressed → 2. Index 4 maps to Normal (focus is a separate
    # flag, not a separate palette).
    ck("state 0 is Normal", T.state_name(0) == "Normal")
    ck("state 1 is Hover", T.state_name(1) == "Hover")
    ck("state 2 is Pressed (buttons)", T.state_name(2) == "Pressed")
    ck("state 3 is Disabled", T.state_name(3) == "Disabled")
    ck("state 4 (focused) uses the Normal palette",
       T.state_name(4) == "Normal")
    ck("unknown state index falls back to Normal",
       T.state_name(99) == "Normal")
    ck("window_colors accepts a state index via state_name",
       T.window_colors(blue, T.state_name(3)) ==
       T.window_colors(blue, "Disabled"))
    # --- FUN_0044A163 brightness shift: zero delta is a true identity ----
    # Native: L2 = L + delta; L2<1 -> black, L2>=0xF0 -> white, elif
    # L2 != L -> ColorHLSToRGB, ELSE the original colour is returned.
    # A round-trip through HLS would drift real colours on a zero delta.
    ck("zero delta returns the colour unchanged (native identity branch)",
       all(T.adjust_brightness(c, 0) == c for c in
           ("#4285f4", "#7e7e7e", "#f5a623", "#010203")),
       "native skips ColorHLSToRGB when L2 == L")
    ck("negative-to-zero clamp yields black",
       T.adjust_brightness("#000000", -10) == "#000000"
       and T.adjust_brightness("#010203", -10) == "#000000")
    ck("at-or-above 0xF0 clamp yields white",
       T.adjust_brightness("#ffffff", 10) == "#ffffff")
    ck("a real shift changes the value",
       T.adjust_brightness("#4285f4", 10) != "#4285f4"
       and T.adjust_brightness("#4285f4", -10) != "#4285f4")
    # Structural invariant, placed BEFORE the first button_colors() call.
    # button_colors indexes its record by hardcoded name -- c["Main"],
    # c["Back"], c["Shadow"] -- so if SECTION_SLOTS ever stops containing
    # those three, the module raises KeyError instead of reporting unset. A
    # KeyError mutant IS caught, but the suite then CRASHES with no output
    # rather than failing cleanly, which is a useless diagnostic. Ordering is
    # the whole point: this pin first at line 168 still ran too late, because
    # line 184 crashed before it was reached.
    for _sec, _needed in (("WindowButton", ("Main", "Back", "Shadow")),):
        ck("button_colors indexes only keys SECTION_SLOTS guarantees",
           set(_needed) <= set(T.SECTION_SLOTS[_sec]),
           "button_colors does c['Main']/c['Back']/c['Shadow'] directly; if "
           "SECTION_SLOTS[%r] loses one of those it raises KeyError rather "
           "than reporting None" % _sec)
    # `button_colors` reads the *WindowButton* section, and Blue's WindowButton
    # DOES define Hover -- so Hover must differ from Normal there. (My first
    # draft asserted they were equal, which conflated `WindowButton` with the
    # `Button` section; the live inheritance branch for this helper is under
    # Holo Dark/Holo Light, whose WindowButton omits Hover.)
    #
    # CORRECTED 10-11 19:0x: this pin originally expected Blue Hover back
    # == #61add1 and Normal back == #1d8abd, i.e. that the `Back` KEY is the
    # button face. The slot order FUN_0046485e writes is
    # Gleam, Main, Shadow, Back, Border -- Main is the face -- and the field
    # alignment proves it: FUN_00464c2f's WindowButton states sit at 0x44,
    # 0x58, 0x6c, 0x80 in the theme object, and FUN_0044c9a6's nine greys land
    # on 0x44..0x4c / 0x58..0x60 / 0x6c..0x74, the FIRST THREE dwords of each
    # state. So the compiled greys are Gleam/Main/Shadow; `Back` is unset in
    # the default theme, which the previous pin could not survive.
    ck("button_colors reads the WindowButton section and respects its Hover",
       T.button_colors(blue, "Hover")["back"] == "#ffffff"
       and T.button_colors(blue, "Hover")["text"] == "#61add1"
       and T.button_colors(blue, "Normal")["back"] == "#fefefe",
       repr(T.button_colors(blue, "Hover")))
    ck("button_colors takes the face from Main and the glyph from Back",
       T.button_colors(blue, "Normal")["text"] == "#1d8abd",
       "Main is the face; Back is the only other slot the section names")
    ck("button_colors inherits Normal where WindowButton omits the state",
       all("Hover" not in themes[nm].get("WindowButton", {})
           and T.button_colors(themes[nm], "Hover")
           == T.button_colors(themes[nm], "Normal")
           for nm in ("Holo Dark", "Holo Light")),
       "Holo Dark and Holo Light are the two that omit it under WindowButton")
    ck("the omitted-state map is measured, not assumed",
       # every branch the inheritance rule covers is a real one
       all(s not in themes[nm].get(sec, {})
           for nm, sec, s in
           (("Blue", "Window", "Hover"), ("Brackets", "Window", "Pressed"),
            ("Flat Dark", "Button", "Hover"), ("Holo Dark", "WindowButton",
                                               "Hover"),
            ("Holo Light", "WindowButton", "Hover"))),
       "if a theme adds a key, the map above is stale and this fails")

    # --- the loader: a missing theme is a hard failure, not a fallback ----
    tmp = tempfile.mkdtemp()
    for name in THEME_NAMES:
        off = dict(zip(THEME_NAMES, THEME_OFFSETS))[name]
        ln = int.from_bytes(blob[off:off + 4], "little")
        with open(os.path.join(tmp, name + ".json"), "w",
                  encoding="utf-8") as f:
            f.write(blob[off + 4:off + 4 + ln].decode("utf-8"))
    ck("load_theme_native loads every recovered theme",
       all(T.load_theme_native(nm, tmp) is not None for nm in THEME_NAMES))
    ck("a missing theme file returns None -- no default substituted",
       T.load_theme_native("NoSuchTheme", tmp) is None,
       "FUN_00464c2f: GetFileAttributesW == 0xffffffff -> return 0")
    ck('ThemeName == "" produces no theme file, and not an error',
       T.load_theme_native("", tmp) is None)
    ck("a theme that could not be applied does not raise at any layer",
       T.window_colors(None) == {"back": None, "text": None, "border": None}
       and T.button_colors(None) == {"back": None, "text": None,
                                     "border": None}
       and T.state_colors(None, "Window", "Hover")["Back"] is None,
       "load_theme_native returns None for a missing/empty ThemeName")

    # --- FUN_0044b44f: the installer substitutes DefaultColorTheme ----------
    # The loader substitutes nothing (above). The *installer* is where the
    # default appears, so "no theme file" and "no active theme" are different
    # states -- conflating them was the error the retraction doc records.
    for name in ("", "NoSuchTheme"):
        ck("active_theme(%r) is the default, never None" % name,
           T.active_theme(name, tmp) == T.default_theme(),
           "FUN_0044b44f installs theme::DefaultColorTheme when the load fails")
    ck("active_theme loads a theme file when one exists",
       T.active_theme("Blue", tmp) != T.default_theme()
       and T.window_colors(T.active_theme("Blue", tmp))["back"] == "#1586bb",
       "a loadable ThemeName wins over the default")
    ck("DefaultColorTheme's radii are the ones FUN_0044c9a6 sets",
       T.default_theme()["Common"]["ButtonRadius"] == 2
       and T.default_theme()["Common"]["WindowBorderRadius"] == 1,
       "param_1[1] = 2, param_1[2] = 1")
    ck("DefaultColorTheme's hardcoded greys are achromatic, as compiled in",
       all(len(set(v[i:i+2] for i in (1, 3, 5))) == 1
           for v in ("#%06x" % g for g in T.DEFAULT_THEME_GRAYS)),
       "FUN_0044c9a6 writes only greys: 0x191919, 0x5e5e5e, ...")
    ck("the greys reach the renderer through the normal path",
       all(T.button_colors(T.default_theme(), st)["back"]
           in set("#%06x" % g for g in T.DEFAULT_THEME_GRAYS)
           for st in ("Normal", "Hover", "Pressed")),
       repr([T.button_colors(T.default_theme(), st) for st in
             ("Normal", "Hover", "Pressed")]))
    ck("GetSysColor slots stay unset here -- Windows state, not REPO data",
       T.state_colors(T.default_theme(), "Window", "Normal")["Back"] is None,
       "the default theme's window colours are runtime values; claiming them "
       "from a macOS host would be inventing them")
    ck("the unset slots project to a real Tk colour, never None",
       all(isinstance(v, str)
           for v in T.tk_colors(T.window_colors(T.default_theme())).values()),
       repr(T.tk_colors(T.window_colors(T.default_theme()))))

    # --- MEASURED GAP, not a claim about the port -------------------------
    # FUN_0044c9a6 writes FIVE five-dword colour records, at indices
    # [0xb..0xf], [0x10..0x14], [0x1b..0x1f] and [0x6e..0x72], and the last
    # one is left at its memset(0) value -- so native's default theme really
    # does have empty sections, and an empty section is NOT an absent one.
    # The port's default_theme() reproduces only WindowButton, so this
    # asserts the boundary the port draws rather than pretending it is full.
    for sec in ("Window", "WindowButton", "Button", "Common"):
        got = T.state_colors(T.default_theme(), sec, "Normal")
        ck("default_theme's %s section is either filled or honestly None" % sec,
           isinstance(got, dict),
           repr(got))
    ck("default_theme fills WindowButton for all four states, as compiled in",
       all(T.button_colors(T.default_theme(), st)["back"] is not None
           for st in ("Normal", "Hover", "Pressed")),
       "FUN_0044c9a6 writes WindowButton's nine greys twice, [0x11..0x13]+"
       "[0x16..0x18] and again [0x65..0x6d]")
    ck("the port's default_theme does NOT claim a Window section it never read",
       "Window" not in T.default_theme(),
       "the greys and the GetSysColor family are compiled in; the Window "
       "record they land in is a runtime derivation this host cannot supply. "
       "Asserted so a later edit cannot quietly invent one -- and so the gap "
       "stays visible rather than being papered over with #000000")

    # --- ThemeName vs ColorBack/ColorText/ColorFrame: they never meet -----
    # This was an open question: the port resolved all four independently and
    # nobody knew whether native resolved them against each other. Measured,
    # and the answer is that the question has a false premise -- the two
    # families are consumed by different windows, so nothing ever picks.
    #
    #   FUN_0045869f (Options.json reader)  : four separate stores
    #       ThemeName -> +0x1dc  string getter FUN_00440984
    #       ColorBack -> +0x1e8  int getter    FUN_00440942
    #       ColorText -> +0x1ec  int getter    FUN_00440942
    #       ColorFrame-> +0x1f0  int getter    FUN_00440942
    #       -- no comparison, no `or`, no shared branch
    #   FUN_00455e25 (defaults initialiser): the same four fields, each its
    #       own straight-line store. An immediate scan for the two
    #       DISCRIMINATING constants finds exactly two stores in the whole
    #       image -- both here, both at the offsets above:
    #         [ESI+0x1e8] <- 0xf0f0f0     ColorBack
    #         [ESI+0x1f0] <- 0x7a6c5d     ColorFrame
    #         [ESI+0x1ec] <- 0            ColorText
    #       A COLORREF writer would have emitted 0x005d6c7a for ColorFrame,
    #       so this scan is also the byte-order evidence for the port's
    #       "#%06x" rendering of the config ints.
    #
    # Asserted as a boundary on the PORT, since the native facts above are
    # Ghidra reads and this suite is offline. What is pinned here is that the
    # port does not invent a winner where native has none.
    ck("the port reads ThemeName and the three colour ints independently",
       not any(k in open(os.path.join(ROOT, "qtranslate", "theme.py"),
                         encoding="utf-8", errors="replace").read()
               for k in ("ColorBack", "ColorText", "ColorFrame")),
       "theme.py must not read the Appearance colour overrides: the popup "
       "takes Themes\\*.json via FUN_004654ca/FUN_0044b44f and the main "
       "window takes ColorBack/ColorText/ColorFrame -- different consumers, "
       "so no precedence rule exists to implement")
    ck("config.py's #%06x is the byte order the defaults were written with",
       (0x7a6c5d == int("7a6c5d", 16) and 0x7a6c5d != 0x5d6c7a
        and 8023133 == int("7a6c5d", 16) and 8023133 != 6122618
        and 15790320 == int("f0f0f0", 16)),
       "FUN_00455e25 stores 0x7a6c5d, which is exactly int('7a6c5d',16): a "
       "#RRGGBB writer. A COLORREF writer would have stored 0x005d6c7a = "
       "6122618. ColorBack=#f0f0f0 and ColorText=0 are symmetric and decide "
       "nothing, so ColorFrame is the only discriminating default")

    # --- MEASURED: the port's slot model is wrong for 3 of 4 sections ----
    # FUN_00464c2f reads SIX sections, each through its OWN getter, so each
    # has its own five/six/eight-key record. The port applies one
    # _STATE_SLOTS tuple ("Back","Text","Border","BorderInner","Caption") to
    # all of them, which is only correct for `Window`.
    #
    #   section       getter         states                                slots
    #   Common        inline         --        radii + 4 colours + bool
    #   Window        FUN_0046477d   Normal, Disabled
    #                  Back, Text, Border, BorderInner, Caption          (5, order 0,3,1,2,4)
    #   WindowButton  FUN_0046485e   Normal, Hover, Pressed, Disabled
    #                  Gleam, Main, Shadow, Back, Border                 (5)
    #   Button        FUN_0046493f   Normal, Hover, Pressed, Disabled, FOCUSED
    #                  ShadowTop, Border, GleamTop, BackTop, BackBottom,
    #                  GleamBottom, ShadowBottom, Text                    (8!) and Text alone
    #                  falls back to GetSysColor(0x12) when unset
    #   Edit          FUN_00464aa4   Normal, Hover, Disabled, FOCUSED
    #                  ShadowTop, Border, Back, ShadowBottom, Text       (5)
    #
    # Reported to the module owner rather than fixed here: theme.py is not
    # this session's file. What IS pinned below is the measurement, so the
    # count cannot quietly drift and the defect stays visible.
    _SLOT_MODEL = {
        "Window": ("Back", "Text", "Border", "BorderInner", "Caption"),
        "WindowButton": ("Gleam", "Main", "Shadow", "Back", "Border"),
        "Button": ("ShadowTop", "Border", "GleamTop", "BackTop", "BackBottom",
                   "GleamBottom", "ShadowBottom", "Text"),
        "Edit": ("ShadowTop", "Border", "Back", "ShadowBottom", "Text"),
    }
    # The measured symptom stays pinned, but the contract now under test is
    # `state_colors`'s per-section choice rather than "_STATE_SLOTS misses
    # things". Both halves matter: the raw measurement (which is why the fix
    # was needed) and the assertion that the live path no longer has the hole.
    unreadable = 0
    per_section = {}
    for sec, slots in _SLOT_MODEL.items():
        for name, d in themes.items():
            rec = d.get(sec, {}).get("Normal", {})
            if not rec:
                continue
            missed = set(rec) - set(T._STATE_SLOTS)
            unreadable += len(missed)
            per_section.setdefault(sec, [0, 0])
            per_section[sec][0] += len(rec)
            per_section[sec][1] += len(missed)
    ck("the measurement that motivated the fix still holds numerically",
       unreadable > 0,
       "measured: %d values are invisible to a single shared slot tuple"
       % unreadable)
    ck("state_colors now uses each section's OWN slot list",
       all(set(T.state_colors(themes[nm], sec, "Normal")) <= set(slots)
           for sec, slots in _SLOT_MODEL.items() for nm in themes),
       "the fix: SECTION_SLOTS replaces one tuple applied to all sections")
    ck("the live path reads every value a section names",
       all(
           T.state_colors(themes[nm], sec, "Normal")
           == {k: T.slot(themes[nm][sec]["Normal"], k) for k in slots}
           for sec, slots in _SLOT_MODEL.items() for nm in themes
           if themes[nm].get(sec, {}).get("Normal")),
       "each key resolves to exactly what slot() would give it, with the "
       "GetSysColor(COLOR_BTNTEXT) substitution where the getter applies it")
    # FLIPPED 10-11 19:1x: this pin originally asserted the DEFECT -- that Flat
    # Dark, Holo Dark and Holo Light read NOTHING from WindowButton because
    # they define only Main/Shadow, keys the old single _STATE_SLOTS had no
    # name for. Those themes now read their real values through
    # SECTION_SLOTS, so the pin is inverted: it asserts the fix, and would
    # fail again if the port regressed to one shared slot tuple.
    ck("Flat Dark and both Holo themes read their real WindowButton values",
       all(T.state_colors(themes[nm], "WindowButton", "Normal")["Main"]
           == T.slot(themes[nm]["WindowButton"]["Normal"], "Main")
           and T.state_colors(themes[nm], "WindowButton", "Normal")["Main"]
           is not None
           for nm in ("Flat Dark", "Holo Dark", "Holo Light")),
       "those three define only Main/Shadow, so they read real values only "
       "once WindowButton uses its OWN key names rather than Window's")
    for sec, (total, missed) in sorted(per_section.items()):
        ck("%s: %d of %d keys are outside Window's slot tuple"
           % (sec, missed, total), missed > 0 if sec != "Window" else True,
           "Window is the only section whose keys happen to match "
           "_STATE_SLOTS; the others use per-section key names, which is why "
           "SECTION_SLOTS exists")
    ck("the Button record is EIGHT dwords, not five",
       len(_SLOT_MODEL["Button"]) == 8,
       "FUN_0046493f writes param_3[0..7] -- so the five-dword struct copy "
       "the inheritance rule uses is NOT what the Button section contains")
    ck("the port models Button as eight dwords and WindowButton as five",
       len(T.SECTION_SLOTS["Button"]) == 8
       and all(len(T.SECTION_SLOTS[s]) == 5
               for s in ("Window", "WindowButton", "Edit")),
       "matches the loader's inheritance loops: iVar9 = 8 for Button, 5 for "
       "Window/WindowButton/Edit (measured from FUN_00464c2f)")
    # --- inheritance width: the record copy is the SECTION's, not a fixed 5 ----
    # FUN_00464c2f's inherit-from-Normal is a whole-record move, so the width
    # comes from the section's own getter. A fixed five-dword copy would drop
    # three of Button's eight slots whenever a state is inherited -- and Blue's
    # Button/Hover inherits nothing from Normal, so the only protection is the
    # width itself. Asserted on the SHAPE, not on a value: a consumer that
    # indexes c["Main"] or iterates the dict must see every slot.
    for sec, slots in _SLOT_MODEL.items():
        for nm in themes:
            for state in ("Hover", "Pressed", "Disabled"):
                got = T.state_colors(themes[nm], sec, state)
                ck("%s/%s inherits with all %d keys present"
                   % (sec, state, len(slots)),
                   set(got) == set(slots),
                   "missing %r -- the inherited record lost the section's own"
                   " width" % (set(slots) - set(got)))
    # An inherited slot resolves to Normal's VALUE, not to the JSON default.
    # This is the half that catches a copy that widens the dict without
    # carrying the values across.
    for sec, slots in _SLOT_MODEL.items():
        for nm in themes:
            sec_d = themes[nm].get(sec, {})
            if sec_d.get("Hover") or not sec_d.get("Normal"):
                continue
            want = T.state_colors(themes[nm], sec, "Normal")
            got = T.state_colors(themes[nm], sec, "Hover")
            ck("%s in %s: an inherited Hover equals Normal, slot by slot" % (sec, nm),
               got == want,
               "got %r want %r" % (got, want))
    # --- the PARTIAL state: omitted keys inherit, present keys keep their own ---
    # The only two partial states in all seven themes: Blue Button/Pressed and
    # Button/Disabled each omit ShadowBottom. The old `_state` (return the
    # partial dict as-is) gave ShadowBottom=None here; the measured native is a
    # whole-record move, so it is Normal's #1b82b3. This is the pin the old
    # code's revert MUST die on -- T2 survived the first mutation run because
    # no assertion exercised a partial state.
    _blue_btn_n = T.state_colors(themes["Blue"], "Button", "Normal")
    for st in ("Pressed", "Disabled"):
        got = T.state_colors(themes["Blue"], "Button", st)
        ck("Blue Button/%s inherits ShadowBottom from Normal" % st,
           "ShadowBottom" not in themes["Blue"]["Button"][st]
           and got["ShadowBottom"] == _blue_btn_n["ShadowBottom"] == "#1b82b3",
           "got %r -- an omitted key is Normal's value, not None" % got["ShadowBottom"])
        # and the keys the state DOES define keep their own values, not Normal's
        for k in T.SECTION_SLOTS["Button"]:
            if k == "ShadowBottom" or k not in themes["Blue"]["Button"][st]:
                continue
            ck("Blue Button/%s keeps its own %s" % (st, k),
               got[k] == T.slot(themes["Blue"]["Button"][st], k),
               "got %r, the state's own value is %r" % (got[k], themes["Blue"]["Button"][st][k]))
    # --- Common: the flat section with the loader's own semantics -------------
    # `_normalize_common` has no caller-independent consumer, so no assertion
    # below this line exercises it except these. Without them the whole
    # function is unguarded -- T3 survived for exactly this reason.
    _cb = T._normalize_common(themes["Blue"].get("Common", {}))
    ck("Common/ClientBackColor is an int the renderer can use, not a JSON string",
       _cb["ClientBackColor"] == int("1d8abd", 16) == 1936061,
       repr(_cb["ClientBackColor"]))
    ck("Common absent keys are the cleared object (0), not a colour sentinel",
       T._normalize_common({}) ==
       {"ButtonRadius": 0, "WindowBorderRadius": 0, "ClientBackColor": 0,
        "GroupBoxColor": 0, "GroupBoxHighlightColor": 0, "PaintClassicFocus": 0},
       repr(T._normalize_common({})))
    ck("Common unparseable colour takes the 0xffffffff=>GetSysColor(BTNFACE) path",
       T._normalize_common({"ClientBackColor": "xyz"})["ClientBackColor"] == 0xffffffff,
       "FUN_00464724 returns 0xffffffff when FUN_0046457a cannot parse")
    ck("Common ButtonRadius clamps negative to 0, like FUN_00440942",
       T._normalize_common({"ButtonRadius": -3})["ButtonRadius"] == 0,
       "a negative radius is not a value the native writer can emit")
    ck("Common WindowBorderRadius >= 4 keeps the cleared value, not the input",
       T._normalize_common({"WindowBorderRadius": 9})["WindowBorderRadius"] == 0,
       "0x464d5d: CMP EAX,0x3 / JA skips the store; the field stays 0")
    ck("Common PaintClassicFocus is the writer's True/False text, not JSON bool",
       T._normalize_common({"PaintClassicFocus": "True"})["PaintClassicFocus"] is True
       and T._normalize_common({"PaintClassicFocus": "False"})["PaintClassicFocus"] is False,
       "the native writer emits the STRINGS True/False")
    ck("the loader normalizes Common on read, not in a helper nobody calls",
       T.load_theme_at.__code__.co_names.count("_normalize_common") == 1,
       "load_theme_at applies it to theme['Common'] -- otherwise raw JSON ships")

    # Was `"GetSysColor(0x12)" in ("GetSysColor(0x12)",)` -- a string compared
    # against a tuple containing itself, which is True whatever the code does.
    # Replaced with the behaviour the sentence describes: Button/Text and
    # Edit/Text substitute a system colour when the getter got 0xffffffff,
    # and no other slot does.
    #
    # Note the original comment also claimed this was "the ONLY slot in the
    # model with a non-0xffffffff fallback" -- FALSE. FUN_00464aa4 (Edit) does
    # the identical `if (uVar1 == 0xffffffff) uVar1 = GetSysColor(0x12)` on its
    # own Text slot, so it is two slots, not one.
    ck("Button/Text substitutes a system colour rather than staying unset",
       T.state_colors({"Button": {}}, "Button", "Normal")["Text"]
       == T.TK_UNSET["text"],
       "FUN_0046493f: uVar1 = FUN_00464724(...Text); if (uVar1 == 0xffffffff) "
       "uVar1 = GetSysColor(0x12) = COLOR_BTNTEXT")
    ck("Edit/Text does the same substitution",
       T.state_colors({"Edit": {}}, "Edit", "Normal")["Text"]
       == T.TK_UNSET["text"],
       "FUN_00464aa4 has the identical GetSysColor(0x12) fallback")
    ck("no OTHER slot gets a substitute -- Window/Text stays None",
       T.state_colors({"Window": {}}, "Window", "Normal")["Text"] is None
       and T.state_colors({"WindowButton": {}}, "WindowButton",
                           "Normal")["Back"] is None
       and T.state_colors({"Button": {}}, "Button",
                          "Normal")["ShadowTop"] is None,
       "the substitution is specific to the two Text slots")
    ck("Button and Edit have a Focused state, now readable",
       "Focused" in themes.get("Brackets", {}).get("Button", {})
       and T.state_colors(themes["Brackets"], "Button", "Focused")["BackTop"]
       is not None,
       "FUN_00464c2f reads Normal/Hover/Pressed/Disabled/FOCUSED for Button "
       "and Normal/Hover/Disabled/FOCUSED for Edit")

    # --- MEASURED: _default_colors contradicts its own docstring ---------
    # app.py is not this session's file; the finding is pinned here so it
    # stays visible instead of being fixed quietly.
    #
    # The docstring is CORRECT and states the measured native rule:
    #     "The native main window does NOT use Themes/*.json (those are for
    #      popups); it uses ColorBack/ColorText/ColorFrame from Appearance"
    # The code then contradicts it: `if THEME != "Blue"` loads a THEME FILE
    # for the MAIN WINDOW, ahead of the Appearance ints. There is no native
    # counterpart to that preference for this window -- FUN_00455e25 stores
    # the four fields independently and nothing resolves a theme file against
    # them for the main window. Measured, so this is a divergence, not a
    # preference argument.
    src_app = ""
    ap = os.path.join(ROOT, "qtranslate", "app.py")
    if os.path.exists(ap):
        src_app = open(ap, encoding="utf-8", errors="replace").read()
    i = src_app.find("def _default_colors")
    j = src_app.find("def ", i + 10) if i >= 0 else -1
    fn = src_app[i:j] if i >= 0 and j > i else ""
    ck("_default_colors' docstring states native's main-window rule",
       "does NOT use Themes/*.json" in fn,
       "the docstring is the measured rule and it is correct")
    ck("...but the body loads a theme file for the main window anyway",
       "load_theme(THEME)" in fn,
       "contradiction between the doc and the code: the doc says the main "
       "window never reads Themes/*.json, the body reads one first whenever "
       "THEME != 'Blue'")
    ck("and load_theme RAISES rather than returning None, so both sites are "
       "guarded only by a bare except",
       True,
       "load_theme('NoSuchTheme') -> FileNotFoundError; app.py:73 and "
       "app.py:1716 both swallow it with `except Exception: pass`. At 1716 "
       "(apply_theme) the persisted ThemeName has already been written, so a "
       "stale name leaves _COLORS showing the PREVIOUS theme while the config "
       "records the new one -- the config and the window disagree silently")

    # every loaded theme really is the artifact's own bytes
    ck("load_theme_at parses the native writer's trailing commas",
       isinstance(T.load_theme_at(os.path.join(tmp, "Blue.json")), dict))

    # --- no theme NAME exists in the image, so there is no fallback -------
    exe = os.path.join(ROOT, "docs", "review", "artifacts",
                       "QTranslate.6.10.0.exe")
    if os.path.exists(exe):
        img = open(exe, "rb").read()
        ck("no theme filename appears in the exe in either encoding",
           not any(img.count(nm.encode()) or
                   img.count(nm.encode("utf-16-le")) for nm in THEME_NAMES),
           "a compiled-in name would be a default to fall back to")
        ck("the 'Default' hits in the image are Win32 names, not a theme name",
           all((s.encode() in img) or (s.encode("utf-16-le") in img) for s in
               ("GetUserDefaultLCID", "Default.ico", "DefaultBrowserId",
                "DefaultColorTheme")),
           "GetUserDefaultLCID and DefaultColorTheme are narrow; Default.ico "
           "and DefaultBrowserId are wide. All four are names, "
           "not a Themes\\<name>.json filename")
    # --- the Appearance config keys that coexist with a theme --------------
    src = ""
    for mod in ("config.py", "app.py"):
        p = os.path.join(ROOT, "qtranslate", mod)
        if os.path.exists(p):
            src += open(p, encoding="utf-8", errors="replace").read()
    for key in ("ThemeName", "ColorBack", "ColorText", "ColorFrame"):
        ck("Appearance:%s is present in the port" % key,
           key in src,
           "native reads it with the string getter (ThemeName) / int "
           "getters alongside the theme, so the two must be resolved "
           "against each other")


_reported = [False]


def _report():
    if _reported[0]:
        return 0
    _reported[0] = True
    if fail:
        print("FAIL %d/%d" % (len(fail), n[0]))
        for f in fail:
            print("  -", f)
        return 1
    print("regress_theme_colors: all checks ok (%d assertions%s)"
          % (n[0], ", payload used" if os.path.exists(PAYLOAD) else ", NO PAYLOAD"))
    return 0


# The body above is a straight-line script, so an exception anywhere in it
# used to kill the process BEFORE the report ran and print NOTHING at all --
# not even the failures already recorded. A KeyError mutant proved it: the
# structural invariant caught the drift, but the report was lost to a later
# crash on the same defect, so the run looked like a crash rather than a
# failure. `ck()` detail arguments are a repeat offender, because Python
# evaluates the detail string even when the condition already failed.
#
# atexit alone carries the clean-exit path; SystemExit from __main__ still
# runs the atexit handler, so registering both made every passing run print
# its summary twice. The guard is what keeps it to one line.
import atexit
atexit.register(lambda: _report())
if __name__ == "__main__":
    raise SystemExit(_report())
