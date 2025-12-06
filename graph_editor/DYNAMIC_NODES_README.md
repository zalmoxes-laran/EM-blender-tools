# Dynamic Node System for EMGraph

## Overview

Il sistema di nodi dinamici genera automaticamente tutte le classi Blender Node dai file JSON di s3dgraphy, eliminando la necessità di modificare il codice Python per aggiungere nuovi tipi di nodi.

## Funzionalità

### ✅ Generazione Automatica dei Nodi
- Legge `s3Dgraphy_node_datamodel .json`
- Genera classi Python per ogni tipo di nodo
- Applica automaticamente colori, icone e socket dal datamodel
- Supporta ereditarietà e sottotipi

### ✅ Validazione degli Edge
- Legge `s3Dgraphy_connections_datamodel.json`
- Valida che ogni edge rispetti le regole definite
- **Supporta ereditarietà dei tipi**: se un edge permette `StratigraphicNode → StratigraphicNode`, permette automaticamente anche `US → USVs` (sottotipi)
- Stampa debug dettagliato per edge non validi

### ✅ Flessibilità Totale
- Aggiorna il JSON → ricarica Blender → nuovi nodi disponibili
- Nessuna modifica al codice Python necessaria
- Sistema formale e robusto

## File Coinvolti

```
graph_editor/
├── dynamic_nodes.py          # ✨ Sistema di generazione dinamica
├── socket_generator.py       # Carica JSON e genera socket
├── __init__.py              # Registra nodi dinamici
└── operators.py             # Usa _NODE_TYPE_MAP per creare nodi
```

## Come Funziona

### 1. Caricamento Datamodel
```python
from .socket_generator import load_datamodels

nodes_dm, connections_dm = load_datamodels()
```

### 2. Generazione Classi
```python
from .dynamic_nodes import generate_all_node_classes

classes = generate_all_node_classes()
# → Genera EMGraph_US_Node, EMGraph_PropertyNode, etc.
```

### 3. Registrazione in Blender
```python
from .dynamic_nodes import register_dynamic_nodes

register_dynamic_nodes()
# → Tutti i nodi disponibili nel Node Editor
```

### 4. Validazione Edge
```python
from .dynamic_nodes import validate_graph_edges

invalid_edges = validate_graph_edges(graph, connections_dm, nodes_dm)
# → Stampa tutti gli edge che violano le regole
```

## Logica di Ereditarietà degli Edge

Il sistema implementa una validazione intelligente degli edge:

**Esempio dal datamodel:**
```json
{
  "is_before": {
    "allowed_connections": {
      "source": ["StratigraphicNode"],
      "target": ["StratigraphicNode"]
    }
  }
}
```

**Validazione:**
```python
# ✅ PERMESSO: US è sottotipo di StratigraphicNode
US --[is_before]--> USVs

# ✅ PERMESSO: SF è sottotipo di StratigraphicNode
SF --[is_before]--> US

# ❌ NON PERMESSO: PropertyNode non è sottotipo di StratigraphicNode
PropertyNode --[is_before]--> US
```

**Implementazione:**
```python
def is_edge_allowed(source_type, target_type, edge_type, ...):
    # Espande i tipi permessi includendo tutti i sottotipi
    expanded_sources = set()
    for allowed_source in allowed_sources:
        expanded_sources.add(allowed_source)
        if allowed_source in node_hierarchy:
            expanded_sources.update(node_hierarchy[allowed_source])

    # Verifica se la connessione è permessa
    return source_type in expanded_sources and target_type in expanded_targets
```

## Debug Output

Quando carichi un grafo, vedrai:

```
============================================================
DYNAMIC NODE GENERATION
============================================================
  ✓ Generated: US (US)
  ✓ Generated: USVs (USV/s)
  ✓ Generated: PropertyNode (Property Node)
  ...
✅ Successfully generated 45 node classes
============================================================

============================================================
EDGE VALIDATION
============================================================

⚠️  Found 3 invalid edges (out of 150 total):

  ✗ US123 (US) --[has_property]--> Prop456 (PropertyNode)
  ✗ SF789 (SF) --[documents]--> Doc101 (DocumentNode)
  ✗ USV234 (USVs) --[wrong_edge]--> US567 (US)

These edges cannot be represented in EMGraph due to datamodel rules.
============================================================
```

## Aggiungere Nuovi Tipi di Nodi

1. **Apri** `s3Dgraphy/src/s3dgraphy/JSON_config/s3Dgraphy_node_datamodel .json`

2. **Aggiungi** il nuovo tipo:
```json
{
  "stratigraphic_nodes": {
    "StratigraphicNode": {
      "subtypes": {
        "USM": {
          "class": "MasonryUnit",
          "abbreviation": "USM",
          "label": "USM (Masonry Unit)",
          "symbol": "brick pattern",
          "description": "Unità stratigrafica muraria"
        }
      }
    }
  }
}
```

3. **Ricarica** Blender → il nodo `USM` sarà automaticamente disponibile!

## Aggiungere Nuove Regole di Connessione

1. **Apri** `s3Dgraphy/src/s3dgraphy/JSON_config/s3Dgraphy_connections_datamodel.json`

2. **Aggiungi** il nuovo edge:
```json
{
  "edge_types": {
    "bonds_with": {
      "name": "bonds_with",
      "label": "Structural Bond",
      "description": "Indicates structural bonding between masonry units",
      "allowed_connections": {
        "source": ["StratigraphicNode"],
        "target": ["StratigraphicNode"]
      }
    }
  }
}
```

3. **Ricarica** Blender → la regola sarà applicata automaticamente!

## Vantaggi

- ✅ **Zero codice da modificare** per nuovi tipi di nodi
- ✅ **Validazione formale** basata su regole JSON
- ✅ **Debug chiaro** di edge non validi
- ✅ **Ereditarietà intelligente** dei tipi
- ✅ **Aggiornamenti rapidi** del datamodel
- ✅ **Sistema robusto** e testato

## Note Tecniche

- Il sistema usa `type()` per creare classi dinamicamente
- Le classi generate ereditano da `EMGraphNodeBase`
- I socket vengono generati da `socket_generator.py`
- La cache `_NODE_TYPE_MAP` mappa `node_type` → classe Blender
- La validazione usa una gerarchia espansa per i sottotipi
