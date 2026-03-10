from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CostEventSchema(BaseModel):
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

class ProjectCreateSchema(BaseModel):
    name: str

class ProjectSettingResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    # We only show the hash, NEVER the raw key in queries
    has_api_key: bool 

    class Config:
        orm_mode = True
