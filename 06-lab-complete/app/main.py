"""Production AI Agent for the Part 6 final project."""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import perf_counter
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StringConstraints
from redis.exceptions import RedisError

from utils.mock_llm import ask as llm_ask

from .auth import verify_api_key
from .config import settings
from .cost_guard import check_budget, record_cost
from .rate_limiter import check_rate_limit
from .redis_client import r, redis_healthy

logger = logging.getLogger("agent")
logger.setLevel(settings.log_level)
logger.addHandler(logging.StreamHandler())
logger.propagate = False


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    logger.log(level, json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "lvl": logging.getLevelName(level),
        "event": event,
        **fields,
    }, ensure_ascii=False))


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event("startup", environment=settings.environment)
    try:
        yield
    finally:
        # Uvicorn drains in-flight requests before calling the lifespan shutdown.
        r.close()
        log_event("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        log_event(
            "request",
            level=logging.ERROR if status >= 500 else logging.INFO,
            method=request.method,
            path=request.url.path,
            status=status,
            ms=round((perf_counter() - started) * 1000, 2),
        )


@app.exception_handler(RedisError)
async def redis_unavailable(request: Request, exc: RedisError):
    log_event("redis_unavailable", level=logging.ERROR, error_type=type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Redis unavailable"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"status": "ready"}


@app.post("/ask")
def ask(body: AskRequest, key: Annotated[str, Depends(verify_api_key)]):
    check_rate_limit(key)
    check_budget()
    answer = llm_ask(body.question)
    # Mock responses have no usage metadata, so estimate one token per four characters.
    record_cost(max(1, len(body.question) // 4), max(1, len(answer) // 4))
    return {"question": body.question, "answer": answer}
