from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jobs_back.api.profiles import router as profiles_router
from jobs_back.api.searches import router as searches_router
from jobs_back.config import get_settings
from jobs_back.search.live import LiveSearchManager


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.search_manager = LiveSearchManager()
        yield
        await app.state.search_manager.close()

    app = FastAPI(title="Job Scout API", version="0.2.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(profiles_router)
    app.include_router(searches_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
