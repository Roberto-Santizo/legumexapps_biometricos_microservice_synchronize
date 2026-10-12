# zkbio-sync

Microservicio que hace **una sola cosa**: disparar la sincronización de personas con los dispositivos biométricos de ZKBio CVAccess, visitando `accPerson.do?edit&personId=<id>` con una sesión autenticada (el "truco" de `trigger_device_sync` en APPS-BIO).

Sin base de datos y **sin autenticación** (modo pruebas). La cola vive en memoria: lo pendiente se pierde si el proceso se reinicia.

## API

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/sync` | Encola `{"person_ids": ["<pers_person.id>", ...]}` y responde **202** `{"encolados": n}` |
| GET | `/api/estado` | Pendientes, persona en curso, último error y últimos resultados (`ok`/`error`) |
| GET | `/up` | Sondeo |

```bash
curl -X POST https://<app>.laravel.cloud/api/sync -H "Content-Type: application/json" -d '{"person_ids":["402881e4..."]}'
```

`person_ids` es el id interno de ZKBio (`pers_person.id`), no el PIN. Cada persona se procesa de a una, con hasta 3 intentos (esperas de 5 s y 15 s).

## Desarrollo local

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
copy .env.example .env          # rellenar
.venv\Scripts\python wsgi.py    # http://127.0.0.1:5050
.venv\Scripts\python -m pytest
```

## Despliegue en Laravel Cloud

1. Esta carpeta debe ser un **repo propio**, con `requirements.txt` en la raíz. `.python-version` fija Python 3.12.
2. Crear la app desde el repo, en la región más cercana a la planta (`us-east-1` o `us-east-2`).
3. Variables de entorno: `ZKBIO_URL`, `ZKBIO_API_USER`, `ZKBIO_API_PASSWORD_HASH` y `ZKBIO_BROWSER_TOKEN`.
4. Comando de inicio:
   ```
   gunicorn wsgi:app --bind [::]:$PORT --workers 1 --threads 4
   ```
   El `--workers 1` es obligatorio: cada proceso tendría su propia cola y su propia sesión ZKBio. Por lo mismo, deja el App cluster en **1 réplica**.
5. Desactivar Scale-to-Zero: si el entorno hiberna, se pierde lo que estaba en la cola.
6. Firewall de ZKBio: debe aceptar las IPs de salida de la región (https://laravel.com/cloud/docs/network, o `curl https://cloud.laravel.com/api/ip`).

En APPS-BIO, agregar `ZKBIO_SYNC_URL=https://<app>.laravel.cloud` al `.env`. Si el servicio no responde, APPS-BIO sincroniza directo como antes.
