import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .routers import admin, feedback, public
from .services.sync import start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    scheduler = start_scheduler()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Ancares Seguidores", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(GZipMiddleware, minimum_size=800)

app.include_router(public.router)
app.include_router(feedback.router)
app.include_router(admin.router)
app.include_router(admin.protected)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/assets/"):
        # Ficheros con hash en el nombre: caché inmutable
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif path in ("/", "/index.html", "/sw.js", "/manifest.webmanifest") or path.startswith("/workbox-"):
        response.headers["Cache-Control"] = "no-cache"
    return response


# Frontend compilado (Svelte). Si no existe, el backend sirve solo la API.
if settings.static_dir.is_dir():
    index_file = settings.static_dir / "index.html"
    app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="static")

    @app.exception_handler(404)
    async def spa_fallback(request: Request, exc):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": getattr(exc, "detail", "No encontrado")}, status_code=404)
        return FileResponse(index_file)
