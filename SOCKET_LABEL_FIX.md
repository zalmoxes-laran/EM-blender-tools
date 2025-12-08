# Socket Label Fix - v1.5.3

**Date**: December 2024
**Issue**: `AttributeError: bpy_struct: attribute "label" from "EMGraphSocketType" is read-only`

## Problem

After the v1.5.3 migration, the `socket_generator.py` was trying to set a `label` property on EMGraphSocketType sockets:

```python
socket.label = label if label else edge_name
```

However, in Blender's node system, socket labels are **read-only** and determined by the socket's **name** (not a separate label property).

### Symptoms

- **Error**: `AttributeError: bpy_struct: attribute "label" from "EMGraphSocketType" is read-only`
- **Only one socket created** per node (loop stopped at first error)
- **Nodes created but not connected**
- Multiple traceback errors in console

## Root Cause

In Blender, the socket "label" displayed in the UI is the **socket's name**, set when calling:

```python
socket = bl_node.inputs.new('EMGraphSocketType', socket_name)
```

The `socket_name` parameter becomes both the identifier AND the display label. There is no separate `label` property that can be set afterward.

## Solution

Updated `socket_generator.py` (lines 424-440) to:

1. **Remove attempt to set `socket.label`**
2. **Use `edge_name` as the socket name** (for correct matching in operators.py)
3. **Store `edge_name` in `socket.edge_type`** property for future reference

### Code Change

**Before (BROKEN)**:
```python
socket = bl_node.inputs.new('EMGraphSocketType', edge_name)
socket.label = label if label else edge_name  # ❌ ERROR!
```

**After (FIXED)**:
```python
socket = bl_node.inputs.new('EMGraphSocketType', edge_name)
socket.edge_type = edge_name  # ✅ Save edge_name for reference
```

## Impact

✅ **Sockets now create successfully** without errors
✅ **All sockets are created** (not just the first one)
✅ **Socket names match edge types** for correct connection matching in operators.py
✅ **`edge_type` property** available for future use (e.g., validation, color-coding)

## Note on Semantic Labels

The original goal of v1.5.3 was to show **semantic labels** like "Is before", "Cuts", etc. in the node editor.

However, due to Blender's socket architecture:
- Socket names MUST be the **edge_name** (for matching in operators.py)
- We cannot have a separate display label

To show semantic labels in the future, we would need to:
1. **Custom socket draw method** - override `draw()` to show custom text
2. **Node tooltip system** - show semantic labels as tooltips
3. **Alternative UI** - use a custom panel to show edge info

For now, users will see **edge names** (e.g., "is_before", "cuts") which are still clear and match the datamodel exactly.

## Testing

After this fix:

1. ✅ No more `AttributeError` messages
2. ✅ All sockets created on each node
3. ✅ Socket matching works correctly (canonical/reverse)
4. ✅ Connections created successfully

---

**Status**: ✅ FIXED
**Related Files**:
- `graph_editor/socket_generator.py` (lines 424-440)
- `graph_editor/operators.py` (canonical/reverse matching)
- `graph_editor/data.py` (EMGraphSocket definition)
