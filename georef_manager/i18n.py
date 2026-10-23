'''Le frasi del pannello Georeferencing nelle lingue di Blender (MICRO georef al
salvataggio, parte 2, 24 ott 2026).

Misurato il 24 ott: EM Tools **non aveva** un sistema di traduzione
dell'interfaccia (E1, 4 ott 2026: l'interfaccia è in inglese;
``translation_tags.py`` mostra le traduzioni dei DATI, fatte in EMStudio). Qui
c'è il primo, con il meccanismo di Blender (``bpy.app.translations``): l'inglese
resta la sorgente (E1 vale ancora: chi non ha chiesto un'altra lingua in
Preferences › Interface › Translation vede l'inglese), e chi l'ha chiesta vede
il pannello Georeferencing nella sua.

Le frasi con valori (un id di grafo, uno shift, un EPSG) sono **modelli** con
segnaposto ``{nome}``: :func:`translate` riconosce una frase inglese già
composta (per esempio ``em_georef.graph_note``, che va anche nel Log in
inglese) e la ricompone nella lingua; un pezzo catturato che è a sua volta una
frase nota (un'accuratezza, il nome di un campo) si traduce anche lui. Una
frase che nessun modello riconosce resta in inglese.

Lingue: ``it_IT`` e ``de_DE`` complete; ``fr_FR`` ed ``es`` complete ma **da
validare** (:data:`TO_VALIDATE`). Nessuna è stata riletta da un madrelingua:
le ha scritte Claude il 24 ott 2026.

Senza bpy al livello del modulo: :func:`translate` si prova fuori da Blender.
'''

from __future__ import annotations

import re
from typing import Callable, Dict, Optional

LOCALES = ('it_IT', 'de_DE', 'fr_FR', 'es')

#: lingue scritte ma da far validare (le altre: it/de, come chiede il MICRO)
TO_VALIDATE = ('fr_FR', 'es')

#: msgid inglese → {locale: traduzione}. Un msgid con ``{nome}`` è un modello.
MESSAGES: Dict[str, Dict[str, str]] = {
    # ── lettura dal grafo ────────────────────────────────────────────────────
    "Georeferencing read from graph {gid}: EPSG:{epsg} · {x}, {y}, {z}": {
        'it_IT': "Georiferimento letto dal grafo {gid}: EPSG:{epsg} · {x}, {y}, {z}",
        'de_DE': "Georeferenzierung aus dem Graphen {gid} gelesen: EPSG:{epsg} · {x}, {y}, {z}",
        'fr_FR': "Géoréférencement lu dans le graphe {gid} : EPSG:{epsg} · {x}, {y}, {z}",
        'es': "Georreferenciación leída del grafo {gid}: EPSG:{epsg} · {x}, {y}, {z}",
    },
    "Georeferencing pulled from graph {gid}: EPSG:{epsg} · {x}, {y}, {z}": {
        'it_IT': "Georiferimento preso dal grafo {gid}: EPSG:{epsg} · {x}, {y}, {z}",
        'de_DE': "Georeferenzierung aus dem Graphen {gid} übernommen: EPSG:{epsg} · {x}, {y}, {z}",
        'fr_FR': "Géoréférencement repris du graphe {gid} : EPSG:{epsg} · {x}, {y}, {z}",
        'es': "Georreferenciación tomada del grafo {gid}: EPSG:{epsg} · {x}, {y}, {z}",
    },
    "Scene and graph {gid} agree on the georeferencing": {
        'it_IT': "Scena e grafo {gid} concordano sul georiferimento",
        'de_DE': "Szene und Graph {gid} stimmen in der Georeferenzierung überein",
        'fr_FR': "La scène et le graphe {gid} concordent sur le géoréférencement",
        'es': "La escena y el grafo {gid} coinciden en la georreferenciación",
    },
    "Scene and graph {gid} differ on {fields}: nothing overwritten": {
        'it_IT': "Scena e grafo {gid} differiscono su {fields}: niente sovrascritto",
        'de_DE': "Szene und Graph {gid} unterscheiden sich in {fields}: nichts überschrieben",
        'fr_FR': "La scène et le graphe {gid} diffèrent sur {fields} : rien n'est écrasé",
        'es': "La escena y el grafo {gid} difieren en {fields}: no se sobrescribe nada",
    },
    "Graph {gid} declares no georeferencing": {
        'it_IT': "Il grafo {gid} non dichiara un georiferimento",
        'de_DE': "Der Graph {gid} gibt keine Georeferenzierung an",
        'fr_FR': "Le graphe {gid} ne déclare aucun géoréférencement",
        'es': "El grafo {gid} no declara ninguna georreferenciación",
    },
    ("Graph {gid} is not the scene's reference graph ({ref}): its "
     "georeferencing is not read into the scene"): {
        'it_IT': ("Il grafo {gid} non è il grafo di riferimento della scena ({ref}): "
                  "il suo georiferimento non passa nella scena"),
        'de_DE': ("Der Graph {gid} ist nicht der Referenzgraph der Szene ({ref}): "
                  "seine Georeferenzierung wird nicht in die Szene übernommen"),
        'fr_FR': ("Le graphe {gid} n'est pas le graphe de référence de la scène ({ref}) : "
                  "son géoréférencement n'est pas repris dans la scène"),
        'es': ("El grafo {gid} no es el grafo de referencia de la escena ({ref}): "
               "su georreferenciación no pasa a la escena"),
    },
    # ── la discrepanza ───────────────────────────────────────────────────────
    "Scene and graph differ (nothing overwritten):": {
        'it_IT': "Scena e grafo differiscono (niente sovrascritto):",
        'de_DE': "Szene und Graph unterscheiden sich (nichts überschrieben):",
        'fr_FR': "La scène et le graphe diffèrent (rien n'est écrasé) :",
        'es': "La escena y el grafo difieren (no se sobrescribe nada):",
    },
    "{field}: scene {sv} · graph {gv}": {
        'it_IT': "{field}: scena {sv} · grafo {gv}",
        'de_DE': "{field}: Szene {sv} · Graph {gv}",
        'fr_FR': "{field} : scène {sv} · graphe {gv}",
        'es': "{field}: escena {sv} · grafo {gv}",
    },
    "Shift X": {'it_IT': "Shift X", 'de_DE': "Verschiebung X",
                'fr_FR': "Décalage X", 'es': "Desplazamiento X"},
    "Shift Y": {'it_IT': "Shift Y", 'de_DE': "Verschiebung Y",
                'fr_FR': "Décalage Y", 'es': "Desplazamiento Y"},
    "Shift Z": {'it_IT': "Shift Z", 'de_DE': "Verschiebung Z",
                'fr_FR': "Décalage Z", 'es': "Desplazamiento Z"},
    "Azimuth": {'it_IT': "Azimut", 'de_DE': "Azimut", 'fr_FR': "Azimut",
                'es': "Acimut"},
    "Never aligned to these values: a save asks first (Push, Pull or Keep)": {
        'it_IT': ("Mai allineata a questi valori: un salvataggio chiede prima "
                  "(Push, Pull o Keep)"),
        'de_DE': ("Nie an diese Werte angeglichen: ein Speichern fragt zuerst "
                  "(Push, Pull oder Keep)"),
        'fr_FR': ("Jamais alignée sur ces valeurs : un enregistrement demande d'abord "
                  "(Push, Pull ou Keep)"),
        'es': ("Nunca alineada con estos valores: al guardar se pregunta antes "
               "(Push, Pull o Keep)"),
    },
    ("The scene changed since it agreed with the graph: the next save writes "
     "it into the graph"): {
        'it_IT': ("La scena è cambiata da quando concordava con il grafo: il "
                  "prossimo salvataggio la scrive nel grafo"),
        'de_DE': ("Die Szene hat sich geändert, seit sie mit dem Graphen übereinstimmte: "
                  "das nächste Speichern schreibt sie in den Graphen"),
        'fr_FR': ("La scène a changé depuis qu'elle concordait avec le graphe : le "
                  "prochain enregistrement l'écrit dans le graphe"),
        'es': ("La escena cambió desde que coincidía con el grafo: el próximo "
               "guardado la escribe en el grafo"),
    },
    "Pull from graph": {'it_IT': "Prendi dal grafo", 'de_DE': "Aus dem Graphen holen",
                        'fr_FR': "Reprendre du graphe", 'es': "Tomar del grafo"},
    "Push to GeoNode": {'it_IT': "Scrivi nel GeoNode", 'de_DE': "In den GeoNode schreiben",
                        'fr_FR': "Écrire dans le GeoNode", 'es': "Escribir en el GeoNode"},
    ("Read EPSG, shift and azimuth from the active graph's GeoPositionNode and "
     "overwrite the scene's values (then BlenderGIS and 3DSC through the usual "
     "propagation). Objects are not moved"): {
        'it_IT': ("Legge EPSG, shift e azimut dal GeoPositionNode del grafo attivo e "
                  "sovrascrive i valori della scena (poi BlenderGIS e 3DSC con la "
                  "propagazione di sempre). Gli oggetti non si spostano"),
        'de_DE': ("Liest EPSG, Verschiebung und Azimut aus dem GeoPositionNode des "
                  "aktiven Graphen und überschreibt die Werte der Szene (danach "
                  "BlenderGIS und 3DSC über die übliche Weitergabe). Objekte werden "
                  "nicht verschoben"),
        'fr_FR': ("Lit l'EPSG, le décalage et l'azimut dans le GeoPositionNode du graphe "
                  "actif et remplace les valeurs de la scène (puis BlenderGIS et 3DSC "
                  "par la propagation habituelle). Les objets ne bougent pas"),
        'es': ("Lee EPSG, desplazamiento y acimut del GeoPositionNode del grafo activo "
               "y sobrescribe los valores de la escena (después BlenderGIS y 3DSC con "
               "la propagación habitual). Los objetos no se mueven"),
    },
    ("Exact shift: {x}, {y}, {z} (the fields show Blender's 32-bit floats)"): {
        'it_IT': "Shift esatto: {x}, {y}, {z} (i campi mostrano i float a 32 bit di Blender)",
        'de_DE': ("Genaue Verschiebung: {x}, {y}, {z} (die Felder zeigen Blenders "
                  "32-Bit-Gleitkommazahlen)"),
        'fr_FR': ("Décalage exact : {x}, {y}, {z} (les champs montrent les flottants "
                  "32 bits de Blender)"),
        'es': ("Desplazamiento exacto: {x}, {y}, {z} (los campos muestran los "
               "flotantes de 32 bits de Blender)"),
    },
    ("Shift Z = {z}: an explicit choice. The project rule is 0 (absolute heights "
     "in the models' vertices); with {z2} the scene heights are the real ones "
     "minus {z3}"): {
        'it_IT': ("Shift Z = {z}: una scelta esplicita. La regola del progetto è 0 "
                  "(quote assolute nei vertici dei modelli); con {z2} le quote della "
                  "scena sono quelle reali meno {z3}"),
        'de_DE': ("Verschiebung Z = {z}: eine ausdrückliche Wahl. Die Projektregel ist 0 "
                  "(absolute Höhen in den Vertices der Modelle); mit {z2} sind die "
                  "Höhen der Szene die realen minus {z3}"),
        'fr_FR': ("Décalage Z = {z} : un choix explicite. La règle du projet est 0 "
                  "(altitudes absolues dans les sommets des modèles) ; avec {z2} les "
                  "altitudes de la scène sont les réelles moins {z3}"),
        'es': ("Desplazamiento Z = {z}: una elección explícita. La regla del proyecto "
               "es 0 (cotas absolutas en los vértices de los modelos); con {z2} las "
               "cotas de la escena son las reales menos {z3}"),
    },
    "Not georeferenced (no EPSG)": {
        'it_IT': "Non georiferita (nessun EPSG)", 'de_DE': "Nicht georeferenziert (kein EPSG)",
        'fr_FR': "Non géoréférencée (aucun EPSG)", 'es': "No georreferenciada (sin EPSG)",
    },
    # ── PROJ, EPSG deprecati, conversione ────────────────────────────────────
    ("PROJ (pyproj) not available here: deprecated codes and transformation "
     "accuracy cannot be checked"): {
        'it_IT': ("PROJ (pyproj) non disponibile qui: codici deprecati e accuratezza "
                  "della trasformazione non si possono controllare"),
        'de_DE': ("PROJ (pyproj) hier nicht verfügbar: veraltete Codes und die "
                  "Genauigkeit der Transformation können nicht geprüft werden"),
        'fr_FR': ("PROJ (pyproj) indisponible ici : les codes obsolètes et la précision "
                  "de la transformation ne peuvent pas être vérifiés"),
        'es': ("PROJ (pyproj) no disponible aquí: no se pueden comprobar los códigos "
               "obsoletos ni la precisión de la transformación"),
    },
    "To WGS 84: {op}": {'it_IT': "Verso WGS 84: {op}", 'de_DE': "Nach WGS 84: {op}",
                        'fr_FR': "Vers WGS 84 : {op}", 'es': "Hacia WGS 84: {op}"},
    "Accuracy to WGS 84: {a} → {b}": {
        'it_IT': "Accuratezza verso WGS 84: {a} → {b}",
        'de_DE': "Genauigkeit nach WGS 84: {a} → {b}",
        'fr_FR': "Précision vers WGS 84 : {a} → {b}",
        'es': "Precisión hacia WGS 84: {a} → {b}",
    },
    "Accuracy: {a} → {b}": {'it_IT': "Accuratezza: {a} → {b}",
                            'de_DE': "Genauigkeit: {a} → {b}",
                            'fr_FR': "Précision : {a} → {b}",
                            'es': "Precisión: {a} → {b}"},
    "Accuracy: {acc}": {'it_IT': "Accuratezza: {acc}", 'de_DE': "Genauigkeit: {acc}",
                        'fr_FR': "Précision : {acc}", 'es': "Precisión: {acc}"},
    "unknown": {'it_IT': "sconosciuta", 'de_DE': "unbekannt", 'fr_FR': "inconnue",
                'es': "desconocida"},
    "unknown (ballpark)": {'it_IT': "sconosciuta (ballpark)",
                           'de_DE': "unbekannt (Ballpark)",
                           'fr_FR': "inconnue (ballpark)",
                           'es': "desconocida (ballpark)"},
    "exact (±0 m)": {'it_IT': "esatta (±0 m)", 'de_DE': "exakt (±0 m)",
                     'fr_FR': "exacte (±0 m)", 'es': "exacta (±0 m)"},
    "EPSG:{epsg} ({name}) is deprecated in the EPSG database": {
        'it_IT': "EPSG:{epsg} ({name}) è deprecato nel database EPSG",
        'de_DE': "EPSG:{epsg} ({name}) ist in der EPSG-Datenbank veraltet",
        'fr_FR': "EPSG:{epsg} ({name}) est obsolète dans la base EPSG",
        'es': "EPSG:{epsg} ({name}) está obsoleto en la base de datos EPSG",
    },
    ("PROJ reaches WGS 84 from it only with a «ballpark» (no datum shift): "
     "accuracy unknown, can be ~100 m"): {
        'it_IT': ("PROJ arriva a WGS 84 da qui solo con un «ballpark» (nessun cambio "
                  "di datum): accuratezza sconosciuta, può essere ~100 m"),
        'de_DE': ("PROJ erreicht WGS 84 von hier nur mit einem «Ballpark» (keine "
                  "Datumsverschiebung): Genauigkeit unbekannt, kann ~100 m sein"),
        'fr_FR': ("PROJ n'atteint WGS 84 qu'avec un «ballpark» (sans changement de "
                  "datum) : précision inconnue, peut être ~100 m"),
        'es': ("PROJ llega a WGS 84 desde aquí solo con un «ballpark» (sin cambio de "
               "datum): precisión desconocida, puede ser ~100 m"),
    },
    "Proposed: EPSG:{epsg} ({name})": {
        'it_IT': "Proposto: EPSG:{epsg} ({name})", 'de_DE': "Vorschlag: EPSG:{epsg} ({name})",
        'fr_FR': "Proposé : EPSG:{epsg} ({name})", 'es': "Propuesto: EPSG:{epsg} ({name})",
    },
    "Same grid: only the code changes, the shift stays": {
        'it_IT': "Stessa griglia: cambia solo il codice, lo shift resta",
        'de_DE': "Gleiches Gitter: nur der Code ändert sich, die Verschiebung bleibt",
        'fr_FR': "Même grille : seul le code change, le décalage reste",
        'es': "Misma cuadrícula: solo cambia el código, el desplazamiento se mantiene",
    },
    ("Another grid: the shift is reprojected; models with absolute plan "
     "coordinates need it too"): {
        'it_IT': ("Un'altra griglia: lo shift si riproietta; anche i modelli con "
                  "coordinate assolute in pianta vanno riproiettati"),
        'de_DE': ("Ein anderes Gitter: die Verschiebung wird umprojiziert; Modelle mit "
                  "absoluten Lagekoordinaten brauchen das auch"),
        'fr_FR': ("Une autre grille : le décalage est reprojeté ; les modèles aux "
                  "coordonnées planimétriques absolues doivent l'être aussi"),
        'es': ("Otra cuadrícula: el desplazamiento se reproyecta; los modelos con "
               "coordenadas planimétricas absolutas también lo necesitan"),
    },
    "Convert to EPSG:{epsg}": {'it_IT': "Converti in EPSG:{epsg}",
                               'de_DE': "In EPSG:{epsg} umwandeln",
                               'fr_FR': "Convertir en EPSG:{epsg}",
                               'es': "Convertir a EPSG:{epsg}"},
    "PROJ's database gives no replacement code": {
        'it_IT': "Il database di PROJ non dà un codice sostitutivo",
        'de_DE': "Die PROJ-Datenbank nennt keinen Ersatzcode",
        'fr_FR': "La base de PROJ ne donne aucun code de remplacement",
        'es': "La base de datos de PROJ no da ningún código de sustitución",
    },
    "Undo the conversion (back to EPSG:{epsg})": {
        'it_IT': "Annulla la conversione (torna a EPSG:{epsg})",
        'de_DE': "Umwandlung rückgängig machen (zurück zu EPSG:{epsg})",
        'fr_FR': "Annuler la conversion (retour à EPSG:{epsg})",
        'es': "Deshacer la conversión (volver a EPSG:{epsg})",
    },
    "Same grid: only the code changes, shift stays ({x}, {y})": {
        'it_IT': "Stessa griglia: cambia solo il codice, lo shift resta ({x}, {y})",
        'de_DE': "Gleiches Gitter: nur der Code ändert sich, die Verschiebung bleibt ({x}, {y})",
        'fr_FR': "Même grille : seul le code change, le décalage reste ({x}, {y})",
        'es': "Misma cuadrícula: solo cambia el código, el desplazamiento se mantiene ({x}, {y})",
    },
    "Another grid: shift reprojected to ({x}, {y}), {acc}": {
        'it_IT': "Un'altra griglia: shift riproiettato in ({x}, {y}), {acc}",
        'de_DE': "Ein anderes Gitter: Verschiebung umprojiziert auf ({x}, {y}), {acc}",
        'fr_FR': "Une autre grille : décalage reprojeté en ({x}, {y}), {acc}",
        'es': "Otra cuadrícula: desplazamiento reproyectado a ({x}, {y}), {acc}",
    },
    "Models with absolute plan coordinates must be treated too": {
        'it_IT': "Anche i modelli con coordinate assolute in pianta vanno trattati",
        'de_DE': "Modelle mit absoluten Lagekoordinaten müssen ebenfalls behandelt werden",
        'fr_FR': "Les modèles aux coordonnées planimétriques absolues doivent aussi être traités",
        'es': "Los modelos con coordenadas planimétricas absolutas también deben tratarse",
    },
    "Cannot plan the conversion: {err}": {
        'it_IT': "Non si può preparare la conversione: {err}",
        'de_DE': "Die Umwandlung lässt sich nicht planen: {err}",
        'fr_FR': "Impossible de préparer la conversion : {err}",
        'es': "No se puede preparar la conversión: {err}",
    },
    "Rewrite shift.txt (keep shift.old.txt beside it)": {
        'it_IT': "Riscrivi shift.txt (tieni shift.old.txt accanto)",
        'de_DE': "shift.txt neu schreiben (shift.old.txt daneben behalten)",
        'fr_FR': "Réécrire shift.txt (garder shift.old.txt à côté)",
        'es': "Reescribir shift.txt (conservar shift.old.txt al lado)",
    },
    "Convert EPSG": {'it_IT': "Converti EPSG", 'de_DE': "EPSG umwandeln",
                     'fr_FR': "Convertir l'EPSG", 'es': "Convertir EPSG"},
    "Undo the conversion": {'it_IT': "Annulla la conversione",
                            'de_DE': "Umwandlung rückgängig machen",
                            'fr_FR': "Annuler la conversion",
                            'es': "Deshacer la conversión"},
    # ── al salvataggio ───────────────────────────────────────────────────────
    "The scene's georeferencing and the graph's differ": {
        'it_IT': "Il georiferimento della scena e quello del grafo differiscono",
        'de_DE': "Die Georeferenzierung der Szene und die des Graphen unterscheiden sich",
        'fr_FR': "Le géoréférencement de la scène et celui du graphe diffèrent",
        'es': "La georreferenciación de la escena y la del grafo difieren",
    },
    ("The scene was never aligned to these values of the graph. Choose before "
     "saving:"): {
        'it_IT': ("La scena non è mai stata allineata a questi valori del grafo. "
                  "Scegli prima di salvare:"),
        'de_DE': ("Die Szene wurde nie an diese Werte des Graphen angeglichen. "
                  "Vor dem Speichern wählen:"),
        'fr_FR': ("La scène n'a jamais été alignée sur ces valeurs du graphe. "
                  "Choisissez avant d'enregistrer :"),
        'es': ("La escena nunca se alineó con estos valores del grafo. "
               "Elige antes de guardar:"),
    },
    "Ask": {'it_IT': "Chiedi", 'de_DE': "Fragen", 'fr_FR': "Demander", 'es': "Preguntar"},
    "Push the scene into the graph": {
        'it_IT': "Scrivi la scena nel grafo", 'de_DE': "Die Szene in den Graphen schreiben",
        'fr_FR': "Écrire la scène dans le graphe", 'es': "Escribir la escena en el grafo",
    },
    "Pull the graph into the scene": {
        'it_IT': "Prendi il grafo nella scena", 'de_DE': "Den Graphen in die Szene holen",
        'fr_FR': "Reprendre le graphe dans la scène", 'es': "Tomar el grafo en la escena",
    },
    "Keep both as they are": {
        'it_IT': "Lascia entrambi come sono", 'de_DE': "Beide lassen, wie sie sind",
        'fr_FR': "Laisser les deux tels quels", 'es': "Dejar ambos como están",
    },
}


def _compile(template: str):
    '''Un modello → una regex con un gruppo per segnaposto (testo libero).'''
    parts = re.split(r'\{(\w+)\}', template)
    out = []
    for i, part in enumerate(parts):
        out.append(re.escape(part) if i % 2 == 0 else f'(?P<{part}>.+?)')
    return re.compile('^' + ''.join(out) + '$', re.S)


_TEMPLATES = [(msgid, _compile(msgid)) for msgid in MESSAGES if '{' in msgid]


def translate(text: str, lookup: Callable[[str], Optional[str]]) -> str:
    '''``text`` (inglese, già composto) nella lingua che ``lookup`` dà:
    ``lookup(msgid)`` → la traduzione del msgid, o None. Prima la frase
    esatta, poi i modelli; i pezzi catturati si traducono a loro volta. Una
    frase composta di più motivi con «; » si traduce motivo per motivo.'''
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
    if '; ' in text:
        parts = text.split('; ')
        done = [translate(p, lookup) for p in parts]
        if done != parts:
            return '; '.join(done)
    return text


def catalogue(locale: str) -> Callable[[str], Optional[str]]:
    '''Il ``lookup`` di una lingua del catalogo (per le prove fuori da Blender).'''
    return lambda msgid: (MESSAGES.get(msgid) or {}).get(locale)


#: the context of the catalogue in Blender: our own, so that a word Blender
#: already translates elsewhere does not come back with Blender's meaning
#: (measured: «Shift X» is the Shift key for Blender — «Umschalt X» in German)
CONTEXT = "EMGeoref"

#: the sentences Blender translates by itself, by their exact text — operator
#: names and descriptions, property names, enum items, a fixed label: these are
#: also registered in Blender's default contexts (``*`` and ``Operator``)
AUTO = (
    "Pull from graph", "Push to GeoNode", "Convert EPSG", "Undo the conversion",
    ("Read EPSG, shift and azimuth from the active graph's GeoPositionNode and "
     "overwrite the scene's values (then BlenderGIS and 3DSC through the usual "
     "propagation). Objects are not moved"),
    "Rewrite shift.txt (keep shift.old.txt beside it)",
    "Ask", "Push the scene into the graph", "Pull the graph into the scene",
    "Keep both as they are", "Not georeferenced (no EPSG)",
)


def tr(text: str) -> str:
    '''``text`` nella lingua dell'interfaccia di Blender (inglese se la
    traduzione dell'interfaccia è spenta o la lingua non è nel catalogo).'''
    try:
        from bpy.app.translations import pgettext_iface
    except Exception:  # noqa: BLE001 — fuori da Blender
        return text

    def lookup(msgid):
        out = pgettext_iface(msgid, CONTEXT)
        return out if out != msgid else None

    return translate(text, lookup)


def blender_dict() -> dict:
    '''Il dizionario di ``bpy.app.translations.register``: ogni frase nel
    contesto del catalogo (:data:`CONTEXT`, letto da :func:`tr`); le frasi che
    Blender traduce da sé (:data:`AUTO`) anche nei suoi contesti (``*`` per
    etichette e proprietà, ``Operator`` per nomi e descrizioni degli
    operatori).'''
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
