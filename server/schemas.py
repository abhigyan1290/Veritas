from pydantic import BaseModel
from typing import Optional

class CostEventCreate(BaseModel):
    feature: str
    model: str
    tokens_in: int
    tokens_out: int
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    latency_ms: float
    cost_usd: float
    code_version: Optional[str] = None
    timestamp: str
    status: str = "ok"
    estimated: bool = False
