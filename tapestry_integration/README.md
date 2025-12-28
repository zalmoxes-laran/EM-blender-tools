# Tapestry Integration for EM-blender-tools

AI-powered photorealistic reconstruction of archaeological proxies using Stable Diffusion and ControlNet.

## Overview

Tapestry Integration permette di:
- Renderizzare proxy archeologici con EXR multilayer (Combined, Depth, Cryptomatte)
- Estrarre automaticamente mask per ogni proxy visible da camera
- Generare JSON con metadata dal grafo s3Dgraphy
- Sottomettere job a Tapestry server per ricostruzione AI fotorealistica

## Dipendenze

### Sistema Centralizzato EM-blender-tools

Le dipendenze sono gestite centralmente tramite `scripts/requirements_wheels.txt`:

```txt
# Tapestry Integration dependencies
mmh3>=4.1.0
# Note: OpenImageIO is optional for Tapestry - if not available, fallback to Blender's image API
# Note: numpy and requests are already included in Blender 4.0+
```

### Installazione

```bash
# Setup development (download wheels)
em.bat setup

# Force re-download (se necessario)
em.bat setup force
```

Le wheels vengono scaricate in `wheels/` e incluse automaticamente nel build.

### Dipendenze Dettagliate

1. **mmh3>=4.1.0** (REQUIRED)
   - MurmurHash3 per Cryptomatte object ID hashing
   - Installata automaticamente via `em.bat setup`

2. **numpy** (Già incluso in Blender 4.0+)
   - NO download necessario
   - Usato per operazioni array su immagini

3. **requests** (Già incluso in Blender 4.0+)
   - NO download necessario
   - Usato per comunicazione con Tapestry server

4. **OpenImageIO** (OPZIONALE)
   - NON inclusa (difficile da packageare come wheel)
   - Se non disponibile, usa fallback Blender image API
   - Fornisce estrazione EXR più efficiente

## Architettura

```
scene.em_tools.tapestry (TapestryManagerProps)
├── Network (server_address, server_port, connection_status)
├── Render (camera, resolution, samples, export_normals)
├── Visible Proxies (visible_proxies CollectionProperty)
└── Generation Params (model, steps, cfg_scale, denoise_strength)
```

## Workflow

1. **Attiva experimental features:**
   - `scene.em_tools.experimental_features = True`
   - Panel "Tapestry" appare in "EM Bridge" tab

2. **Analisi scena:**
   - Seleziona camera da Visual Manager
   - Click "Analyze Camera View"
   - Identifica proxy visibili dal grafo s3Dgraphy

3. **Render ed export:**
   - Click "Setup Render" - configura Cycles ID-only mode
   - Click "Render for Tapestry":
     - Render EXR (Combined, Depth, Cryptomatte)
     - Estrai RGB, Depth, Masks PNG
     - Genera JSON con metadata
     - Submit a Tapestry server (opzionale)

## Output

Directory: `//tapestry_export/blender_<timestamp>/`

Files generati:
- `render.exr` - Raw multilayer (Combined, Depth, Cryptomatte)
- `render_rgb.png` - RGB render
- `render_depth.png` - Depth normalizzato
- `mask_USM100.png` - Mask per proxy USM100
- `tapestry_input.json` - JSON per Tapestry server

## Integrazione EM Infrastructure

### s3Dgraphy Graph
- Query US nodes con proprietà archeologiche
- Filter by epoch (EM mode)
- Metadata: type, material, period, style, condition

### EM Naming Convention
- Proxy name: `<graph_code>.<US_name>` (es. "VDL16.USM100")
- Usa `node_name_to_proxy_name()` e object cache O(1)

### Visual Manager
- Selezione camera per rendering
- Frustum culling per visibility check

### Epoch Manager
- Filter US by active epoch

## Configurazione Render (ID-Only Mode)

```python
# Cycles FORCED, NO lighting calculation
scene.render.engine = 'CYCLES'
scene.cycles.samples = 8  # Low samples
scene.cycles.max_bounces = 0  # NO light bouncing!
# ... all bounce types = 0

# EXR Multilayer
scene.render.image_settings.file_format = 'OPEN_EXR_MULTILAYER'

# Passes: Combined, Depth, Cryptomatte Object/Material
```

**Motivo:** Solo ID/depth/normals necessari per ControlNet, NO lighting. Veloce e efficiente.

## Development

### Build Extension

```bash
em.bat dev              # Quick: increment dev build + build
em.bat devrel           # Dev release: inc + build + commit + tag + push

em.bat build dev        # Build without increment
em.bat build rc         # Build release candidate
em.bat build stable     # Build stable release
```

### Testing

1. Verifica addon carica senza errori
2. Verifica panel visibile con `experimental_features = True`
3. Test con scena EM reale (proxy, s3Dgraphy graph, camera)
4. Test rendering EXR con Cryptomatte
5. Test estrazione masks
6. Test network integration (se Tapestry server running)

## Troubleshooting

### ImportError: mmh3 not found

```bash
# Re-download wheels
em.bat setup force

# Verifica wheels directory
dir wheels\mmh3*.whl

# Rebuild extension
em.bat build dev
```

### OpenImageIO not available

Non è un errore! OpenImageIO è opzionale. Il sistema usa automaticamente il fallback Blender API per estrazione EXR.

Se vuoi OpenImageIO (più efficiente):
- Installazione manuale (difficile)
- O usa fallback (funziona bene)

### Panel non visibile

Verifica:
```python
# In Blender Python Console
import bpy
scene = bpy.context.scene

# Attiva experimental features
scene.em_tools.experimental_features = True

# Verifica tapestry properties esistano
print(scene.em_tools.tapestry)
```

### Cryptomatte mask vuota

Verifica:
1. Oggetti hanno material assegnato
2. Cryptomatte Object pass abilitato nel render
3. View layer ha `use_pass_cryptomatte_object = True`

## Links

- **Tapestry Server:** `EM-Tapestry/` repository
- **s3Dgraphy:** Knowledge graph for archaeological data
- **EM-blender-tools:** Main addon repository

## License

GPL-3.0 (same as EM-blender-tools)
