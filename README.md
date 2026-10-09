# Ancares Seguidores 🏐

PWA **no oficial** para que las familias del CDF Voleibol Ancares sigan la clasificación, el calendario y los resultados de cada categoría. Los datos salen de los Excel que publica la Federación de Voleibol de Castilla y León (fvcl.es).

- **Frontend:** Svelte 5 + Vite + vite-plugin-pwa (unos 40 KB gzip). Es instalable, funciona sin conexión, tiene splash animado y tema claro y oscuro.
- **Backend:** FastAPI + SQLite + APScheduler. Sincroniza los Excel cada día.
- **Despliegue:** Docker Compose + Caddy (HTTPS automático).

## Estructura

```
backend/   API FastAPI, parsers de los Excel, sincronización, tests (pytest)
frontend/  PWA Svelte (src/routes = pantallas, src/components, src/sw.js = service worker)
samples/   Excel reales de la FVCL que usan los tests
scripts/   gen_icons.py: regenera iconos y splash a partir de frontend/assets-src/logo.png
```

## Desarrollo local

```bash
# Backend (Python 3.9 o superior)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest                       # tests
ADMIN_PASSWORD=prueba .venv/bin/uvicorn app.main:app --reload --port 8000

# Frontend (Node 20 o superior), en otra terminal
cd frontend
npm install
npm run dev        # http://localhost:5173 (redirige /api al backend)
npm run build      # genera frontend/dist, que el backend sirve en http://localhost:8000
```

El panel de admin está en `/#/admin` y no aparece en el menú.

## Despliegue (VPS con Docker)

1. Apunta un dominio, o subdominio, a la IP del servidor.
2. `cp .env.example .env` y rellena `DOMAIN`, `PUBLIC_URL`, `ADMIN_PASSWORD`, `SECRET_KEY` y, si quieres avisos por email, `SMTP_*` y `ADMIN_EMAIL`.
3. `docker compose up -d --build`

La base de datos queda en `./data/ancares.db`. Para tener una copia de seguridad basta con copiar ese fichero.

## Uso del panel de admin

1. **Nueva categoría.** Rellena:
   - el nombre visible;
   - el *nombre FVCL*: lo que aparece en el nombre del Excel, por ejemplo `CRE Infantil Femenino Liga Oro`;
   - los dos enlaces `export-xls` de la federación (clasificación y calendario).
2. **Sincronizar** descarga e importa los dos Excel al momento. Además se hace solo cada día a la hora de `SYNC_CRON`.
3. **Si la federación bloquea la descarga** (fvcl.es tiene una protección anti-bots y a veces responde con un 429), la categoría queda como *Bloqueado* y, si el email está configurado, llega un aviso. Para actualizarla a mano:
   - **Android (con la app instalada):** abre el enlace, descarga el Excel y pulsa *Compartir → Ancares*. Se sube solo.
   - **iPhone u ordenador:** descarga los Excel y pulsa *Subir Excel* en la categoría.
4. **Feedback:** aquí aparecen los comentarios que mandan las familias desde la pestaña *Club*.

> La app **no intenta saltarse** la protección de la federación: hace una sola petición al día por enlace, con un User-Agent que la identifica. Si el bloqueo se vuelve habitual, lo mejor es pedir a la FVCL que permita la IP del servidor.

## Particularidades de los Excel de la FVCL (Clupik)

- Son `.xls` antiguos con el contenedor OLE «corrupto», así que se abren con `xlrd` y `ignore_workbook_corruption=True`.
- En el calendario, local y visitante vienen **en la misma celda** (`"CDF Voleibol Ancares UVa VCV Castilla"`). Se separan usando los nombres de la clasificación.
- El `GMT+2` de las fechas es el desfase **del día de la exportación**, no del partido. Por eso la hora de reloj se interpreta siempre en Europe/Madrid.
- Cuando se publiquen los primeros resultados, revisa que el formato coincide con lo esperado (`3 - 1` y parciales `25-20…`). El texto original se guarda en `matches.raw_result`.
