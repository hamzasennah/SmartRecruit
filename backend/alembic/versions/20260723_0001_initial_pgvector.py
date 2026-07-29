from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260723_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "resumes",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("candidate_name", sa.String(length=255), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("text_preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_resumes_filename", "resumes", ["filename"])
    op.create_index("ix_resumes_candidate_name", "resumes", ["candidate_name"])
    op.create_index("ix_resumes_content_hash", "resumes", ["content_hash"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("text_preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_filename", "jobs", ["filename"])
    op.create_index("ix_jobs_job_title", "jobs", ["job_title"])
    op.create_index("ix_jobs_content_hash", "jobs", ["content_hash"])

    op.create_table(
        "analyses",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("namespace", sa.String(length=120), nullable=False),
        sa.Column("job_id", sa.String(length=64), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("total_candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_analyses_namespace", "analyses", ["namespace"])
    op.create_index("ix_analyses_job_id", "analyses", ["job_id"])

    op.create_table(
        "vector_chunks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("namespace", sa.String(length=120), nullable=False),
        sa.Column("document_id", sa.String(length=255), nullable=False),
        sa.Column("section", sa.String(length=80), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("vector_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "namespace",
            "document_id",
            "section",
            "chunk_index",
            name="uq_vector_chunks_namespace_document_section_index",
        ),
    )
    # The configured NVIDIA embedding model returns 2048-dimensional vectors;
    # pgvector HNSW indexes require this dimension to be declared on the column.
    op.execute("ALTER TABLE vector_chunks ADD COLUMN embedding vector(2048)")
    op.create_index("ix_vector_chunks_namespace", "vector_chunks", ["namespace"])
    op.create_index("ix_vector_chunks_document_id", "vector_chunks", ["document_id"])
    op.create_index("ix_vector_chunks_section", "vector_chunks", ["section"])
    op.create_index("ix_vector_chunks_namespace_document", "vector_chunks", ["namespace", "document_id"])
    # HNSW on the vector type is limited to 2000 dimensions in pgvector; the
    # current NVIDIA embedding model returns 2048 dimensions. Search still uses
    # pgvector's cosine operator, while approximate indexing would need halfvec
    # or a projected embedding dimension in a later migration.


def downgrade() -> None:
    op.drop_table("vector_chunks")
    op.drop_table("analyses")
    op.drop_table("jobs")
    op.drop_table("resumes")

# Role dans le projet:
# Ce fichier cree le schema PostgreSQL initial. Il definit les tables d'analyses, documents et chunks vectoriels utilises par le pipeline.
