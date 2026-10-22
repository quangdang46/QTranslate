# DECISIONS

The decisions taken, why, and what they cost. Each one names the
evidence it rests on, because a decision without evidence is a guess.

## D1 -- The UI is ported to PySide6, not to tkinter

**Decision.** The native's look is reproduced in PySide6, in a new
`qtranslate/qt/` package, and the tkinter front end stays as it is
until the new one is finished.

**Why.** The tkinter port sits at roughly **0.51** on the pixel
measure, against the native's own captures. The gap is not a matter of
polish: a Win32 `BS_GROUPBOX` cannot be a tkinter `LabelFrame` (it is a
1px etched frame with the caption ON its top edge and a white
interior), the flat Win11 scrollbars and the joined back/forward button
pair have no tkinter equivalent, and the layout has to be placed by
pixel because the native's is not self-sizing. PySide6 draws those
things.

**Cost.** Two front ends exist at once. The core is shared, so the cost
is in the views, not in the behaviour.

**Evidence.** `qtranslate-pyside6-spec.md`, `BASELINE_RESULTS.md`.

## D2 -- The font is Tahoma, and it is measured

**Decision.** The controls are Tahoma 8pt (11px). The two text panes of
the main window are Tahoma 9pt (12px). The spec's "Segoe UI 9pt" is
wrong and was corrected.

**Why.** The native's own text says which font it is in pixels. The
main window's help line "Double Ctrl => Show main window (with
translation of selected text, if any)" is **418px** wide in the
capture: Tahoma 9pt is 420, Tahoma 8pt is 363, Segoe UI 9pt is 353.
The Options label "Keyboard layout indicator:" is **125px**: Tahoma 8pt
is 127, Segoe UI 8pt is 135. And the line PITCH in the main window is
**14px**, which is Tahoma 9pt's line height and not Segoe UI's 16.

**Cost.** The main window needs two fonts, so the two `QTextEdit`s set
their document's font explicitly -- a stylesheet does not reach a
`QTextDocument`'s default font.

**Evidence.** the measurement table in `qtranslate-pyside6-spec.md` §1.

## D3 -- The pixel measure is the total ink, not the RGB difference

**Decision.** The acceptance number is the fraction of pixels whose
TOTAL INK (the sum of the three channels) differs by more than 8 levels.
The plain RGB difference is reported next to it, but it is not the
number that counts.

**Why.** The native captures are drawn with ClearType, so the same
glyph puts its ink on different subpixels there than in the render. A
pixel that is `(219,143,57)` in the capture can be `(255,219,143)` in
the render: a 200-level difference in the blue channel for text that is
in fact identical. The sum of the channels is what ClearType preserves.
The spec already said the fringes are to be ignored; this is how.

**Cost.** None. It is a change in the measurement, not in the render.
On the main window it took the number from 0.0926 to 0.0237 with no
pixel changed.

**Evidence.** `BASELINE_RESULTS.md` §1, and the spec's rule 7.

## D4 -- The layout is placed by pixel, not by layout managers

**Decision.** Every widget is placed with an absolute geometry, in the
coordinates of the native capture.

**Why.** The native's own layout is absolute -- the group boxes are
484px wide whatever the page holds, the combos are right-aligned at
x = 455, the footer buttons are at fixed x. A layout manager would
compute something else.

**Cost.** The coordinates have to be measured. `tools/ui_measure.py`
exists so that they can be.

## D5 -- The group box is drawn by hand, in both front ends

**Decision.** The Win32 `BS_GROUPBOX` is drawn as a 1px `#7e7e7e`
etched frame with a white interior and the caption ON the top edge,
breaking the edge where it sits.

**Why.** tkinter's `LabelFrame` paints a themed border, keeps the
parent's face colour inside and puts the caption in a title strip --
none of which is what the native draws. PySide6's `QGroupBox` cannot
draw the white offset line either, so `qtranslate_style.EtchedGroupBox`
paints it.

**Cost.** The tkinter group box is no longer a `Labelframe` widget, so
the test that asserted the group titles had to learn where the caption
now lives. The meaning of the assertion did not change.

**Evidence.** `qtranslate/windows.py`'s `_groupbox`, and
`qtranslate_style.EtchedGroupBox`.

## D6 -- The icons are recovered, and their alpha is recovered with them

**Decision.** The 16x16 icons come out of the native binary (the EXE's
`RT_ICON` resources, and the installer payload's `Service.ico` files),
and `qtranslate/qt/icons.py` recovers their alpha from the flattened
colour so they composite over white and over a button the way the
native's do.

**Why.** The recovered PNGs are the icon ALREADY COMPOSITED over the
window face, so they carry a grey background where the icon is
transparent. Drawn as they are, they would paint a grey box over the
white source pane. For a one-colour icon, `asset = C*a + FACE*(1-a)`
gives the alpha from the luminance and the ink from the asset.

**Cost.** The coloured service icons keep their own pixels and only the
exact face colour is keyed out, so their edge pixels land a level or
two off the native's. That is the largest single contributor to the
residual difference on the strip.

**Evidence.** `qtranslate/assets/ui_icons/manifest.json` and
`qtranslate/assets/service_icons/manifest.json`, each of which names the
binary and the capture the icon was matched against.

## D7 -- The native's runtime page order wins over the template's

**Decision.** The Options nav list is Basics, **Hotkeys**, Internet,
Services, Languages, Appearance, Exceptions, Advanced, Updates -- the
order the native draws at runtime. The template's own order (Hotkeys
seventh) is not what the user sees.

**Why.** The nav list is in the captures 2140 and 2141, and it reads
that way. The template order is what the DLG resource lists the pages
in, which is a different thing.

**Cost.** The test that asserted the template order was wrong and was
corrected, with the evidence in the comment.

## D8 -- The settings defaults are the native's, and the tests read the defaults

**Decision.** `config.default_config()` carries the native's twenty
sections with the native's values, and the tests that check the
defaults read the DEFAULT document, not the live `Options.json`.

**Why.** The live file is the USER's file. On the machine the tests
were written on it was the native's own; on this one it is the port's
defaults, because the native's was lost. A test that reads it is
asserting about whose machine it runs on, not about the port.

**Cost.** The values the native's file carried and that could not be
recovered are 0 (unbound) rather than invented, and the saved window
placement is a user setting, so a fresh install has none.

**Evidence.** `qtranslate/config.py`'s `default_config()`, and
`G9_TEMPLATE_VS_PLACEMENT_2026-10-15.md` for the saved rect.

## D9 -- The provider strip's short names are cut to two characters and three dots

**Decision.** The nine provider buttons show `Go...`, `Mi...`, `Pr...`,
`Ba...`, `Ya...`, `yo...`, `Ba...`, `Pa...`, `DeepL` -- the name cut to
two characters and an ellipsis when it does not fit.

**Why.** Measured off the capture: the native's `Go...` has its three
dots at x = 45, 49 and 53, four pixels apart, and the whole label is 24
px wide. Tahoma 8pt's `Go...` is 25px of advance and `Go..` is 21.

**Cost.** The last button is 60px wide where the others are 56 --
that is how "DeepL" fits -- and the label is cut only when the name's
width exceeds the room.

## D10 -- The main window's strip is built from the session's services, not a fixed list

**Decision.** The nine buttons are the services the config lists, in
the config's order, with the icon of each and its display name.

**Why.** Native's strip is the session's translation services, and the
Services page lets the user reorder them. A fixed list would be a
different app.

**Cost.** The icons are looked up by service key, so a service without
a recovered icon falls back to its own name.
