"""Punto de entrada WSGI: gunicorn wsgi:app"""

from sync_service.web import create_app

app = create_app()

if __name__ == "__main__":
    # Solo para desarrollo local; en Laravel Cloud se usa gunicorn.
    app.run(host="127.0.0.1", port=5050, debug=True)
