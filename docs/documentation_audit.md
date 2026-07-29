# Etat De La Documentation

## Structure

```text
README.md
docs/
  README.md
  SmartRecruit_Documentation_Complete.tex
  LATEX_COMPILATION_GUIDE.md
  code_comments_report.md
  documentation_audit.md
```

## Configuration De Reference

- Backend vectoriel: `VECTOR_BACKEND=pgvector`.
- Base locale: conteneur Docker `smartrecruit-db`, image `pgvector/pgvector:pg16`.
- Port PostgreSQL expose: `127.0.0.1:5433`.
- Extension PostgreSQL: `vector`.
- Version d'extension observee: `0.8.6`.
- Migration Alembic: `20260723_0001`.
- Colonne vectorielle: `vector_chunks.embedding vector(2048)`.
- Mode `json`: alternative explicite de developpement, sans bascule automatique depuis pgvector.

## Commandes Documentees

Backend:

```powershell
cd backend
python -m pip install -r requirements-dev.txt
docker compose up -d
docker exec smartrecruit-db psql -U postgres -d smartrecruit -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker exec smartrecruit-db psql -U postgres -d smartrecruit -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"
python scripts/initialize_databases.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
python -m ruff check app tests scripts
python -m pytest tests -q
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
npm run lint
npm test -- --run
npm run build
```

## Documentation Technique

- Le README racine sert de guide de demarrage.
- `docs/SmartRecruit_Documentation_Complete.tex` contient la documentation technique approfondie.
- `docs/code_comments_report.md` liste les commentaires de code et les roles de fichiers.
- `docs/LATEX_COMPILATION_GUIDE.md` decrit les conditions de compilation du document LaTeX.
