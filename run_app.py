import subprocess
import webbrowser
import time

# Démarrer le serveur Flask
subprocess.Popen(["python", "server.py"], shell=True)

# Attendre que le serveur soit prêt
time.sleep(2)

# Ouvrir le navigateur
webbrowser.open("http://127.0.0.1:5001")
