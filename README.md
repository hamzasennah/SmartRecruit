# SmartRecruit

Backend FastAPI pour analyser une fiche de poste et classer des CV avec une approche RAG explicable.

Le projet contient uniquement le backend pour le moment.

## Fonctionnement

- extraction de texte depuis PDF, DOCX, TXT et MD ;
- structuration de la fiche de poste et des CV par Qwen ;
- normalisation des competences, diplomes, langues et intitules ;
- decoupage des sections de CV en chunks ;
- transformation des chunks en embeddings Qwen ;
- stockage des chunks vectorises dans PostgreSQL avec SQLAlchemy ;
- recherche semantique des preuves les plus proches de la fiche de poste ;
- scoring explicable par categories avec redistribution des poids sur les criteres presents ;
- classement final avec rang, score, forces, faiblesses et preuves.

## Prerequis

- Python 3.11 ou plus ;
- Docker Compose pour PostgreSQL ;
- Ollama pour servir Qwen sur CPU ;
- modele LLM : `qwen2.5:7b` ;
- modele embeddings : `qwen3-embedding:0.6b`.

## Configuration

Exemple `.env` :

```env
QWEN_BASE_URL=http://127.0.0.1:11434/v1
QWEN_LLM_MODEL=qwen2.5:7b
QWEN_EMBEDDING_BASE_URL=http://127.0.0.1:11434/v1
QWEN_EMBEDDING_MODEL=qwen3-embedding:0.6b
DATABASE_URL=postgresql+psycopg2://smartrecruit:smartrecruit@localhost:5432/smartrecruit
MAX_UPLOAD_MB=20
```

Le backend utilise les services configures. Si Qwen, les embeddings ou PostgreSQL ne repondent pas, l'analyse retourne une erreur.

## Lancement CPU

Terminal 1 - PostgreSQL :

```bash
cd ~/SmartRecruit/backend
docker compose down
docker compose up -d
```

Terminal 2 - Serveur Qwen CPU :

```bash
cd ~/SmartRecruit/backend
python scripts/free_port.py 11434
ollama serve
```

Terminal 3 - Modeles Qwen :

```bash
ollama pull qwen2.5:7b
ollama pull qwen3-embedding:0.6b
```

Terminal 4 - FastAPI :

```bash
cd ~/SmartRecruit/backend
python scripts/free_port.py 8002

python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8002
```

API : `http://127.0.0.1:8002`
Swagger : `http://127.0.0.1:8002/docs`

## Endpoint principal

`POST /api/ranking/analyze`

Form-data :

- `job_file` : fiche de poste ;
- `cv_files` : un ou plusieurs CV ;
- `top_k` : nombre de preuves semantiques recuperees par candidat.

## Tests

Tests unitaires :

```bash
cd ~/SmartRecruit/backend
pytest tests/unit tests/test_health.py
python -m compileall app
```

Tests d'integration avec Qwen, embeddings et PostgreSQL actifs :

```bash
cd ~/SmartRecruit/backend
export SMARTRECRUIT_RUN_INTEGRATION=1
pytest tests/integration
```
