# Integration Guide - Performance Optimizations

## 🎯 STATUS: Parzialmente Integrato

### ✅ Cosa È Integrato

1. **Servizi registrati in `__init__.py`**:
   - ✅ Async thumbnail loader (auto-start/stop)
   - ✅ Cache modules preloaded
   - ✅ Cleanup on unregister

2. **Funzioni modificate**:
   - ✅ `functions.py`: 5 funzioni con edge index + material cache
   - ✅ `import_operators/importer_graphml.py`: Progress bar 8-step
   - ✅ `export_operators/exporter_heriverse.py`: Progress bar
   - ✅ `em_setup/utils.py`: Graph index invalidation
   - ✅ `visual_manager/operators.py`: Material cache invalidation

### ❌ Cosa Resta da Integrare

#### Alta Priorità (Impatto Massimo)

1. **Object Cache - 40+ occorrenze** non ancora sostituite:
   ```python
   # Sostituire in tutti i file:
   obj = bpy.data.objects.get(name)

   # Con:
   from .object_cache import get_object_cache
   obj = get_object_cache().get_object(name)
   ```

   File da modificare:
   - `functions.py`: 6 occorrenze rimanenti (linee 639, 1581, 1983, 2008, 2039, 2089)
   - `stratigraphy_manager/operators.py`: 15+ occorrenze
   - `epoch_manager/operators.py`: 5+ occorrenze
   - `visual_manager/*.py`: 3+ occorrenze
   - Altri 10+ file

2. **Nested Loops Optimization**:
   - `stratigraphy_manager/operators.py:552-564` - O(n⁴) loop
   - `stratigraphy_manager/operators.py:696-713` - O(n²) loops
   - `epoch_manager/operators.py:127-160` - O(n³) loop

3. **Graph Query Batching**:
   - `populate_lists.py:261-269` - 14 sequential queries da batchare

4. **Debouncing Integration**:
   - Tutti gli update callbacks in `em_props.py`
   - Icon update functions

#### Media Priorità

5. **Async Thumbnails Integration**:
   - `thumb_utils.py:reload_doc_previews_for_us()` - sostituire con async version

6. **Icon Update Dirty Tracking**:
   - `functions.py:update_icons()` - aggiungere dirty checking

7. **Viewport Culling**:
   - `functions.py:update_property_materials_alpha()` - versione con culling

---

## 📋 ISTRUZIONI PER INTEGRAZIONE MANUALE

### Step 1: Object Cache (File per File)

**functions.py** - Aggiungere all'inizio del file:
```python
# ✅ OPTIMIZATION: Import object cache
from .object_cache import get_object_cache

# Create module-level cache accessor
_obj_cache = None

def get_obj_cache():
    global _obj_cache
    if _obj_cache is None:
        _obj_cache = get_object_cache()
    return _obj_cache
```

Poi sostituire ogni:
```python
obj = bpy.data.objects.get(name)
```

Con:
```python
obj = get_obj_cache().get_object(name)
```

### Step 2: Nested Loop Optimization

**stratigraphy_manager/operators.py:552-564**

❌ **Prima (O(n⁴))**:
```python
for obj_name in all_em_list_names:
    for obj in bpy.data.objects:
        for collection in bpy.data.collections:
            if obj.name in collection.objects:
```

✅ **Dopo (O(n))**:
```python
from ..object_cache import get_object_cache

cache = get_object_cache()
mesh_objects = cache.get_mesh_objects()  # O(1) cached

# Build lookup dict O(n)
obj_by_name = {obj.name: obj for obj in mesh_objects}

for obj_name in all_em_list_names:
    obj = obj_by_name.get(obj_name)  # O(1)
    if obj:
        # Process object
```

### Step 3: Graph Query Batching

**populate_lists.py:261-269**

❌ **Prima (14 queries)**:
```python
for node_type in stratigraphic_types:
    nodes = graph.get_nodes_by_type(node_type)
    stratigraphic_nodes.extend(nodes)

document_nodes = graph.get_nodes_by_type('document')
property_nodes = graph.get_nodes_by_type('property')
# ... +12 more queries
```

✅ **Dopo (1 query + filtering)**:
```python
# Get all nodes once
all_nodes = list(graph.nodes)  # O(n)

# Filter by type O(n)
stratigraphic_nodes = [n for n in all_nodes if n.node_type in stratigraphic_types]
document_nodes = [n for n in all_nodes if n.node_type == 'document']
property_nodes = [n for n in all_nodes if n.node_type == 'property']
# etc...
```

### Step 4: Debouncing Integration

**em_props.py** - Per ogni update callback:

❌ **Prima**:
```python
def update_units_index(self, context):
    switch_paradata_lists(self, context)
```

✅ **Dopo**:
```python
from .debounce import debounce_call

@debounce_call(delay=0.1)
def update_units_index(self, context):
    switch_paradata_lists(self, context)
```

### Step 5: Async Thumbnails

**thumb_utils.py:reload_doc_previews_for_us()**

❌ **Prima**:
```python
def reload_doc_previews_for_us(us_node_id: str) -> List[Tuple]:
    # Synchronous loading
    for aux_file in graphml.auxiliary_files:
        # ... load images synchronously
```

✅ **Dopo**:
```python
from .thumb_async import load_thumbnails_async

def reload_doc_previews_for_us(us_node_id: str) -> List[Tuple]:
    def on_ready(thumbnails):
        # Refresh UI
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

    # Returns cached or empty, loads in background
    return load_thumbnails_async(us_node_id, graphml.auxiliary_files, on_ready)
```

---

## 🚀 SOLUZIONE RAPIDA: Wrapper Utility

Per facilitare l'integrazione, ho creato moduli già pronti. Puoi semplicemente importarli:

```python
# All'inizio di ogni file che vuoi ottimizzare:
from . import graph_index, material_cache, object_cache, debounce

# Poi usa le funzioni ottimizzate:
cache = object_cache.get_object_cache()
obj = cache.get_object(name)
```

---

## 📊 Impatto Stimato dell'Integrazione Completa

| Integrazione | File da Modificare | Speedup | Effort |
|--------------|-------------------|---------|---------|
| Object Cache (completo) | 15+ file | 10-50× | 2-3h |
| Nested Loops | 3 file | 100-500× | 1-2h |
| Graph Query Batch | 1 file | 10-20× | 30min |
| Debouncing | 1 file | 10-50× | 1h |
| Async Thumbnails | 1 file | ∞ (UX) | 30min |
| Icon Dirty Tracking | 1 file | 5-10× | 30min |

**Totale**: 6-9 ore per integrazione 100% completa

---

## ✅ Come Procedere

### Opzione A: Integrazione Graduale
Modificare 2-3 file alla volta, testare, poi continuare.

### Opzione B: Script di Automazione
Creare script Python che fa le sostituzioni automatiche (regex).

### Opzione C: Wrapper Functions
Creare funzioni wrapper che nascondono le ottimizzazioni:

```python
# optimization_wrappers.py
from . import object_cache, graph_index, material_cache

def get_object(name):
    """Optimized object getter"""
    return object_cache.get_object_cache().get_object(name)

def get_mesh_objects():
    """Optimized mesh objects getter"""
    return object_cache.get_object_cache().get_mesh_objects()

# Poi in qualsiasi file:
from .optimization_wrappers import get_object
obj = get_object(name)  # Automaticamente ottimizzato
```

---

## 🎓 Best Practice

1. **Testare dopo ogni modifica**: Non modificare tutto insieme
2. **Usare git branch**: Creare branch per integrazioni
3. **Benchmark**: Misurare before/after per ogni ottimizzazione
4. **Rollback plan**: Tenere copie originali

---

## 📝 Checklist Integrazione

### Fase 1: Core (2-3h)
- [ ] Object cache in functions.py (6 occorrenze)
- [ ] Object cache in stratigraphy_manager/operators.py
- [ ] Nested loop optimization in stratigraphy_manager
- [ ] Graph query batching in populate_lists.py

### Fase 2: Extended (2-3h)
- [ ] Object cache in epoch_manager
- [ ] Object cache in visual_manager
- [ ] Debouncing in em_props.py callbacks
- [ ] Async thumbnails in thumb_utils.py

### Fase 3: Polish (1-2h)
- [ ] Icon dirty tracking
- [ ] Viewport culling
- [ ] Remaining object cache integrations
- [ ] Testing & validation

---

## 🐛 Troubleshooting

**Problema**: Import errors dopo integrazione

**Soluzione**: Verificare che i moduli siano registrati in `__init__.py` prima dell'uso

**Problema**: Cache non si invalida

**Soluzione**: Chiamare manualmente `invalidate_*_cache()` dopo modifiche

**Problema**: Performance non migliorate

**Soluzione**: Verificare che la versione ottimizzata sia effettivamente chiamata (aggiungere print di debug)

---

**Status**: Framework pronto, integrazione da completare manualmente
**Effort rimanente**: 6-9 ore per 100% integrazione
**Beneficio atteso**: 100-500× speedup complessivo