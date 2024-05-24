import bpy
import socket
import threading
from bpy.props import BoolProperty
from bpy.types import Panel

# Variabile globale per conservare il thread del server
server_thread = None

class EM_ServerPanel:
    bl_label = "EM Server"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        row = layout.row(align=True)
        split = row.split()

        col = split.column()
        op = row.operator("start.server", text="Start", emboss=True, icon='KEYTYPE_JITTER_VEC')
        col = split.column()
        op = row.operator("stop.server", text="Stop", emboss=True, icon='HANDLETYPE_FREE_VEC')
        col = split.column()

        if scene.EM_server_status:
            col.label(text="Status", icon='KEYTYPE_JITTER_VEC')
        else:
            col.label(text="Status", icon='HANDLETYPE_FREE_VEC')


class VIEW3D_PT_ServerPanel(Panel, EM_ServerPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ServerPanel"
    bl_context = "objectmode"


class TCPServerThread(threading.Thread):
    def __init__(self, host='localhost', port=9999):
        super().__init__()
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.running = True

    def run(self):
        print("Server TCP in esecuzione su {}:{}".format(self.host, self.port))
        while self.running:
            client, address = self.sock.accept()
            print("Connessione da", address)
            data = client.recv(1024).decode('utf-8')
            if data:
                print("Ricevuto:", data)
                # Esegui un'azione in Blender
                self.execute_command(data)
                client.sendall("Comando ricevuto".encode('utf-8'))
            client.close()

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

        if server_thread is None or not server_thread.is_alive():
            server_thread = TCPServerThread()
            server_thread.start()
            scene.EM_server_status = True
            self.report({'INFO'}, "Server started")
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


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.EM_server_status
