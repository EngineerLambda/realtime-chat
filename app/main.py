from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .db import connect, close
from .routers import auth, chat
from .socketio_server import sio
from socketio import ASGIApp as SocketIOASGIApp
from fastapi.openapi.models import APIKey
from fastapi.openapi.utils import get_openapi
from .deps import get_current_user_from_cookie
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

api_key_scheme = APIKey(name="Authorization", scheme_name="Bearer", type="apiKey", **{"in": "header"})


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
    )

    # Add CORS middleware to allow cross-origin requests from the frontend
    # In production, you should restrict this to your frontend's domain
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],  # No origins needed for same-site hosting
        allow_credentials=True,
        allow_methods=["*"],  # Allows all methods
        allow_headers=["*"],  # Allows all headers
    )

    @app.on_event("startup")
    async def startup():
        connect()

    @app.on_event("shutdown")
    async def shutdown():
        close()

    # Routers that do NOT require auth by default
    app.include_router(auth.router)

    # Routers that DO require auth by default
    app.include_router(chat.router, dependencies=[Depends(get_current_user_from_cookie)])

    # Custom OpenAPI schema
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=settings.app_name,
            version="1.0.0",
            description="Realtime Chat API",
            routes=app.routes,
        )
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
        openapi_schema["security"] = [{"BearerAuth": []}]
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    app.openapi = custom_openapi

    # Serve chat.html at the /chat endpoint
    @app.get("/chat")
    async def serve_chat():
        return FileResponse("static/chat.html")

    # Serve index.html at the root endpoint
    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse("static/index.html")

    # Mount the static directory for CSS, JS, etc.
    app.mount("/", StaticFiles(directory="static"), name="static")

    return app


# create the FastAPI app
fastapi_app = create_app()

# wrap FastAPI app with Socket.IO ASGI app so both work under same server
asgi_app = SocketIOASGIApp(sio, other_asgi_app=fastapi_app)

# exported ASGI app for the server (uvicorn). Use `app` as the ASGI application.
app = asgi_app
