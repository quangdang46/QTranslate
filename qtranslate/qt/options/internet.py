"""The Internet page of the Options dialog.

The geometry was measured off the native capture; see
``qtranslate-pyside6-spec.md`` section 5.

WIRED: timeout and proxy settings write through to Options.json
(``Internet.Timeout`` / ``Proxy.*``) like every other page.
"""

from .base import OptionsBase, cfg_load, cfg_section, cfg_set, check, \
    combo, field, group, label


class InternetPage(OptionsBase):
    SEL = 2
    # The port-owned "Retries" group (.tmp NetworkPanel) extends the
    # native-measured 362px page, same precedent as AdvancedPage.
    SIZE = (644, 452)
    CHROME = dict(OptionsBase.CHROME)
    CHROME["panel"] = (4, 29, 142, 414)
    CHROME["shadow_row"] = (3, 443, 144, 1)
    CHROME["rule"] = (448, 3, 638)
    CHROME["buttons"] = {k: (x, y + 90, w, sh)
                         for k, (x, y, w, sh)
                         in OptionsBase.CHROME["buttons"].items()}

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
        # Tooltips double as the settings-search hint: the proxy rows
        # carry no left label (native's own layout), so the search
        # index finds them by hint, like upstream's registerSearchEntry.
        c_px.setToolTip("Proxy type")

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
        f1.setToolTip("Proxy host")
        f1.setText(str(proxy.get("Host", proxy.get("Address", ""))))
        f1.editingFinished.connect(
            lambda: cfg_set("Proxy", "Host", f1.text()))
        f2 = field(self, 532, 133, 95, 20,
                   str(proxy.get("Port", "0")), enabled=(idx == 2))
        f2.setToolTip("Proxy port")
        f2.editingFinished.connect(
            lambda: cfg_set("Proxy", "Port", f2.text()))
        self._px_fields += [f1, f2]
        f3 = field(self, 248, 159, 186, 20,
                   str(proxy.get("Username", proxy.get("UserName", ""))),
                   enabled=(idx == 2))
        f3.setToolTip("Proxy username")
        f3.editingFinished.connect(
            lambda: cfg_set("Proxy", "Username", f3.text()))
        # Proxy.Password never lives in Options.json (.tmp keeps it in
        # the SecretStore; port: qtranslate/secrets.py). The field shows
        # the stored secret and writes back to the secrets file only.
        try:
            from qtranslate import secrets as _sec
            from qtranslate import config as _cfg
            _sp = _sec.path_for(_cfg.DEFAULT_PATH)
            _px_pw = str(_sec.get(_sec.PROXY_PASSWORD_KEY, "",
                                  path=_sp) or "")
        except Exception:
            _sp = None
            _px_pw = ""
        f4 = field(self, 441, 159, 186, 20, _px_pw, enabled=(idx == 2))
        f4.setToolTip("Proxy password")
        try:
            from PySide6.QtWidgets import QLineEdit
            f4.setEchoMode(QLineEdit.Password)
        except Exception:
            pass
        def _pw_changed():
            try:
                from qtranslate import secrets as _sec
                _sec.set(_sec.PROXY_PASSWORD_KEY, f4.text(), path=_sp)
            except Exception:
                pass
        f4.editingFinished.connect(_pw_changed)
        self._px_fields += [f3, f4]
        combo(self, 162, 133, 78, "HTTP", enabled=False)
        # The scheme label sits where native's combo is; it is display
        # only because the port's proxy is HTTP/HTTPS through requests.

        # AI Translate (.tmp ai-services plugin): an OpenAI-compatible
        # chat endpoint. Keys live in General.Ai* -- the same section
        # qtranslate.services.ai_translate._settings() reads. Local
        # endpoints (localhost/RFC1918) need no key.
        gen = cfg_section("General")
        group(self, 152, 205, 484, 145, "AI Translate")
        for cy, t, key, default in [
                (225, "Base URL:", "AiBaseUrl",
                 "https://openrouter.ai/api/v1"),
                (249, "API key:", "AiApiKey", ""),
                (273, "Model:", "AiModel", "openrouter/free"),
                (297, "Temperature:", "AiTemperature", "0.3"),
                (321, "Max tokens:", "AiMaxTokens", "4096")]:
            label(self, 158, cy, t)
            f = field(self, 300, cy - 10, 325, 20,
                      str(gen.get(key, default)))
            f.editingFinished.connect(
                lambda w=f, k=key: cfg_set("General", k, w.text()))

        # .tmp NetworkPanel retry rows (NetworkConfig): shared policy
        # for every provider -- 429 retries any method, 5xx only
        # idempotent ones, exponential backoff honouring Retry-After.
        group(self, 152, 362, 484, 80, "Retries")
        rb = check(self, 158, 394, "Retry failed requests",
                   on=bool(inet.get("RetryEnabled", True)))
        rb.toggled.connect(
            lambda on: cfg_set("Internet", "RetryEnabled", bool(on)))
        label(self, 158, 410, "Max retries:")
        retries = combo(self, 280, 400, 70,
                        str(int(inet.get("MaxRetries", 2))),
                        values=[str(i) for i in range(0, 11)])
        retries.activated.connect(
            lambda i: cfg_set("Internet", "MaxRetries",
                              int(retries.itemText(i))))
        label(self, 380, 410, "Delay, sec:")
        delays = combo(self, 500, 400, 80,
                       str(int(inet.get("RetryDelayMs", 1000)) // 1000),
                       values=["1", "2", "3", "5", "10", "30", "60"])
        delays.activated.connect(
            lambda i: cfg_set("Internet", "RetryDelayMs",
                              int(delays.itemText(i)) * 1000))
