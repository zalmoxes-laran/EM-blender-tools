# Hide Unused Sockets Feature

**Date**: December 2024
**Feature**: Automatic hiding of unconnected sockets for cleaner graph visualization

## Overview

After drawing a graph, all sockets that don't have connections are automatically hidden. This makes the graph much cleaner and easier to read, showing only the relevant connections for the current view.

## Benefits

✅ **Cleaner Visualization** - Only connected sockets are visible
✅ **Better Focus** - Users can see actual connections without clutter
✅ **Professional Look** - Graph appears organized and intentional
✅ **Context-Aware** - Different filter modes show different sockets
✅ **Performance** - Minimal overhead, runs once after graph creation

## Implementation

### Location
`graph_editor/operators.py` - `GRAPHEDIT_OT_draw_graph` class

### Method: `hide_unused_sockets()`

```python
def hide_unused_sockets(self, node_map):
    """
    Nasconde i socket che non hanno connessioni.
    Questo rende il grafo più pulito e leggibile.
    """
    for node_id, bl_node in node_map.items():
        # Hide unused input sockets
        for input_socket in bl_node.inputs:
            if not input_socket.is_linked:
                input_socket.hide = True
            else:
                input_socket.hide = False

        # Hide unused output sockets
        for output_socket in bl_node.outputs:
            if not output_socket.is_linked:
                output_socket.hide = True
            else:
                output_socket.hide = False
```

### Execution Flow

```
1. Load graph nodes
2. Create connections between nodes
3. ✨ Hide unused sockets (NEW)
4. Calculate hierarchical layout
5. Apply layout to nodes
6. Display graph
```

## Behavior

### Before Hiding

```
┌─────────────────────────┐
│ material                │
├─────────────────────────┤
│ [PropertyNode]          │
├─────────────────────────┤
│ ○ is_property_of        │ ← Used
│ ○ generic_connection    │ ← Unused
│ ○ has_same_material     │ ← Unused
│                         │
│      has_property ○     │ ← Used
│  generic_connection ○   │ ← Unused
│   similar_material ○    │ ← Unused
└─────────────────────────┘
```

### After Hiding

```
┌─────────────────────────┐
│ material                │
├─────────────────────────┤
│ [PropertyNode]          │
├─────────────────────────┤
│ ○ is_property_of        │ ← Only used socket
│                         │
│      has_property ○     │ ← Only used socket
└─────────────────────────┘
```

## Use Cases

### 1. Filter Mode: "Stratigraphic Only"

When viewing only stratigraphic relationships:
- Shows: `is_before`, `is_after`, `cuts`, `is_cut_by`, etc.
- Hides: All paradata sockets, model sockets, etc.

### 2. Filter Mode: "Node + Context"

When viewing a specific node with its context:
- Shows: Only sockets with actual connections in this view
- Hides: All other potential sockets

### 3. Filter Mode: "By Edge Types"

When filtering by specific edge types:
- Shows: Only the selected edge type sockets
- Hides: All other edge types

## Technical Details

### Socket State

Blender sockets have a `.hide` property:
- `socket.hide = True` - Socket is hidden (not visible in UI)
- `socket.hide = False` - Socket is visible
- `socket.is_linked` - Boolean indicating if socket has connections

### Performance

- **Complexity**: O(n×s) where n = nodes, s = average sockets per node
- **Timing**: Runs once after graph creation (~1-10ms for typical graphs)
- **Memory**: No additional memory overhead

### Integration

Called automatically in `populate_tree()`:

```python
# Create edges
edge_count = self.create_links(...)

# Hide unused sockets (automatic)
self.hide_unused_sockets(node_map)

# Apply layout
self.apply_layout(...)
```

## Future Enhancements

Potential improvements:

1. **Toggle Button** - Allow users to show/hide unused sockets manually
2. **Keyboard Shortcut** - Quick toggle (e.g., 'H' key)
3. **Preferences** - User setting to enable/disable auto-hiding
4. **Socket Groups** - Hide/show sockets by category (stratigraphic, paradata, etc.)
5. **Smart Hiding** - Hide only if node has >X sockets total

## Debugging

If sockets should be visible but aren't:

1. **Check `is_linked` state**:
   ```python
   for socket in node.inputs:
       print(f"{socket.name}: linked={socket.is_linked}, hidden={socket.hide}")
   ```

2. **Verify connections exist**:
   ```python
   print(f"Links: {len(tree.links)}")
   for link in tree.links:
       print(f"  {link.from_socket.name} → {link.to_socket.name}")
   ```

3. **Manually unhide all**:
   ```python
   for node in tree.nodes:
       for socket in node.inputs + node.outputs:
           socket.hide = False
   ```

## Console Output

When enabled, you'll see:

```
✅ Created 129 nodes

🔗 Creating edges...
✅ Created 45 edges

🔌 Hiding unused sockets...
✅ Unused sockets hidden

📐 Calculating hierarchical layout...
✅ Layout applied
```

---

**Status**: ✅ IMPLEMENTED
**Default**: ENABLED (automatic)
**Files Modified**: `graph_editor/operators.py` (lines 445-478)
