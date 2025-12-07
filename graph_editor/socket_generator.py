"""
Socket Generator for Graph Viewer
Dynamically generates input/output sockets based on s3Dgraphy JSON configuration files.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

# ============================================================================
# CONFIGURATION LOADING
# ============================================================================

def get_s3dgraphy_config_path() -> Optional[Path]:
    """
    Trova il percorso dei file di configurazione JSON di s3dgraphy.
    Cerca prima nel package installato, poi nel repository locale.
    """
    try:
        import s3dgraphy
        s3dgraphy_path = Path(s3dgraphy.__file__).parent
        config_path = s3dgraphy_path / "JSON_config"

        if config_path.exists():
            return config_path
    except ImportError:
        pass

    # Fallback: cerca nel repository locale
    current_file = Path(__file__).resolve()
    em_framework = current_file.parent.parent.parent
    local_config = em_framework / "s3Dgraphy" / "src" / "s3dgraphy" / "JSON_config"

    if local_config.exists():
        return local_config

    return None


def load_datamodels() -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Carica i file JSON di configurazione di s3dgraphy.

    Returns:
        Tuple of (nodes_datamodel, connections_datamodel) or (None, None) if not found
    """
    config_path = get_s3dgraphy_config_path()

    if not config_path:
        print("⚠️  s3dgraphy JSON config path not found")
        return None, None

    # Nota: il file dei nodi ha uno spazio nel nome!
    nodes_file = config_path / "s3Dgraphy_node_datamodel .json"
    connections_file = config_path / "s3Dgraphy_connections_datamodel.json"

    nodes_data = None
    connections_data = None

    try:
        if nodes_file.exists():
            with open(nodes_file, 'r', encoding='utf-8') as f:
                nodes_data = json.load(f)
            print(f"✅ Loaded node datamodel from {nodes_file}")
        else:
            print(f"⚠️  Node datamodel not found: {nodes_file}")
    except Exception as e:
        print(f"❌ Error loading node datamodel: {e}")

    try:
        if connections_file.exists():
            with open(connections_file, 'r', encoding='utf-8') as f:
                connections_data = json.load(f)
            print(f"✅ Loaded connections datamodel from {connections_file}")
        else:
            print(f"⚠️  Connections datamodel not found: {connections_file}")
    except Exception as e:
        print(f"❌ Error loading connections datamodel: {e}")

    return nodes_data, connections_data


# ============================================================================
# NODE TYPE MAPPING
# ============================================================================

def build_node_type_family_map(nodes_datamodel: Dict) -> Dict[str, str]:
    """
    Costruisce una mappa da node_type (subtypes) → node_type_family (parent).

    Esempi:
        "US" → "StratigraphicNode"
        "USVs" → "StratigraphicNode"
        "PropertyNode" → "ParadataNode"
        "EpochNode" → "EpochNode" (è già un parent)

    Args:
        nodes_datamodel: Il JSON dei nodi s3dgraphy

    Returns:
        Dict mapping node_type → parent_node_type
    """
    if not nodes_datamodel:
        return {}

    type_family_map = {}

    # Processa ogni categoria di nodi
    for category_key, category_data in nodes_datamodel.items():
        if category_key in ['s3Dgraphy_data_model_version', 'description', 'components']:
            continue

        # Categoria può contenere un parent node e i suoi subtypes
        for node_key, node_data in category_data.items():
            if not isinstance(node_data, dict):
                continue

            parent_class = node_data.get('class')

            # Se ha subtypes, mappa ogni subtype al parent
            if 'subtypes' in node_data:
                for subtype_key, subtype_data in node_data['subtypes'].items():
                    subtype_class = subtype_data.get('class')
                    # Il subtype punta al parent
                    type_family_map[subtype_class] = parent_class
                    # Anche l'abbreviazione punta al parent
                    if 'abbreviation' in subtype_data:
                        type_family_map[subtype_data['abbreviation']] = parent_class
                    # Anche il key stesso
                    type_family_map[subtype_key] = parent_class

            # Il parent punta a se stesso
            type_family_map[parent_class] = parent_class
            type_family_map[node_key] = parent_class

    # Aggiungi mappature speciali
    # Nodi che non hanno subtypes ma sono usati direttamente
    special_mappings = {
        'EpochNode': 'EpochNode',
        'GeoPositionNode': 'GeoPositionNode',
        'LinkNode': 'LinkNode',
        'AuthorNode': 'AuthorNode',
        'RepresentationModelNode': 'RepresentationModelNode',
        'RepresentationModelDocNode': 'RepresentationModelDocNode',
        'RepresentationModelSpecialFindNode': 'RepresentationModelSpecialFindNode',
        'SemanticShapeNode': 'SemanticShapeNode',
        'UnknownNode': 'StratigraphicNode',  # Fallback

        # ✅ FIXED: Mappature lowercase → PascalCase (s3dgraphy usa lowercase nei node_type)
        'document': 'DocumentNode',
        'property': 'PropertyNode',
        'extractor': 'ExtractorNode',
        'combiner': 'CombinerNode',
        'link': 'LinkNode',
        'geo_position': 'GeoPositionNode',
        'geoposition': 'GeoPositionNode',
        'author': 'AuthorNode',
        'epoch': 'EpochNode',
    }

    type_family_map.update(special_mappings)

    return type_family_map


def get_node_type_family(node_type: str, type_family_map: Dict[str, str]) -> str:
    """
    Dato un node_type (es. "US", "PropertyNode"), ritorna il parent/family.

    Args:
        node_type: Il tipo del nodo (es. "US", "USVs", "PropertyNode")
        type_family_map: La mappa costruita da build_node_type_family_map()

    Returns:
        Il parent node type (es. "StratigraphicNode", "ParadataNode")
    """
    return type_family_map.get(node_type, 'StratigraphicNode')  # Fallback


# ============================================================================
# SOCKET MAP BUILDING
# ============================================================================

def build_socket_map(connections_datamodel: Dict, type_family_map: Dict[str, str]) -> Dict[str, Dict[str, List[str]]]:
    """
    Costruisce una mappa dei socket richiesti per ogni node_type_family.

    Struttura ritornata:
    {
        "StratigraphicNode": {
            "inputs": ["is_after", "is_cut_by", "is_filled_by", ...],
            "outputs": ["is_before", "cuts", "fills", "has_property", ...]
        },
        "PropertyNode": {
            "inputs": ["has_property"],
            "outputs": ["has_data_provenance", ...]
        },
        ...
    }

    Args:
        connections_datamodel: Il JSON delle connessioni s3dgraphy
        type_family_map: Mappa node_type → parent_family

    Returns:
        Dict con inputs/outputs per ogni node_type_family
    """
    if not connections_datamodel or 'edge_types' not in connections_datamodel:
        return {}

    socket_map = {}

    # ✅ FIXED: Pre-popola con 'generic_connection' per tutti i tipi possibili
    # Questo garantisce che TUTTI i nodi abbiano almeno generic_connection come fallback
    all_node_families = set(type_family_map.values())
    for family in all_node_families:
        socket_map[family] = {
            'inputs': ['generic_connection'],
            'outputs': ['generic_connection']
        }

    edge_types = connections_datamodel['edge_types']

    for edge_type_name, edge_data in edge_types.items():
        if 'allowed_connections' not in edge_data:
            continue

        allowed = edge_data['allowed_connections']
        source_types = allowed.get('source', [])
        target_types = allowed.get('target', [])

        # Per ogni source type, aggiungi questo edge come OUTPUT
        for source_type in source_types:
            # Normalizza il source_type al suo parent family
            # (ma usa il source_type direttamente se è già un parent)
            family = source_type  # Di solito nel JSON sono già i parent

            if family not in socket_map:
                socket_map[family] = {'inputs': [], 'outputs': []}

            if edge_type_name not in socket_map[family]['outputs']:
                socket_map[family]['outputs'].append(edge_type_name)

        # Per ogni target type, aggiungi questo edge come INPUT
        for target_type in target_types:
            family = target_type

            if family not in socket_map:
                socket_map[family] = {'inputs': [], 'outputs': []}

            if edge_type_name not in socket_map[family]['inputs']:
                socket_map[family]['inputs'].append(edge_type_name)

    return socket_map


# ============================================================================
# SOCKET GENERATION
# ============================================================================

def generate_sockets_for_node(bl_node, node_type: str, socket_map: Dict, type_family_map: Dict):
    """
    Genera dinamicamente i socket per un nodo Blender basandosi sul suo node_type.

    IMPORTANTE: I socket vengono ereditati dalla gerarchia. Se PropertyNode è figlio di
    ParadataNode, eredita TUTTI i socket di ParadataNode E i socket specifici di PropertyNode.

    Args:
        bl_node: L'istanza del nodo Blender
        node_type: Il tipo del nodo s3dgraphy (es. "US", "PropertyNode", "EpochNode")
        socket_map: La mappa costruita da build_socket_map()
        type_family_map: La mappa costruita da build_node_type_family_map()
    """
    # Trova la famiglia del nodo
    node_family = get_node_type_family(node_type, type_family_map)

    # ✅ Raccogli socket dalla famiglia e dal tipo specifico (se diverso)
    all_inputs = set()
    all_outputs = set()

    # 1. Socket della famiglia parent
    if node_family in socket_map:
        all_inputs.update(socket_map[node_family]['inputs'])
        all_outputs.update(socket_map[node_family]['outputs'])

    # 2. Socket del tipo specifico (se diverso dal parent)
    if node_type != node_family and node_type in socket_map:
        all_inputs.update(socket_map[node_type]['inputs'])
        all_outputs.update(socket_map[node_type]['outputs'])

    # Crea INPUT sockets
    for input_socket_name in all_inputs:
        # Verifica che non esista già
        if input_socket_name not in [s.name for s in bl_node.inputs]:
            bl_node.inputs.new('EMGraphSocketType', input_socket_name)

    # Crea OUTPUT sockets
    for output_socket_name in all_outputs:
        # Verifica che non esista già
        if output_socket_name not in [s.name for s in bl_node.outputs]:
            bl_node.outputs.new('EMGraphSocketType', output_socket_name)


# ============================================================================
# GLOBAL INITIALIZATION
# ============================================================================

# Cache globale per evitare di ricaricare i JSON ad ogni nodo
_NODES_DATAMODEL = None
_CONNECTIONS_DATAMODEL = None
_SOCKET_MAP = None
_TYPE_FAMILY_MAP = None


def initialize_socket_system():
    """
    Inizializza il sistema di socket caricando i JSON e costruendo le mappe.
    Deve essere chiamato una volta all'avvio del modulo.
    """
    global _NODES_DATAMODEL, _CONNECTIONS_DATAMODEL, _SOCKET_MAP, _TYPE_FAMILY_MAP

    print("\n🔌 Initializing dynamic socket system...")

    # Carica i JSON
    _NODES_DATAMODEL, _CONNECTIONS_DATAMODEL = load_datamodels()

    if not _CONNECTIONS_DATAMODEL:
        print("⚠️  Warning: Could not load s3dgraphy datamodels. Socket generation will be limited.")
        _SOCKET_MAP = {}
        _TYPE_FAMILY_MAP = {}
        return

    # Costruisci le mappe
    _TYPE_FAMILY_MAP = build_node_type_family_map(_NODES_DATAMODEL)
    _SOCKET_MAP = build_socket_map(_CONNECTIONS_DATAMODEL, _TYPE_FAMILY_MAP)

    print(f"✅ Socket system initialized:")
    print(f"   - {len(_TYPE_FAMILY_MAP)} node type mappings")
    print(f"   - {len(_SOCKET_MAP)} node families with sockets")

    # Debug: mostra alcuni esempi
    if _SOCKET_MAP:
        print("\n📊 Socket map examples:")
        for family in ['StratigraphicNode', 'PropertyNode', 'EpochNode']:
            if family in _SOCKET_MAP:
                inputs_count = len(_SOCKET_MAP[family]['inputs'])
                outputs_count = len(_SOCKET_MAP[family]['outputs'])
                print(f"   - {family}: {inputs_count} inputs, {outputs_count} outputs")


def get_socket_map() -> Dict:
    """Ritorna la socket map globale (inizializza se necessario)"""
    global _SOCKET_MAP
    if _SOCKET_MAP is None:
        initialize_socket_system()
    return _SOCKET_MAP or {}


def get_type_family_map() -> Dict:
    """Ritorna la type family map globale (inizializza se necessario)"""
    global _TYPE_FAMILY_MAP
    if _TYPE_FAMILY_MAP is None:
        initialize_socket_system()
    return _TYPE_FAMILY_MAP or {}


# ============================================================================
# PUBLIC API
# ============================================================================

def generate_sockets(bl_node, node_type: str):
    """
    API pubblica per generare socket per un nodo.

    Args:
        bl_node: L'istanza del nodo Blender
        node_type: Il tipo del nodo s3dgraphy

    Example:
        from .socket_generator import generate_sockets

        class EMGraphUSNode(EMGraphStratigraphicNode):
            def init(self, context):
                generate_sockets(self, "US")
                self.use_custom_color = True
                self.color = (0.8, 0.8, 0.8)
    """
    socket_map = get_socket_map()
    type_family_map = get_type_family_map()

    if not socket_map or not type_family_map:
        print(f"⚠️  Socket system not initialized, using fallback for {node_type}")
        return

    generate_sockets_for_node(bl_node, node_type, socket_map, type_family_map)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_node_color_from_datamodel(node_type: str) -> Optional[Tuple[float, float, float]]:
    """
    Ottiene il colore suggerito per un node_type dal datamodel.
    Usa il "symbol" field per determinare il colore.

    Returns:
        RGB tuple (0.0-1.0) or None
    """
    global _NODES_DATAMODEL

    if not _NODES_DATAMODEL:
        return None

    # Mappa simboli → colori
    symbol_colors = {
        'white rectangle': (0.9, 0.9, 0.9),           # US
        'black parallelogram': (0.2, 0.3, 0.5),       # USVs - blu scuro
        'black hexagon': (0.2, 0.5, 0.3),             # USVn - verde scuro
        'white octagon': (0.95, 0.85, 0.3),           # SF - giallo
        'black octagon': (0.7, 0.6, 0.2),             # VSF - giallo ocra
        'white ellipse': (0.85, 0.85, 0.85),          # serSU
        'black ellipse green border': (0.3, 0.6, 0.4), # serUSVn
        'black ellipse blue border': (0.3, 0.4, 0.6),  # serUSVs
        'white round rectangle with orange border': (0.9, 0.7, 0.5), # USD
        'dotted white rectangle with red border': (0.9, 0.6, 0.6),   # TSU
        'black rhombus': (0.3, 0.3, 0.3),             # BR
    }

    # Cerca il node_type nel datamodel
    for category_key, category_data in _NODES_DATAMODEL.items():
        if category_key in ['s3Dgraphy_data_model_version', 'description', 'components']:
            continue

        for node_key, node_data in category_data.items():
            if not isinstance(node_data, dict):
                continue

            # Controlla subtypes
            if 'subtypes' in node_data:
                for subtype_key, subtype_data in node_data['subtypes'].items():
                    if subtype_key == node_type or subtype_data.get('abbreviation') == node_type:
                        symbol = subtype_data.get('symbol', '')
                        return symbol_colors.get(symbol)

    return None


def list_all_edge_types() -> List[str]:
    """
    Ritorna la lista di tutti i tipi di edge disponibili.
    Utile per debugging.
    """
    global _CONNECTIONS_DATAMODEL

    if not _CONNECTIONS_DATAMODEL or 'edge_types' not in _CONNECTIONS_DATAMODEL:
        return []

    return list(_CONNECTIONS_DATAMODEL['edge_types'].keys())


def get_edge_type_info(edge_type: str) -> Optional[Dict]:
    """
    Ritorna le informazioni complete per un edge_type.
    """
    global _CONNECTIONS_DATAMODEL

    if not _CONNECTIONS_DATAMODEL or 'edge_types' not in _CONNECTIONS_DATAMODEL:
        return None

    return _CONNECTIONS_DATAMODEL['edge_types'].get(edge_type)
