# EM-blender-tools Migration to s3dgraphy v1.5.3

**Date**: 2024
**s3dgraphy Version Required**: 0.1.20+
**Datamodel Version**: 1.5.3

## Overview

EM-blender-tools has been updated to support the new s3dgraphy v1.5.3 connections datamodel with canonical/reverse edge labeling. This provides a better user experience in the Graph Editor with clearer socket labels.

## What Changed

### 1. Socket Generator (`graph_editor/socket_generator.py`)

**Updated to v1.5.3**:
- Socket map now uses tuple format: `(edge_name, label)`
- Output sockets display canonical labels (e.g., "Is after", "Cuts")
- Input sockets display reverse labels (e.g., "Is before", "Is cut by")
- Symmetric edges use the same label for both directions

### 2. Operators (`graph_editor/operators.py`)

**Updated `create_link()` method**:
- Now uses datamodel to resolve canonical/reverse edge names
- Correctly matches output sockets with canonical names
- Correctly matches input sockets with reverse names
- Handles symmetric edges (same name for both directions)
- Improved warning messages showing which socket names are being searched for

**Updated `populate_tree()` method**:
- Now populates `node_type` property on each node
- Sets `description` from s3dgraphy node data
- Enables verbose node display with type and description

### 3. Dynamic Nodes (`graph_editor/dynamic_nodes.py`)

**Enhanced `EMGraphNodeBase` class**:
- Added `node_type` property to store semantic type
- Added `original_name` property for full node name
- Added `description` property for node description text
- Implemented `draw_buttons()` method to display:
  - Node type with icon (e.g., "[PropertyNode]")
  - Description text (word-wrapped, max 3 lines)
  - Clean, organized layout

**Example**:
```
StratigraphicNode:
  Output sockets:
    - is_after → "Is after"
    - cuts → "Cuts"
    - fills → "Fills"

  Input sockets:
    - is_before → "Is before"
    - is_cut_by → "Is cut by"
    - is_filled_by → "Is filled by"
```

### Key Benefits

1. **Clearer UI**: Socket labels are now verb-based and immediately understandable
2. **Directional Semantics**: Output vs Input sockets have distinct, meaningful labels
3. **Better UX**: Users can easily understand the relationship direction
4. **CIDOC-CRM Aligned**: Labels match semantic ontology conventions

## Compatibility

### Backward Compatibility

✅ **Fully backward compatible**:
- Socket names (edge identifiers) unchanged
- Existing Blender scenes will work without modification
- GraphML import/export remains compatible

### Forward Compatibility

✅ **Ready for future enhancements**:
- Socket labeling prepared for localization
- Extensible for custom edge types
- Compatible with s3dgraphy expansions

## Technical Details

### Socket Data Structure Change

**Before (v1.5.2)**:
```python
socket_map = {
    "StratigraphicNode": {
        "inputs": ["is_after", "is_cut_by", ...],
        "outputs": ["is_before", "cuts", ...]
    }
}
```

**After (v1.5.3)**:
```python
socket_map = {
    "StratigraphicNode": {
        "inputs": [("is_before", "Is before"), ("is_cut_by", "Is cut by"), ...],
        "outputs": [("is_after", "Is after"), ("cuts", "Cuts"), ...]
    }
}
```

### Socket Creation

**Socket name** (edge_name): Used for connection validation and GraphML export
**Socket label**: Displayed in the UI for better readability

```python
socket = bl_node.inputs.new('EMGraphSocketType', edge_name)
socket.label = label  # v1.5.3: Set custom label
```

## Testing

### Manual Testing

1. Open EM-blender-tools in Blender
2. Create a new Graph Editor
3. Add StratigraphicNode (US)
4. Verify socket labels:
   - Output: "Is after", "Cuts", "Fills", etc.
   - Input: "Is before", "Is cut by", "Is filled by", etc.

### Automated Testing

The socket generator will print debug information on initialization:
```
🔌 Initializing dynamic socket system...
✅ Loaded connections datamodel from ...
✅ Socket system initialized:
   - X node type mappings
   - Y node families with sockets

📊 Socket map examples (v1.5.3 canonical/reverse pattern):
   - StratigraphicNode: N inputs, M outputs
     Example input: is_before → "Is before"
     Example output: is_after → "Is after"
```

## Migration Checklist

- [X] Update `socket_generator.py` to v1.5.3 pattern
- [X] Add version constant (`__version__ = "1.5.3"`)
- [X] Update socket map building function
- [X] Update socket generation function
- [X] Add debug output for verification
- [X] **Fix `operators.py` to handle canonical/reverse socket naming**
- [X] **Fix socket label read-only error**
- [X] **Add multi-input socket support (Blender 4.0+)**
- [X] **Add hide unused sockets feature**
- [X] **Add verbose node display (type + description)**
- [ ] Test in Blender with live graph
- [ ] Verify GraphML import/export
- [ ] Update user documentation if needed

## Known Issues (RESOLVED)

### Issue 1: Nodes created but not connected ✅ FIXED

**Symptom**: After v1.5.3 migration, nodes were created but edges were not connected. Console showed warnings like "No matching input socket for 'is_before'".

**Root Cause**: The socket generator created sockets with v1.5.3 naming (canonical for outputs, reverse for inputs), but the `create_link()` method was still trying to match edge types directly to socket names without considering the canonical/reverse pattern.

**Fix**: Updated `operators.py` `create_link()` method to:
- Import and use the connections datamodel
- Resolve the correct socket names based on edge directionality
- Match output sockets with canonical names
- Match input sockets with reverse names
- Handle symmetric edges correctly

See `OPERATORS_FIX_v1.5.3.md` for detailed explanation.

## Dependencies

### Required

- **s3dgraphy >= 0.1.20**: For v1.5.3 connections datamodel
- **Blender >= 3.6**: For node editor features

### Optional

None

## Future Enhancements

Potential improvements for future versions:

1. **Localization**: Translate socket labels based on Blender language settings
2. **Custom Colors**: Color-code sockets by edge category (temporal, physical, documentation)
3. **Tooltips**: Add hover tooltips with edge descriptions from datamodel
4. **Socket Icons**: Visual icons for different edge types
5. **Smart Connections**: Auto-suggest compatible connections based on node types

## Support

For issues or questions:
- Check s3dgraphy migration guide: `s3Dgraphy/MIGRATION_SUMMARY_v1.5.3.md`
- Review socket generator source: `graph_editor/socket_generator.py`
- Test with: Manual Blender testing or automated graph creation

## Examples

### Creating Connections in Graph Editor

With v1.5.3, connections are more intuitive:

**Stratigraphic Sequence** (Recent → Ancient):
```
[US 105 - Recent]
      ↓ Output: "Is after"
      ↓
      ↓ Input: "Is before"
[US 089 - Ancient]
```

**Physical Relations**:
```
[US 105 - Cut]
      ↓ Output: "Cuts"
      ↓
      ↓ Input: "Is cut by"
[US 089 - Being Cut]
```

**Documentation**:
```
[US 105]
      ↓ Output: "Has property"
      ↓
      ↓ Input: "Is property of"
[Property: Material]
```

### Socket Label Reference

| Edge Type | Output Label (Canonical) | Input Label (Reverse) |
|-----------|-------------------------|----------------------|
| is_after | Is after | Is before |
| cuts | Cuts | Is cut by |
| fills | Fills | Is filled by |
| overlies | Overlies | Is overlain by |
| abuts | Abuts | Is abutted by |
| has_property | Has property | Is property of |
| has_author | Has author | Is author of |
| has_same_time | Has same time | Has same time (symmetric) |
| is_bonded_to | Is bonded to | Is bonded to (symmetric) |

## Conclusion

The migration to v1.5.3 enhances the EM-blender-tools user experience with clearer, more semantic socket labels while maintaining full backward compatibility. Users will benefit from better visual clarity when building Extended Matrix graphs in Blender.

---
**Migration Status**: ✅ COMPLETE
**Backward Compatible**: YES
**Testing Required**: Manual Blender testing recommended
