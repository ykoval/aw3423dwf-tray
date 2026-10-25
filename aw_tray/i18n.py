"""UI strings in English and Russian.

The language follows the Windows display language until the user picks one in the
tray menu; that choice is kept in %APPDATA%\\AWMonitorTray\\settings.json.
"""
import ctypes
import json
import os

LANGUAGES = {"en": "English", "ru": "Русский"}
_LANG_RUSSIAN = 0x19  # primary language id of any Russian locale

_STRINGS = {
    "brightness": {"en": "Brightness", "ru": "Яркость"},
    "contrast": {"en": "Contrast", "ru": "Контрастность"},
    "mode": {"en": "Mode", "ru": "Режим"},
    "hdr_mode": {"en": "HDR mode", "ru": "HDR-режим"},
    "on": {"en": "On", "ru": "Вкл"},
    "off": {"en": "Off", "ru": "Выкл"},
    "switching": {"en": "Switching: {what}", "ru": "Переключаю: {what}"},
    "hdr_hint": {"en": "HDR modes turn Windows HDR on by themselves",
                 "ru": "Режимы HDR сами включают HDR в Windows"},
    "hdr_turning_on": {"en": "HDR on…", "ru": "HDR вкл…"},
    "hdr_turning_off": {"en": "HDR off…", "ru": "HDR выкл…"},
    "hdr_failed": {"en": "Could not switch HDR", "ru": "Не удалось переключить HDR"},
    "error": {"en": "Error: {error}", "ru": "Ошибка: {error}"},
    "no_ddc": {"en": "The monitor does not answer over DDC/CI (remote session or monitor off)",
               "ru": "Монитор не отвечает по DDC/CI (удалённый сеанс или монитор выключен)"},
    "value_rejected": {"en": "The monitor did not accept the value",
                       "ru": "Монитор не принял значение"},
    "mode_not_confirmed": {"en": "The monitor did not confirm {mode}; it reports {current}",
                           "ru": "Монитор не подтвердил режим {mode}: сейчас {current}"},
    "stabilizer_not_confirmed": {"en": "The monitor did not confirm Dark Stabilizer {level}",
                                 "ru": "Монитор не подтвердил Dark Stabilizer {level}"},
    "unknown_mode": {"en": "unknown ({value})", "ru": "неизвестный ({value})"},
    "menu_open": {"en": "Open panel", "ru": "Открыть панель"},
    "menu_level": {"en": "Level {level}", "ru": "Уровень {level}"},
    "menu_autostart": {"en": "Start with Windows", "ru": "Запускать при входе в Windows"},
    "menu_quit": {"en": "Quit", "ru": "Выход"},
}

_SETTINGS_PATH = os.path.join(os.environ.get("APPDATA", "."), "AWMonitorTray", "settings.json")


def _windows_language():
    return "ru" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == _LANG_RUSSIAN else "en"


def _load_settings():
    try:
        with open(_SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _initial_language():
    chosen = _load_settings().get("language")
    return chosen if chosen in LANGUAGES else _windows_language()


_current = _initial_language()


def language():
    return _current


def set_language(code):
    global _current
    _current = code
    settings = _load_settings()
    settings["language"] = code
    os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def t(key, **values):
    return _STRINGS[key][_current].format(**values)
