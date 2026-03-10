from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class CostEventSchema(BaseModel):
    feature:               str   = Field(..., max_length=200)
    model:                 str   = Field(..., max_length=200)
    tokens_in:             int
    tokens_out:            int
    cache_creation_tokens: int   = 0
    cache_read_tokens:     int   = 0
    latency_ms:            float
    cost_usd:              float
    code_version:          Optional[str] = Field(None, max_length=200)
    timestamp:             str   = Field(..., max_length=50)
    status:                str   = Field("ok", max_length=50)
    estimated:             bool  = False

class ProjectCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

class ProjectSettingResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    # We only show the hash, NEVER the raw key in queries
    has_api_key: bool 

    class Config:
        from_attributes = True
