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
- environnement GPU avec vLLM ;
- modele LLM : `Qwen/Qwen3.5-9B` ;
- modele embeddings : `Qwen/Qwen3-Embedding-0.6B`.

## Configuration

Exemple `.env` :

```env
QWEN_BASE_URL=http://127.0.0.1:8000/v1
QWEN_LLM_MODEL=Qwen/Qwen3.5-9B
QWEN_EMBEDDING_BASE_URL=http://127.0.0.1:8003/v1
QWEN_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
DATABASE_URL=postgresql+psycopg2://smartrecruit:smartrecruit@localhost:5432/smartrecruit
MAX_UPLOAD_MB=20
```

Le backend utilise les services configures. Si Qwen, les embeddings ou PostgreSQL ne repondent pas, l'analyse retourne une erreur.

## Lancement sur Lightning AI

Terminal 1 — PostgreSQL :

```bash
cd ~/SmartRecruit/backend
docker compose down
docker compose up -d
```

Terminal 2 — Qwen LLM :

```bash
cd ~/SmartRecruit/backend
python scripts/free_port.py 8000
source .venv-vllm/bin/activate

vllm serve Qwen/Qwen3.5-9B \
  --host 127.0.0.1 \
  --port 8000 \
  --dtype auto \
  --gpu-memory-utilization 0.90 \
  --max-model-len 4096 \
  --max-num-seqs 1 \
  --enforce-eager
```

Terminal 3 — Qwen embeddings :

```bash
cd ~/SmartRecruit/backend
python scripts/free_port.py 8003
source .venv-vllm/bin/activate

vllm serve Qwen/Qwen3-Embedding-0.6B \
  --host 127.0.0.1 \
  --port 8003 \
  --dtype auto \
  --max-model-len 4096 \
  --max-num-seqs 8 \
  --enforce-eager
```

Terminal 4 — FastAPI :

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
cd backend
pytest tests/unit tests/test_health.py
python -m compileall app
```

Tests d'integration avec Qwen, embeddings et PostgreSQL actifs :

```bash
cd backend
export SMARTRECRUIT_RUN_INTEGRATION=1
pytest tests/integration
```
