# color_ramps.py

"""
Predefined color ramps for the EM tools visual manager.
Colors are in RGB format (0-1 range) for direct use in Blender materials.
"""

COLOR_RAMPS = {
    "sequential": {
        "viridis": {
            "name": "Viridis",
            "description": "A perceptually uniform colormap (matplotlib's default)",
            "colors": [
                (0.267004, 0.004874, 0.329415),  # #440154 dark purple
                (0.253935, 0.265254, 0.529983),  # #3B518B blue
                (0.163625, 0.471133, 0.558148),  # #2A788E light blue
                (0.134692, 0.658636, 0.517649),  # #22A884 turquoise
                (0.477504, 0.821444, 0.318195),  # #7AD151 green
                (0.993248, 0.906157, 0.143936)   # #FDE725 yellow
            ]
        },
        "blues": {
            "name": "Blues",
            "description": "Classic blue sequential scale",
            "colors": [
                (0.031372, 0.188235, 0.419608),  # #083056 dark blue
                (0.031372, 0.317647, 0.607843),  # #08519C medium blue
                (0.129412, 0.443137, 0.709804),  # #2171B5 light blue
                (0.262745, 0.576471, 0.764706),  # #4393C3 lighter blue
                (0.572549, 0.772549, 0.870588),  # #92C5DE very light blue
                (0.819608, 0.898039, 0.941176)   # #D1E5F0 palest blue
            ]
        },
        "heat": {
            "name": "Heat",
            "description": "Traditional heat map colors",
            "colors": [
                (0.019608, 0.188235, 0.380392),  # #053061 dark blue
                (0.088235, 0.403922, 0.537255),  # #165C89 medium blue
                (0.454902, 0.678431, 0.819608),  # #74ADD1 light blue
                (0.956863, 0.647059, 0.509804),  # #F4A582 light orange
                (0.839216, 0.376471, 0.301961),  # #D6604D dark orange
                (0.698039, 0.094118, 0.168627)   # #B2182B dark red
            ]
        }
    },
    "diverging": {
        "red_blue": {
            "name": "Red-Blue",
            "description": "Classic diverging scale for positive/negative values",
            "colors": [
                (0.403922, 0.000000, 0.121569),  # #67001F darkest red
                (0.839216, 0.376471, 0.301961),  # #D6604D light red
                (0.992157, 0.858824, 0.780392),  # #FDDBC7 pale red
                (0.968627, 0.968627, 0.968627),  # #F7F7F7 white
                (0.819608, 0.898039, 0.941176),  # #D1E5F0 pale blue
                (0.262745, 0.576471, 0.764706),  # #4393C3 light blue
                (0.019608, 0.188235, 0.380392)   # #053061 darkest blue
            ]
        },
        "brown_teal": {
            "name": "Brown-Teal",
            "description": "Earthy diverging scale",
            "colors": [
                (0.329412, 0.188235, 0.019608),  # #543005 dark brown
                (0.768627, 0.505882, 0.176471),  # #C48113 light brown
                (0.964706, 0.909804, 0.764706),  # #F6E8C3 pale brown
                (0.960784, 0.960784, 0.960784),  # #F5F5F5 white
                (0.780392, 0.917647, 0.898039),  # #C7EAE5 pale teal
                (0.211765, 0.592157, 0.560784),  # #36978F light teal
                (0.003922, 0.235294, 0.188235)   # #013C30 dark teal
            ]
        }
    },
    "qualitative": {
        "set1": {
            "name": "Set 1",
            "description": "Distinct colors for categorical data",
            "colors": [
                (0.894118, 0.101961, 0.109804),  # #E41A1C red
                (0.215686, 0.494118, 0.721569),  # #377EB8 blue
                (0.301961, 0.686275, 0.290196),  # #4DAF4A green
                (0.596078, 0.305882, 0.639216),  # #984EA3 purple
                (1.000000, 0.498039, 0.000000),  # #FF7F00 orange
                (1.000000, 1.000000, 0.200000),  # #FFFF33 yellow
                (0.650000, 0.337255, 0.156863)   # #A65628 brown
            ]
        },
        "pastel": {
            "name": "Pastel",
            "description": "Soft pastel colors for categorical data",
            "colors": [
                (0.984314, 0.705882, 0.682353),  # #FCB4AE light red
                (0.701961, 0.803922, 0.890196),  # #B3CDE3 light blue
                (0.800000, 0.921569, 0.772549),  # #CCEBC5 light green
                (0.870588, 0.796078, 0.894118),  # #DECBE4 light purple
                (0.996078, 0.850980, 0.650980),  # #FED9A6 light orange
                (1.000000, 1.000000, 0.800000)   # #FFFFCC light yellow
            ]
        }
    }
}