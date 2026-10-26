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
        "Tape Operations": "Band-Operationen",
        "Job Queue": "Auftragswarteschlange",
        "Live Dashboard": "Live-Dashboard",
        "Device": "Gerät",
        "Generation": "Generation",
        "Status": "Status",
        "Speed": "Geschwindigkeit",
        "Capacity": "Kapazität",
        "Audit Log": "Audit-Protokoll",
        "About": "Über",
        "Help": "Hilfe",
        "No sources": "Keine Quellen",
        "Please select at least one source.": "Bitte mindestens eine Quelle auswählen.",
        "Failed": "Fehlgeschlagen",
        "Idle": "Bereit",
    },
}

_current = "en"


def set_language(lang: str) -> None:
    global _current
    if lang in _TRANSLATIONS:
        _current = lang


def tr(text: str) -> str:
    return _TRANSLATIONS.get(_current, {}).get(text, text)
