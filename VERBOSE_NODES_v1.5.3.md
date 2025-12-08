# Verbose Node Display - v1.5.3

**Date**: December 2024
**Feature**: Enhanced node visualization with type and description

## Overview

Nodes in the EMGraph editor now display more information to help users understand the graph structure at a glance:

1. **Node Type** - Shows the semantic type (e.g., "[PropertyNode]", "[US]", "[Document]")
2. **Description** - Displays the node's description from the s3dgraphy datamodel (if available)

## Visual Layout

Each node now shows:

```
┌─────────────────────────┐
│ Node Name (label)       │ ← Title bar
├─────────────────────────┤
│ [NodeType] 🔸          │ ← Type with icon
├─────────────────────────┤
│ ╔═══════════════════╗  │
│ ║ Description text  ║  │ ← Description box
│ ║ wrapped to ~30    ║  │   (max 3 lines)
│ ║ characters/line   ║  │
│ ╚═══════════════════╝  │
├─────────────────────────┤
│ ○ input_socket_1        │ ← Sockets
│ ○ input_socket_2        │
│                         │
│        output_socket ○  │
└─────────────────────────┘
```

## Implementation

### 1. Base Node Class (`dynamic_nodes.py`)

Added new properties to `EMGraphNodeBase`:

```python
class EMGraphNodeBase(Node):
    node_id: bpy.props.StringProperty(name="Node ID")
    node_type: bpy.props.StringProperty(name="Node Type")  # NEW
    original_name: bpy.props.StringProperty(name="Original Name")  # NEW
    description: bpy.props.StringProperty(name="Description")  # NEW
```

### 2. Draw Method (`draw_buttons()`)

Added a custom draw method to display node information:

```python
def draw_buttons(self, context, layout):
    # Node type with icon
    row = layout.row(align=True)
    row.scale_y = 0.7
    row.label(text=f"[{self.bl_label}]", icon=self.bl_icon)

    # Description (wrapped, max 3 lines)
    if self.description:
        box = layout.box()
        col = box.column(align=True)
        col.scale_y = 0.8
        # ... word wrapping logic ...
        for line in lines[:3]:
            col.label(text=line)
```

### 3. Population (`operators.py`)

Updated node creation to populate the new properties:

```python
bl_node = tree.nodes.new(node_type_id)
bl_node.node_id = s3d_node.node_id
bl_node.node_type = s3d_node.node_type  # NEW
bl_node.original_name = s3d_node.name    # NEW
bl_node.label = s3d_node.name

# Set description if available
if hasattr(s3d_node, 'description') and s3d_node.description:
    bl_node.description = s3d_node.description  # NEW
```

## Features

### Node Type Display

- **Format**: `[NodeType]` with icon
- **Examples**:
  - `[PropertyNode]` 🔸
  - `[US]` 🟦
  - `[DocumentNode]` 📄
  - `[EpochNode]` ⏰

### Description Display

- **Word wrapping**: Automatically wraps long descriptions (~30 chars/line)
- **Line limit**: Shows max 3 lines + "..." if longer
- **Styled box**: Description appears in a subtle box for visual separation
- **Compact**: Uses smaller font (scale_y = 0.8) to save space

### Smart Layout

- Type label uses `scale_y = 0.7` (more compact)
- Description box auto-sizes based on content
- Empty descriptions don't create empty boxes

## Examples

### Property Node Example

```
┌─────────────────────────┐
│ material                │
├─────────────────────────┤
│ [PropertyNode] 🔸      │
├─────────────────────────┤
│ ╔═══════════════════╗  │
│ ║ Material of the   ║  │
│ ║ stratigraphic     ║  │
│ ║ unit              ║  │
│ ╚═══════════════════╝  │
├─────────────────────────┤
│ ○ is_property_of        │
│                         │
│      has_property ○     │
└─────────────────────────┘
```

### US Node Example

```
┌─────────────────────────┐
│ B41                     │
├─────────────────────────┤
│ [US (or SU)] 🟦        │
├─────────────────────────┤
│ ╔═══════════════════╗  │
│ ║ Stratigraphic     ║  │
│ ║ unit from trench  ║  │
│ ║ B, level 41       ║  │
│ ╚═══════════════════╝  │
├─────────────────────────┤
│ ○ is_before             │
│ ○ is_cut_by             │
│ ○ is_filled_by          │
│                         │
│         is_after ○      │
│            cuts ○       │
│           fills ○       │
└─────────────────────────┘
```

### Document Node (No Description)

```
┌─────────────────────────┐
│ DOC.151.151.001         │
├─────────────────────────┤
│ [DocumentNode] 📄       │
├─────────────────────────┤
│ ○ is_source_for_...     │
│                         │
│    extracted_from ○     │
└─────────────────────────┘
```

## Benefits

✅ **Immediate Context** - Users can see node type at a glance
✅ **Better Understanding** - Descriptions explain what each node represents
✅ **Reduced Confusion** - Clear distinction between node name and type
✅ **Professional Look** - Clean, organized node layout
✅ **Archaeological Context** - Descriptions provide excavation/interpretation context

## Performance

- **Minimal Impact**: Drawing is done by Blender's UI system
- **No Extra Queries**: Data is loaded once when graph is drawn
- **Efficient**: Only shows when node is visible in editor

## User Experience

### Before (v1.5.2 and earlier)

Nodes showed only:
- Node name in title bar
- Sockets

Users had to:
- Remember what each node type means
- Look up descriptions elsewhere
- Infer context from connections

### After (v1.5.3)

Nodes show:
- Node name (title)
- Type with icon
- Description (if available)
- Sockets

Users can:
- Instantly identify node types
- Read descriptions in-place
- Understand context immediately

## Customization

The display can be customized by editing `draw_buttons()`:

- **Font size**: Adjust `scale_y` values
- **Line length**: Change max chars per line (default: 30)
- **Max lines**: Change `lines[:3]` to show more/fewer lines
- **Box style**: Modify `layout.box()` properties
- **Icon display**: Change or remove icon in type label

## Future Enhancements

Potential improvements:
- **Collapsible descriptions** - Click to expand/collapse
- **Tooltips** - Hover to see full description
- **Custom colors** - Type-based text colors
- **Attributes display** - Show key attributes in node body
- **Mini preview** - Thumbnail for image/model nodes

---

**Status**: ✅ IMPLEMENTED
**Files Modified**:
- `graph_editor/dynamic_nodes.py` (lines 18-68)
- `graph_editor/operators.py` (lines 403-411)

**Ready for Testing**: YES
