'''The sentences of ``em`` in Blender, in Blender's languages (MICRO-PL19, W16).

The mechanism of ``community_packages/i18n.py`` (``bpy.app.translations``,
templates with ``{name}`` recomposed in the language): English is the source,
Italian complete (written by Claude on 19 Nov 2026, not reread by a native
speaker). What ``em`` and the contract say (refusals, «no application», the
plugins' problems) already carries EN and IT: shown as the library writes it.

No bpy at module level: :func:`translate` is measured outside Blender.
'''

from __future__ import annotations

import re
from typing import Callable, Dict, Optional

LOCALES = ('it_IT',)

MESSAGES: Dict[str, Dict[str, str]] = {
    # ── the menu EM ▸ Plugin ────────────────────────────────────────────────
    "Plugin": {'it_IT': "Plugin"},
    "Python plugins and the EM console": {'it_IT': "I plugin Python e la console EM"},
    "No plugin for Blender on this computer": {'it_IT': "Nessun plugin per Blender su questo computer"},
    "The bundled s3dgraphy has no em (older than dev124)": {
        'it_IT': "L's3dgraphy impacchettato non ha em (più vecchio della dev124)"},
    "not verified": {'it_IT': "non verificato"},
    "development": {'it_IT': "sviluppo"},
    "{name} {version} · {badge}": {'it_IT': "{name} {version} · {badge}"},
    "not loaded: {why}": {'it_IT': "non caricato: {why}"},
    "no command": {'it_IT': "nessun comando"},
    # ── operators ───────────────────────────────────────────────────────────
    "Open EM console": {'it_IT': "Apri console EM"},
    "Open Blender's Python console with em ready (from s3dgraphy import em), EM Tools as its host": {
        'it_IT': "Apre la console Python di Blender con em pronto (from s3dgraphy import em), EM Tools come ospite"},
    "Run as EM script": {'it_IT': "Esegui come script EM"},
    "Run this text with em; what it writes is one step each, its code kept in the DTC": {
        'it_IT': "Esegue questo testo con em; ogni scrittura è un passo, il suo codice resta nel DTC"},
    "Undo the last EM write": {'it_IT': "Annulla l'ultima scrittura EM"},
    "Undo the newest act written through em (a script, the console, a plugin)": {
        'it_IT': "Annulla l'atto più recente scritto con em (uno script, la console, un plugin)"},
    "Undo «{label}»": {'it_IT': "Annulla «{label}»"},
    "Reload the plugins": {'it_IT': "Ricarica i plugin"},
    "Read enabled.json again (and the development folder, with Experimental on)": {
        'it_IT': "Rilegge enabled.json (e la cartella di sviluppo, con Experimental acceso)"},
    "EM Log": {'it_IT': "Log EM"},
    "What em wrote in this Blender, and what it said": {
        'it_IT': "Che cosa ha scritto em in questo Blender, e che cosa ha detto"},
    "Run a plugin's command": {'it_IT': "Esegui il comando di un plugin"},
    "A command of a plugin, through the contract": {'it_IT': "Un comando di un plugin, attraverso il contratto"},
    # ── what they say ───────────────────────────────────────────────────────
    "em is ready · host: blender · em.help()": {'it_IT': "em è pronto · ospite: blender · em.help()"},
    "No 3D-view window to open the console from": {
        'it_IT': "Nessuna finestra da cui aprire la console"},
    "Nothing to undo": {'it_IT': "Niente da annullare"},
    "Undone: {label}": {'it_IT': "Annullato: {label}"},
    "Not undone: {why}": {'it_IT': "Non annullato: {why}"},
    "Plugins: {loaded} loaded, {other} not": {'it_IT': "Plugin: {loaded} caricati, {other} no"},
    "No text to run": {'it_IT': "Nessun testo da eseguire"},
    "The script failed: {error}": {'it_IT': "Lo script non è riuscito: {error}"},
    "Script run: {n} write(s)": {'it_IT': "Script eseguito: {n} scrittura/e"},
    "Done: {label}": {'it_IT': "Fatto: {label}"},
    "Saved: {path}": {'it_IT': "Salvato: {path}"},
    "Nothing written yet": {'it_IT': "Ancora niente di scritto"},
    "{when} · {label} · {who}": {'it_IT': "{when} · {label} · {who}"},
    "{when} · {label} · {who} · undone": {'it_IT': "{when} · {label} · {who} · annullato"},
    "Experimental is off: EM ▸ Utils ▸ Experimental": {
        'it_IT': "Experimental è spento: EM ▸ Utils ▸ Experimental"},
}

#: our own context, so a word Blender translates elsewhere keeps our meaning
CONTEXT = "EMScripting"

#: operator names and descriptions: also in Blender's default contexts
AUTO = (
    "Plugin", "Open EM console",
    "Open Blender's Python console with em ready (from s3dgraphy import em), EM Tools as its host",
    "Run as EM script", "Run this text with em; what it writes is one step each, its code kept in the DTC",
    "Undo the last EM write", "Undo the newest act written through em (a script, the console, a plugin)",
    "Reload the plugins", "Read enabled.json again (and the development folder, with Experimental on)",
    "EM Log", "What em wrote in this Blender, and what it said",
    "Run a plugin's command", "A command of a plugin, through the contract",
    "Python plugins and the EM console",
)


def _compile(template: str):
    parts = re.split(r'\{(\w+)\}', template)
    out, seen = [], set()
    for i, part in enumerate(parts):
        if i % 2 == 0:
            out.append(re.escape(part))
        elif part in seen:
            out.append(f'(?P={part})')
        else:
            seen.add(part)
            out.append(f'(?P<{part}>.+?)')
    return re.compile('^' + ''.join(out) + '$', re.S)


_TEMPLATES = [(msgid, _compile(msgid)) for msgid in MESSAGES if '{' in msgid]


def translate(text: str, lookup: Callable[[str], Optional[str]]) -> str:
    if not text:
        return text
    if text in MESSAGES:
        return lookup(text) or text
    for msgid, rx in _TEMPLATES:
        m = rx.match(text)
        if not m:
            continue
        target = lookup(msgid)
        if not target:
            return text
        groups = {k: translate(v, lookup) for k, v in m.groupdict().items()}
        try:
            return target.format(**groups)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def catalogue(locale: str) -> Callable[[str], Optional[str]]:
    return lambda msgid: (MESSAGES.get(msgid) or {}).get(locale)


def tr(text: str) -> str:
    try:
        from bpy.app.translations import pgettext_iface
    except Exception:  # noqa: BLE001 — outside Blender
        return text

    def lookup(msgid):
        out = pgettext_iface(msgid, CONTEXT)
        return out if out != msgid else None

    return translate(text, lookup)


def lang_code() -> str:
    """``it`` or ``en``: the language em's own sentences are shown in."""
    try:
        import bpy  # type: ignore
        from ..vocabulary_labels import blender_lang
        return "it" if blender_lang(getattr(bpy.app.translations, "locale", "")) == "it" else "en"
    except Exception:  # noqa: BLE001
        return "en"


def blender_dict() -> dict:
    out = {}
    for msgid, by_locale in MESSAGES.items():
        contexts = (CONTEXT, '*', 'Operator') if msgid in AUTO else (CONTEXT,)
        for locale, msgstr in by_locale.items():
            d = out.setdefault(locale, {})
            for ctx in contexts:
                d[(ctx, msgid)] = msgstr
    return out


def register():
    import bpy  # type: ignore
    try:
        bpy.app.translations.unregister(__name__)
    except Exception:  # noqa: BLE001
        pass
    bpy.app.translations.register(__name__, blender_dict())


def unregister():
    import bpy  # type: ignore
    try:
        bpy.app.translations.unregister(__name__)
    except Exception:  # noqa: BLE001
        pass
