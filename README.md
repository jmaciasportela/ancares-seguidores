# Ancares Seguidores 🏐

PWA **no oficial** para que las familias del CDF Voleibol Ancares sigan la clasificación, el calendario y los resultados de cada categoría. Los datos salen de los Excel que publica la Federación de Voleibol de Castilla y León (fvcl.es).

- **Frontend:** Svelte 5 + Vite + vite-plugin-pwa (unos 40 KB gzip). Es instalable, funciona sin conexión, tiene splash animado y tema claro y oscuro.
- **Backend:** FastAPI + SQLite + APScheduler. Sincroniza los Excel cada día.
- **Despliegue:** Docker Compose detrás de Nginx Proxy Manager (que pone el HTTPS).

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

## Despliegue (VPS con Nginx Proxy Manager)

1. Apunta un dominio, o subdominio, a la IP del VPS.
2. La app se conecta a la red Docker externa `amacium`, la misma que usa Nginx Proxy Manager (está fijada en `docker-compose.yml`). Si tu red se llama de otra forma (consúltalo con `docker network ls`), cámbiala ahí.
3. `cp .env.example .env` y rellena `PUBLIC_URL`, `ADMIN_PASSWORD`, `SECRET_KEY` y, si quieres avisos por email, `SMTP_*` y `ADMIN_EMAIL`. Deja `COOKIE_SECURE=true`.
4. `docker compose up -d --build`
5. En Nginx Proxy Manager, crea un *Proxy Host*:
   - **Domain Names:** tu dominio.
   - **Scheme / Forward Hostname / Port:** `http` · `ancares-app` · `8000`.
   - **Block Common Exploits:** activado.
   - **Pestaña SSL:** *Request a new SSL Certificate* con *Force SSL* y *HTTP/2*.

La app no publica ningún puerto en el VPS: solo es accesible a través de Nginx Proxy Manager. El HTTPS es obligatorio para que la PWA se pueda instalar.

La base de datos queda en `./data/ancares.db`. Para tener una copia de seguridad basta con copiar ese fichero.

## Uso del panel de admin

1. **Nueva categoría.** Rellena:
   - el nombre visible;
   - el *nombre FVCL*: lo que aparece en el nombre del Excel, por ejemplo `CRE Infantil Femenino Liga Oro`;
   - los dos enlaces `export-xls` de la federación (clasificación y calendario).
2. **Sincronizar** descarga e importa los dos Excel al momento. Además se hace solo cada día a la hora de `SYNC_CRON`.
3. **Prueba de trabajo de fvcl.es.** A veces fvcl.es responde con un 429 y un reto de prueba de trabajo (SHA-256) en lugar del Excel. La app lo resuelve sola (`backend/app/services/pow.py`, basado en `scripts/descargar_pow.py`):
   - usa siempre su propio User-Agent;
   - hace un solo intento por sincronización;
   - comparte la cookie del reto entre los ficheros de la misma pasada.

   Se puede desactivar con `POW_ENABLED=false`.
4. **Si aun así no llega el Excel**, la categoría queda como *Bloqueado* y, si el email está configurado, llega un aviso. Para actualizarla a mano:
   - **Android (con la app instalada):** abre el enlace, descarga el Excel y pulsa *Compartir → Ancares*. Se sube solo.
   - **iPhone u ordenador:** descarga los Excel y pulsa *Subir Excel* en la categoría.
5. **Equipos y logos.** La pestaña *Equipos* lista todos los equipos de las clasificaciones, y hay dos formas de ponerles escudo:
   - **Automática:** el botón *Buscar logos en la FVCL* abre la página de clasificación de cada categoría (la URL del Excel sin `/export-xls`) y busca la imagen asociada a cada nombre de equipo. También se hace sola en la sincronización diaria, como mucho una vez por semana para cada equipo sin logo.
   - **Manual:** con *Subir* o *Enlace* (PNG, JPG o WebP). Un logo puesto a mano nunca lo sustituye la búsqueda automática.

   Las imágenes se convierten a WebP de 160 px y se guardan en `data/logos/`. Los equipos sin logo muestran sus iniciales.
6. **Feedback:** aquí aparecen los comentarios que mandan las familias desde la pestaña *Club*.

> La app no se hace pasar por un navegador y descarga como mucho una vez al día por enlace. Si la federación pide que no se acceda así, pon `POW_ENABLED=false` y usa la subida manual.

## Particularidades de los Excel de la FVCL (Clupik)

- Son `.xls` antiguos con el contenedor OLE «corrupto», así que se abren con `xlrd` y `ignore_workbook_corruption=True`.
- En el calendario, local y visitante vienen **en la misma celda** (`"CDF Voleibol Ancares UVa VCV Castilla"`). Se separan usando los nombres de la clasificación.
- El `GMT+2` de las fechas es el desfase **del día de la exportación**, no del partido. Por eso la hora de reloj se interpreta siempre en Europe/Madrid.
- Cuando se publiquen los primeros resultados, revisa que el formato coincide con lo esperado (`3 - 1` y parciales `25-20…`). El texto original se guarda en `matches.raw_result`.
