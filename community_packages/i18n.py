'''The sentences of the community packages in Blender's languages (MICRO-PL12, W9).

The same mechanism as ``georef_manager/i18n.py`` (``bpy.app.translations``):
English is the source (E1: whoever has not asked Blender for another language
in Preferences › Interface › Translation reads English), Italian is complete
(the MICRO asks EN + IT; written by Claude on 18 Nov 2026, not reread by a
native speaker). A sentence with values is a TEMPLATE with ``{name}``
placeholders: :func:`tr` recognises it already composed and recomposes it in
the language. The library's own problems (``s3dgraphy.profiles.problems``)
already carry their EN and IT sentence: they are shown as the library writes
them (:func:`core.problem_text`), never retranslated here.

No bpy at module level: :func:`translate` is measured outside Blender.
'''

from __future__ import annotations

import re
from typing import Callable, Dict, Optional

LOCALES = ('it_IT',)

#: msgid (English) → {locale: translation}. A msgid with ``{name}`` is a template.
MESSAGES: Dict[str, Dict[str, str]] = {
    # ── Preferences ─────────────────────────────────────────────────────────
    "Community packages": {'it_IT': "Pacchetti di comunità"},
    "Install from disk…": {'it_IT': "Installa da disco…"},
    "Open the folder": {'it_IT': "Apri la cartella"},
    "Refresh": {'it_IT': "Aggiorna"},
    "The same packages as EMStudio, in {folder}": {
        'it_IT': "Gli stessi pacchetti di EMStudio, in {folder}"},
    "No package installed on this computer": {'it_IT': "Nessun pacchetto installato su questo computer"},
    "The bundled s3dgraphy has no community packages (older than dev117)": {
        'it_IT': "L's3dgraphy impacchettato non conosce i pacchetti di comunità (più vecchio della dev117)"},
    "data {version}": {'it_IT': "dati {version}"},
    "no data": {'it_IT': "nessun dato"},
    "code not installed: {reason}": {'it_IT': "codice non installato: {reason}"},
    # ── W16 (MICRO-PL19): the code that runs in Blender ─────────────────────
    "code: for {hosts}, not run by EM Tools": {'it_IT': "codice: per {hosts}, EM Tools non lo esegue"},
    "code: {state}": {'it_IT': "codice: {state}"},
    "off": {'it_IT': "spento"},
    "Turn on": {'it_IT': "Accendi"},
    "Turn off": {'it_IT': "Spegni"},
    "Enable the code": {'it_IT': "Accendi il codice"},
    "Turn this package's code on or off on this computer (EMStudio's too)": {
        'it_IT': "Accende o spegne il codice di questo pacchetto su questo computer (anche per EMStudio)"},
    "Code on: {name}": {'it_IT': "Codice acceso: {name}"},
    "Code off: {name}": {'it_IT': "Codice spento: {name}"},
    "on, not loaded yet (EM ▸ Plugin ▸ Reload the plugins)": {
        'it_IT': "acceso, non ancora caricato (EM ▸ Plugin ▸ Ricarica i plugin)"},
    "loaded in Blender, not verified": {'it_IT': "caricato in Blender, non verificato"},
    "not loaded: {why}": {'it_IT': "non caricato: {why}"},
    "Install": {'it_IT': "Installa"},
    "Install the code too: I trust it": {'it_IT': "Installa anche il codice: me ne fido"},
    "A Python plugin has the powers of your user: tick «Install the code too» only if you trust it": {
        'it_IT': "Un plugin Python ha i poteri del tuo utente: spunta «Installa anche il codice» solo se te ne fidi"},
    "Same permissions, capabilities and source as the last trust: no new question": {
        'it_IT': "Stessi permessi, capability e fonte dell'ultima fiducia: nessuna nuova domanda"},
    "The code does not run in Blender: EM Tools installs the data only (EMStudio can install the code)": {
        'it_IT': "Il codice non gira in Blender: EM Tools installa solo i dati (EMStudio può installare il codice)"},
    "A plugin with no data, and its code does not run in Blender: install it in EMStudio (Tools ▸ Extensions…)": {
        'it_IT': "Un plugin senza dati, e il suo codice non gira in Blender: installalo in EMStudio "
                 "(Strumenti ▸ Estensioni…)"},
    "A plugin with no data: tick «Install the code too» to install it": {
        'it_IT': "Un plugin senza dati: spunta «Installa anche il codice» per installarlo"},
    "Installed: {name} {version} (data and code, not verified)": {
        'it_IT': "Installato: {name} {version} (dati e codice, non verificato)"},
    "Installed: {name} {version} (code, not verified)": {
        'it_IT': "Installato: {name} {version} (codice, non verificato)"},
    "used by this file": {'it_IT': "usato da questo file"},
    "incomplete: a required package is missing": {'it_IT': "incompleto: manca un pacchetto richiesto"},
    "Remove": {'it_IT': "Rimuovi"},
    "This file uses packages not installed here: {names}": {
        'it_IT': "Questo file usa pacchetti non installati qui: {names}"},
    "community package": {'it_IT': "pacchetto di comunità"},
    "mixed": {'it_IT': "misto"},
    "plugin": {'it_IT': "plugin"},
    # ── the confirmation ────────────────────────────────────────────────────
    "Install the community package": {'it_IT': "Installa il pacchetto di comunità"},
    "Install the data": {'it_IT': "Installa i dati"},
    "Licence: {lic}": {'it_IT': "Licenza: {lic}"},
    "Data {version}: no code, read by every EM tool": {
        'it_IT': "Dati {version}: nessun codice, li legge ogni strumento EM"},
    "vocabulary {scheme} {version} · {license} · tier {tier}": {
        'it_IT': "vocabolario {scheme} {version} · {license} · fascia {tier}"},
    "qualia": {'it_IT': "qualia"},
    "extractors": {'it_IT': "estrattori"},
    "landmark sets": {'it_IT': "insiemi di punti canonici"},
    "combiners": {'it_IT': "combinatori"},
    "sheets": {'it_IT': "schede"},
    "colour schemes": {'it_IT': "schemi colori"},
    "primitives: {p}": {'it_IT': "primitive: {p}"},
    "Already installed, identical: nothing changes": {
        'it_IT': "Già installato, identico: non cambia nulla"},
    "Code {version}: NOT VERIFIED, from disk": {'it_IT': "Codice {version}: NON VERIFICATO, da disco"},
    "runs in: {hosts}": {'it_IT': "gira in: {hosts}"},
    "Not installed: {why}": {'it_IT': "Non installato: {why}"},
    "Installed: {name} {version} (data)": {'it_IT': "Installato: {name} {version} (dati)"},
    "Installed: {name} {version} (data; the code left out)": {
        'it_IT': "Installato: {name} {version} (dati; il codice resta fuori)"},
    "Choose a .zip, or the em-extension.toml / profile.json of a folder": {
        'it_IT': "Scegli uno .zip, o l'em-extension.toml / il profile.json di una cartella"},
    # ── removing ────────────────────────────────────────────────────────────
    "Remove the package {name}?": {'it_IT': "Rimuovere il pacchetto {name}?"},
    "Its data and its code leave this computer, for EMStudio too": {
        'it_IT': "I suoi dati e il suo codice lasciano questo computer, anche per EMStudio"},
    "Its vocabularies stay (like fonts): {names}": {
        'it_IT': "I suoi vocabolari restano (come i font): {names}"},
    "Remove its vocabularies too": {'it_IT': "Togli anche i suoi vocabolari"},
    "Removed: {name}": {'it_IT': "Rimosso: {name}"},
    # ── Visual Manager ──────────────────────────────────────────────────────
    "Colour schemes of the packages": {'it_IT': "Schemi colori dei pacchetti"},
    "Apply": {'it_IT': "Applica"},
    "not a colour scheme": {'it_IT': "non è uno schema colori"},
    "Vocabularies of the packages": {'it_IT': "Vocabolari dei pacchetti"},
    "{label}: {scheme} {version} · {n} terms": {'it_IT': "{label}: {scheme} {version} · {n} voci"},
    "{label}: {scheme} {version} · not installed here": {
        'it_IT': "{label}: {scheme} {version} · non installato qui"},
    "{label}: {scheme} {version} · installed {have}": {
        'it_IT': "{label}: {scheme} {version} · installata la {have}"},
    "No property {prop} in the active graph": {'it_IT': "Nessuna proprietà {prop} nel grafo attivo"},
    "Colour scheme «{name}» of the package applied ({prop})": {
        'it_IT': "Schema colori «{name}» del pacchetto applicato ({prop})"},
    # ── the chain, read ─────────────────────────────────────────────────────
    "From the graph": {'it_IT': "Dal grafo"},
    "Point from the graph": {'it_IT': "Punto dal grafo"},
    "Take the position of a point measured in the graph (EMStudio's chain or EM Tools' x/y/z)": {
        'it_IT': "Prende la posizione di un punto misurato nel grafo (la catena di EMStudio o x/y/z di EM Tools)"},
    "No measured point in the active graph": {'it_IT': "Nessun punto misurato nel grafo attivo"},
    "{label}: read from the graph ({source})": {'it_IT': "{label}: letto dal grafo ({source})"},
    "chain": {'it_IT': "catena"},
    "attributes": {'it_IT': "attributi"},
    "Areale from a graph surface": {'it_IT': "Areale da una superficie del grafo"},
    "Make the areale from a surface placed in the graph (EMStudio), on the target RM": {
        'it_IT': "Fa l'areale da una superficie posata nel grafo (EMStudio), sull'RM di destinazione"},
    "No surface placed in the active graph": {'it_IT': "Nessuna superficie posata nel grafo attivo"},
    "Pick a target RM first": {'it_IT': "Scegli prima l'RM di destinazione"},
    "The surface cannot become an areale: {why}": {
        'it_IT': "La superficie non può diventare un areale: {why}"},
    "Areale made from the surface {label} ({n} vertices)": {
        'it_IT': "Areale fatto dalla superficie {label} ({n} vertici)"},
    "The surface is on {on}, not on {rm}: made on {rm} all the same": {
        'it_IT': "La superficie sta su {on}, non su {rm}: fatto lo stesso su {rm}"},
    "Measures of the packages": {'it_IT': "Misure dei pacchetti"},
    "Compute the measures": {'it_IT': "Calcola le misure"},
    "Compute the measures the packages declare from the points placed on each model": {
        'it_IT': "Calcola le misure che i pacchetti dichiarano dai punti posati su ogni modello"},
    "{n} measure(s) computed, {m} waiting for points": {
        'it_IT': "{n} misura/e calcolata/e, {m} in attesa di punti"},
    "No package with combiners is active": {'it_IT': "Nessun pacchetto attivo ha combinatori"},
    # ── X6 (MICRO-PL26): the repositories ───────────────────────────────────
    "Repositories": {'it_IT': "Repository"},
    "The bundled s3dgraphy has no repositories (older than dev125)": {
        'it_IT': "L's3dgraphy impacchettato non conosce i repository (più vecchio della dev125)"},
    "No repository yet: add a folder of the lab, or an index on the internet": {
        'it_IT': "Ancora nessun repository: aggiungi una cartella del laboratorio, o un indice su internet"},
    "Refresh all": {'it_IT': "Aggiorna tutti gli elenchi"},
    "Update all ({n})": {'it_IT': "Aggiorna tutto ({n})"},
    "Online access is off in Blender (Preferences ▸ System ▸ Network): only folders and file:// are read": {
        'it_IT': "L'accesso in rete è spento in Blender (Preferenze ▸ Sistema ▸ Rete): "
                 "si leggono solo cartelle e file://"},
    "Online access: {state}, decided by the environment": {
        'it_IT': "Accesso in rete: {state}, lo decide l'ambiente"},
    "on": {'it_IT': "acceso"},
    "Allow online access": {'it_IT': "Consenti l'accesso in rete"},
    "Let the repositories on the internet be read, for every EM tool of this computer; "
    "folders and file:// are read all the same": {
        'it_IT': "Lascia leggere i repository su internet, per ogni strumento EM di questo computer; "
                 "cartelle e file:// si leggono comunque"},
    "one switch for this computer, EMStudio's too": {
        'it_IT': "un solo interruttore per questo computer, anche per EMStudio"},
    "folder": {'it_IT': "cartella"},
    "on the internet": {'it_IT': "su internet"},
    "official": {'it_IT': "ufficiale"},
    "read {when}: {n} entries": {'it_IT': "letto {when}: {n} voci"},
    "not read yet: «Refresh»": {'it_IT': "non ancora letto: «Aggiorna»"},
    "Check for updates at start-up": {'it_IT': "Controlla gli aggiornamenti all'avvio"},
    "Its reviews count": {'it_IT': "Le sue revisioni contano"},
    "Access token (set)": {'it_IT': "Token di accesso (impostato)"},
    "Access token…": {'it_IT': "Token di accesso…"},
    "Access token": {'it_IT': "Token di accesso"},
    "Offered by the repositories": {'it_IT': "Offerti dai repository"},
    "installed {version}": {'it_IT': "installata la {version}"},
    "Update": {'it_IT': "Aggiorna"},
    "{n} plugin(s) for EMStudio only, not listed here": {
        'it_IT': "{n} plugin solo per EMStudio, non elencati qui"},
    "mixed: data, and code for Blender": {'it_IT': "misto: dati, e codice per Blender"},
    "data (its code is not for Blender)": {'it_IT': "dati (il suo codice non è per Blender)"},
    "plugin for Blender": {'it_IT': "plugin per Blender"},
    "verified": {'it_IT': "verificato"},
    "from {repo}": {'it_IT': "da {repo}"},
    # adding, reading, removing a repository
    "Add repository…": {'it_IT': "Aggiungi repository…"},
    "Add a repository of extensions: a folder of the lab, a NAS, or an index on the internet": {
        'it_IT': "Aggiunge un repository di estensioni: una cartella del laboratorio, un NAS, o un indice su internet"},
    "Address": {'it_IT': "Indirizzo"},
    "https://…/index.json, file://…, or a folder": {'it_IT': "https://…/index.json, file://…, o una cartella"},
    "Or a folder": {'it_IT': "Oppure una cartella"},
    "ExtendedMatrix (official)": {'it_IT': "ExtendedMatrix (ufficiale)"},
    "Name": {'it_IT': "Nome"},
    "Lower-case letters, digits, - and _; from the address when empty": {
        'it_IT': "Lettere minuscole, cifre, - e _; dall'indirizzo se vuoto"},
    "Add": {'it_IT': "Aggiungi"},
    "The token is kept on this computer only and sent only to the index's address": {
        'it_IT': "Il token resta solo su questo computer e va solo all'indirizzo dell'indice"},
    "Write an address or choose a folder": {'it_IT': "Scrivi un indirizzo o scegli una cartella"},
    "Repository added: {name}": {'it_IT': "Repository aggiunto: {name}"},
    "{name}: {n} entries read": {'it_IT': "{name}: lette {n} voci"},
    "Updates available: {list}": {'it_IT': "Aggiornamenti disponibili: {list}"},
    "Read the index of the repository again (all of them when none is named)": {
        'it_IT': "Rilegge l'indice del repository (di tutti, se non se ne nomina uno)"},
    "Remove the repository": {'it_IT': "Rimuovi il repository"},
    "Forget this repository (EMStudio's too); what was installed from it stays": {
        'it_IT': "Dimentica questo repository (anche per EMStudio); ciò che si è installato da lì resta"},
    "Remove the repository {name}?": {'it_IT': "Rimuovere il repository {name}?"},
    "What was installed from it stays installed": {'it_IT': "Ciò che si è installato da lì resta installato"},
    "No repository called {name}": {'it_IT': "Nessun repository di nome {name}"},
    "Repository removed: {name}": {'it_IT': "Repository rimosso: {name}"},
    "Change the repository": {'it_IT': "Cambia il repository"},
    "Check this repository at start-up, or let its reviews count (EMStudio's too)": {
        'it_IT': "Controlla questo repository all'avvio, o fa contare le sue revisioni (anche per EMStudio)"},
    "Set or clear the access token of this repository (sent only to the index's address)": {
        'it_IT': "Imposta o toglie il token di accesso di questo repository (va solo all'indirizzo dell'indice)"},
    "Save": {'it_IT': "Salva"},
    "Empty: the token is cleared": {'it_IT': "Vuoto: il token si toglie"},
    "Token set: {name}": {'it_IT': "Token impostato: {name}"},
    "Token cleared: {name}": {'it_IT': "Token tolto: {name}"},
    # installing from a repository
    "Install from the repository": {'it_IT': "Installa dal repository"},
    "Install or update this extension from its repository, after the confirmation": {
        'it_IT': "Installa o aggiorna questa estensione dal suo repository, dopo la conferma"},
    "Code {version}: NOT VERIFIED, from {repo}": {'it_IT': "Codice {version}: NON VERIFICATO, da {repo}"},
    "Code {version}: verified — {note}": {'it_IT': "Codice {version}: verificato — {note}"},
    "loaded in Blender, verified": {'it_IT': "caricato in Blender, verificato"},
    "The archive is the one the index of {repo} names ({hash})": {
        'it_IT': "L'archivio è quello che l'indice di {repo} nomina ({hash})"},
    "The requirements go round in a circle: {cycle}": {'it_IT': "I requisiti girano in tondo: {cycle}"},
    "The requirements go round in a circle: nothing installed": {
        'it_IT': "I requisiti girano in tondo: non si installa nulla"},
    "Installed first, because it requires them:": {'it_IT': "Installati prima, perché li richiede:"},
    "with code that runs in Blender, not verified": {'it_IT': "con codice che gira in Blender, non verificato"},
    "with code for {hosts}: left for EMStudio": {'it_IT': "con codice per {hosts}: lasciato a EMStudio"},
    "no repository has it": {'it_IT': "nessun repository ce l'ha"},
    "Offers {id} {range} (optional, not installed): {where}": {
        'it_IT': "Offre {id} {range} (facoltativo, non installato): {where}"},
    "Tier C vocabulary {scheme}: downloaded to this computer from {url}": {
        'it_IT': "Vocabolario di fascia C {scheme}: scaricato su questo computer da {url}"},
    "Tier C vocabulary {scheme}: not downloaded now («Download locally» later)": {
        'it_IT': "Vocabolario di fascia C {scheme}: non scaricato ora («Scarica in locale» più tardi)"},
    "Tier C vocabulary {scheme}: downloaded": {'it_IT': "Vocabolario di fascia C {scheme}: scaricato"},
    "Installed first: {id} {version} from {repo}": {'it_IT': "Installato prima: {id} {version} da {repo}"},
    "Installed: {name} {version} from {repo} (data and code)": {
        'it_IT': "Installato: {name} {version} da {repo} (dati e codice)"},
    "Installed: {name} {version} from {repo} (code)": {'it_IT': "Installato: {name} {version} da {repo} (codice)"},
    "Installed: {name} {version} from {repo} (data; the code left out)": {
        'it_IT': "Installato: {name} {version} da {repo} (dati; il codice resta fuori)"},
    "Installed: {name} {version} from {repo} (data)": {'it_IT': "Installato: {name} {version} da {repo} (dati)"},
    # «Update all»
    "Update all": {'it_IT': "Aggiorna tutto"},
    "Install every update the repositories offer; the ones that would ask the trust again are said first": {
        'it_IT': "Installa ogni aggiornamento che i repository offrono; quelli che chiederebbero di nuovo "
                 "la fiducia sono detti prima"},
    "Update these too: I trust them": {'it_IT': "Aggiorna anche questi: me ne fido"},
    "Everything is up to date": {'it_IT': "Tutto è aggiornato"},
    "These ask the trust again:": {'it_IT': "Questi chiedono di nuovo la fiducia:"},
    "source": {'it_IT': "fonte"},
    "its code is not for Blender: update it in EMStudio": {
        'it_IT': "il suo codice non è per Blender: aggiornalo in EMStudio"},
    "These update without a question:": {'it_IT': "Questi si aggiornano senza domande:"},
    "data only (the code was left out)": {'it_IT': "solo i dati (il codice era stato lasciato fuori)"},
    "The new data go beside the old: every file keeps the version it declares": {
        'it_IT': "I dati nuovi si affiancano ai vecchi: ogni file tiene la versione che dichiara"},
    "Updated: {id} {old} → {new} ({repo})": {'it_IT': "Aggiornato: {id} {old} → {new} ({repo})"},
    "Not updated, it asks the trust again: {id} {version} — update it in EMStudio": {
        'it_IT': "Non aggiornato, chiede di nuovo la fiducia: {id} {version} — aggiornalo in EMStudio"},
    "Not updated, it asks the trust again: {id} {version}": {
        'it_IT': "Non aggiornato, chiede di nuovo la fiducia: {id} {version}"},
    "Not updated: {id} ({why})": {'it_IT': "Non aggiornato: {id} ({why})"},
}


def _compile(template: str):
    parts = re.split(r'\{(\w+)\}', template)
    out, seen = [], set()
    for i, part in enumerate(parts):
        if i % 2 == 0:
            out.append(re.escape(part))
        elif part in seen:              # a placeholder said twice: the same text
            out.append(f'(?P={part})')
        else:
            seen.add(part)
            out.append(f'(?P<{part}>.+?)')
    return re.compile('^' + ''.join(out) + '$', re.S)


_TEMPLATES = [(msgid, _compile(msgid)) for msgid in MESSAGES if '{' in msgid]


def translate(text: str, lookup: Callable[[str], Optional[str]]) -> str:
    '''``text`` (English, maybe composed) in the language ``lookup`` gives:
    the exact sentence first, then the templates (each captured piece
    translated in turn). A sentence nobody knows stays English.'''
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
    '''The ``lookup`` of a language of the catalogue (tests outside Blender).'''
    return lambda msgid: (MESSAGES.get(msgid) or {}).get(locale)


#: our own context, so a word Blender translates elsewhere keeps our meaning
CONTEXT = "EMPackages"

#: sentences Blender translates by itself (operator names and descriptions,
#: property names): also registered in its default contexts
AUTO = (
    "Install", "Install the code too: I trust it", "Enable the code",
    "Turn this package's code on or off on this computer (EMStudio's too)",
    "Install from disk…", "Open the folder", "Refresh", "Remove", "Install the data", "Apply",
    "Remove its vocabularies too", "From the graph", "Point from the graph",
    "Take the position of a point measured in the graph (EMStudio's chain or EM Tools' x/y/z)",
    "Areale from a graph surface",
    "Make the areale from a surface placed in the graph (EMStudio), on the target RM",
    "Compute the measures",
    "Compute the measures the packages declare from the points placed on each model",
    # X6 · operator names and descriptions, property names
    "Allow online access",
    "Let the repositories on the internet be read, for every EM tool of this computer; "
    "folders and file:// are read all the same",
    "Add repository…", "Add a repository of extensions: a folder of the lab, a NAS, or an index on the internet",
    "Address", "https://…/index.json, file://…, or a folder", "Or a folder", "ExtendedMatrix (official)", "Name",
    "Lower-case letters, digits, - and _; from the address when empty", "Access token",
    "Check for updates at start-up", "Read the index of the repository again (all of them when none is named)",
    "Remove the repository", "Forget this repository (EMStudio's too); what was installed from it stays",
    "Change the repository", "Check this repository at start-up, or let its reviews count (EMStudio's too)",
    "Access token…", "Set or clear the access token of this repository (sent only to the index's address)",
    "Install from the repository",
    "Install or update this extension from its repository, after the confirmation",
    "Update all", "Install every update the repositories offer; the ones that would ask the trust again "
    "are said first", "Update these too: I trust them",
)


def tr(text: str) -> str:
    '''``text`` in Blender's interface language (English when translation is
    off or the language is not in the catalogue).'''
    try:
        from bpy.app.translations import pgettext_iface
    except Exception:  # noqa: BLE001 — outside Blender
        return text

    def lookup(msgid):
        out = pgettext_iface(msgid, CONTEXT)
        return out if out != msgid else None

    return translate(text, lookup)


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
    except Exception:  # noqa: BLE001 — not registered yet
        pass
    bpy.app.translations.register(__name__, blender_dict())


def unregister():
    import bpy  # type: ignore
    try:
        bpy.app.translations.unregister(__name__)
    except Exception:  # noqa: BLE001
        pass
