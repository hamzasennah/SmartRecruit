from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class ResumeRecord(Base):
    __tablename__ = "resumes"

    id = Column(String(64), primary_key=True)
    filename = Column(String(255), nullable=False, index=True)
    candidate_name = Column(String(255), nullable=True, index=True)
    content_hash = Column(String(64), nullable=False, index=True)
    text_preview = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class JobRecord(Base):
    __tablename__ = "jobs"

    id = Column(String(64), primary_key=True)
    filename = Column(String(255), nullable=False, index=True)
    job_title = Column(String(255), nullable=True, index=True)
    content_hash = Column(String(64), nullable=False, index=True)
    text_preview = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AnalysisRecord(Base):
    __tablename__ = "analyses"

    id = Column(String(64), primary_key=True)
    namespace = Column(String(120), nullable=False, index=True)
    job_id = Column(String(64), nullable=True, index=True)
    total_candidates = Column(Integer, nullable=False, default=0)
    summary = Column(Text, nullable=False, default="")
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class VectorChunkRecord(Base):
    __tablename__ = "vector_chunks"

    id = Column(String(64), primary_key=True)
    namespace = Column(String(120), nullable=False, index=True)
    document_id = Column(String(255), nullable=False, index=True)
    section = Column(String(80), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    vector_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
