# qtranslate-sdk

The QTranslate extension SDK: the contracts an extension writes
against, and nothing else.

```python
from qtranslate_sdk import FakeAPI, Result, MENU_SLOTS


def register(api):
    api.register_provider("my.provider", my_translate)
    api.register_ui("menu", "tray", my_menu_entry)
```

An extension runs INSIDE the QTranslate host process. The host passes
the real API object to your `register(api)`; this package only declares
its shape, so an extension can be written and tested with nothing but
this installed.

`FakeAPI` records what you register, so an extension's own tests can
assert its contributions without the desktop app:

```python
api = FakeAPI()
register(api)
assert "my.provider" in api.providers
```

The package has no dependencies and imports no GUI toolkit.

**Provisional.** The distribution name is not a release commitment;
the PyPI name and its usage rights have not been verified.
