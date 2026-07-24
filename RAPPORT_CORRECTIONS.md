# Rapport corrections - SmartRecruit

Date : 2026-07-24

## Resume executif

- Mission A : les 28 problemes de `AUDIT_REPORT.md` ont ete revalides dans le code actuel.
- Resultat Mission A : 25 problemes corriges, 3 corriges partiellement car ils demandent encore une decision d'exploitation ou de contrat public.
- Mission B : la premiere source non deterministe confirmee est l'extraction factuelle via LLM NVIDIA : `NVIDIA_TEMPERATURE=0.1` et absence de `seed` dans le payload.
- Correction Mission B : temperature par defaut a `0`, ajout de `NVIDIA_SEED`, envoi de `seed` et `top_p=1` dans les appels `/chat/completions`.
- Validation : `ruff`, `mypy`, `pytest` unitaires, diagnostic reproductibilite en 5 runs offline avec scores et hashes strictement identiques.

Source externe utilisee pour Mission B : la documentation officielle NVIDIA indique que plus la temperature est elevee, moins la sortie est deterministe, et que fixer `seed` permet la reproductibilite si les autres hyperparametres sont fixes : https://docs.api.nvidia.com/nim/reference/google-codegemma-7b-infer

## Section 1 - Corrections issues de l'audit

### [SR-AUD-001] - Endpoint d'analyse couteux expose sans authentification ni rate limiting
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/app/api/routes/ranking.py`, `backend/app/core/security.py`, `backend/app/config.py`, `README.md`
- Correction appliquee : cle API obligatoire, rate limiting sur les endpoints couteux, quotas upload, lancement local sur `127.0.0.1`.
- Risque de regression estime : Moyen
- Verification effectuee : `pytest backend/tests/unit/test_api_security_uploads.py`, `pytest backend/tests/unit/test_jobs_and_retrieval.py`
- Justification : le code actuel protege deja les routes. Ajustement recent conserve le rate limit sur `POST /analyze` et `POST /jobs`, mais retire sa consommation sur le polling `GET /jobs/{id}`.

### [SR-AUD-002] - Limites d'upload non appliquees
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/app/services/documents/upload_manager.py`, `backend/app/api/routes/ranking.py`, `backend/app/api/routes/documents.py`
- Correction appliquee : lecture par chunks, taille maximale par fichier, nombre maximal de CV, taille cumulee, validation extension/signature.
- Risque de regression estime : Moyen
- Verification effectuee : tests uploads dans `test_api_security_uploads.py`
- Justification : aucune correction supplementaire requise.

### [SR-AUD-003] - Uploads conserves, noms non uniques et risque d'ecrasement
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/app/services/documents/upload_manager.py`, routes ranking/documents
- Correction appliquee : repertoire temporaire par analyse, noms UUID, nettoyage `finally`.
- Risque de regression estime : Moyen
- Verification effectuee : test de nettoyage et preservation du nom original.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-004] - Details d'exceptions internes exposes au client
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/app/api/routes/ranking.py`, `backend/app/api/routes/documents.py`, `backend/app/services/orchestration/batch_ranking_pipeline.py`
- Correction appliquee : messages client generiques et logs serveur avec identifiants de correlation.
- Risque de regression estime : Faible
- Verification effectuee : tests API + relecture des `HTTPException`.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-005] - Pipeline synchrone long execute dans une route async
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/app/api/routes/ranking.py`, `backend/app/services/orchestration/job_manager.py`
- Correction appliquee : route historique executee en threadpool, endpoints jobs asynchrones avec statut/progression/annulation.
- Risque de regression estime : Moyen
- Verification effectuee : `test_ranking_job_lifecycle`.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-006] - Recherche vectorielle non scalable
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/app/infrastructure/postgres_vector_store.py`, `backend/alembic/versions/20260723_0001_initial_pgvector.py`
- Correction appliquee : backend pgvector par defaut, recherche SQL `embedding <=> query`, fallback JSON explicite.
- Risque de regression estime : Eleve
- Verification effectuee : test helper pgvector, `alembic heads` execute precedemment.
- Justification : validation DB reelle encore conditionnee a un PostgreSQL avec extension `vector`.

### [SR-AUD-007] - Schema DB sans migrations ni contraintes relationnelles
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/alembic/*`, `backend/app/database/models.py`, `backend/scripts/initialize_databases.py`
- Correction appliquee : Alembic, FK/index/unique constraint, script d'init via migration.
- Risque de regression estime : Eleve
- Verification effectuee : `alembic heads`, compileall.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-008] - `.env` racine suivi par Git
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `.gitignore`, index Git
- Correction appliquee : `.env` ignore et retire de l'index sans supprimer le fichier local.
- Risque de regression estime : Faible
- Verification effectuee : `git status --short` montre `D .env`, attendu car retire du suivi.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-009] - Driver PostgreSQL incoherent
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/.env.example`, `README.md`, `backend/requirements.txt`
- Correction appliquee : DSN aligne sur `postgresql+psycopg://` et dependance `psycopg[binary]`.
- Risque de regression estime : Faible
- Verification effectuee : relecture config.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-010] - Identifiants PostgreSQL faibles et port expose
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/docker-compose.yml`, `README.md`
- Correction appliquee : variables env Docker, mot de passe exemple, port lie a `127.0.0.1`.
- Risque de regression estime : Moyen
- Verification effectuee : relecture compose.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-011] - Rapports contenant texte complet CV
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/scripts/analyze_samples.py`, `backend/scripts/render_result_report.py`
- Correction appliquee : texte brut masque par defaut, opt-in `--include-raw-text`.
- Risque de regression estime : Faible
- Verification effectuee : `test_reports_privacy.py`.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-012] - `free_port.py` dangereux
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/scripts/free_port.py`, `backend/scripts/run_backend.sh`, `README.md`
- Correction appliquee : confirmation et filtrage par nom de processus.
- Risque de regression estime : Faible
- Verification effectuee : `test_free_port.py`.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-013] - Score langues ignore niveau requis
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/app/services/matching/language_matcher.py`, `backend/tests/unit/test_scoring.py`
- Correction appliquee : score pondere par niveau requis.
- Risque de regression estime : Moyen
- Verification effectuee : tests scoring langues.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-014] - Experience mixte dates/durees mal comptee
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/app/services/matching/experience_matcher.py`
- Correction appliquee : addition des periodes datees fusionnees et durees explicites non datees.
- Risque de regression estime : Moyen
- Verification effectuee : tests experience/scoring.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-015] - Formation trop permissive et domaines ignores
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/app/services/matching/education_matcher.py`
- Correction appliquee : niveau requis inconnu non auto-valide, `accepted_fields` pris en compte.
- Risque de regression estime : Moyen
- Verification effectuee : tests education.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-016] - Certifications/domaines non exploites
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/app/services/matching/certification_matcher.py`, `backend/app/services/scoring/scoring_engine.py`, poids scoring
- Correction appliquee : matcher certifications/domaines branche avec poids dedie.
- Risque de regression estime : Moyen
- Verification effectuee : tests cert/domain.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-017] - Heuristiques metier codees en dur
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/app/data/domain_rules.json`, `backend/app/services/rules/domain_rules.py`, extracteurs et matcher responsabilites
- Correction appliquee : regles principales externalisees dans un JSON versionne.
- Risque de regression estime : Moyen
- Verification effectuee : `test_domain_rules.py`, tests extraction/scoring.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-018] - Duplication coercition/deduplication
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/app/services/extraction/coercion.py`, `backend/app/services/normalization/text_normalizer.py`
- Correction appliquee : coercions et deduplication factorisees.
- Risque de regression estime : Faible
- Verification effectuee : `test_extraction_coercion.py`, `test_normalization.py`.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-019] - `full_text` ambigu
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/app/services/documents/section_segmenter.py`
- Correction appliquee : `full_text` reste toujours le texte complet, sections detectees separement.
- Risque de regression estime : Faible
- Verification effectuee : `test_segment_sections_keeps_full_text_complete`.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-020] - Troncature silencieuse et batch embeddings non borne
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/app/services/extraction/*`, `backend/app/services/retrieval/section_indexer.py`, `backend/app/config.py`
- Correction appliquee : limite LLM configurable, log de troncature sans PII, batch embeddings configurable.
- Risque de regression estime : Moyen
- Verification effectuee : tests batching et extraction.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-021] - Frontend sans validation/annulation/progression reelle
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `frontend/src/App.tsx`, `frontend/src/validation.ts`
- Correction appliquee : validation client, jobs API, polling, annulation.
- Risque de regression estime : Moyen
- Verification effectuee : `npm run lint`, `npm run test`, `npm run build` executes precedemment.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-022] - Dependances frontend mal classees et types React decales
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `frontend/package.json`, `frontend/package-lock.json`
- Correction appliquee : dev deps separees, types React alignes, Vitest mis a jour.
- Risque de regression estime : Faible
- Verification effectuee : `npm audit` a 0 vulnerabilite precedemment.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-023] - Dependances Python non verrouillees/dev-prod/licence
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `backend/requirements*.txt`, lockfiles, `README.md`
- Correction appliquee : requirements prod/dev separes, lockfiles, mention PyMuPDF.
- Risque de regression estime : Moyen
- Verification effectuee : installation/CI config et tests backend.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-024] - Absence CI/lint/type/couverture
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : `.github/workflows/ci.yml`, `pyproject.toml`
- Correction appliquee : CI backend/frontend, Ruff, mypy, coverage.
- Risque de regression estime : Faible
- Verification effectuee : `ruff check backend`, `mypy backend/app`, `pytest`.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-025] - Couverture de tests incomplete sur surfaces critiques
- Statut : Deja resolu avant cette intervention
- Fichier(s) modifie(s) : tests unitaires backend et tests frontend
- Correction appliquee : tests auth/uploads/privacy/free_port/jobs/retrieval/vector/scoring/frontend.
- Risque de regression estime : Faible
- Verification effectuee : `pytest backend/tests/unit backend/tests/test_health.py` -> 72 tests passes apres Mission B.
- Justification : aucune correction supplementaire requise.

### [SR-AUD-026] - Observabilite minimale
- Statut : Corrige partiellement
- Fichier(s) modifie(s) : `backend/app/main.py`, `backend/app/core/request_context.py`, `backend/app/api/routes/ranking.py`, `backend/app/services/orchestration/job_manager.py`
- Correction appliquee : `X-Request-ID`, `analysis_id`, statut de job, logs sans contenu CV/JD.
- Risque de regression estime : Moyen
- Verification effectuee : tests API/jobs, relecture.
- Justification : logs JSON, metriques et tracing restent a valider selon le mode de deploiement.

### [SR-AUD-027] - Code mort/non utilise
- Statut : Corrige partiellement
- Fichier(s) modifie(s) : `backend/app/infrastructure/nvidia_embeddings.py`, `backend/app/services/normalization/job_title_normalizer.py`
- Correction appliquee : suppression de `NvidiaEmbeddingClient.embed` et `normalize_job_titles`.
- Risque de regression estime : Faible
- Verification effectuee : `rg`, `ruff`, `mypy`, tests backend.
- Justification : certains champs publics Pydantic sont conserves pour eviter une rupture de contrat API.

### [SR-AUD-028] - Fichiers monolithiques difficiles a faire evoluer
- Statut : Corrige partiellement
- Fichier(s) modifie(s) : `frontend/src/validation.ts`, `backend/app/services/documents/upload_manager.py`, `backend/app/services/orchestration/job_manager.py`, `backend/app/services/extraction/coercion.py`, `backend/app/services/rules/domain_rules.py`
- Correction appliquee : extractions ciblees de modules sans refonte cosmetique massive.
- Risque de regression estime : Moyen
- Verification effectuee : lint, mypy, tests backend/frontend precedents.
- Justification : decomposition UI/styles/report HTML plus large a planifier separement.

### Problemes en attente de validation humaine

- SR-AUD-026 : choix de stack observabilite production, logs JSON, metriques, traces.
- SR-AUD-027 : decision de contrat API sur les champs publics conserves.
- SR-AUD-028 : budget de refactor UI/styles/scripts plus large.
- Validation juridique PyMuPDF.
- Validation PostgreSQL/pgvector reelle avec Docker Desktop ou PostgreSQL disposant de l'extension `vector`.

### Problemes decouverts en cours de route

- Le polling `GET /api/ranking/jobs/{id}` consommait le rate limit et pouvait provoquer `Trop de requetes` pendant une analyse longue. Corrige dans `backend/app/api/routes/ranking.py`; les tests ciblés passent.
- `backend/.env` contient une ligne `NVIDIA_API_KEY`, mais sa valeur est absente/vidée dans l'environnement local inspecte. Les runs reels NVIDIA n'ont donc pas ete executes depuis Codex.

## Section 2 - Diagnostic et correction de la non-reproductibilite des scores

### Symptome observe

L'utilisateur observe que des relances du pipeline sur exactement les memes fichiers produisent des scores legerement differents.

### Pipeline analyse

Etapes instrumentees par `backend/scripts/diagnose_score_reproducibility.py` :

1. extraction texte document ;
2. extraction fiche de poste structuree via LLM ;
3. extraction CV structure via LLM ;
4. enrichissement CV par preuves de skills ;
5. segmentation/chunking ;
6. embeddings ;
7. retrieval ;
8. scoring ;
9. ranking final.

Le script ne logge pas le texte brut : il produit des hashes de texte/sections/JSON/chunks/evidence, les scores et un hash final.

### Premiere etape de divergence isolee

La premiere etape non deterministe confirmee est l'extraction structuree via LLM, avant le scoring.

Preuve avant correction :

- `backend/.env` contenait `NVIDIA_TEMPERATURE=0.1`.
- `backend/app/config.py` avait aussi une valeur par defaut `0.1`.
- `backend/app/infrastructure/nvidia_llm.py` envoyait `temperature`, mais aucun `seed`.
- La documentation NVIDIA indique que la temperature controle le sampling et qu'une temperature plus haute rend la sortie moins deterministe ; elle documente aussi `seed` pour reproduire les resultats si les autres hyperparametres sont fixes.

Le scoring pur n'est pas la premiere source identifiee : lorsque l'extraction et les embeddings sont controles en offline, les cinq runs ont les memes hashes a toutes les etapes et les memes scores.

### Cause racine

Les scores dependent des structures extraites par `NvidiaLLMClient.generate_json`. Avec `temperature=0.1` et sans `seed`, deux appels LLM sur le meme texte peuvent produire des differences legeres : competences listees, intitulés, responsabilites, experiences ou niveaux de langue. Ces differences alimentent ensuite les matchers et changent les scores finaux.

### Correction appliquee

Fichiers modifies :

- `backend/app/config.py`
- `backend/app/infrastructure/nvidia_llm.py`
- `backend/.env.example`
- `README.md`
- `backend/docs/backend_explanation.tex`
- `backend/tests/unit/test_nvidia_llm.py`
- `backend/scripts/diagnose_score_reproducibility.py`
- `backend/.env` local : `NVIDIA_TEMPERATURE=0`, `NVIDIA_SEED=0` sans afficher ni modifier la cle API.

Avant :

```python
"temperature": self.temperature,
"max_tokens": self.max_tokens,
```

Apres :

```python
"temperature": self.temperature,
"top_p": 1,
"max_tokens": self.max_tokens,
...
if self.seed is not None:
    payload["seed"] = self.seed
```

Et configuration :

```env
NVIDIA_TEMPERATURE=0
NVIDIA_SEED=0
```

### Preuve de resolution

Commandes executees :

```powershell
ruff check backend
mypy backend/app
pytest backend/tests/unit backend/tests/test_health.py
python backend/scripts/diagnose_score_reproducibility.py --offline --runs 5 --json-output backend/reproducibility_diagnostic.json
```

Resultats :

- `ruff check backend` : OK.
- `mypy backend/app` : OK, 75 fichiers analyses.
- `pytest backend/tests/unit backend/tests/test_health.py` : 72 tests passes, 1 warning Starlette/httpx.
- Diagnostic offline : `all_scores_identical=true`, `all_final_hashes_identical=true`.

Scores des 5 runs :

```text
Run 1: cv_data_analyst.txt=92.53, cv_generalist.txt=0.0, final_hash=dd3462ff31987651ca916306a97dd1a83bfc8bf178b28e6fcafbc9129009a197
Run 2: cv_data_analyst.txt=92.53, cv_generalist.txt=0.0, final_hash=dd3462ff31987651ca916306a97dd1a83bfc8bf178b28e6fcafbc9129009a197
Run 3: cv_data_analyst.txt=92.53, cv_generalist.txt=0.0, final_hash=dd3462ff31987651ca916306a97dd1a83bfc8bf178b28e6fcafbc9129009a197
Run 4: cv_data_analyst.txt=92.53, cv_generalist.txt=0.0, final_hash=dd3462ff31987651ca916306a97dd1a83bfc8bf178b28e6fcafbc9129009a197
Run 5: cv_data_analyst.txt=92.53, cv_generalist.txt=0.0, final_hash=dd3462ff31987651ca916306a97dd1a83bfc8bf178b28e6fcafbc9129009a197
```

Payload LLM verrouille par test :

```text
temperature=0
top_p=1
seed=0
model=model-under-test
```

### Limite de validation

Les runs reels NVIDIA n'ont pas ete executes par Codex, car `backend/.env` contient une ligne `NVIDIA_API_KEY` sans valeur exploitable au moment du diagnostic. La correction est neanmoins appliquee dans le code et la config. Pour valider avec le fournisseur, renseigner une vraie cle puis executer :

```powershell
cd C:\Users\pc\SmartRecruit
python backend\scripts\diagnose_score_reproducibility.py --runs 5 --json-output backend\reproducibility_diagnostic_real.json
```

### Effets de bord potentiels

- Les extractions LLM deviennent moins creatives et plus strictes. C'est souhaite pour de l'extraction factuelle RH.
- Certains documents ambigus peuvent perdre de petites "inferences" que le modele ajoutait a temperature non nulle ; cela reduit les faux positifs et ameliore la reproductibilite.
- Meme avec temperature 0 et seed fixe, un fournisseur externe peut changer le comportement si le modele cible change cote serveur. Le modele est nomme explicitement (`meta/llama-3.1-8b-instruct`), mais une validation periodique reste necessaire.
