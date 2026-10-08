from typing import Annotated

import structlog
from fastapi import Depends, FastAPI
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql import text
from starlette.responses import JSONResponse

from gisdb.config import get_settings
from gisdb.db import engine, get_session

log = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    from gisdb.logging_config import configure_logging

    configure_logging(get_settings().log_level)

    app = FastAPI(title="gisdb", version="0.1.0")

    @app.get("/health", tags=["health"])
    def health(session: Annotated[Session, Depends(get_session)]):
        try:
            session.execute(text("SELECT 1"))
            return {"status": "ok", "database": "ok"}
        except SQLAlchemyError as exc:
            log.warning("health.check.failed", error=str(exc))
            return JSONResponse(
                status_code=503,
                content={"status": "degraded", "database": "error"},
            )

    log.info("app.startup", version="0.1.0", db_dialect=engine.dialect.name)

    return app


app = create_app()
