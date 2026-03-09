from sqlalchemy import Column, Integer, String, Float, Boolean
from server.database import Base
class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    api_key_hash = Column(String, nullable=False)
    created_at = Column(String, nullable=False)


class CloudCostEvent(Base):
    __tablename__ = "events"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    
    # Tenancy Isolation
    project_id = Column(String, index=True, nullable=False)
    
    # Event Data (Matches Veritas SDK CostEvent Schema)
    feature = Column(String, index=True, nullable=False)
    model = Column(String, nullable=False)
    tokens_in = Column(Integer, default=0, nullable=False)
    tokens_out = Column(Integer, default=0, nullable=False)
    cache_creation_tokens = Column(Integer, default=0, nullable=False)
    cache_read_tokens = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Float, nullable=False)
    cost_usd = Column(Float, nullable=False)
    code_version = Column(String, index=True, nullable=True)
    
    # Time Data
    timestamp = Column(String, index=True, nullable=False) # ISO String
    status = Column(String, default='ok', nullable=False)
    estimated = Column(Boolean, default=False, nullable=False)
