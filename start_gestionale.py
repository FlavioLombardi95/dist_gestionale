import webbrowser
import threading
import time
import app

def run_flask():
    app.app.run(debug=False, use_reloader=False)

t = threading.Thread(target=run_flask)
t.daemon = True
t.start()
time.sleep(2)
webbrowser.open('http://localhost:5000')

# Mantieni il processo attivo
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass 