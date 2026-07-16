# SmartRecruit

Backend FastAPI pour analyser une fiche de poste et classer des CV avec une approche RAG explicable.

Le projet contient uniquement le backend pour le moment.

## Fonctionnement

- extraction de texte depuis PDF, DOCX, TXT et MD ;
- structuration de la fiche de poste et des CV par un modele NVIDIA appele via API ;
- normalisation des competences, diplomes, langues et intitules ;
- decoupage des sections de CV en chunks ;
- transformation des chunks en embeddings NVIDIA ;
- stockage des chunks vectorises dans PostgreSQL avec SQLAlchemy ;
- recherche semantique des preuves les plus proches de la fiche de poste ;
- scoring explicable par categories avec redistribution des poids sur les criteres presents ;
- classement final avec rang, score, forces, faiblesses et preuves.

## Arborescence utile

```text
backend/
  app/
    api/routes/              Endpoints FastAPI
    config.py                Configuration .env
    database/                Base SQLAlchemy et table vector_chunks
    infrastructure/          Clients NVIDIA API et stockage vectoriel PostgreSQL
    schemas/                 Modeles Pydantic
    services/
      documents/             Lecture PDF/DOCX/TXT/MD et segmentation
      extraction/            Prompts stricts et validation JSON
      normalization/         Normalisation des valeurs extraites
      experience/            Calcul de duree et pertinence experience
      retrieval/             Chunking, embeddings, recherche semantique
      matching/              Matching par categorie
      scoring/               Score final et explications
      orchestration/         Pipeline complet fiche + CV + ranking
  scripts/
    check_nvidia_api.py      Test reel NVIDIA API
    free_port.py             Liberation d'un port local
    initialize_databases.py  Creation des tables PostgreSQL
    run_backend.sh           Lancement FastAPI
```

## Prerequis

- Python 3.11 ou plus ;
- Docker Compose pour PostgreSQL ;
- cle API NVIDIA ;
- modele LLM : `meta/llama-3.1-8b-instruct` ;
- modele embeddings : `nvidia/llama-nemotron-embed-1b-v2`.

## Configuration

Ne jamais versionner la vraie cle API. Elle doit rester dans `.env`.

Exemple `.env` :

```env
NVIDIA_API_KEY=your_nvidia_api_key_here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_LLM_MODEL=meta/llama-3.1-8b-instruct
NVIDIA_EMBEDDING_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_EMBEDDING_MODEL=nvidia/llama-nemotron-embed-1b-v2
NVIDIA_TIMEOUT=120
NVIDIA_MAX_RETRIES=2
NVIDIA_RETRY_DELAY=2
NVIDIA_MAX_TOKENS=1400
NVIDIA_TEMPERATURE=0.0
NVIDIA_EMBEDDING_DIMENSIONS=
DATABASE_URL=postgresql+psycopg2://smartrecruit:smartrecruit@localhost:5432/smartrecruit
MAX_UPLOAD_MB=20
```

Le backend utilise les services configures. Si NVIDIA API ou PostgreSQL ne repond pas, l'analyse retourne une erreur.

## Lancement

Terminal 1 - PostgreSQL :

```bash
cd ~/SmartRecruit/backend
docker compose down
docker compose up -d
```

Terminal 2 - Backend FastAPI :

```bash
cd ~/SmartRecruit/backend
python scripts/free_port.py 8002

python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8002
```

API : `http://127.0.0.1:8002`
Swagger : `http://127.0.0.1:8002/docs`

## Verification NVIDIA API

Cette commande fait de vrais appels a NVIDIA API : liste des modeles, generation JSON et embedding.

```bash
cd ~/SmartRecruit/backend
python scripts/check_nvidia_api.py
```

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

Tests d'integration avec NVIDIA API et PostgreSQL actifs :

```bash
cd ~/SmartRecruit/backend
export SMARTRECRUIT_RUN_INTEGRATION=1
pytest tests/integration
```
