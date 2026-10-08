# PLAN
## 1. Conventions
- Tokens written <NAME=value> in a prompt mean: use value. If PLAN.md §3 "Placeholder values" gives NAME a different value, use PLAN's value and say so in your reply.
- Stack: Python 3.12, code stays 3.11-compatible (no `type X = ...`, no `class C[T]`); uv only (`uv add`, `uv run`; never pip, never requirements.txt); FastAPI + uvicorn; SQLAlchemy 2.x typed ORM; Alembic; psycopg 3; Pydantic v2 + pydantic-settings; structlog; pytest + fastapi.testclient; ruff.
- Layout: package gisdb in src/gisdb/ (config, db, models, logging_config, records, ingest, geodesy, analysis, cli, api/{app,deps,schemas,routes}); migrations/; tests/; scripts/. Import as gisdb.<module>. No extra layers (no repositories, services packages, DI frameworks).
- SQLAlchemy: class Base(DeclarativeBase) in models.py with the naming convention; Mapped[...], mapped_column(), relationship(), select(), session.scalars()/.execute()/.get(). NEVER declarative_base(), Column() in models, session.query(), engine.execute().
- Sync only: create_engine, sessionmaker, Session; endpoints are plain def. NEVER AsyncSession, create_async_engine, asyncpg, aiosqlite, async def endpoints.
- Database URL only from settings (GISDB_DATABASE_URL). Postgres URLs are postgresql+psycopg://. NEVER postgresql:// or psycopg2.
- Keys: id = internal integer PK, never in the API; <x>_id = natural string key used in URLs and JSON (exception: ingest_run_id and analysis_run_id in CLI output and logs are the runs' integer id); <x>_pk = integer FK to <x>s.id. Units in names: _km, _m, _s. Times are timezone-aware UTC.
- Types: UTCDateTime and JSONType from gisdb.models; server_default=text("CURRENT_TIMESTAMP"), NEVER func.now(); String(n) + named CheckConstraint instead of Enum; no ARRAY, no Geography.
- Coordinates: in code a position is (lat, lon) in degrees; the source's coordinate layout (PLAN §3, COORD_ORDER) is unpacked only at the JSON boundary in records.py.
- Pydantic v2: model_config = ConfigDict(...), field_validator, model_validator, model_validate, model_dump. NEVER class Config, orm_mode, @validator, @root_validator, parse_obj, .dict(). Settings: from pydantic_settings import BaseSettings, SettingsConfigDict.
- FastAPI: Annotated parameters (Annotated[Session, Depends(get_session)], Annotated[int, Query(ge=1, le=500)] = 50); GET routes only; NEVER @app.on_event.
- Logging: log = structlog.get_logger(__name__); log.info("area.object.verb", key=value) with names from PLAN §7; logs go to stderr; NEVER print() in src/ (a CLI writes its one JSON result line with sys.stdout.write); never log whole payloads or coordinate arrays.
- Errors: catch specific exceptions (e.g. sqlalchemy.exc.SQLAlchemyError, json.JSONDecodeError); `except Exception` only to log.exception(...) or to re-raise; inside except, raise NewError(...) from exc.
- Geo: a sphere with the radius in PLAN §8 (EARTH_RADIUS_KM); all geodesy in src/gisdb/geodesy.py with math only; NEVER interpolate, average or subtract raw lat/lon.
- Migrations: the human runs autogenerate and reviews. NEVER create or edit files in migrations/versions/.
- Tests: NEVER weaken, skip or delete a test or an expected value to make it pass; if a test looks wrong, stop and say why.
- Scope: change only the files the prompt names; add dependencies only when the prompt names them; never run git; never leave a server running; after 3 failed attempts at the same command, stop and report.
- Lint: once pyproject.toml exists, run uv run ruff format and uv run ruff check --fix on the .py files you changed before replying, and fix what remains by hand (lines of at most 100 characters; split a long string in src/ into implicitly concatenated pieces).
- Replies: changed files (one line each) plus the last 15 lines of any command you ran; never paste whole files back.
## 2. Brief
## 3. Data mapping
## 4. Schema
## 5. Ingestion
## 6. API
## 7. Logging
## 8. Analysis
## 9. Commands
## 10. Decisions and open questions
## 11. Status
