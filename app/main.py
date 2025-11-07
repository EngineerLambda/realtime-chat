from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from .config import settings
from .db import connect, close
from .routers import auth, chat
from fastapi.staticfiles import StaticFiles
import os
from .socketio_server import sio
from socketio import ASGIApp as SocketIOASGIApp


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    @app.on_event("startup")
    async def startup():
        connect()

    @app.on_event("shutdown")
    async def shutdown():
        close()

    app.include_router(auth.router)
    app.include_router(chat.router)

    # static
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        path = os.path.join(static_dir, "index.html")
        with open(path, "r") as f:
            return HTMLResponse(f.read())

    @app.get("/chat", response_class=HTMLResponse)
    async def chat_page(request: Request):
        # protect chat page: if no valid access_token cookie, redirect to login page
        from .utils import decode_token
        token = request.cookies.get("access_token")
        if not token:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/")
        try:
            payload = decode_token(token)
        except Exception:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/")
        path = os.path.join(static_dir, "chat.html")
        with open(path, "r") as f:
            return HTMLResponse(f.read())

    # admin: quick model counts
    @app.get("/admin/models")
    async def admin_models():
        db = connect()
        return {
            "users": await db["users"].count_documents({}),
            "sessions": await db["sessions"].count_documents({}),
            "groups": await db["groups"].count_documents({}),
            "messages": await db["messages"].count_documents({}),
        }

    return app


# create the FastAPI app
fastapi_app = create_app()

# wrap FastAPI app with Socket.IO ASGI app so both work under same server
asgi_app = SocketIOASGIApp(sio, other_asgi_app=fastapi_app)

# exported ASGI app for the server (uvicorn). Use `app` as the ASGI application.
app = asgi_app
