"""Track mock LLM spending by UTC day in Redis."""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from .config import settings
from .redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def budget_period() -> tuple[str, datetime]:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    key = f"agent:{settings.environment}:cost:{today.date()}"
    return key, today + timedelta(days=1)


def check_budget() -> None:
    key, _ = budget_period()
    if float(r.get(key) or 0) >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exhausted")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    cost = (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000
    key, resets_at = budget_period()
    with r.pipeline() as transaction:
        transaction.incrbyfloat(key, cost)
        transaction.expireat(key, resets_at)
        transaction.execute()
    return cost
