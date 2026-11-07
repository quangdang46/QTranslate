"""The Internet page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.

WIRED: timeout and proxy settings write through to Options.json
(``Internet.Timeout`` / ``Proxy.*``) like every other page.
"""

from .base import OptionsBase, cfg_load, cfg_section, cfg_set, combo, \
    field, group, label


class InternetPage(OptionsBase):
    SEL = 2

    def build(self):
        inet = cfg_section("Internet")
        proxy = cfg_section("Proxy")
        group(self, 152, 35, 484, 45, "Connection")
        label(self, 158, 58, "Timeout, sec:")
        vals = [str(v) for v in (5, 10, 15, 30, 60)]
        try:
            cur_s = str(int(inet.get("Timeout", 10000)) // 1000)
        except Exception:
            cur_s = "10"
        c_to = combo(self, 455, 49, 175,
                     cur_s if cur_s in vals else "10", values=vals)
        c_to.currentTextChanged.connect(
            lambda v: cfg_set("Internet", "Timeout",
                              int(v) * 1000 if v.isdigit() else 10000))

        group(self, 152, 91, 484, 100, "Proxy")
        ptype = str(proxy.get("ProxyType", 0))
        pnames = ["No proxy", "Use system proxy settings", "Manual proxy"]
        # Native ProxyType: 0=system, 1=none, 2=manual — UI order differs.
        _ptype_to_ui = {"0": 1, "1": 0, "2": 2}
        idx = _ptype_to_ui.get(ptype, 1)
        c_px = combo(self, 157, 104, 470, pnames[idx], values=pnames)

        def _px_changed(i):
            # UI index -> native ProxyType value.
            cfg_set("Proxy", "ProxyType", (1, 0, 2)[i])
            # Manual fields only make sense for manual proxy; enabling
            # them live is cosmetic, the readers ignore them otherwise.
            for w in getattr(self, "_px_fields", []):
                w.setEnabled(i == 2)
        c_px.currentIndexChanged.connect(_px_changed)
        self._px_fields = []
        f1 = field(self, 248, 133, 277, 20, enabled=(idx == 2))
        f1.setText(str(proxy.get("Host", proxy.get("Address", ""))))
        f1.editingFinished.connect(
            lambda: cfg_set("Proxy", "Host", f1.text()))
        f2 = field(self, 532, 133, 95, 20,
                   str(proxy.get("Port", "0")), enabled=(idx == 2))
        f2.editingFinished.connect(
            lambda: cfg_set("Proxy", "Port", f2.text()))
        self._px_fields += [f1, f2]
        f3 = field(self, 248, 159, 186, 20,
                   str(proxy.get("Username", proxy.get("UserName", ""))),
                   enabled=(idx == 2))
        f3.editingFinished.connect(
            lambda: cfg_set("Proxy", "Username", f3.text()))
        f4 = field(self, 441, 159, 186, 20,
                   str(proxy.get("Password", "")), enabled=(idx == 2))
        f4.editingFinished.connect(
            lambda: cfg_set("Proxy", "Password", f4.text()))
        self._px_fields += [f3, f4]
        combo(self, 162, 133, 78, "HTTP", enabled=False)
        # The scheme label sits where native's combo is; it is display
        # only because the port's proxy is HTTP/HTTPS through requests.
