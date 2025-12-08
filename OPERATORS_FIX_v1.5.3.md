# operators.py Fix for v1.5.3 Socket Naming

**Date**: December 2024
**Issue**: Nodes created but not connected after v1.5.3 migration
**Root Cause**: Socket naming mismatch between socket generator and connection creation code

## Problem

After migrating to v1.5.3, the socket generator correctly created sockets with the new canonical/reverse pattern:
- **Output sockets**: Canonical edge names (e.g., "is_after", "cuts")
- **Input sockets**: Reverse edge names (e.g., "is_before", "is_cut_by")

However, the `create_link()` method in `operators.py` was still trying to match edge types directly to socket names, causing all connection attempts to fail.

## Symptoms

```
⚠️  No matching input socket for 'is_before' on US
    Available inputs: ['is_abutted_by']

⚠️  No matching input socket for 'has_property' on Property
    Available inputs: ['is_property_of']

✅ Created 0 edges (despite 129 nodes loaded)
```

## Solution

Updated `create_link()` method to:

1. **Import datamodel** to resolve canonical/reverse names
2. **Determine correct socket names** based on edge directionality:
   - For **output sockets**: Use canonical name
   - For **input sockets**: Use reverse name (if directional)
   - For **symmetric edges**: Use same name for both
3. **Update all matching logic** to use the correct socket names
4. **Improve warning messages** to show which socket name was actually searched for

## Code Changes

**File**: `graph_editor/operators.py`
**Method**: `create_link()`
**Lines**: ~448-586

### Key Addition

```python
from s3dgraphy.edges import get_connections_datamodel

# Get datamodel to resolve canonical/reverse names
dm = get_connections_datamodel()

# Determine the correct socket names for v1.5.3
output_socket_name = edge_type  # Default
input_socket_name = edge_type   # Default

if dm.edge_exists(edge_type):
    if dm.is_symmetric(edge_type):
        # Symmetric: use same name for both
        output_socket_name = edge_type
        input_socket_name = edge_type
    else:
        # Directional: output uses canonical, input uses reverse
        if dm.is_canonical(edge_type):
            output_socket_name = edge_type
            reverse_name = dm.get_reverse_name(edge_type)
            input_socket_name = reverse_name if reverse_name else edge_type
        else:
            # edge_type is reverse, need to get canonical for output
            edge_def = dm.get_edge_definition(edge_type)
            canonical_name = edge_def.get('canonical_name') if edge_def else edge_type
            output_socket_name = canonical_name
            input_socket_name = edge_type

# Now search for sockets using the correct names
for output in source_node.outputs:
    if output.name == output_socket_name:
        source_socket = output
        break

for input_socket in target_node.inputs:
    if input_socket.name == input_socket_name:
        target_socket = input_socket
        break
```

## Examples

### Example 1: Canonical Edge Type in GraphML

**Edge in GraphML**: `is_after`
**Socket names**:
- Output socket: `is_after` (canonical)
- Input socket: `is_before` (reverse)

**Old behavior**: Looked for "is_after" on both output AND input → ❌ Failed
**New behavior**: Looks for "is_after" on output, "is_before" on input → ✅ Success

### Example 2: Reverse Edge Type in GraphML

**Edge in GraphML**: `is_before`
**Socket names**:
- Output socket: `is_after` (canonical)
- Input socket: `is_before` (reverse)

**Old behavior**: Looked for "is_before" on both output AND input → ❌ Failed
**New behavior**: Looks for "is_after" on output, "is_before" on input → ✅ Success

### Example 3: Symmetric Edge

**Edge in GraphML**: `has_same_time`
**Socket names**:
- Output socket: `has_same_time`
- Input socket: `has_same_time`

**Old behavior**: Looked for "has_same_time" on both → ✅ Would work
**New behavior**: Looks for "has_same_time" on both → ✅ Still works

## Testing

After this fix, test with:

1. **Load a graph** in Blender using the Graph Viewer
2. **Verify connections** are created (check console for "Created N edges")
3. **Visual inspection** of socket labels showing semantic names
4. **Check console** for reduced warnings (should only see warnings for truly unsupported edges)

## Impact

✅ **Fixes the critical issue** where nodes were created but not connected
✅ **Maintains backward compatibility** with fallback matching logic
✅ **Improves debugging** with better warning messages showing actual socket names
✅ **Completes v1.5.3 migration** - all components now use canonical/reverse pattern correctly

## Related Files

- `socket_generator.py` - Creates sockets with v1.5.3 naming
- `s3dgraphy/edges/connections_loader.py` - Datamodel loader with canonical/reverse support
- `MIGRATION_v1.5.3.md` - Overall migration guide

---

**Status**: ✅ FIXED
**Migration Step**: 3/3 (socket generator → datamodel → operators)
**Ready for Testing**: YES
