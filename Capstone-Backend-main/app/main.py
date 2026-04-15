import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from dotenv import load_dotenv

from app.database import engine, Base
from app.routers import auth, upload, participant, survey

# Create database tables
Base.metadata.create_all(bind=engine)


def _ensure_schema_extensions():
    if engine.url.get_backend_name() != "postgresql":
        return

    statements = [
        "ALTER TABLE surveys ADD COLUMN IF NOT EXISTS arrow_time_limit_sec INTEGER",
        "ALTER TABLE surveys ADD COLUMN IF NOT EXISTS mcq_time_limit_sec INTEGER",
        "ALTER TABLE surveys ADD COLUMN IF NOT EXISTS text_entry_time_limit_sec INTEGER",
        "ALTER TABLE surveys ADD COLUMN IF NOT EXISTS participant_form_config JSONB",
        "ALTER TABLE participants ADD COLUMN IF NOT EXISTS consent VARCHAR",
        "ALTER TABLE answers ADD COLUMN IF NOT EXISTS angle_deviation DOUBLE PRECISION",
        "ALTER TABLE answers ADD COLUMN IF NOT EXISTS text_answer TEXT",
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


_ensure_schema_extensions()

load_dotenv()

app = FastAPI(
    title=os.getenv("APP_NAME", "Capstone Backend"),
    version="0.1.0"
)

allowed_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
if not allowed_origins:
    allowed_origins = [
        "http://127.0.0.1:8001",
        "http://localhost:8001",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_error_message(detail: Any, default: str) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str) and message.strip():
            return message
    return default


@app.exception_handler(HTTPException)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException):
    message = _extract_error_message(exc.detail, "Request failed")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": False,
            "message": message,
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "status": False,
            "message": "Validation error",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, __: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "status": False,
            "message": "Internal server error",
        },
    )

app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(participant.router)
app.include_router(survey.router)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "app_name": os.getenv("APP_NAME"),
        "environment": os.getenv("APP_ENV", "unknown")
    }

@app.get("/")
def read_root():
    return {"message": "Welcome to the Capstone Backend API. Visit /docs for the API documentation."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)