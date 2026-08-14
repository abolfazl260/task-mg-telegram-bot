import os

HOST = os.getenv("WEBAPP_HOST", "127.0.0.1")
PORT = int(os.getenv("WEBAPP_PORT", "8081"))


def health_config():
    return {"status": "ok", "host": HOST, "port": PORT}
