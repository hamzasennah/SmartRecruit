# Audit technique approfondi - SmartRecruit

Date de l'audit : 2026-07-23
Mode : audit statique du depot + executions locales ciblees, sans correction du code applicatif.

## 1. Resume executif

SmartRecruit est un prototype avance et coherent de classement de CV par pipeline FastAPI + React + PostgreSQL + API NVIDIA. La base fonctionnelle est lisible, le backend est decoupe en couches metier, et les tests unitaires couvrent une bonne partie des heuristiques de scoring/extraction. Les verifications disponibles donnent un signal positif : `pytest tests/unit tests/test_health.py` passe avec 51 tests, `python -m compileall app` passe, `npm.cmd run build` passe hors sandbox, et `npm.cmd audit` indique 0 vulnerabilite npm.

L'etat de maturite reste toutefois pre-production. Les risques principaux concernent la securite et l'exploitation de donnees RH : endpoint couteux sans authentification ni rate limiting, uploads conserves localement, absence de limite de taille effective, details d'erreur renvoyes au client, stockage de rapports contenant le texte complet des CV, et moteur de recherche vectorielle non scalable. La logique de scoring contient aussi plusieurs raccourcis fonctionnels qui peuvent fausser un classement reel.

Problemes detectes : 28

| Gravite | Nombre |
| --- | ---: |
| 🔴 Critique | 0 |
| 🟠 Elevee | 7 |
| 🟡 Moyenne | 16 |
| 🟢 Faible | 5 |
| ⚪ Info | 0 |

Priorites a traiter avant production :

1. Securiser `/api/ranking/analyze` : authentification, rate limiting, quotas, erreurs generiques.
2. Refaire la gestion d'upload : limite de taille appliquee, noms uniques, nettoyage garanti, stockage temporaire.
3. Remplacer la recherche vectorielle brute par une vraie strategie PostgreSQL/pgvector ou equivalent indexe.
4. Stabiliser les dependances et la configuration : driver PostgreSQL, fichiers `.env`, lock backend, CI.
5. Corriger les biais de scoring connus : langues, experience mixte, education, certifications/domaines.

## 2. Cartographie du projet

### Stack identifiee

- Backend : Python, FastAPI, Pydantic v2, SQLAlchemy, PostgreSQL, `httpx`, PyMuPDF, python-docx, pytest.
- IA externe : NVIDIA API pour LLM et embeddings.
- Frontend : React 18, Vite 6, TypeScript, lucide-react.
- Base de donnees : PostgreSQL via SQLAlchemy, tables `resumes`, `jobs`, `analyses`, `vector_chunks`.
- Scripts : initialisation DB, verification NVIDIA, analyse d'echantillons, liberation de port, rendu HTML.
- Documentation : README + documents LaTeX dans `docs/` et `backend/docs/`.

### Arborescence et points d'entree

- Backend API : `backend/app/main.py`, routes dans `backend/app/api/routes/`.
- Pipeline principal : `backend/app/services/orchestration/batch_ranking_pipeline.py`.
- Extraction : `backend/app/services/extraction/`.
- Matching/scoring : `backend/app/services/matching/`, `backend/app/services/scoring/`.
- Retrieval/vector store : `backend/app/services/retrieval/`, `backend/app/infrastructure/postgres_vector_store.py`.
- Frontend principal : `frontend/src/App.tsx`, styles dans `frontend/src/styles.css`.
- Tests : `backend/tests/unit/`, `backend/tests/integration/`, `backend/tests/test_health.py`.

### Perimetre effectivement inspecte

- 114 fichiers suivis par Git.
- Fichiers source, schemas, routes, scripts, docs, configs, dependances et tests inspectes.
- Artefacts locaux ignores reperes mais non audites comme source : `backend/.venv/`, `frontend/node_modules/`, `frontend/dist/`, caches Python, PDF presents dans `backend/uploads/` et `backend/samples/`.

## 3. Detail des problemes detectes

### [SR-AUD-001] - Endpoint d'analyse couteux expose sans authentification ni rate limiting
- Categorie : Securite, abus de ressources, protection des donnees
- Gravite : 🟠 Elevee
- Fichier(s) / ligne(s) concerne(s) : `backend/app/api/routes/ranking.py:17`, `backend/scripts/run_backend.sh:7`, `README.md:153`, `backend/app/main.py:22-25`
- Description : `POST /api/ranking/analyze` accepte des fichiers RH, declenche des appels NVIDIA et ecrit en base sans authentification, autorisation, rate limiting, quota utilisateur ni anti-abus. La documentation lance Uvicorn sur `0.0.0.0`, ce qui peut rendre l'API joignable sur le reseau local ou une VM exposee.
- Cause probable : prototype local transforme en API sans couche d'exploitation.
- Consequences possibles : fuite de CV, couts NVIDIA non controles, deni de service applicatif, analyse non autorisee de documents sensibles.
- Recommandation de correction : ajouter une authentification explicite, un rate limiter par cle/utilisateur/IP, des quotas de fichiers et de volume, et limiter l'ecoute reseau par defaut a `127.0.0.1` hors environnement controle.
- Exemple de correction :

```python
# Principe
@router.post("/analyze", dependencies=[Depends(require_api_key), Depends(rate_limit)])
async def analyze_ranking(...):
    ...
```

### [SR-AUD-002] - Limite d'upload declaree mais jamais appliquee
- Categorie : Securite, performance, robustesse
- Gravite : 🟠 Elevee
- Fichier(s) / ligne(s) concerne(s) : `backend/app/config.py:84-85`, `backend/app/api/routes/ranking.py:31-37`, `backend/app/api/routes/documents.py:23-30`
- Description : `MAX_UPLOAD_MB` existe mais les routes lisent chaque fichier entierement via `await file.read()` puis ecrivent tout en memoire/disque. Il n'y a pas de controle de taille, de nombre total de CV, de taille cumulee, ni de limite de pages.
- Cause probable : validation limitee a l'extension de fichier.
- Consequences possibles : OOM, saturation disque, temps de traitement excessif, couts embeddings/LLM incontrôles.
- Recommandation de correction : lire par chunks, refuser au-dela de `settings.max_upload_mb`, fixer un nombre maximal de CV, verifier `Content-Length` si disponible et revalider apres lecture.
- Exemple de correction :

```python
limit = settings.max_upload_mb * 1024 * 1024
size = 0
with target.open("wb") as out:
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > limit:
            raise HTTPException(status_code=413, detail="Fichier trop volumineux.")
        out.write(chunk)
```

### [SR-AUD-003] - Uploads conserves, noms non uniques et risque d'ecrasement
- Categorie : Securite, confidentialite, robustesse
- Gravite : 🟠 Elevee
- Fichier(s) / ligne(s) concerne(s) : `backend/app/api/routes/ranking.py:35-37`, `backend/app/api/routes/documents.py:27-30`, `backend/app/services/orchestration/batch_ranking_pipeline.py:66-67`
- Description : les fichiers sont sauvegardes dans `backend/uploads` sous un nom derive du nom original. Le pipeline nettoie les chunks vectoriels, mais pas les fichiers uploades. `git status --ignored` montre de nombreux PDF de CV et fiches de poste encore presents dans `backend/uploads/`.
- Cause probable : stockage local temporaire devenu persistant par oubli.
- Consequences possibles : retention involontaire de donnees personnelles, collision/ecrasement entre utilisateurs, confusion entre analyses, risque de fuite lors d'une sauvegarde ou d'un partage du dossier.
- Recommandation de correction : creer un repertoire temporaire unique par analyse, utiliser des noms aleatoires, nettoyer dans un `finally`, definir une politique de retention explicite si la persistance est voulue.
- Exemple de correction :

```python
analysis_dir = settings.upload_dir / uuid4().hex
try:
    ...
finally:
    shutil.rmtree(analysis_dir, ignore_errors=True)
```

### [SR-AUD-004] - Details d'exceptions internes exposes au client
- Categorie : Securite, gestion des erreurs
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : `backend/app/api/routes/ranking.py:26-28`, `backend/app/services/orchestration/batch_ranking_pipeline.py:57`
- Description : l'exception brute est incluse dans le `detail` HTTP 500 et dans `errors`. Des erreurs DB, chemins locaux, noms de fichiers ou details fournisseur peuvent etre renvoyes au frontend.
- Cause probable : debug utile en local conserve dans le contrat API.
- Consequences possibles : fuite d'information interne, exposition de noms de fichiers contenant des donnees personnelles, surface de reconnaissance pour un attaquant.
- Recommandation de correction : journaliser l'exception complete cote serveur avec un identifiant de correlation, renvoyer au client un message generique et non sensible.

### [SR-AUD-005] - Pipeline synchrone long execute dans une route async
- Categorie : Performance, disponibilite
- Gravite : 🟠 Elevee
- Fichier(s) / ligne(s) concerne(s) : `backend/app/api/routes/ranking.py:17-21`, `backend/app/infrastructure/nvidia_llm.py:88-109`, `backend/app/infrastructure/nvidia_embeddings.py:76-97`, `backend/app/services/orchestration/batch_ranking_pipeline.py:26-67`
- Description : la route est `async`, mais appelle directement un pipeline synchrone long : parsing, LLM, embeddings, SQLAlchemy sync, `httpx.post` sync et `time.sleep` pendant les retries. Sous Uvicorn, cela peut bloquer le worker pendant toute l'analyse.
- Cause probable : pipeline metier synchrone branche directement sur FastAPI.
- Consequences possibles : latence elevee, timeouts, absence de backpressure, degradation de toutes les requetes concurrentes.
- Recommandation de correction : passer par une file de jobs, un worker, `BackgroundTasks` controlees ou `run_in_threadpool` a court terme ; utiliser `httpx.AsyncClient` si le pipeline reste dans le process API.

### [SR-AUD-006] - Recherche vectorielle non scalable : vecteurs JSON et tri en Python
- Categorie : Performance, architecture donnees
- Gravite : 🟠 Elevee
- Fichier(s) / ligne(s) concerne(s) : `backend/app/database/models.py:50-51`, `backend/app/infrastructure/postgres_vector_store.py:135-162`, `backend/app/infrastructure/postgres_vector_store.py:169`
- Description : les embeddings sont stockes dans une colonne `Text` en JSON, puis toutes les lignes du namespace/document sont chargees, parsees et triees en Python. PostgreSQL n'indexe pas la similarite.
- Cause probable : implementation simple de preuve de concept.
- Consequences possibles : temps de reponse lineaire avec le nombre de chunks, charge memoire forte, impossibilite de passer a de gros volumes de CV.
- Recommandation de correction : utiliser `pgvector` ou un moteur vectoriel dedie, type `vector`, index HNSW/IVFFlat, recherche `ORDER BY embedding <=> query LIMIT top_k`.

### [SR-AUD-007] - Schema DB cree automatiquement, sans migrations ni contraintes relationnelles
- Categorie : Architecture, maintenabilite, donnees
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : `backend/app/infrastructure/postgres_vector_store.py:27`, `backend/scripts/initialize_databases.py:14`, `backend/app/database/models.py:5-52`
- Description : `Base.metadata.create_all` est utilise au runtime et dans le script d'initialisation. Aucun outil de migration n'est versionne. Les relations logiques ne sont pas materialisees par des foreign keys ou contraintes uniques.
- Cause probable : demarrage rapide sans cycle de migration.
- Consequences possibles : schema divergent entre environnements, migrations manuelles dangereuses, difficultes de rollback, coherence historique faible.
- Recommandation de correction : introduire Alembic, versionner les migrations, ajouter FK/contraintes/index adaptes, separer creation schema et execution applicative.

### [SR-AUD-008] - `.env` racine suivi par Git et ignore incomplet
- Categorie : Securite, controle de version
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : `.env`, `.gitignore:4`, `backend/.gitignore:6`
- Description : `.env` est suivi par Git (`git ls-files -s .env` montre un blob vide), tandis que `.gitignore` ignore `backend/.env` mais pas `.env` a la racine. Le fichier est vide aujourd'hui, mais il est pret a recevoir accidentellement un secret.
- Cause probable : fichier cree avant la regle d'ignore ou ignore limite au backend.
- Consequences possibles : commit accidentel de cle NVIDIA, mots de passe DB ou tokens.
- Recommandation de correction : retirer `.env` de l'index, ignorer tous les `.env` non exemples, conserver uniquement `.env.example`.

### [SR-AUD-009] - Incoherence de driver PostgreSQL entre `.env.example`, README et requirements
- Categorie : Configuration, dependances
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : `backend/.env.example:12`, `README.md:128`, `backend/requirements.txt:10`
- Description : `.env.example` utilise `postgresql+psycopg2://`, le README utilise `postgresql+psycopg://`, et `requirements.txt` declare `psycopg[binary]` mais pas `psycopg2-binary`.
- Cause probable : migration partielle de psycopg2 vers psycopg v3.
- Consequences possibles : un nouvel environnement cree depuis `.env.example` peut echouer au premier acces DB.
- Recommandation de correction : choisir un driver unique, aligner tous les fichiers, ajouter un test de demarrage DB sur environnement frais.

### [SR-AUD-010] - Identifiants PostgreSQL faibles et port DB expose par defaut
- Categorie : Securite, configuration environnement
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : `backend/docker-compose.yml:5-9`, `README.md:128`
- Description : Docker Compose expose PostgreSQL sur `5432:5432` avec `smartrecruit/smartrecruit`. C'est acceptable pour un dev local isole, pas pour un environnement partage.
- Cause probable : configuration de developpement non marquee comme telle dans le fichier Compose.
- Consequences possibles : acces DB non autorise sur un poste ou serveur expose, recuperation de resultats d'analyse contenant des donnees RH.
- Recommandation de correction : charger les secrets depuis `.env`, documenter le caractere dev-only, lier le port a `127.0.0.1` ou ne pas l'exposer.

### [SR-AUD-011] - Rapports et artefacts locaux contiennent le texte complet des CV
- Categorie : Confidentialite, protection des donnees personnelles
- Gravite : 🟠 Elevee
- Fichier(s) / ligne(s) concerne(s) : `backend/scripts/analyze_samples.py:36-44`, `backend/scripts/analyze_samples.py:74-83`, `backend/scripts/analyze_samples.py:121-133`, `backend/scripts/render_result_report.py:270-272`, `backend/.gitignore:13-14`
- Description : le script genere `result.json` et `result_report.html`, puis le rapport HTML inclut le texte brut complet extrait. Les fichiers sont ignores par `backend/.gitignore`, mais restent sur disque et sont facilement partageables.
- Cause probable : besoin de debug et de verification visuelle.
- Consequences possibles : diffusion accidentelle de CV complets, non-conformite RGPD/retention si utilise avec de vrais candidats.
- Recommandation de correction : rendre l'inclusion du texte brut opt-in, masquer les donnees personnelles, stocker les rapports dans un dossier temporaire nettoye, documenter une politique de retention.

### [SR-AUD-012] - `free_port.py` peut terminer n'importe quel processus sur un port
- Categorie : Robustesse, outillage
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : `backend/scripts/free_port.py:7-12`, `backend/scripts/free_port.py:35-41`, `README.md:150`, `backend/scripts/run_backend.sh:4`
- Description : le script parcourt les connexions et termine tout processus en ecoute sur le port donne, sans verifier qu'il s'agit de SmartRecruit/Uvicorn.
- Cause probable : confort de developpement local.
- Consequences possibles : arret involontaire d'un service systeme ou d'une autre application, perte de travail local.
- Recommandation de correction : demander confirmation, filtrer le nom/commande du processus, ou preferer un port libre au lieu de tuer le listener.

### [SR-AUD-013] - Le score de langues ignore le niveau minimal requis
- Categorie : Bug fonctionnel, scoring
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : `backend/app/services/matching/language_matcher.py:15-42`, `backend/tests/unit/test_scoring.py:260`
- Description : `below_required_level` est calcule mais le score reste `presence_based`. Les tests confirment qu'un candidat avec niveau `professional` obtient 100% pour une exigence `fluent`.
- Cause probable : choix de ne pas penaliser le niveau, mais expose comme details seulement.
- Consequences possibles : classement trop favorable a des candidats qui ne satisfont pas une contrainte linguistique.
- Recommandation de correction : integrer le niveau dans le score ou marquer explicitement la categorie comme informative/non penalite, puis adapter l'UI.

### [SR-AUD-014] - Les durees explicites sont ignorees si au moins une experience a des dates
- Categorie : Bug fonctionnel, scoring experience
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : `backend/app/services/matching/experience_matcher.py:23-39`
- Description : si `periods` contient au moins une experience datee, `total_months` et `relevant_months` utilisent uniquement les periodes fusionnees et ignorent `explicit_total`/`explicit_relevant`.
- Cause probable : branchement `if periods else explicit_total` trop global.
- Consequences possibles : sous-estimation de l'experience de candidats dont certains postes ont seulement une duree declaree.
- Recommandation de correction : additionner les periodes fusionnees et les durees explicites non convertibles, avec une regle claire contre le double comptage.

### [SR-AUD-015] - Matching formation trop permissif et champs de domaine ignores
- Categorie : Bug fonctionnel, scoring
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : `backend/app/services/matching/education_matcher.py:10-23`, `backend/app/schemas/job.py:17-18`, `backend/app/services/extraction/job_extractor.py:81-82`
- Description : si `education_rank(required)` vaut 0 pour un niveau inconnu, tout candidat avec rang >= 0 obtient 100%. Le champ `accepted_fields` est extrait mais jamais utilise dans le matching.
- Cause probable : modele de scoring formation simplifie.
- Consequences possibles : faux positifs sur diplome et specialite, surtout si le LLM extrait une formulation non normalisee.
- Recommandation de correction : traiter un niveau requis inconnu comme "non applicable" ou "a verifier", et ajouter une comparaison sur le champ d'etudes.

### [SR-AUD-016] - Certifications, domaines et certains champs extraits ne participent pas au score
- Categorie : Code mort, dette fonctionnelle
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : `backend/app/services/matching/certification_matcher.py:1`, `backend/app/services/scoring/scoring_engine.py:17-31`, `backend/app/schemas/job.py:13`, `backend/app/schemas/job.py:32`, `backend/app/schemas/cv.py:56`
- Description : un `match_certifications` existe mais n'est jamais importe par `ScoringEngine` et retourne toujours 100%. Les champs `certifications`, `required_domains`, `accepted_fields` et `extraction_confidence` sont modelises/extraits mais tres peu ou pas exploites.
- Cause probable : extension prevue mais non branchee.
- Consequences possibles : attentes produit non satisfaites, faux sentiment de couverture, dette de contrat API.
- Recommandation de correction : supprimer le matcher mort ou l'implementer, ajouter des poids explicites, documenter les champs informatifs.

### [SR-AUD-017] - Heuristiques metier tres specifiques codees en dur
- Categorie : Architecture, maintenabilite, biais metier
- Gravite : 🟠 Elevee
- Fichier(s) / ligne(s) concerne(s) : `backend/app/services/extraction/cv_extractor.py:18-73`, `backend/app/services/extraction/job_extractor.py:171-208`, `backend/app/services/matching/responsibility_matcher.py:14-57`
- Description : de nombreuses regles citent des outils, societes et contextes precis (`Power BI`, `Snowflake`, `Azure`, `SPM`, `ITMS`, `Experteye`, `BCP`, etc.). Ces regles sont dispersees entre extraction, normalisation et matching.
- Cause probable : calibrage sur un jeu d'exemples concret.
- Consequences possibles : biais fort vers certains postes/data tools, regression difficile a prevoir, mauvais resultats sur d'autres secteurs ou langues.
- Recommandation de correction : deplacer ces regles dans des donnees configurees/testees par domaine, isoler des profils de scoring, documenter le perimetre RH couvert.

### [SR-AUD-018] - Duplication de logique de coercition et de deduplication
- Categorie : Qualite code, duplication
- Gravite : 🟢 Faible
- Fichier(s) / ligne(s) concerne(s) : `backend/app/services/extraction/cv_extractor.py:172-229`, `backend/app/services/extraction/job_extractor.py:128-158`, `backend/app/services/extraction/job_extractor.py:384`, `backend/app/services/matching/responsibility_matcher.py:305`
- Description : `_coerce_string_list`, `_coerce_scalar` et plusieurs variantes de `_dedupe` existent dans plusieurs modules avec des comportements proches.
- Cause probable : evolution parallele des extracteurs CV et job.
- Consequences possibles : corrections appliquees dans un fichier mais oubliees dans l'autre, divergence subtile entre schemas.
- Recommandation de correction : factoriser les coercions LLM dans un module commun, avec tests unitaires dedies.

### [SR-AUD-019] - Segmentation de sections fragile et `full_text` ambigu
- Categorie : Robustesse extraction, retrieval
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : `backend/app/services/documents/section_segmenter.py:7-30`, `backend/app/services/retrieval/chunk_builder.py:8-13`
- Description : `full_text` commence comme section courante mais, si des lignes precedent le premier titre detecte, il ne represente plus tout le texte ; sinon `compact.setdefault("full_text", text)` le remplit avec le texte complet. Le sens de `full_text` varie donc selon la structure du document.
- Cause probable : segmentation heuristique minimaliste.
- Consequences possibles : chunks incoherents, retrieval incomplet ou duplique, preuves RAG moins fiables.
- Recommandation de correction : conserver toujours une cle `full_text` complete et ajouter des sections detectees separement ; renforcer les regex de titres.

### [SR-AUD-020] - Troncature LLM et batch embeddings non bornes
- Categorie : Robustesse, performance
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : `backend/app/services/extraction/cv_extractor.py:108`, `backend/app/services/extraction/job_extractor.py:20`, `backend/app/services/retrieval/section_indexer.py:9-12`
- Description : les prompts n'envoient que `document.text[:12000]` sans indiquer a l'appelant qu'une partie du document est ignoree. Tous les chunks d'un document sont envoyes en un seul appel embeddings, sans limite de batch ni retry par chunk.
- Cause probable : limites de tokens gerees par coupe simple.
- Consequences possibles : criteres ou experiences en fin de document ignores, appel embedding trop volumineux, echec complet d'un CV au lieu d'une degradation partielle.
- Recommandation de correction : tracer la troncature, segmenter le LLM par sections pertinentes, batcher les embeddings avec taille maximale configuree.

### [SR-AUD-021] - Frontend sans validation taille/nombre de fichiers ni annulation
- Categorie : UX, robustesse client
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : `frontend/src/App.tsx:139-172`, `frontend/src/App.tsx:221-232`, `frontend/src/App.tsx:156-164`
- Description : le frontend se limite a `accept=".pdf,.docx,.txt,.md"` et envoie tous les fichiers selectionnes. Il n'y a pas de controle de taille/nombre, pas d'annulation de requete, et la progression est simulee par timer.
- Cause probable : interface prototype centree demo.
- Consequences possibles : UX trompeuse pendant les echecs, envoi accidentel de fichiers trop nombreux/lourds, impossible d'interrompre une analyse couteuse.
- Recommandation de correction : aligner les validations client sur le backend, utiliser `AbortController`, afficher une progression par etat serveur/job.

### [SR-AUD-022] - Dependances frontend mal classees et types React decales
- Categorie : Dependances, maintenance frontend
- Gravite : 🟢 Faible
- Fichier(s) / ligne(s) concerne(s) : `frontend/package.json:11-21`
- Description : `@vitejs/plugin-react`, `typescript` et `vite` sont dans `dependencies` alors qu'ils sont des dependances de build. `@types/react` et `@types/react-dom` sont en v19 tandis que React runtime est en v18.
- Cause probable : installation rapide sans tri prod/dev.
- Consequences possibles : package de production inutilement large, risques de mismatch de types lors d'evolutions.
- Recommandation de correction : deplacer les outils de build en `devDependencies`, aligner `@types/*` sur React 18 ou migrer React.

### [SR-AUD-023] - Dependances Python non verrouillees, dev/prod melanges et risque licence PyMuPDF
- Categorie : Dependances, supply chain, licences
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : `backend/requirements.txt:1-11`
- Description : les versions sont declarees en bornes basses (`>=`) sans lockfile backend. `pytest` est dans les requirements applicatifs. `pip show pymupdf` indique une licence "AGPL 3.0 or Artifex Commercial License", point a valider pour un usage commercial/proprietaire.
- Cause probable : gestion de dependances simple par `requirements.txt`.
- Consequences possibles : builds non reproductibles, upgrades implicites cassants, obligations licence incompatibles avec l'usage cible.
- Recommandation de correction : separer prod/dev, ajouter un lock (`pip-tools`, `uv`, Poetry), auditer les licences, valider PyMuPDF juridiquement ou remplacer selon le contexte.

### [SR-AUD-024] - Absence de CI/CD, lint, format, typing Python et couverture
- Categorie : CI/CD, qualite
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : absence de `.github/workflows`, `pyproject.toml`, `ruff`, `mypy`, `pytest.ini`, config coverage ; seuls `backend/docker-compose.yml`, `frontend/tsconfig.json`, `frontend/vite.config.ts` sont presents comme configs suivies.
- Description : les tests et builds sont documentes dans le README mais aucun pipeline ne les impose.
- Cause probable : projet local/prototype.
- Consequences possibles : regressions non detectees avant merge/deploiement, style divergent, absence de seuils de couverture.
- Recommandation de correction : ajouter CI avec tests backend, build frontend, audit npm, lint/format, controle de couverture et integration optionnelle avec services.

### [SR-AUD-025] - Couverture de tests incomplete sur les surfaces critiques
- Categorie : Tests
- Gravite : 🟡 Moyenne
- Fichier(s) / ligne(s) concerne(s) : `backend/tests/integration/test_api_ranking.py:8-13`, `backend/tests/integration/test_ranking_pipeline.py:8-13`, `README.md:217-226`
- Description : les tests unitaires sont nombreux, mais les tests d'integration sont skips sauf `SMARTRECRUIT_RUN_INTEGRATION=1`. Il manque des tests pour limites d'upload, nettoyage des fichiers, erreurs non sensibles, concurrence, DB/migrations, frontend, et scenarios RGPD.
- Cause probable : dependance a NVIDIA API/PostgreSQL et focus sur scoring.
- Consequences possibles : bugs d'exploitation non detectes malgre un backend metier bien teste.
- Recommandation de correction : ajouter des fakes/mocks pour LLM/embeddings/vector store, tester les routes sans services externes, ajouter tests frontend et controles de non-regression securite.

### [SR-AUD-026] - Observabilite minimale
- Categorie : Observabilite, exploitation
- Gravite : 🟢 Faible
- Fichier(s) / ligne(s) concerne(s) : `backend/app/core/logging_config.py:4-8`, `backend/app/api/routes/ranking.py:27`, `backend/app/infrastructure/nvidia_llm.py:93-109`
- Description : logs basiques `logging.basicConfig`, pas de JSON logs, pas de request id, pas de durees par etape, pas de metriques, pas de tracing, pas de statut de job.
- Cause probable : execution locale principalement.
- Consequences possibles : diagnostic difficile en production, impossibilite de mesurer couts/latences par document.
- Recommandation de correction : ajouter logs structures, correlation id, durees d'etapes, compteurs d'erreurs fournisseur, metriques Prometheus/OpenTelemetry si deploiement service.

### [SR-AUD-027] - Petits elements morts ou non utilises
- Categorie : Code mort
- Gravite : 🟢 Faible
- Fichier(s) / ligne(s) concerne(s) : `backend/app/config.py:21-25`, `backend/app/infrastructure/nvidia_embeddings.py:38`, `backend/app/services/normalization/job_title_normalizer.py:22`, `backend/app/schemas/matching.py:20`
- Description : plusieurs elements existent sans usage observe dans le code suivi : `Settings.project_root`, `document_storage_dir`, `result_storage_dir`, `NvidiaEmbeddingClient.embed`, `normalize_job_titles`, champ `CategoryScore.evidence`.
- Cause probable : API prevue pour extensions futures.
- Consequences possibles : bruit mental, contrats ambigus, fausses attentes pour les consommateurs.
- Recommandation de correction : supprimer ou documenter comme extension planifiee, puis ajouter tests/usages si conserve.

### [SR-AUD-028] - Fichiers monolithiques difficiles a faire evoluer
- Categorie : Maintenabilite
- Gravite : 🟢 Faible
- Fichier(s) / ligne(s) concerne(s) : `frontend/src/App.tsx` 590 lignes, `frontend/src/styles.css` 603 lignes, `backend/scripts/render_result_report.py` 372 lignes, `backend/app/services/extraction/cv_extractor.py` 452 lignes, `backend/app/services/extraction/job_extractor.py` 346 lignes
- Description : plusieurs fichiers concentrent interface, logique de formatage, heuristiques et rendu HTML.
- Cause probable : croissance organique.
- Consequences possibles : revues plus difficiles, conflits de merge, regressions lors d'ajouts fonctionnels.
- Recommandation de correction : extraire composants frontend, modules de formatage, regles de normalisation et templates de rapport.

## 4. Plan d'action priorise

### Quick wins

1. Retirer `.env` de Git et ignorer `.env` a tous les niveaux ; verifier l'historique si des secrets y ont deja ete places.
2. Aligner `backend/.env.example`, README et `requirements.txt` sur `postgresql+psycopg://`.
3. Renvoyer des erreurs API generiques et garder les details seulement dans les logs serveur.
4. Ajouter une validation de taille/nombre de fichiers cote backend et frontend.
5. Nettoyer les uploads apres analyse avec noms aleatoires par analyse.
6. Deplacer `vite`, `typescript`, `@vitejs/plugin-react` en `devDependencies` et aligner les types React.
7. Retirer ou brancher `match_certifications`, `normalize_job_titles`, `CategoryScore.evidence` et autres surfaces mortes.
8. Proteger `free_port.py` par confirmation ou verification du processus cible.

### Chantiers structurants

1. Securiser l'API : auth, rate limiting, quotas, audit logs et politique de retention des documents.
2. Sortir le pipeline long de la route HTTP : file de jobs, workers, statut d'analyse, annulation.
3. Remplacer le vector store JSON par `pgvector` ou un moteur vectoriel indexe.
4. Introduire Alembic et une strategie de migration DB.
5. Revoir le modele de scoring : langues par niveau, experience mixte, formation/domaine, certifications, calibration par domaine.
6. Externaliser les heuristiques metier dans des jeux de regles versionnes/configurables.
7. Ajouter CI/CD : tests backend, build frontend, lint/format/type-check, coverage, audit npm, audit Python si outil installe.
8. Mettre en place observabilite : logs structures, correlation id, metriques de duree/cout par analyse.

## 5. Limites de l'audit

- Analyse principalement statique. Je n'ai pas lance PostgreSQL ni NVIDIA API, donc les tests d'integration reels sont restes hors verification.
- `pip-audit` n'est pas installe dans l'environnement Python courant ni dans `backend/.venv`; aucun audit CVE Python automatique complet n'a donc ete produit. `npm.cmd audit` a ete execute et retourne 0 vulnerabilite.
- Les PDF presents dans `backend/uploads/` et `backend/samples/` ont ete inventories par nom/taille et statut Git, mais leur contenu n'a pas ete ouvert afin d'eviter d'exposer inutilement des CV.
- Pas de test de charge, de concurrence, de latence NVIDIA, ni de mesure de cout.
- Pas d'audit juridique complet de licence ; le point PyMuPDF doit etre valide selon le modele de distribution reel.
- Pas d'audit accessibilite navigateur visuel ; le frontend a seulement ete inspecte statiquement et compile.
- Le dossier `.pytest_cache` a refuse l'acces pendant certaines enumerations ; les fichiers suivis par Git ont toutefois ete inventories via `git ls-files`.

## Conclusion

Le projet est bien structure pour un prototype fonctionnel et explicable : les couches backend sont identifiables, les schemas Pydantic sont clairs, et les tests metier donnent une base serieuse. En revanche, il ne doit pas etre considere pret production sans durcissement. Les priorites sont la protection des donnees RH, la maitrise des uploads et couts IA, la scalabilite du retrieval, la reproductibilite des environnements et la correction des raccourcis de scoring. Avec ces chantiers traites, SmartRecruit peut evoluer vers une application beaucoup plus robuste et auditables.
