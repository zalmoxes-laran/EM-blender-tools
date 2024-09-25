# S3Dgraphy/utils.py

def convert_shape2type(yedtype, border_style): 
    # Restituisce una coppia di informazioni: codice breve e descrizione estesa
    if yedtype == "rectangle":
        nodetype = ["US", "Stratigraphic Unit"]
    elif yedtype == "parallelogram":
        nodetype = ["USVs", "Structural Virtual Stratigraphic Units"]
    elif yedtype == "ellipse" and border_style == "#31792D":
        nodetype = ["serUSVn", "Series of USVn"]
    elif yedtype == "ellipse" and border_style == "#248FE7":        
        nodetype = ["serUSVs", "Series of USVs"]         
    elif yedtype == "ellipse" and border_style == "#9B3333":
        nodetype = ["serSU", "Series of US"]        
    elif yedtype == "hexagon":
        nodetype = ["USVn", "Non-Structural Virtual Stratigraphic Units"]
    elif yedtype == "octagon" and border_style == "#D8BD30":
        nodetype = ["SF", "Special Find"]
    elif yedtype == "octagon" and border_style == "#B19F61":
        nodetype = ["VSF", "Virtual Special Find"]
    elif yedtype == "roundrectangle":
        nodetype = ["USD", "Documentary Stratigraphic Unit"]
    else:
        print(f"Non riconosciuto: yedtype='{yedtype}', border_style='{border_style}'")
        nodetype = ["unknown", "Unrecognized node"]
    return nodetype
