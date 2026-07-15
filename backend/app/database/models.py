from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.orm import declarative_base


Base = declarative_base()


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
