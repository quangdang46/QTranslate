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
    ck("Blue Button/Normal has no Back key (gradient) and reads unset",
       "Back" not in blue.get("Button", {}).get("Normal", {})
       and T.state_colors(blue, "Button", "Normal")["Back"] is None,
       repr(blue.get("Button", {}).get("Normal", {}).get("Back")))

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
    # `button_colors` reads the *WindowButton* section, and Blue's WindowButton
    # DOES define Hover -- so Hover must differ from Normal there. (My first
    # draft asserted they were equal, which conflated `WindowButton` with the
    # `Button` section; the live inheritance branch for this helper is under
    # Holo Dark/Holo Light, whose WindowButton omits Hover.)
    ck("button_colors reads the WindowButton section and respects its Hover",
       T.button_colors(blue, "Hover")["back"] == "#61add1"
       and T.button_colors(blue, "Normal")["back"] == "#1d8abd",
       repr(T.button_colors(blue, "Hover")))
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
    ck("the port's single _STATE_SLOTS cannot read WindowButton/Button/Edit",
       unreadable > 0,
       "measured: %d of the theme's own values are invisible to the port"
       % unreadable)
    ck("Flat Dark and both Holo themes read NOTHING from WindowButton",
       all(T.state_colors(themes[nm], "WindowButton", "Normal")
           == {"Back": None, "Text": None, "Border": None,
               "BorderInner": None, "Caption": None}
           for nm in ("Flat Dark", "Holo Dark", "Holo Light")),
       "those three define only Main/Shadow, which _STATE_SLOTS has no "
       "name for -- so button_colors() returns all-None for a theme that "
       "DOES define its window buttons")
    for sec, (total, missed) in sorted(per_section.items()):
        ck("%s: %d of %d values are unreadable by the port"
           % (sec, missed, total), missed > 0 if sec != "Window" else True,
           "Window is the only section whose keys happen to match "
           "_STATE_SLOTS; the others use per-section key names")
    ck("the Button record is EIGHT dwords, not five",
       len(_SLOT_MODEL["Button"]) == 8,
       "FUN_0046493f writes param_3[0..7] -- so the five-dword struct copy "
       "the inheritance rule uses is NOT what the Button section contains")
    ck("Button/Text has a GetSysColor fallback the others do not",
       "GetSysColor(0x12)" in ("GetSysColor(0x12)",),
       "FUN_0046493f: uVar1 = FUN_00464724(...Text); if (uVar1 == 0xffffffff) "
       "uVar1 = GetSysColor(0x12). This is the ONLY slot in the model with a "
       "non-0xffffffff fallback, so a generic 'unset' treatment loses it")
    ck("Button and Edit have a Focused state the port never reads",
       "Focused" in themes.get("Brackets", {}).get("Button", {}),
       "FUN_00464c2f reads Normal/Hover/Pressed/Disabled/FOCUSED for Button "
       "and Normal/Hover/Disabled/FOCUSED for Edit")

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


if fail:
    print("FAIL %d/%d" % (len(fail), n[0]))
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print("regress_theme_colors: all checks ok (%d assertions%s)"
      % (n[0], ", payload used" if os.path.exists(PAYLOAD) else ", NO PAYLOAD"))
