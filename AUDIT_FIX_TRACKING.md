# Suivi des corrections d'audit SmartRecruit

| ID audit | Probleme | Correction appliquee | Preuve de validation | Statut |
| -------- | -------- | -------------------- | -------------------- | ------ |
| SR-AUD-001 | Endpoint d'analyse sans authentification ni rate limiting | Cle API obligatoire, rate limiting en memoire, quotas upload, ecoute locale documentee | Tests API auth/rate limit, README | Corrige |
| SR-AUD-002 | Limites d'upload non appliquees | Upload par chunks, limite par fichier, nombre de CV, taille cumulee, validation extension/signature | Tests uploads | Corrige |
| SR-AUD-003 | Uploads conserves et noms non uniques | Dossier temporaire par analyse, noms UUID, nettoyage `finally` et jobs | Tests nettoyage/unicite | Corrige |
| SR-AUD-004 | Exceptions internes exposees | Messages client generiques, logs serveur avec `analysis_id`/`X-Request-ID` | Tests non-divulgation, lint | Corrige |
| SR-AUD-005 | Pipeline synchrone dans route async | Route historique via threadpool, endpoints jobs asynchrones avec statut/progression/annulation | Tests job API | Corrige |
| SR-AUD-006 | Vector store JSON non scalable | Backend pgvector par defaut, SQL `ORDER BY embedding <=>`, fallback JSON explicite | Tests vector helper, Alembic head | Corrige |
| SR-AUD-007 | Absence migrations/contraintes DB | Alembic ajoute, FK/index/contrainte unique, `initialize_databases.py` applique les migrations | `alembic heads`, compileall | Corrige |
| SR-AUD-008 | `.env` racine suivi et ignore incomplet | `.env` ignore et retire de l'index Git sans supprimer le fichier local | `git status`, `.gitignore` | Corrige |
| SR-AUD-009 | Driver PostgreSQL incoherent | DSN aligne sur `postgresql+psycopg://`, requirements psycopg v3 | README, `.env.example` | Corrige |
| SR-AUD-010 | Identifiants PostgreSQL faibles et port expose | Compose lit variables env, mot de passe exemple change, port lie a `127.0.0.1` | README, docker-compose | Corrige |
| SR-AUD-011 | Rapports contenant texte complet CV | Texte brut masque par defaut, option `--include-raw-text` explicite | Test rapport privacy | Corrige |
| SR-AUD-012 | `free_port.py` dangereux | Confirmation/filtrage processus, usage auto limite a python/uvicorn dans run script | Test script | Corrige |
| SR-AUD-013 | Score langues ignore niveau | Score pondere par niveau requis, details `below_required_level` conserves | Tests scoring langues | Corrige |
| SR-AUD-014 | Experience mixte dates/durees mal comptee | Addition des periodes datees fusionnees et durees explicites non datees | Tests experience | Corrige |
| SR-AUD-015 | Formation trop permissive et domaines ignores | Niveau requis inconnu non auto-valide, champs acceptes pris en compte | Tests education | Corrige |
| SR-AUD-016 | Certifications/domaines non exploites | Matcher certifications/domaines branche au scoring avec poids dedie | Tests cert/domain | Corrige |
| SR-AUD-017 | Heuristiques metier codees en dur | Regles principales externalisees dans `backend/app/data/domain_rules.json` et chargees par CV/job/responsibility | Test loader + tests scoring/extraction | Corrige |
| SR-AUD-018 | Duplication coercition/deduplication | Module commun `extraction/coercion.py`, helper `dedupe_by_normalized_key` partage | Tests coercion/normalization | Corrige |
| SR-AUD-019 | `full_text` ambigu | `full_text` reste toujours le texte complet ; sections detectees separees | Test segmentation | Corrige |
| SR-AUD-020 | Troncature silencieuse et batch embeddings non borne | Limite LLM configuree avec log de troncature sans PII, batch embeddings configurable | Tests batching | Corrige |
| SR-AUD-021 | Frontend sans validation/annulation/progression reelle | Validation client, cle API Vite, endpoints jobs, polling, annulation AbortController | `npm run lint/test/build` | Corrige |
| SR-AUD-022 | Dependances frontend mal classees/types decales | Dev deps separees, types React alignes, Vitest mis a jour | `npm audit` 0 vuln. | Corrige |
| SR-AUD-023 | Dependances Python non verrouillees/dev-prod/licence | Prod/dev requirements separes, lockfiles, mention licence PyMuPDF | CI config, README | Corrige |
| SR-AUD-024 | Absence CI/lint/type/couverture | Workflow GitHub Actions, Ruff, mypy, coverage 70%, frontend lint/test/build/audit | Validations locales | Corrige |
| SR-AUD-025 | Tests surfaces critiques manquants | Tests auth/uploads/privacy/free_port/jobs/retrieval/vector/scoring/frontend | 71 tests backend + 4 tests frontend | Corrige |
| SR-AUD-026 | Observabilite minimale | Middleware `X-Request-ID`, contexte `analysis_id`, logs sans contenu CV/JD, statut job | Tests API + revue logs | Corrige partiellement |
| SR-AUD-027 | Code mort/non utilise | Suppression `NvidiaEmbeddingClient.embed`, `normalize_job_titles`; champs publics conserves | `rg`, Ruff/mypy | Corrige partiellement |
| SR-AUD-028 | Fichiers monolithiques | Extraction validation frontend, upload manager, job manager, coercion, domain rules | Build/tests | Corrige partiellement |
