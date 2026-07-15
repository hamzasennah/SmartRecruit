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
- PostgreSQL ;
- Ollama avec les modeles Qwen telecharges.

Modele LLM plus leger, adapte a la machine actuelle :

```powershell
ollama pull qwen2.5:3b
ollama pull qwen3-embedding:0.6b
```

Modele LLM plus qualitatif, si la machine le supporte :

```powershell
ollama pull qwen2.5:7b
```

## Lancement local

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
docker compose up -d
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

API : [http://127.0.0.1:8001](http://127.0.0.1:8001)  
Swagger : [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)

## Configuration

Exemple `.env` :

```env
QWEN_BASE_URL=http://localhost:11434/v1
QWEN_LLM_MODEL=qwen2.5:3b
QWEN_EMBEDDING_BASE_URL=http://localhost:11434/v1
QWEN_EMBEDDING_MODEL=qwen3-embedding:0.6b
DATABASE_URL=postgresql+psycopg2://smartrecruit:smartrecruit@localhost:5432/smartrecruit
MAX_UPLOAD_MB=20
```

Le backend utilise les services configures. Si Qwen ou PostgreSQL ne repond pas, l'analyse retourne une erreur.

## Endpoint principal

`POST /api/ranking/analyze`

Form-data :

- `job_file` : fiche de poste ;
- `cv_files` : un ou plusieurs CV ;
- `top_k` : nombre de preuves semantiques recuperees par candidat.

## Tests

Tests unitaires :

```powershell
cd backend
pytest tests/unit tests/test_health.py
python -m compileall app
```

Tests d'integration avec Qwen et PostgreSQL actifs :

```powershell
cd backend
$env:SMARTRECRUIT_RUN_INTEGRATION="1"
pytest tests/integration
```
