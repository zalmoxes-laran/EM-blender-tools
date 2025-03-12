import bpy
import socket
import threading
from bpy.props import BoolProperty, StringProperty, IntProperty
from bpy.types import Panel

# Variabile globale per conservare il thread del server
server_thread = None

class EM_ServerPanel:
    bl_label = "EM Server"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        # Restituisce True se mode_switch è False, quindi il pannello viene mostrato solo in modalità 3D GIS
        return em_tools.mode_switch
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene

        row = layout.row()
        if scene.EM_server_status:
            row.label(text="Status: ON", icon='KEYTYPE_JITTER_VEC')
        else:
            row.label(text="Status: OFF", icon='HANDLETYPE_FREE_VEC')

        row = layout.row()
        layout.prop(scene, "server_host", text="Host")
        layout.prop(scene, "server_port", text="Port")

        row = layout.row(align=True)
        split = row.split()

        col = split.column()
        op = col.operator("start.server", text="Start", emboss=True, icon='KEYTYPE_JITTER_VEC')
        col = split.column()
        op = col.operator("stop.server", text="Stop", emboss=True, icon='HANDLETYPE_FREE_VEC')
        #col = split.column()




class VIEW3D_PT_ServerPanel(Panel, EM_ServerPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ServerPanel"
    bl_context = "objectmode"


class TCPServerThread(threading.Thread):
    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(1.0)  # Timeout di 1 secondo
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.running = True

    def run(self):
        print("Server TCP in esecuzione su {}:{}".format(self.host, self.port))
        while self.running:
            try:
                client, address = self.sock.accept()
                print("Connessione da", address)
                data = client.recv(1024).decode('utf-8')
                if data:
                    print("Ricevuto:", data)
                    # Esegui un'azione in Blender
                    self.execute_command(data)
                    client.sendall("Comando ricevuto".encode('utf-8'))
                client.close()
            except socket.timeout:
                continue  # Ritorna al loop se il timeout scade
            except ConnectionAbortedError:
                break  # Uscire dal loop se la connessione è stata abortita

    def execute_command(self, command):
        if command == "run_function":
            bpy.ops.object.select_all(action='SELECT')
            print("comando arrivato da EM-manager")

    def stop(self):
        self.running = False
        self.sock.close()


class EM_server_start(bpy.types.Operator):
    bl_idname = "start.server"
    bl_label = "Start server for EM output connections"
    bl_description = "This server is able to send and receive commands"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        global server_thread
        scene = context.scene

        host = scene.server_host
        port = scene.server_port

        if server_thread is None or not server_thread.is_alive():
            server_thread = TCPServerThread(host=host, port=port)
            server_thread.start()
            scene.EM_server_status = True
            self.report({'INFO'}, f"Server started at {host}:{port}")
        else:
            self.report({'INFO'}, "Server is already running")
        return {'FINISHED'}


class EM_server_stop(bpy.types.Operator):
    bl_idname = "stop.server"
    bl_label = "Stop server for EM output connections"
    bl_description = "This server is able to send and receive commands"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        global server_thread
        scene = context.scene

        if server_thread is not None and server_thread.is_alive():
            server_thread.stop()
            server_thread.join()
            server_thread = None
            scene.EM_server_status = False
            self.report({'INFO'}, "Server stopped")
        else:
            self.report({'INFO'}, "Server is not running")
        return {'FINISHED'}


classes = [
    VIEW3D_PT_ServerPanel,
    EM_server_start,
    EM_server_stop
]


# Registration
def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.EM_server_status = BoolProperty(name="Server status", description="This indicates if the server is on or off", default=False)
    bpy.types.Scene.server_host = StringProperty(name="Server Host", description="The host address for the server", default="localhost")
    bpy.types.Scene.server_port = IntProperty(name="Server Port", description="The port number for the server", default=9001)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.EM_server_status
    del bpy.types.Scene.server_host
    del bpy.types.Scene.server_port
