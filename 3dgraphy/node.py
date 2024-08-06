# 3dgraphy/node.py

class Node:

    def __init__(self, id, name, description, shape, y_pos, fill_color):
        self.id = id
        self.name = name
        self.description = description
        self.shape = shape
        self.y_pos = y_pos
        self.fill_color = fill_color
        self.has_continuity = False
        # Aggiungi altre proprietà utili per un nodo 3D, come coordinate o riferimenti a oggetti 3D in Blender

