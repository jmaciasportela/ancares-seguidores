# Ancares Seguidores 🏐

PWA **no oficial** para que las familias del CDF Voleibol Ancares sigan la clasificación, el calendario y los resultados de cada categoría. Los datos salen de los Excel que publica la Federación de Voleibol de Castilla y León (fvcl.es).

- **Frontend:** Svelte 5 + Vite + vite-plugin-pwa (unos 40 KB gzip). Es instalable, funciona sin conexión, tiene splash animado y tema claro y oscuro.
- **Backend:** FastAPI + SQLite + APScheduler. Sincroniza los Excel dos veces al día (12:00 y 16:00).
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
npm test           # tests de la lógica del marcador (vitest)
```

El panel de admin está en `/#/admin` y no aparece en el menú.

### Versión de la PWA

Cada commit sube automáticamente la versión *patch* de `frontend/package.json` (1.0.0 → 1.0.1). Lo hace el hook `.githooks/pre-commit`, que se activa una vez por cada clon del repositorio:

```bash
git config core.hooksPath .githooks
```

Una versión nueva cambia el service worker, y los móviles que tienen la app instalada la descargan solos. La app recarga al momento si se acaba de abrir; si no, espera a que el usuario vuelva a ella, y avisa con «App actualizada a la versión X». La versión se ve al pie de la pestaña *Club*.

- Para un salto mayor: `python3 scripts/bump_version.py minor` (o `major`) antes del commit.
- Para saltarse la subida en un commit concreto: `SKIP_BUMP=1 git commit …`.

## Despliegue (VPS con Nginx Proxy Manager)

1. Apunta un dominio, o subdominio, a la IP del VPS.
2. La app se conecta a la red Docker externa `amacium`, la misma que usa Nginx Proxy Manager (está fijada en `docker-compose.yml`). Si tu red se llama de otra forma (consúltalo con `docker network ls`), cámbiala ahí.
3. `cp .env.example .env` y rellena `PUBLIC_URL`, `ADMIN_PASSWORD`, `SECRET_KEY` y, si quieres avisos por email, `SMTP_*` y `ADMIN_EMAIL`. Deja `COOKIE_SECURE=true`.
4. `docker compose up -d --build`
5. En Nginx Proxy Manager, crea un *Proxy Host*:
   - **Domain Names:** tu dominio.
   - **Scheme / Forward Hostname / Port:** `http` · `ancares-app` · `8000`.
   - **Block Common Exploits:** activado.
   - **Websockets Support:** activado (para el marcador en directo; sin él funciona igual, pero las familias ven el tanteo con unos segundos de retraso).
   - **Pestaña SSL:** *Request a new SSL Certificate* con *Force SSL* y *HTTP/2*.

La app no publica ningún puerto en el VPS: solo es accesible a través de Nginx Proxy Manager. El HTTPS es obligatorio para que la PWA se pueda instalar.

La app debe correr en **un solo proceso** de uvicorn (como en el `Dockerfile`): los visores del marcador en directo se reparten en memoria.

La base de datos queda en `./data/ancares.db`. Para tener una copia de seguridad basta con copiar ese fichero.

## Uso del panel de admin

1. **Nueva categoría.** Rellena:
   - el nombre visible;
   - el *nombre FVCL*: lo que aparece en el nombre del Excel, por ejemplo `CRE Infantil Femenino Liga Oro`;
   - los dos enlaces `export-xls` de la federación (clasificación y calendario).
2. **Sincronizar** descarga e importa los dos Excel al momento. Además se hace solo a las 12:00 y a las 16:00 (hora de Madrid), según `SYNC_CRON`.
   - **Solo cuentan las novedades reales.** Clupik pone la hora de exportación dentro de cada Excel, así que dos descargas con los mismos datos nunca son iguales byte a byte. La app compara los **datos** partido a partido y equipo a equipo:
     - Si nada ha cambiado, registra «Sin cambios» y no toca nada.
     - Si hay cambios, los guarda y apunta qué cambió, por ejemplo «2 resultados nuevos · 1 cambio de horario o pabellón (Ancares – Colón: dom 18/10 10:30 → 12:00)». La lista completa se ve en *Registro*.
   - **En la portada:** «Novedades de la federación hace X · comprobado hace Y».
   - **Si la FVCL lo permite**, la app pregunta antes de descargar si el Excel ha cambiado (cabeceras `ETag`/`Last-Modified`, con respuesta `304`). Si no lo indica, el admin lo avisa y se compara el contenido.
3. **Prueba de trabajo de fvcl.es.** A veces fvcl.es responde con un 429 y un reto de prueba de trabajo (SHA-256) en lugar del Excel. La app lo resuelve sola (`backend/app/services/pow.py`, basado en `scripts/descargar_pow.py`):
   - usa siempre su propio User-Agent;
   - hace un solo intento por sincronización;
   - comparte la cookie del reto entre los ficheros de la misma pasada.

   Se puede desactivar con `POW_ENABLED=false`.
4. **Si aun así no llega el Excel**, la categoría queda como *Bloqueado* y, si el email está configurado, llega un aviso. Para actualizarla a mano:
   - **Android (con la app instalada):** abre el enlace, descarga el Excel y pulsa *Compartir → Ancares*. Se sube solo.
   - **iPhone u ordenador:** descarga los Excel y pulsa *Subir Excel* en la categoría.
5. **Equipos y logos.** La pestaña *Equipos* lista todos los equipos de las clasificaciones, y hay dos formas de ponerles escudo:
   - **Automática:** el botón *Buscar logos en la FVCL* abre la página de clasificación de cada categoría (la URL del Excel sin `/export-xls`), busca la imagen asociada a cada nombre de equipo y rehace los logos que ya vinieron de la FVCL. También se hace sola en las sincronizaciones programadas, como mucho una vez por semana para cada equipo sin logo. Las miniaturas pequeñas se amplían para llenar el escudo y las de menos de 16 px se descartan.
   - **Manual:** con *Subir* o *Enlace* (PNG, JPG o WebP). Un logo puesto a mano nunca lo sustituye la búsqueda automática.

   Las imágenes se convierten a WebP de 160 px y se guardan en `data/logos/`. Los equipos sin logo muestran sus iniciales.
6. **Feedback:** aquí aparecen los comentarios que mandan las familias desde la pestaña *Club*.

> La app no se hace pasar por un navegador y descarga como mucho dos veces al día por enlace. Si la federación pide que no se acceda así, pon `POW_ENABLED=false` y usa la subida manual.

## Portada y previsión del tiempo

La portada muestra para cada categoría el **próximo partido** en grande, con cuenta atrás y previsión del tiempo, y debajo una tarjeta más pequeña con el **siguiente partido**.

La previsión sale de [Open-Meteo](https://open-meteo.com), un servicio gratuito y sin clave. Se pide para la hora del partido y el servidor la guarda en caché una hora. Solo hay previsión hasta unos 15 días vista; antes, la tarjeta indica desde qué día estará disponible.

Como los pabellones no traen coordenadas, la ubicación es aproximada por ciudad:
1. Se busca una localidad conocida de Castilla y León en el nombre del pabellón o en el del equipo local (*Rio Duero **Soria** A*).
2. Si no aparece, se geolocaliza lo que va tras la última coma del pabellón (*Pabellón X, **Localidad***).
3. Si tampoco, se usa `WEATHER_DEFAULT_CITY` (Valladolid).

La tarjeta indica siempre para qué ciudad es la previsión. Los pabellones habituales sin ciudad en el nombre se añaden en `VENUE_HINTS` (`backend/app/services/weather.py`).

## Compartir imagen

Los botones de compartir (resultados, tarjeta del próximo partido y resumen del marcador) abren un panel con la imagen generada en el propio móvil (Canvas 2D, sin servidor).
- **Formatos:** *Historia* (1080×1920, para las historias de Instagram) o *Cuadrado* (1080×1080).
- **Resultado:** titular desde el punto de vista de Ancares (¡VICTORIA!, DERROTA o EMPATE), escudos, sets, parciales y la banda «Resultado provisional» si aún no es oficial.
- **Previa:** día, hora, pabellón y previsión del tiempo.

Con «Compartir imagen» se usa la hoja nativa del móvil; si el navegador no permite compartir ficheros, la imagen se descarga. También se puede compartir *solo texto*. El código está en `src/lib/shareImage.js` y se carga bajo demanda.

## Estadísticas

La pestaña **Estadísticas** de cada categoría muestra:
- la racha de Ancares (últimos 5 partidos, con los provisionales en ámbar);
- posición, puntos, % de sets ganados y puntos por set;
- la gráfica **«Posición por jornada»**: la línea de Ancares destacada sobre las del resto de equipos; se toca para ver el detalle y tiene tabla de datos;
- curiosidades: set más largo, victoria más clara y mejor racha.

El Excel solo trae la clasificación actual, así que la evolución se reconstruye con los resultados del calendario y la puntuación de la FVCL: 3 puntos por ganar sin llegar al set decisivo, 2 por ganarlo en el decisivo, 1 por perderlo en el decisivo y 0 en otro caso. Si no cuadra con la tabla oficial, se avisa de que es aproximada.

En **Clasificación**, si hay resultados provisionales, el interruptor «Incluir resultados provisionales» muestra una tabla orientativa con flechas en los equipos que suben o bajan. A igualdad de puntos se respeta el orden oficial.

## Día de partido

El día que juega Ancares (en hora de Madrid), la portada cambia sola:
- **Aviso:** una franja animada «¡HOY JUEGA ANCARES!» con la hora (o las horas, si hay varios partidos). Al tocarla, baja hasta la tarjeta del primer partido.
- **Tarjetas del día:** los partidos de hoy brillan con un pulso verde y llevan la etiqueta «🏐 HOY», que pasa a «🔴 EN JUEGO» desde la hora de inicio hasta 2 h después. El pabellón abre la ruta en Google Maps (**Cómo llegar**) y aparece el botón **Marcador**.
- **Ánimos:** en la tarjeta del partido, «💚 ¡Vamos Ancares!» y frases predefinidas, con emojis que suben flotando y un contador colectivo. Se pueden mandar desde 24 h antes hasta 4 h después del partido. Los toques se envían agrupados, son anónimos y nunca se escribe texto libre. Hay límites: 25 por envío y 300 por móvil y partido. Después, el resultado muestra cuántos ánimos recibió.
- **Celebración:** en cuanto hay resultado, aunque sea provisional, la app lo celebra una sola vez por móvil: confeti y «¡VICTORIA!» si se gana, un mensaje de ánimo si se pierde. Ese día la portada se refresca cada 45 s.

Con «reducir movimiento» activado en el móvil, no hay animaciones.

## Torneos

Además de las ligas de la FVCL, el admin puede dar de alta **torneos** con *Nueva liga o torneo → Torneo*. No llevan enlaces de la federación: los partidos se meten a mano desde el botón **Partidos** de la tarjeta del torneo.
- **Uno a uno:** fase, fecha, hora, local, visitante, pabellón y, opcionalmente, el resultado.
- **Pegando una lista:** un partido por línea, por ejemplo `19/12 10:00 · Grupo A · Ancares UVa - CV Laguna · Pabellón Pisuerga`. Los campos se separan con `·`, `|` o `;` y los equipos con ` - ` o ` vs `. Antes de guardar se muestra una vista previa con los errores de cada línea; si se pone fecha, la hora es obligatoria.

**Resultados:** los de los anotadores (desde el Marcador) son **provisionales** hasta que el admin los **confirma**, desde el editor de partidos o desde *Anotadores*. El admin también puede escribir el resultado directamente: `3-1` o `25-20 23-25 15-12`.

**Clasificación:** se calcula sola por cada fase (Grupo A, Grupo B…) con la puntuación 3/2/1/0. Las eliminatorias (semifinal, final, 3er puesto…) solo se ven como partidos. Los torneos aparecen en la portada, el calendario y el marcador como cualquier categoría, con la etiqueta «Torneo».

## Uso de la app (anónimo)

La pestaña **Uso** del admin muestra:
- dispositivos activos hoy, en 7 días y en 30 días;
- **instalaciones activas** (la app abierta como app instalada) y altas nuevas;
- dispositivos por día;
- frecuencia (días de uso en el último mes);
- plataformas y versiones.

**Cómo se recoge:** cada móvil genera un identificador aleatorio que solo se guarda en él y, al abrir la app, como mucho cada 30 minutos, envía un aviso a `/api/ping`. El aviso lleva ese identificador, si la app está instalada, la plataforma y la versión. En el servidor se guarda solo el hash del identificador.

**Privacidad:** no se guardan IPs ni datos personales, y lo que tiene más de 180 días se borra en la sincronización programada. En iPhone, la app instalada y Safari cuentan como dos dispositivos.

## Marcador y resultados provisionales

La pestaña **Marcador** permite llevar el tanteo de un partido con un toque por punto. Sigue la normativa FIVB/RFEVB:
- **Sets:** se ganan al llegar a 25 (o 15) con 2 puntos de diferencia y sin tope. El set decisivo se juega a 15 y, en él, la app avisa del cambio de campo a los 8 puntos.
- **Formatos:** al mejor de 3 o de 5, o un número fijo de sets.
- **Formato por categoría:** el admin lo fija al editar la categoría y se puede cambiar antes de empezar el partido.

**Partidos fuera de fecha:** el marcador propone los partidos de ±2 días. Como a veces se juegan otro día u otra hora que la del Excel, el admin ve además «Otro día u otra hora» con el resto de partidos sin resultado (también los que aún no tienen fecha) y puede anotarlos y emitirlos en directo.

El partido en curso se guarda en el móvil, así que no se pierde si se cierra la app. Se puede deshacer, corregir el marcador, cambiar los lados y terminar en cualquier momento. Al acabar, la app propone el partido de liga más cercano por día y hora.

**Quién puede publicar:**
- **Cualquiera:** puede usar el marcador y compartir el resultado por WhatsApp.
- **Anotadores:** publican el resultado en la app como **provisional**. El admin les crea un código en la pestaña *Anotadores* (se muestra una sola vez) y ellos lo introducen en la app, en *Club → Funciones extra*. Revocar un anotador lo desactiva al momento en todos sus móviles. El admin también puede publicar.
- **Qué se publica:** el resultado aparece con la etiqueta «Provisional · pendiente de confirmar por la federación», no cuenta para la clasificación y desaparece en cuanto la FVCL publica el oficial. Desde el admin se pueden ver y borrar.
- **Manda el primero:** si dos anotadores publican el mismo partido, se queda el primero. Solo quien lo publicó puede corregirlo, y el admin siempre puede sustituirlo o borrarlo. Si alguien lo intenta, el marcador le dice quién lo publicó.

## Marcador en directo

Cuando un anotador (o el admin) empieza a llevar un partido de liga, se **emite en directo**: cada punto llega al momento a quien lo esté viendo.
- **Una sola persona emite:** el *anotador principal*, que es el primero que empieza. Si otro anotador intenta llevar el mismo partido, la app le dice quién lo está retransmitiendo y le deja verlo en directo o llevar su marcador sin emitir.
- **Relevo:** si el principal deja de dar señal 10 minutos (sin batería, sin cobertura...), otro anotador puede **tomar el relevo** y sigue desde el tanteo emitido. El admin puede hacerlo siempre. Desde el menú del marcador se puede *Dejar de emitir* o *Compartir el directo*.
- **Para las familias:** en las tarjetas de los partidos de hoy aparece **Ver en directo**. El visor (`#/directo/{id}`, se puede compartir por WhatsApp) muestra los puntos con un destello en cada tanto, los avisos de punto de set, fin de set, cambio de campo y final, cuánta gente lo está viendo y los ánimos. Si aún no ha empezado, espera y se pone en marcha solo.
- **Portada y calendario:** mientras se emite, la tarjeta muestra el tanteo con «EN DIRECTO» y el calendario una pastilla que lleva al visor.
- **Cómo funciona:** el anotador manda el estado completo del marcador en cada cambio (un reintento con mala cobertura no descuadra nada) y un latido cada minuto. Los visores lo reciben por WebSocket; si no conecta, consultan cada 5 s. El estado se guarda en la base de datos, así que un reinicio no lo pierde, y se borra a los 2 días.
- **Resultado:** el directo no cuenta como resultado. Al terminar, el anotador publica el resultado provisional como siempre.

## Puntuación y desempates

La clasificación oficial se muestra tal cual la publica la federación. La app solo calcula puntos en la **clasificación provisional**, en la **evolución** de Estadísticas y en los **grupos de los torneos**, y lo hace según la normativa de la FVCL (Normas Generales de Voleibol 2026-27, «Sistema de puntuación»):

| Categorías | Gana | Pierde | No presentado |
|---|---|---|---|
| Cadete, Infantil, Alevín y Benjamín (**2-1-0**) | 2 | 1 | 0 |
| Juvenil, Júnior y Sénior (**3-2-1-0**) | 3 si gana 3-0 o 3-1; 2 si gana 3-2 | 1 si pierde 2-3; 0 si pierde 0-3 o 1-3 | 0 |

- **Qué regla se aplica:** la que elija el admin en la categoría. En «Automática», que es la opción por defecto, se usa la que cuadra con la clasificación oficial cuando los resultados permiten distinguirla. Si aún no hay resultados, o solo partidos 3-2, se usa la de la normativa según el nombre de la categoría. Se ve en la lista de categorías del admin.
- **Para las familias:** la leyenda de la clasificación explica la puntuación («Pts: 2 por partido ganado y 1 por perdido»).
- **Desempates:** la FVCL no los fija, así que se aplica de forma supletoria la RFEVB. El orden es puntos, partidos ganados, cociente de sets y cociente de puntos. El último criterio, el resultado entre los empatados, no se aplica: la app ordena entonces por nombre.
- **Fuentes:** [Normas Generales de Voleibol FVCL 26-27](https://cdn.leverade.com/files/cyNue0tvjp.pdf) (pág. 22), [Normas Específicas de Voleibol FVCL 26-27](https://cdn.leverade.com/files/FI6iWOoYc0.pdf) y [Normas Generales de Competición RFEVB 25-26](https://esvoley.es/media/plkbqsz1/nevb-2526-normas-generales-competici%C3%B3n-cd-28-10-25.pdf) (art. 24.1).

## Particularidades de los Excel de la FVCL (Clupik)

- Son `.xls` antiguos con el contenedor OLE «corrupto», así que se abren con `xlrd` y `ignore_workbook_corruption=True`.
- En el calendario, local y visitante vienen **en la misma celda** (`"CDF Voleibol Ancares UVa VCV Castilla"`). Se separan usando los nombres de la clasificación.
- El `GMT+2` de las fechas es el desfase **del día de la exportación**, no del partido. Por eso la hora de reloj se interpreta siempre en Europe/Madrid.
- **Resultados:** la columna «Resultado» repite la fecha también en los partidos jugados. El resultado viene en «Parciales», todo seguido y sin separadores: `131425112525181225‐‐` son sets 1-3 y parciales 14-25, 11-25, 25-18, 12-25. Se busca la única forma de partirlo en sets válidos que cuadre con los sets ganados. Si no cuadra (acta incompleta), no se da por jugado. El texto original se guarda en `matches.raw_result`.
- **Provisionales:** en cuanto el calendario trae el resultado oficial, el provisional se borra. Si la clasificación oficial ya cuenta un partido que el calendario aún no trae, tampoco se suma otra vez.
