"""
API HTTP del servicio (sin autenticacion por ahora, para pruebas).

Endpoints:
    GET  /up          -> sondeo.
    POST /api/sync    -> encola {"person_ids": ["...", ...]}. Responde 202.
    GET  /api/estado  -> pendientes, persona en curso y ultimos resultados.
"""

import logging
import sys

from flask import Flask, jsonify, request

from .sincronizador import Sincronizador

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SYNC] %(levelname)s %(message)s",
    stream=sys.stdout,
)


def create_app(sincronizador=None):
    app = Flask(__name__)
    app.json.ensure_ascii = False
    sincronizador = sincronizador or Sincronizador()

    @app.get("/")
    @app.get("/up")
    def up():
        return jsonify({"ok": True})

    @app.post("/api/sync")
    def sync():
        cuerpo = request.get_json(silent=True) or {}
        person_ids = cuerpo.get("person_ids") or []
        if isinstance(person_ids, (str, int)):
            person_ids = [person_ids]
        sincronizador.encolar(person_ids)
        return jsonify({"encolados": len(person_ids)}), 202

    @app.get("/api/estado")
    def estado():
        return jsonify(sincronizador.estado())

    return app
