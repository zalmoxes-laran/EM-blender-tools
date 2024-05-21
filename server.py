import bpy
import socket
import threading

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
            # Esegui la funzione che desideri in Blender

    def stop(self):
        self.running = False
        self.sock.close()

# Avvio del server
server_thread = TCPServerThread()
server_thread.start()

# Per fermare il server, puoi chiamare:
# server_thread.stop()
