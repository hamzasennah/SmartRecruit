# SmartRecruit

SmartRecruit est une application FastAPI + React qui analyse une fiche de poste et classe des CV avec un scoring explicable. Elle s'adresse a un contexte RH ou projet academique qui veut comparer des candidats sur des criteres visibles: competences, experience, responsabilites, formation, langues, certifications et preuves textuelles.

Le README sert de point d'entree. Les explications exhaustives sont dans [docs/](docs/README.md), et le code contient des commentaires sur les limites connues du scoring.

## Objectif

Le projet lit une fiche de poste et plusieurs CV, extrait leur texte, structure les informations avec un LLM NVIDIA, indexe des passages de CV avec des embeddings NVIDIA, retrouve des preuves pertinentes, puis calcule un classement final detaille.

Le but n'est pas de remplacer un recruteur: le score aide a trier et auditer, mais il reste dependant de la qualite des documents, des extractions et des regles de matching.

## Fonctionnalites

- Upload d'une fiche de poste et de plusieurs CV.
- Formats acceptes: PDF, DOCX, TXT, MD.
- Extraction structuree des jobs et CV avec NVIDIA API.
- Normalisation des competences, titres, langues, formations et dates.
- Recherche de preuves par embeddings et similarite vectorielle.
- Scoring par categories avec forces, faiblesses, manquants et preuves.
- Interface React avec suivi d'analyse asynchrone.
- Audit JSONL des appels modele, sans stocker le texte complet des CV.

## Stack Et Architecture

- Backend: FastAPI, Pydantic, SQLAlchemy, Alembic, httpx.
- Frontend: React, TypeScript, Vite, lucide-react.
- Documents: PyMuPDF pour PDF, python-docx pour DOCX.
- IA: `meta/llama-3.1-8b-instruct` pour l'extraction JSON, `nvidia/llama-nemotron-embed-1b-v2` pour les embeddings.
- Donnees: PostgreSQL pour CV/jobs/analyses/chunks.
- Vectoriel: configuration actuelle verifiee en local avec `VECTOR_BACKEND=json`; le mode `pgvector` existe dans le code mais demande l'extension PostgreSQL `vector`.

Flux resume:

```text
Documents -> parsing -> extraction LLM -> normalisation
          -> chunking + embeddings -> PostgreSQL -> retrieval
          -> matchers par categorie -> score final -> frontend
```

## Prerequis Verifies

Environnement local utilise pour verifier cette documentation:

- Python `3.13.13`
- Node.js `24.18.0`
- npm `11.16.0`
- Docker CLI `29.6.1`
- PostgreSQL local present sur le port `5432`

La configuration Python cible `py311` dans `pyproject.toml`; utilisez donc Python 3.11 ou plus.

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

Note: `npm ci` nettoie `node_modules`. Dans l'environnement verifie, cette commande a echoue car un serveur Vite existant verrouillait `esbuild.exe`; `npm install` a ete teste avec succes.

## Configuration

Backend:

- Creer `backend/.env` a partir de [backend/.env.example](backend/.env.example).
- Renseigner une vraie valeur `NVIDIA_API_KEY`.
- Renseigner `SMARTRECRUIT_API_KEY`; le frontend doit envoyer la meme valeur.
- Conserver `VECTOR_BACKEND=json` pour le mode local actuellement verifie.
- Renseigner `DATABASE_URL` vers une base PostgreSQL existante.

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

`VITE_API_URL=` vide fonctionne avec le frontend servi sur le meme domaine logique pendant le developpement. Pour un backend separe, utilisez par exemple `VITE_API_URL=http://127.0.0.1:8002`.

## Base De Donnees

La configuration locale actuelle est:

```env
VECTOR_BACKEND=json
```

Dans ce mode, les vecteurs sont stockes en JSON dans PostgreSQL et la similarite cosinus est calculee en Python. Cela evite de dependre de l'extension `vector`, mais reste moins adapte a de gros volumes qu'un index pgvector.

Le mode `pgvector` existe dans `backend/app/infrastructure/postgres_vector_store.py` et `backend/docker-compose.yml`, mais il n'a pas ete valide dans l'environnement actuel: Docker Desktop n'etait pas demarre, et le PostgreSQL local ne disposait pas de l'extension `vector`.

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

Ouvrir l'URL affichee par Vite. Le port normal est `http://127.0.0.1:5173`; dans l'environnement verifie, ce port etait deja occupe et Vite a demarre sur `http://127.0.0.1:5174`.

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

Les tests d'integration NVIDIA/PostgreSQL existent dans `backend/tests/integration/`, mais restent ignores par defaut via configuration d'environnement.

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
- Le mode local `VECTOR_BACKEND=json` est pratique pour developper, mais moins performant que `pgvector` pour de gros volumes.

## Documentation Complementaire

- [Index docs](docs/README.md)
- [Documentation technique complete LaTeX](docs/SmartRecruit_Documentation_Complete.tex)
- [Guide de compilation LaTeX](docs/LATEX_COMPILATION_GUIDE.md)
- [Rapport des commentaires de code](docs/code_comments_report.md)
