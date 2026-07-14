try:
    from sqlalchemy import Column, DateTime, Float, Integer, String, Text, func
    from sqlalchemy.orm import declarative_base
except ImportError:
    declarative_base = None

Base = declarative_base() if declarative_base else object

if declarative_base:
    class DocumentRecord(Base):
        __tablename__ = "documents"
        id = Column(Integer, primary_key=True, index=True)
        filename = Column(String(255), nullable=False)
        kind = Column(String(50), nullable=False)
        text = Column(Text, nullable=False)
        created_at = Column(DateTime(timezone=True), server_default=func.now())

    class AnalysisRecord(Base):
        __tablename__ = "analyses"
        id = Column(Integer, primary_key=True, index=True)
        candidate_name = Column(String(255), nullable=False)
        filename = Column(String(255), nullable=False)
        final_score = Column(Float, nullable=False)
        payload = Column(Text, nullable=False)
        created_at = Column(DateTime(timezone=True), server_default=func.now())

