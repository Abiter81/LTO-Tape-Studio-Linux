"""Minimal translation helper."""

from __future__ import annotations

_TRANSLATIONS = {
    "en": {},
    "de": {
        "Backup": "Sicherung",
        "Restore": "Wiederherstellung",
        "Start Backup": "Sicherung starten",
        "Cancel": "Abbrechen",
        "Completed": "Abgeschlossen",
    },
}

_current = "en"


def set_language(lang: str) -> None:
    global _current
    if lang in _TRANSLATIONS:
        _current = lang


def tr(text: str) -> str:
    return _TRANSLATIONS.get(_current, {}).get(text, text)