# SmartRecruit

Application FastAPI + React pour analyser une fiche de poste et classer des CV avec une approche RAG explicable.

Le projet contient un backend FastAPI et un frontend React/Vite.

## Idee du projet

SmartRecruit recoit une fiche de poste et un nombre libre de CV. La fiche de poste sert de reference d'evaluation, tandis que les CV sont les documents a analyser et a classer.

Le backend ne donne pas un score directement a partir du nom du fichier ou d'une base de resultats deja calculee. A chaque analyse, il relit les documents, extrait leur texte, structure les informations avec le LLM NVIDIA, vectorise les passages des CV avec le modele d'embedding NVIDIA, recherche les preuves pertinentes dans PostgreSQL, puis calcule un score explicable.

## Fonctionnement

- extraction de texte depuis PDF, DOCX, TXT et MD ;
- structuration de la fiche de poste et des CV par un modele NVIDIA appele via API ;
- normalisation des competences, diplomes, langues et intitules ;
- application de regles metier versionnees dans `backend/app/data/domain_rules.json` ;
- decoupage des sections de CV en chunks ;
- transformation des chunks en embeddings NVIDIA ;
- stockage des chunks vectorises dans PostgreSQL/pgvector avec SQLAlchemy ;
- historisation structuree des CV, fiches de poste et analyses dans PostgreSQL ;
- recherche semantique des preuves les plus proches de la fiche de poste ;
- scoring explicable par categories avec redistribution des poids sur les criteres presents ;
- classement final avec rang, score, forces, faiblesses et preuves.

## Architecture logique

```mermaid
flowchart TD
    A["PDF fiche de poste"] --> B["Extraction du texte brut"]
    C["PDF CV candidats"] --> D["Extraction du texte brut"]

    B --> E["LLM NVIDIA"]
    D --> F["LLM NVIDIA"]

    E --> G["JSON fiche de poste structuree<br/>competences, responsabilites, langues..."]
    F --> H["JSON CV structure<br/>nom, experiences, formation, skills..."]

    D --> I["Segmentation du texte CV<br/>sections: experience, skills, projets..."]
    I --> J["Decoupage en chunks"]
    J --> K["Modele embedding NVIDIA"]
    K --> L["Vecteurs des chunks CV"]
    L --> M["PostgreSQL<br/>table vector_chunks"]
    G --> DB1["PostgreSQL<br/>table jobs"]
    H --> DB2["PostgreSQL<br/>table resumes"]

    G --> N["Construction de la requete semantique<br/>criteres du poste"]
    N --> O["Modele embedding NVIDIA"]
    O --> P["Vecteur de requete"]

    P --> Q["Recherche semantique<br/>similarite cosinus"]
    M --> Q

    Q --> R["Passages pertinents / preuves RAG"]

    G --> S["Matching et scoring"]
    H --> S
    R --> S

    S --> T["Classement final<br/>scores, forces, faiblesses, preuves"]
    T --> DB3["PostgreSQL<br/>table analyses"]
    T --> U["Frontend React<br/>progression et resultats detailles"]
```

Le schema montre que le backend suit deux chemins complementaires apres l'extraction du texte. D'un cote, le texte brut de la fiche de poste et des CV est envoye au LLM NVIDIA pour etre transforme en JSON structure. De l'autre cote, le texte brut des CV est segmente puis decoupe en chunks, qui sont envoyes au modele d'embedding NVIDIA pour etre transformes en vecteurs et stockes temporairement dans PostgreSQL. Ensuite, les criteres extraits de la fiche de poste sont aussi vectorises afin de rechercher les passages de CV les plus proches semantiquement. Le scoring utilise enfin le JSON structure et les preuves RAG pour produire le classement final.

Important : les vecteurs sont isoles par un `namespace` propre a chaque analyse, puis supprimes a la fin du traitement. Cela evite de melanger les tests et garantit qu'un nouveau lancement relit les documents fournis.

## Arborescence utile

```text
backend/
  app/
    api/routes/              Endpoints FastAPI
    config.py                Configuration .env
    data/domain_rules.json   Regles metier versionnees pour extraction et matching
    database/                Base SQLAlchemy: resumes, jobs, analyses, vector_chunks
    infrastructure/          Clients NVIDIA API et stockage vectoriel PostgreSQL/pgvector
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
    free_port.py             Liberation controlee d'un port local
    initialize_databases.py  Application des migrations Alembic
    render_result_report.py  Generateur de rapport HTML
    run_backend.sh           Lancement FastAPI

frontend/
  src/App.tsx                 Interface upload, progression et resultats
  src/styles.css              Mise en page et design responsive
  package.json                Scripts Vite
```

## Prerequis

- Python 3.11 ou plus ;
- Node.js 18 ou plus pour le frontend ;
- PostgreSQL avec pgvector accessible localement ou via Docker Compose ;
- cle API NVIDIA ;
- modele LLM : `meta/llama-3.1-8b-instruct` ;
- modele embeddings : `nvidia/llama-nemotron-embed-1b-v2`.

## Configuration

Ne jamais versionner les vraies cles. Elles doivent rester dans `backend/.env` et, pour Vite, dans `frontend/.env.local`.

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
NVIDIA_MAX_TOKENS=8192
NVIDIA_TEMPERATURE=0
NVIDIA_SEED=0
NVIDIA_EMBEDDING_DIMENSIONS=
DATABASE_URL=postgresql+psycopg://smartrecruit:change_me@localhost:5432/smartrecruit
MAX_UPLOAD_MB=20
MAX_TOTAL_UPLOAD_MB=100
MAX_CV_FILES=20
SMARTRECRUIT_API_KEY=change_me_for_local_development
RATE_LIMIT_REQUESTS=20
RATE_LIMIT_WINDOW_SECONDS=60
JOB_WORKER_COUNT=2
EMBEDDING_BATCH_SIZE=32
LLM_INPUT_CHAR_LIMIT=12000
VECTOR_BACKEND=pgvector
```

Le frontend doit envoyer la meme cle API au backend :

```env
VITE_SMARTRECRUIT_API_KEY=change_me_for_local_development
VITE_MAX_UPLOAD_MB=20
VITE_MAX_TOTAL_UPLOAD_MB=100
VITE_MAX_CV_FILES=20
```

Le backend exige `SMARTRECRUIT_API_KEY` sur les routes d'analyse et de document. Les clients doivent envoyer `X-API-Key: <cle>` ou `Authorization: Bearer <cle>`. Si NVIDIA API ou PostgreSQL ne repond pas, l'analyse retourne une erreur generique cote client et garde les details dans les logs serveur.

## Lancement

Terminal 1 - PostgreSQL avec Docker Compose, si vous utilisez Docker :

```bash
cd ~/SmartRecruit/backend
docker compose down
docker compose up -d
python scripts/initialize_databases.py
```

Le compose utilise l'image `pgvector/pgvector:pg16`, lie le port a `127.0.0.1` et lit les identifiants depuis les variables `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` et `POSTGRES_PORT`. Changez au minimum `POSTGRES_PASSWORD` hors developpement local.

Si PostgreSQL est installe directement sur la machine, il faut que la base indiquee dans `DATABASE_URL` existe, que l'extension `vector` soit disponible, puis lancer les migrations avec `python scripts/initialize_databases.py`.

Terminal 2 - Backend FastAPI :

```bash
cd ~/SmartRecruit/backend
python scripts/free_port.py 8002 --yes --allowed-name python --allowed-name uvicorn

python -m uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8002
```

API : `http://127.0.0.1:8002`
Swagger : `http://127.0.0.1:8002/docs`

Terminal 3 - Frontend React :

```bash
cd ~/SmartRecruit/frontend
npm install
npm run dev
```

Interface : `http://127.0.0.1:5173`

## Endpoints principaux

`POST /api/ranking/analyze`

Form-data :

- `job_file` : fiche de poste ;
- `cv_files` : un ou plusieurs CV ;
- `top_k` : nombre de preuves semantiques recuperees par candidat.

Cette route reste disponible pour compatibilite, mais l'interface utilise le mode asynchrone :

- `POST /api/ranking/jobs` : cree une analyse et retourne `analysis_id` ;
- `GET /api/ranking/jobs/{analysis_id}` : suit l'etat, la progression et le resultat ;
- `DELETE /api/ranking/jobs/{analysis_id}` : demande l'annulation de l'analyse.

Les uploads sont lus par chunks, limites par fichier, par nombre de CV et par taille cumulee, stockes sous noms aleatoires dans un dossier temporaire par analyse, puis supprimes en fin de traitement.

## Tests

Backend :

```bash
cd ~/SmartRecruit/backend
python -m compileall app scripts tests alembic
ruff check .
mypy app
coverage run -m pytest tests/unit tests/test_health.py
coverage report
```

Frontend :

```bash
cd ~/SmartRecruit/frontend
npm run lint
npm run test
npm run build
npm audit
```

Tests d'integration avec NVIDIA API et PostgreSQL/pgvector actifs :

```bash
cd ~/SmartRecruit/backend
export SMARTRECRUIT_RUN_INTEGRATION=1
pytest tests/integration
```

## Confidentialite et dependances

- Les fichiers envoyes ne sont pas conserves apres l'analyse.
- Les logs doivent rester sans texte de CV ni contenu de fiche de poste ; ils utilisent des identifiants de correlation (`X-Request-ID`, `analysis_id`).
- Les dependances Python de production sont dans `backend/requirements.txt`, les dependances de developpement dans `backend/requirements-dev.txt`, et les verrous dans `backend/requirements.lock` / `backend/requirements-dev.lock`.
- PyMuPDF est utilise pour l'extraction PDF ; verifier sa licence et ses conditions de distribution avant tout usage commercial ou redistribution.
