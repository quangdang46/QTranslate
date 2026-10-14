"""Translate/dictionary service modules.

This package used to carry a ``REGISTRY = {name: module}`` map. It was dead
code: nothing imported it (``grep -rn REGISTRY qtranslate/`` found only the
definition), and it had quietly drifted -- it listed 5 of the 9 modules in
this package, omitting ``babylon``, ``naver`` and ``promt``, all three of
which ARE wired into the live app through ``app.py``'s ``_t_*`` adapters and
``TRANSLATORS`` table. A registry that disagrees with the code it claims to
describe is worse than none, so it is removed.

The real dispatch tables live in ``qtranslate/app.py``:
  * ``TRANSLATORS`` -- service id -> ``_t_<id>(text, src, tgt)`` adapter
    (all 9 service modules, incl. ``promt``/``babylon``/``naver``)
  * ``DICTS``      -- dictionary id -> lookup callable
``REGISTRY`` never fed either. Import the modules directly, e.g.
``from qtranslate.services import naver``.
"""
