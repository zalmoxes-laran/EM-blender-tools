# bl_info.py
bl_info = {
    "name": "EM tools",
    "description": "Blender tools for Extended Matrix",
    "author": "E. Demetrescu",
    "version": (1, 5, 0),  # This is fine as a tuple
    "blender": (4, 0, 0),  # Make sure this matches the minimum Blender version you support
    "devel_version": "v1.5.0 dev12",  # This is already a string, which is good
    "location": "3D View > Toolbox",
    "warning": "This addon is in dev12 stage.",
    "wiki_url": "",
    "category": "Tools",
}

def get_bl_info():
    return bl_info