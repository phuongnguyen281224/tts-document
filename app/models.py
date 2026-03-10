from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from .database import Base

class AudioJob(Base):
    __tablename__ = "audio_jobs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True, nullable=False)
    filename = Column(String, nullable=False)
    status = Column(String, nullable=False, default="PENDING") # PENDING, SUCCESS, FAILURE, REVOKED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
