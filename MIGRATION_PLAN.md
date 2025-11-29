# Piano di Migrazione Scene Properties → scene.em_tools

## Obiettivo
Migrare TUTTE le proprietà registrate direttamente su `bpy.types.Scene` dentro `scene.em_tools` per seguire le best practices di Blender (un solo PointerProperty per addon).

## Analisi Proprietà Trovate

### Proprietà in __init__.py (CORE)

#### Collections (setup_scene_collections)
- `emviq_error_list`: EMviqListErrors
- `edges_list`: EDGESListItem
- `em_sources_list`: EMListParadata
- `em_properties_list`: EMListParadata
- `em_extractors_list`: EMListParadata
- `em_combiners_list`: EMListParadata
- `em_v_sources_list`: EMListParadata (versioned/streaming)
- `em_v_properties_list`: EMListParadata (versioned/streaming)
- `em_v_extractors_list`: EMListParadata (versioned/streaming)
- `em_v_combiners_list`: EMListParadata (versioned/streaming)

#### Indices (setup_scene_indices)
- `selected_epoch_us_list_index`
- `emviq_error_list_index`
- `em_list_index` ⚠️ LEGACY - già migrato?
- `epoch_list_index`
- `edges_list_index`
- `em_sources_list_index`
- `em_properties_list_index`
- `em_extractors_list_index`
- `em_combiners_list_index`
- `em_v_sources_list_index`
- `em_v_properties_list_index`
- `em_v_extractors_list_index`
- `em_v_combiners_list_index`

#### Boolean Properties (setup_scene_properties)
- `paradata_streaming_mode`
- `prop_paradata_streaming_mode`
- `comb_paradata_streaming_mode`
- `extr_paradata_streaming_mode`
- `proxy_shader_mode`

#### String Properties (setup_scene_properties)
- `EM_file` - GraphML file path
- `EMviq_folder` - Export folder
- `EMviq_scene_folder` - Scene folder
- `EMviq_project_name` - Project name
- `EMviq_user_name` - User name
- `EMviq_user_password` - Password
- `ATON_path` - ATON framework path
- `EMviq_model_author_name` - Author name
- `proxy_display_mode` - Display mode
- `proxy_blend_mode` - Blend mode

#### Float Properties
- `proxy_display_alpha` - Alpha value for proxies

#### Integer Properties
- `EM_gltf_export_quality` - Export quality
- `EM_gltf_export_maxres` - Max resolution

#### Pointer Properties (setup_pointer_properties)
- `em_settings`: EM_Other_Settings
- `em_graph`: None (runtime)

### Proprietà in Altri Moduli

#### proxy_to_rm_projection/__init__.py
- `proxy_projection_auto_trigger`: BoolProperty
- `proxy_projection_settings`: ProxyProjectionSettings

#### activity_manager.py
- `activity_manager`: ActivityManagerProperties

#### server.py
- `EM_server_status`: BoolProperty
- `server_host`: StringProperty
- `server_port`: IntProperty

#### EMdb_excel.py
- `EMdb_xlsx_filepath`: StringProperty

#### visual_manager/operators.py
- `property_enum`: EnumProperty (temporaneo)
- `selected_property`: StringProperty (temporaneo)

#### visual_manager/data.py
- `property_values`: CollectionProperty
- `active_value_index`: IntProperty
- `show_all_graphs`: BoolProperty
- `color_ramp_props`: ColorRampProperties
- `camera_em_list`: CollectionProperty
- `active_camera_em_index`: IntProperty
- `label_settings`: LabelSettings

#### cronofilter/__init__.py
- `cf_settings`: CF_CronoFilterSettings

#### paradata_manager.py
- `paradata_auto_update`: BoolProperty
- `paradata_image`: ParadataImageProps

#### Altri file (da analizzare)
- `anastylosis_*` properties
- `rm_list`, `rm_list_index`, `rm_settings`
- `epoch_list` ⚠️ Già usato ma dove è definito?
- `filter_by_epoch`, `filter_by_activity`
- `sync_list_visibility`, `sync_rm_visibility`
- `show_reconstruction_units`, `include_surviving_units`
- `proxy_inflate_*` properties
- `heriverse_*` export properties
- `landscape_mode_active`
- `last_active_graph_code`
- `graph_editor_settings`

## Strategia di Migrazione

### Fase 1: Preparazione
1. ✅ Identificare tutte le proprietà
2. ⏳ Categorizzare per tipo e modulo
3. ⏳ Verificare quali sono già in em_props.py

### Fase 2: Migrazione Incrementale
1. Migrare proprietà CORE (__init__.py)
   - Collections paradata
   - Indices
   - Boolean/String/Float/Int properties

2. Migrare proprietà Manager
   - activity_manager
   - anastylosis_*
   - rm_manager
   - visual_manager properties

3. Migrare proprietà Export/Server
   - server_*
   - heriverse_*
   - EMviq_*
   - ATON_*

4. Migrare proprietà Proxy
   - proxy_display_*
   - proxy_inflate_*
   - proxy_projection_*

### Fase 3: Aggiornamento Riferimenti
- Sostituire `scene.property_name` con `scene.em_tools.property_name`
- Aggiornare tutti i file che usano queste proprietà

### Fase 4: Test
- Verificare che tutto funzioni
- Test import GraphML
- Test export
- Test managers

## Note Importanti

⚠️ **ATTENZIONE**: Questa è una migrazione BREAKING CHANGE!
- I file .blend esistenti perderanno i valori delle proprietà migrate
- Serve una funzione di migrazione per convertire vecchi file

## Proprietà da NON migrare (WindowManager/Object)
- `WindowManager.em_addon_settings`
- `WindowManager.export_vars`
- `WindowManager.export_tables_vars`
- `Object.EM_ep_belong_ob`
- `Object.EM_ep_belong_ob_index`

Queste vanno bene dove sono perché sono su WindowManager o Object, non su Scene.
