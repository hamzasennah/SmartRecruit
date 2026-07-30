# SmartRecruit

SmartRecruit est une application FastAPI + React qui analyse une fiche de poste et classe des CV avec un scoring explicable. Elle s'adresse a un contexte RH ou academique qui veut comparer des candidats sur des criteres visibles: competences, experience, responsabilites, formation, langues, certifications et preuves textuelles.

Le projet utilise NVIDIA API pour l'extraction structuree et les embeddings, PostgreSQL avec pgvector pour la recherche vectorielle, et une interface React pour le suivi et la consultation du classement.

## Deroulement

```mermaid
flowchart LR
    A["Fiche de poste<br/>+ CV"]:::input
    B["Parsing<br/>PDF, DOCX, TXT, MD"]:::process
    C["Extraction LLM NVIDIA<br/>donnees structurees"]:::ai
    D["Normalisation<br/>competences, dates, langues"]:::process
    E["Chunking CV<br/>+ embeddings NVIDIA"]:::ai
    F[("PostgreSQL<br/>pgvector")]:::db
    G["Retrieval<br/>preuves textuelles"]:::process
    H["Matching metier<br/>competences, experience, langues"]:::process
    I["Scoring explicable<br/>forces, faiblesses, manquants"]:::score
    J["Classement<br/>candidats ordonnes"]:::score
    K["Interface React<br/>resultats et details"]:::output

    A --> B --> C --> D
    D --> E --> F --> G --> H
    D --> H
    H --> I --> J --> K

    classDef input fill:#eef6ff,stroke:#2563eb,color:#111827,stroke-width:1px;
    classDef process fill:#f8fafc,stroke:#64748b,color:#111827,stroke-width:1px;
    classDef ai fill:#fef3c7,stroke:#d97706,color:#111827,stroke-width:1px;
    classDef db fill:#ecfdf5,stroke:#059669,color:#111827,stroke-width:1px;
    classDef score fill:#f3e8ff,stroke:#7c3aed,color:#111827,stroke-width:1px;
    classDef output fill:#fee2e2,stroke:#dc2626,color:#111827,stroke-width:1px;
```

## Objectif

SmartRecruit transforme une fiche de poste et une liste de CV en classement detaille. Le score aide a trier et auditer les candidatures, tout en restant dependant de la qualite des documents, des extractions et des regles de matching.

## Fonctionnalites

- Upload d'une fiche de poste et de plusieurs CV.
- Formats acceptes: PDF, DOCX, TXT, MD.
- Extraction structuree des jobs et CV avec NVIDIA API.
- Normalisation des competences, titres, langues, formations et dates.
- Recherche de preuves par embeddings et similarite vectorielle pgvector.
- Scoring par categories avec forces, faiblesses, manquants et preuves.
- Interface React avec suivi d'analyse asynchrone.
- Audit JSONL des appels modele, sans stocker le texte complet des CV.

## Stack Et Architecture

- Backend: FastAPI, Pydantic, SQLAlchemy, Alembic, httpx.
- Frontend: React, TypeScript, Vite, lucide-react.
- Documents: PyMuPDF pour PDF, python-docx pour DOCX.
- IA: `meta/llama-3.1-8b-instruct` pour l'extraction JSON, `nvidia/llama-nemotron-embed-1b-v2` pour les embeddings.
- Donnees: PostgreSQL pour CV, jobs, analyses et chunks.
- Vectoriel: PostgreSQL avec extension pgvector.

Flux technique resume:

```text
Documents -> parsing -> extraction LLM -> normalisation
          -> chunking + embeddings -> PostgreSQL/pgvector -> retrieval
          -> matchers par categorie -> score final -> frontend
```

## Prerequis

- Python 3.11 ou plus.
- Node.js et npm.
- Docker Desktop.
- Une cle `NVIDIA_API_KEY`.
- PostgreSQL/pgvector via Docker, conteneur `smartrecruit-db`, image `pgvector/pgvector:pg16`, port `127.0.0.1:5433`.

La configuration Python cible `py311` dans `pyproject.toml`.

## Installation

Backend:

```powershell
cd backend
python -m pip install -r requirements-dev.txt
```

Frontend:

```powershell
cd frontend
npm install
```

## Configuration

Backend:

- Creer `backend/.env` a partir de [backend/.env.example](backend/.env.example).
- Renseigner `NVIDIA_API_KEY`.
- Renseigner `SMARTRECRUIT_API_KEY`; le frontend doit envoyer la meme valeur.
- Utiliser `VECTOR_BACKEND=pgvector`.
- Utiliser `DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5433/smartrecruit` avec la configuration Docker fournie.

Frontend:

- Creer `frontend/.env.local`.
- Renseigner au minimum:

```env
VITE_API_URL=
VITE_SMARTRECRUIT_API_KEY=change_me_for_local_development
VITE_MAX_UPLOAD_MB=20
VITE_MAX_TOTAL_UPLOAD_MB=100
VITE_MAX_CV_FILES=20
```

`VITE_API_URL=` vide utilise le proxy Vite vers le backend local. Pour un backend separe, utiliser par exemple `VITE_API_URL=http://127.0.0.1:8002`.

## Base De Donnees

Le backend vectoriel actif est pgvector:

```env
VECTOR_BACKEND=pgvector
```

Les embeddings sont stockes dans `vector_chunks.embedding` en `vector(2048)`, dimension du modele `nvidia/llama-nemotron-embed-1b-v2`. La recherche utilise l'operateur cosinus pgvector `<=>`.

Le fichier [backend/docker-compose.yml](backend/docker-compose.yml) lance PostgreSQL/pgvector sur `127.0.0.1:5433`.

Commandes de preparation:

```powershell
cd backend
docker compose up -d
docker exec smartrecruit-db psql -U postgres -d smartrecruit -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker exec smartrecruit-db psql -U postgres -d smartrecruit -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"
python scripts/initialize_databases.py
```

La migration cree `vector_chunks.embedding` en `vector(2048)`. Aucun index HNSW n'est defini sur cette colonne, car pgvector limite les index HNSW sur le type `vector` a 2000 dimensions.

## Demarrage

Terminal backend:

```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
```

Verification rapide:

```text
http://127.0.0.1:8002/api/health
```

Terminal frontend:

```powershell
cd frontend
npm run dev
```

Ouvrir l'URL affichee par Vite.

## Tests

Backend:

```powershell
cd backend
python -m ruff check app tests scripts
python -m pytest tests -q
```

Frontend:

```powershell
cd frontend
npm run lint
npm test -- --run
npm run build
```

Les tests d'integration NVIDIA/PostgreSQL sont dans `backend/tests/integration/` et s'activent via configuration d'environnement.

## Structure Du Projet

```text
backend/
  app/
    api/routes/          Routes FastAPI
    core/                Configuration transverse, securite, logs, audit
    data/                Regles et alias JSON
    database/            Modeles et sessions SQLAlchemy
    infrastructure/      Clients NVIDIA et stockage vectoriel
    schemas/             Contrats Pydantic
    services/            Parsing, extraction, normalisation, RAG, scoring
  tests/                 Tests unitaires et integration optionnelle

frontend/
  src/                   Application React et validation client

docs/
  README.md              Index de documentation
  SmartRecruit_Documentation_Complete.tex
  LATEX_COMPILATION_GUIDE.md
  code_comments_report.md
```

## Limitations Connues

- Le vocabulaire de reference peut etre desequilibre entre familles de metier; ce biais doit etre mesure avec un jeu de CV varie.
- Plusieurs matchers utilisent des intersections de mots-cles et des alias; ils ne comprennent pas toutes les formulations semantiquement equivalentes.
- La similarite par tokens de type Jaccard peut penaliser des textes longs mais pertinents.
- Certains scores `0.0` representent une absence de signal ou une categorie non applicable, pas toujours une faiblesse reelle du candidat.
- Les poids de scoring sont fixes et globaux; ils ne s'adaptent pas encore au type de poste.
- Le mode pgvector exige une base PostgreSQL avec l'extension `vector`.

## Documentation Complementaire

- [Index docs](docs/README.md)
- [Documentation technique complete LaTeX](docs/SmartRecruit_Documentation_Complete.tex)
- [Guide de compilation LaTeX](docs/LATEX_COMPILATION_GUIDE.md)
- [Rapport des commentaires de code](docs/code_comments_report.md)
