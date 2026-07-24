# Rapport de correction d'audit - SmartRecruit

Date : 2026-07-23

## Synthese

Les 28 points de l'audit ont ete traites.

- 25 points sont corriges.
- 3 points sont corriges partiellement et documentes comme suites de durcissement : observabilite avancee, nettoyage complet de contrat public, decomposition plus large des gros fichiers.
- Aucun CV reel n'a ete modifie ni ouvert pour verifier son contenu.
- `.env` a ete retire de l'index Git et reste ignore localement.

Le detail point par point est dans `AUDIT_FIX_TRACKING.md`.

## Corrections principales

### Securite API et uploads

- Ajout d'une authentification par `SMARTRECRUIT_API_KEY` sur les routes ranking/documents.
- Ajout d'un rate limiter en memoire par cle ou IP.
- Ajout de quotas : taille fichier, nombre de CV, taille cumulee.
- Lecture des uploads par chunks, validation d'extension/signature minimale, noms UUID.
- Dossiers temporaires par analyse et nettoyage garanti.
- Messages d'erreur client generiques ; details conserves cote serveur.
- `run_backend.sh` et README utilisent `127.0.0.1` par defaut.

### Jobs et disponibilite

- `POST /api/ranking/jobs` cree une analyse asynchrone.
- `GET /api/ranking/jobs/{analysis_id}` expose statut/progression/resultat.
- `DELETE /api/ranking/jobs/{analysis_id}` demande l'annulation.
- La route historique `/api/ranking/analyze` execute le pipeline synchrone dans un threadpool.

### Donnees et pgvector

- Ajout d'Alembic et d'une migration initiale pgvector.
- Ajout de contraintes/index et FK `analyses.job_id -> jobs.id`.
- `PostgresVectorStore` utilise pgvector par defaut avec recherche SQL indexable.
- Le fallback JSON reste explicite via `VECTOR_BACKEND=json`.
- `initialize_databases.py` applique les migrations au lieu de `create_all`.

### Confidentialite

- Les rapports locaux masquent le texte brut des documents par defaut.
- `--include-raw-text` est requis pour inclure explicitement le texte extrait.
- Les logs ajoutent `X-Request-ID` et `analysis_id` sans journaliser le contenu CV/JD.

### Scoring

- Langues : score pondere par niveau requis.
- Experience : periodes datees et durees explicites additionnees sans branche exclusive.
- Formation : niveau requis inconnu non auto-valide, champs acceptes pris en compte.
- Certifications/domaines : matcher branche au scoring avec poids dedie.
- Heuristiques principales externalisees dans `backend/app/data/domain_rules.json`.

### Frontend

- Validation client des extensions, tailles et nombre de CV.
- Envoi de la cle API via `VITE_SMARTRECRUIT_API_KEY`.
- Progression basee sur le statut serveur.
- Annulation via `AbortController` et endpoint job.
- Dependances build deplacees en `devDependencies`, types React alignes, Vitest mis a jour.

### Qualite, CI et dependances

- Ajout de `pyproject.toml` : pytest, coverage, Ruff, mypy.
- Ajout de `.github/workflows/ci.yml`.
- Separation `requirements.txt` / `requirements-dev.txt`.
- Ajout de lockfiles backend.
- Mention de la licence PyMuPDF dans le README.
- Factorisation des coercions LLM et de la deduplication.
- Suppression de deux elements morts confirmes.

## Validations locales

- `ruff check backend` : OK.
- `mypy backend/app` : OK, 75 modules.
- `python -m compileall backend\app backend\scripts backend\tests backend\alembic` : OK.
- `coverage run -m pytest backend\tests\unit backend\tests\test_health.py` : OK, 71 tests passes.
- `coverage report` : OK, couverture globale 77% pour un seuil CI de 70%.
- `alembic -c alembic.ini heads` : OK, `20260723_0001 (head)`.
- `pytest backend\tests\integration` : 2 tests skips attendus sans NVIDIA API/PostgreSQL actifs.
- `npm.cmd run lint` : OK.
- `npm.cmd run test` : OK, 4 tests passes.
- `npm.cmd run build` : OK.
- `npm.cmd audit` : OK, 0 vulnerabilite.

## Points restant a durcir avant production

- SR-AUD-026 : ajouter logs JSON, metriques, traces et durees par etape si deploiement service.
- SR-AUD-027 : decider si les champs publics conserves comme `CategoryScore.evidence` restent dans le contrat API ou doivent etre retires lors d'une version majeure.
- SR-AUD-028 : poursuivre la decomposition UI et scripts de rendu au-dela des extractions deja faites.
- Lancer les tests d'integration avec PostgreSQL/pgvector et NVIDIA API reels avant toute mise en production.
- Faire valider juridiquement la licence PyMuPDF selon le mode de distribution cible.
