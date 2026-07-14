# SmartRecruit

Backend FastAPI pour classer des CV par rapport a une fiche de poste avec une approche hybride :

- extraction de texte depuis PDF/DOCX/TXT/MD ;
- structuration CV et fiche de poste ;
- normalisation des competences, diplomes, langues et intitules ;
- calcul Python des durees d'experience et fusion des periodes chevauchantes ;
- retrieval semantique par sections avec embeddings Qwen et Qdrant ;
- scoring explicable par categories, avec redistribution des poids sur les criteres reellement presents dans la fiche de poste ;
- calcul de l'experience utile uniquement sur les periodes jugees pertinentes pour le poste ;
- classement final avec forces, faiblesses et preuves.

Le projet contient uniquement le backend pour le moment.

## Lancement local

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

API : [http://127.0.0.1:8001](http://127.0.0.1:8001)  
Swagger : [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)

## Services externes

Le backend est prepare pour :

- LLM Qwen via vLLM endpoint OpenAI-compatible ;
- embeddings Qwen via endpoint `/embeddings` ;
- Qdrant comme base vectorielle ;
- Postgres pour la persistence future.

Pour demarrer Qdrant et Postgres :

```powershell
cd backend
docker compose up -d
```

## Endpoint principal

`POST /api/ranking/analyze`

Form-data :

- `job_file` : fiche de poste ;
- `cv_files` : un ou plusieurs CV ;
- `top_k` : nombre de preuves semantiques recuperees par candidat.

## Tests

Les tests activent `SMARTRECRUIT_TEST_MODE=1`. Ce mode utilise des embeddings deterministes et ne depend pas d'un serveur GPU.

```powershell
cd backend
pytest
python -m compileall app
```
