# Correzione Direzioni Edge in EMGraph

## Problema Identificato

Quando si importa un grafo s3dgraphy in EMGraph, alcuni edge potrebbero avere la **direzione sbagliata** rispetto alle regole definite nel datamodel JSON.

**⚠️ IMPORTANTE:** I nodi `DocumentNode` vengono creati **dinamicamente** quando si caricano file ausiliari (EMdb Excel) che hanno resource folders associate (thumbnails indicizzate in JSON). Gli edge potrebbero essere stati creati con direzione o tipo sbagliato.

### Esempio del Problema

```
DocumentNode → StratigraphicNode  ❌ NON PERMESSO
```

Secondo `s3Dgraphy_connections_datamodel.json`, l'edge `has_documentation` permette **solo**:

```
StratigraphicNode → DocumentNode  ✅ PERMESSO
```

## Casi Specifici: DocumentNode da Resource Folders

### Problema
I `DocumentNode` vengono creati automaticamente durante l'import di file ausiliari (EMdb) quando vengono trovate thumbnail indicizzate. Il codice potrebbe aver creato edge con:
- **Edge type sbagliato:** `generic_connection` invece di `has_documentation`
- **Direzione sbagliata:** `DocumentNode → US` invece di `US → DocumentNode`

### Soluzione Implementata
Il codice in `thumb_utils.py:reload_doc_previews_for_us()` è stato aggiornato per supportare:
1. ✅ Edge type corretto: `has_documentation`
2. ✅ Fallback retrocompatibile: `generic_connection` (con verifica tipo nodo)
3. ✅ Entrambe le direzioni: supporta sia `US → Document` che `Document → US`

**File modificato:** `EM-blender-tools/thumb_utils.py:465-489`

Questo garantisce che le thumbnails vengano trovate e visualizzate nello Stratigraphy Manager **indipendentemente** da come gli edge sono stati creati.

## Soluzioni Implementate

### 1. ✅ Fallback Intelligente in EMGraph (COMPLETATO)

Il sistema EMGraph ora usa il socket `generic_connection` come fallback quando non trova il socket specifico:

**Priorità di matching in `create_link()`:**
1. Match esatto del nome socket
2. Match case-insensitive
3. Match parziale con keywords
4. **Fallback a `generic_connection`** ← NUOVO!
5. Ultimo resort: primo socket disponibile (con warning estesi)

**Vantaggi:**
- Il socket `generic_connection` è valido per **qualsiasi nodo** → **qualsiasi nodo** secondo il datamodel
- Identifica chiaramente le connessioni problematiche nel grafo visuale
- Warning dettagliati nella console di Blender

**File modificato:** `EM-blender-tools/graph_editor/operators.py:447-543`

### 2. ✅ Script di Correzione (COMPLETATO)

Creato script Python per trovare e correggere automaticamente gli edge con direzioni sbagliate nei grafi s3dgraphy.

**Posizione:** `EM-blender-tools/scripts/fix_edge_directions.py`

## Come Usare lo Script di Correzione

### Prerequisiti

Lo script richiede:
- Python 3.x
- s3dgraphy installato
- Accesso ai file JSON di configurazione

### Comandi Disponibili

#### 1. Analizzare un Grafo

```bash
cd EM_framework
python EM-blender-tools/scripts/fix_edge_directions.py --graph US02
```

Output:
```
============================================================
ANALYZING GRAPH: US02
============================================================

✓ Graph loaded
  Total nodes: 45
  Total edges: 67

⚠️  Found 3 edge direction issues:

1. Edge: has_documentation
   Current:  DOC.US02.US02.004 (DocumentNode) → US02 (US)
   ✓ FIX:    US02 (US) → DOC.US02.US02.004 (DocumentNode)

2. Edge: has_representation_model
   Current:  RM.US05 (RepresentationModelNode) → US05 (US)
   ✓ FIX:    US05 (US) → RM.US05 (RepresentationModelNode)
```

#### 2. Vedere le Modifiche (Dry Run)

```bash
python EM-blender-tools/scripts/fix_edge_directions.py --graph US02 --dry-run
```

Mostra esattamente cosa verrebbe modificato **senza applicare** le modifiche.

#### 3. Applicare le Correzioni

```bash
python EM-blender-tools/scripts/fix_edge_directions.py --graph US02 --fix
```

**⚠️ ATTENZIONE:** Questo modifica il grafo nel database s3dgraphy!

Output:
```
============================================================
APPLYING FIXES:
============================================================

1. Reversing edge 'has_documentation'
   FROM: DOC.US02.US02.004 → US02
   TO:   US02 → DOC.US02.US02.004
   ✓ Fixed

💾 Saving graph 'US02'...
✅ Graph saved successfully!
```

## Workflow Consigliato

### Quando Importi un Grafo in EMGraph

1. **Carica il grafo in Blender**
   - Usa l'operatore "Draw Graph" in EMGraph

2. **Controlla i warning nella console**
   - Cerca messaggi come:
     ```
     ⚠️ No matching output socket for 'has_documentation' on Document
         Using 'generic_connection' fallback socket
     ```

3. **Identifica gli edge problematici nel grafo visuale**
   - Gli edge che usano `generic_connection` sono evidenziati nei warning

4. **Analizza il grafo con lo script**
   ```bash
   python EM-blender-tools/scripts/fix_edge_directions.py --graph GRAPH_ID
   ```

5. **Applica le correzioni**
   ```bash
   python EM-blender-tools/scripts/fix_edge_directions.py --graph GRAPH_ID --fix
   ```

6. **Ricarica il grafo in Blender**
   - Le connessioni ora dovrebbero essere corrette!

## Dettagli Tecnici

### Regole di Direzione Edge

Le regole sono definite in:
```
s3Dgraphy/src/s3dgraphy/JSON_config/s3Dgraphy_connections_datamodel.json
```

Esempio per `has_documentation`:
```json
{
  "has_documentation": {
    "allowed_connections": {
      "source": ["StratigraphicNode", "SpecialFindUnit", "VirtualStratigraphicUnit"],
      "target": ["DocumentNode"]
    }
  }
}
```

### Socket `generic_connection`

Definizione nel datamodel:
```json
{
  "generic_connection": {
    "allowed_connections": {
      "source": ["Node"],
      "target": ["Node"]
    }
  }
}
```

Questo socket è universale e permette **qualsiasi** connessione tra nodi.

### Validazione Automatica

Il sistema EMGraph implementa validazione automatica in:
- `graph_editor/dynamic_nodes.py:243-299` - Funzione `is_edge_allowed()`
- `graph_editor/dynamic_nodes.py:302-362` - Funzione `validate_graph_edges()`

Questa validazione:
- ✅ Supporta ereditarietà dei tipi (US, USVs, SF sono tutti sottotipi di StratigraphicNode)
- ✅ Espande automaticamente i tipi permessi per includere sottotipi
- ✅ Stampa report dettagliati degli edge non validi

## Esempi di Edge Comuni con Direzioni Specifiche

### ✅ Direzioni CORRETTE

```
US → DocumentNode                    (has_documentation)
US → PropertyNode                    (has_property)
US → EpochNode                       (has_first_epoch, survive_in_epoch)
US → RepresentationModelNode         (has_representation_model)
ExtractorNode → DocumentNode         (extracted_from)
PropertyNode → ExtractorNode         (has_data_provenance)
```

### ❌ Direzioni SBAGLIATE (da correggere)

```
DocumentNode → US                    ❌ Invertire a: US → DocumentNode
PropertyNode → US                    ❌ Invertire a: US → PropertyNode
RepresentationModelNode → US         ❌ Invertire a: US → RepresentationModelNode
DocumentNode → ExtractorNode         ❌ Invertire a: ExtractorNode → DocumentNode
```

## Troubleshooting

### "Graph not found"

Lo script usa `s3dgraphy.get_graph()`. Verifica che:
- s3dgraphy sia installato correttamente
- Il GRAPH_ID sia corretto
- Hai i permessi per accedere al database

### "Cannot load connections datamodel"

Verifica che:
- Il file `s3Dgraphy/src/s3dgraphy/JSON_config/s3Dgraphy_connections_datamodel.json` esista
- Il path sia corretto rispetto alla tua installazione

### Warning "No 'generic_connection' socket found"

Alcuni nodi potrebbero non avere il socket `generic_connection`. In questo caso:
1. Verifica che il datamodel JSON sia aggiornato
2. Ricarica i nodi dinamici in Blender
3. Se il problema persiste, il nodo potrebbe aver bisogno di essere aggiunto al datamodel

## Riferimenti

- **Datamodel Nodi:** `s3Dgraphy/src/s3dgraphy/JSON_config/s3Dgraphy_node_datamodel .json`
- **Datamodel Connessioni:** `s3Dgraphy/src/s3dgraphy/JSON_config/s3Dgraphy_connections_datamodel.json`
- **Sistema Dinamico EMGraph:** `EM-blender-tools/graph_editor/DYNAMIC_NODES_README.md`
- **Codice Validazione:** `EM-blender-tools/graph_editor/dynamic_nodes.py`
