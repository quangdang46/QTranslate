"""Service registry: name -> module."""
from . import baidu, deepl, microsoft, yandex, youdao

REGISTRY = {
    "deepl": deepl,
    "microsoft": microsoft,
    "yandex": yandex,
    "baidu": baidu,
    "youdao": youdao,
}
