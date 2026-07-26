import threading
import sys
import os

# Ensure UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

def run_flask():
    from app import app
    port = int(os.getenv("PORT", 8080))
    app.run(debug=False, port=port, host='0.0.0.0', threaded=True)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    import main
