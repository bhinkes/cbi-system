from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import pytz
from .database import Base

class Submission(Base):
    __tablename__ = "submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(50), nullable=False)
    username = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(pytz.timezone('America/New_York')))
    down_target_multiple = Column(Numeric(10, 4))
    base_target_multiple = Column(Numeric(10, 4))
    up_target_multiple = Column(Numeric(10, 4))
    down_target_price = Column(Numeric(10, 2))
    base_target_price = Column(Numeric(10, 2))
    up_target_price = Column(Numeric(10, 2))
    
    kpis = relationship("KPI", back_populates="submission", cascade="all, delete-orphan")

class KPI(Base):
    __tablename__ = "kpis"
    
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"))
    kpi_name = Column(String(200), nullable=False)
    down_value = Column(Numeric(15, 4))
    base_value = Column(Numeric(15, 4))
    up_value = Column(Numeric(15, 4))
    
    submission = relationship("Submission", back_populates="kpis")
