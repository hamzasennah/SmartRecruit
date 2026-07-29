# Rapport de documentation du code par commentaires

Ce rapport liste les fichiers commentables modifies. Le compteur indique les commentaires explicatifs ajoutes hors paragraphe de fin de fichier; les paragraphes de role sont resumes dans la derniere colonne.

- Fichiers commentables modifies: 122
- Commentaires explicatifs hors paragraphes de fin: 258
- Paragraphes de role ajoutes: un par fichier commentable modifie

## Fichiers modifies

| Fichier | Commentaires de ligne ajoutes | Paragraphe de fin de fichier |
| --- | ---: | --- |
| `.github/workflows/ci.yml` | 0 | Ce fichier orchestre la verification continue. Il installe les dependances backend/frontend, lance les tests, et sert de filet de securite avant integration des changements. |
| `.gitignore` | 0 | Ce fichier separe le code source des artefacts locaux. Il evite de versionner secrets, caches, environnements virtuels et sorties generees. |
| `backend/.env.example` | 0 | Ce fichier documente les variables attendues par le backend. Il sert de modele de configuration sans contenir les secrets reels charges par app.config. |
| `backend/.gitignore` | 0 | Ce fichier limite le suivi Git dans le backend. Il garde hors depot les environnements, uploads et artefacts d'execution propres a la machine. |
| `backend/alembic.ini` | 0 | Ce fichier configure Alembic pour les migrations. Il relie les commandes de migration au dossier backend/alembic et au chargement de configuration. |
| `backend/alembic/env.py` | 0 | Ce fichier connecte Alembic aux modeles SQLAlchemy. Les migrations l'utilisent pour retrouver les metadonnees et la configuration PostgreSQL. |
| `backend/alembic/versions/20260723_0001_initial_pgvector.py` | 0 | Ce fichier cree le schema PostgreSQL initial. Il definit les tables d'analyses, documents et chunks vectoriels utilises par le pipeline. |
| `backend/app/__init__.py` | 0 | Ce fichier marque app comme package Python. Il permet aux routes, services et schemas d'etre importes par FastAPI et les tests. |
| `backend/app/api/__init__.py` | 0 | Ce fichier marque le package API. Il regroupe les modules de routes exposes par app.main. |
| `backend/app/api/routes/__init__.py` | 0 | Ce fichier marque le package des routes HTTP. app.main importe les routeurs voisins depuis ce namespace. |
| `backend/app/api/routes/documents.py` | 4 | Ce fichier expose l'endpoint de parsing de document. Il est appele par FastAPI, utilise upload_manager et DoclingParser, et reste separe du classement pour diagnostiquer l'extraction seule. |
| `backend/app/api/routes/health.py` | 0 | Ce fichier expose la route de sante. Il renseigne le frontend et les tests sur l'etat minimal de configuration du backend. |
| `backend/app/api/routes/ranking.py` | 8 | Ce fichier expose les endpoints de classement synchrones et asynchrones. Il applique securite, quotas d'upload et delegation au BatchRankingPipeline. |
| `backend/app/config.py` | 4 | Ce fichier centralise les parametres runtime lus depuis l'environnement. Les clients, routes et services l'utilisent pour eviter des constantes dispersees. |
| `backend/app/core/__init__.py` | 0 | Ce fichier marque le package core. Il regroupe configuration transversale, securite, logging, contexte et erreurs. |
| `backend/app/core/config_validation.py` | 5 | Ce fichier valide la configuration au demarrage. Il protege le pipeline contre des erreurs tardives de secrets, URLs, limites ou backend vectoriel. |
| `backend/app/core/constants.py` | 0 | Ce fichier regroupe les constantes transversales. Il evite que les extensions acceptees ou valeurs partagees divergent entre modules. |
| `backend/app/core/exceptions.py` | 0 | Ce fichier definit les exceptions metier. Il permet aux routes de transformer les echecs internes en reponses HTTP coherentes. |
| `backend/app/core/logging_config.py` | 0 | Ce fichier configure les logs Python. Il donne un format commun aux routes, pipelines et clients externes. |
| `backend/app/core/model_audit.py` | 4 | Ce fichier audite les appels modele. Les clients NVIDIA l'appellent pour relier latence, endpoint, modele et contexte d'analyse. |
| `backend/app/core/request_context.py` | 0 | Ce fichier stocke request_id et analysis_id en variables de contexte. Les logs et audits les recuperent sans passer ces identifiants partout en parametres. |
| `backend/app/core/security.py` | 6 | Ce fichier protege les routes sensibles. Il gere cle API et rate limit local avant que les analyses couteuses soient lancees. |
| `backend/app/database/__init__.py` | 0 | Ce fichier marque le package database. Il isole les modeles et sessions SQLAlchemy utilises par l'infrastructure. |
| `backend/app/database/models.py` | 0 | Ce fichier declare les tables SQLAlchemy. Le vector store et Alembic s'appuient dessus pour persister documents, analyses et chunks. |
| `backend/app/database/session.py` | 0 | Ce fichier construit le moteur et les sessions SQLAlchemy generiques. Il sert aux composants qui veulent acceder directement a PostgreSQL. |
| `backend/app/dependencies.py` | 0 | Ce fichier assemble les dependances principales. Les routes l'utilisent comme point unique de composition des parsers, clients et stores. |
| `backend/app/infrastructure/__init__.py` | 0 | Ce fichier marque le package infrastructure. Il separe les clients externes NVIDIA et PostgreSQL des services metier. |
| `backend/app/infrastructure/nvidia_client.py` | 4 | Ce fichier factorise le transport HTTP NVIDIA. Les clients LLM et embeddings heritent de ses retries, headers et evenements d'audit. |
| `backend/app/infrastructure/nvidia_embeddings.py` | 4 | Ce fichier implemente le client d'embeddings NVIDIA. Le retrieval l'utilise pour vectoriser chunks et requetes avant stockage/recherche. |
| `backend/app/infrastructure/nvidia_llm.py` | 6 | Ce fichier implemente le client LLM NVIDIA. Les extracteurs de job et CV l'utilisent pour produire du JSON structure valide. |
| `backend/app/infrastructure/postgres_vector_store.py` | 9 | Ce fichier encapsule le stockage vectoriel PostgreSQL. pgvector est le mode actif verifie; le mode json reste explicite pour usages legacy/dev, sans fallback automatique. |
| `backend/app/main.py` | 4 | Ce fichier cree l'application FastAPI. Il valide la configuration, branche les middlewares et expose les routeurs API. |
| `backend/app/schemas/__init__.py` | 0 | Ce fichier marque le package schemas. Il regroupe les modeles Pydantic partages par extraction, scoring, API et frontend. |
| `backend/app/schemas/cv.py` | 0 | Ce fichier definit le schema CV structure. Il est produit par CVExtractor puis consomme par matchers, scoring et API ranking. |
| `backend/app/schemas/document.py` | 0 | Ce fichier definit le texte de document parse. Il relie upload/parsing aux extracteurs et au chunking RAG. |
| `backend/app/schemas/experience.py` | 0 | Ce fichier definit les objets de duree et periode d'experience. Les calculs de duree et matchers l'utilisent pour compter les mois fiables. |
| `backend/app/schemas/job.py` | 0 | Ce fichier definit la fiche de poste structuree. JobExtractor la produit et tous les matchers y lisent les criteres de recrutement. |
| `backend/app/schemas/matching.py` | 0 | Ce fichier definit les objets de score et preuve. ScoringEngine les remplit et les routes les renvoient au frontend. |
| `backend/app/schemas/ranking.py` | 0 | Ce fichier definit les reponses de classement et de jobs async. Les routes et le frontend s'appuient sur ce contrat API. |
| `backend/app/services/__init__.py` | 0 | Ce fichier marque le package services. Il regroupe la logique metier appelee par les routes et pipelines. |
| `backend/app/services/documents/__init__.py` | 0 | Ce fichier marque le package documents. Il isole upload, parsing et segmentation des fichiers recus. |
| `backend/app/services/documents/docling_parser.py` | 4 | Ce fichier extrait le texte des PDF, DOCX et fichiers texte. Il nourrit ensuite segmentation, extraction LLM et indexation RAG. |
| `backend/app/services/documents/section_segmenter.py` | 3 | Ce fichier segmente le texte en sections heuristiques. Le retrieval et l'affichage des preuves utilisent ces sections pour filtrer le contexte. |
| `backend/app/services/documents/upload_manager.py` | 6 | Ce fichier gere sauvegarde temporaire et politiques d'upload. Les routes l'appellent avant tout parsing ou appel modele. |
| `backend/app/services/experience/__init__.py` | 0 | Ce fichier marque le package experience. Il regroupe calculs de duree, chevauchement et pertinence d'experience. |
| `backend/app/services/experience/duration_calculator.py` | 6 | Ce fichier calcule les durees d'experience a partir de dates ou durees declarees. Le CVExtractor l'utilise avant le matching d'experience. |
| `backend/app/services/experience/overlap_manager.py` | 2 | Ce fichier fusionne les periodes d'experience chevauchantes. Le matcher d'experience l'utilise pour eviter le double comptage de seniorite. |
| `backend/app/services/experience/relevance_calculator.py` | 6 | Ce fichier estime la pertinence d'une experience pour un job. Le matcher d'experience l'utilise pour separer mois totaux et mois pertinents. |
| `backend/app/services/extraction/__init__.py` | 0 | Ce fichier marque le package extraction. Il regroupe prompts, coercition et extracteurs LLM pour jobs et CV. |
| `backend/app/services/extraction/coercion.py` | 4 | Ce fichier nettoie les formes imparfaites renvoyees par le LLM. Les extracteurs l'appellent avant validation Pydantic. |
| `backend/app/services/extraction/cv_extractor.py` | 21 | Ce fichier transforme un CV texte en StructuredCV. Il combine LLM, coercition, normalisation, enrichissements raw-text et durees. |
| `backend/app/services/extraction/job_extractor.py` | 11 | Ce fichier transforme une fiche de poste en StructuredJobDescription. Il normalise les criteres et applique des regles textuelles explicites. |
| `backend/app/services/extraction/output_validator.py` | 4 | Ce fichier valide les sorties JSON du LLM. Il protege les schemas en isolant la logique de recuperation/parsing tolerant. |
| `backend/app/services/extraction/prompts.py` | 3 | Ce fichier contient les prompts d'extraction. Il maintient les consignes LLM separees du code de validation et de scoring. |
| `backend/app/services/matching/__init__.py` | 0 | Ce fichier marque le package matching. Il regroupe les matchers par categorie utilises par le moteur de scoring. |
| `backend/app/services/matching/certification_matcher.py` | 6 | Ce fichier matche certifications et domaines. ScoringEngine l'appelle comme categorie specialisee dans le score final. |
| `backend/app/services/matching/education_matcher.py` | 6 | Ce fichier matche niveaux et domaines de formation. Il transforme les criteres education en score explicable. |
| `backend/app/services/matching/experience_matcher.py` | 7 | Ce fichier matche la duree d'experience pertinente. Il combine durees calculees, chevauchements et pertinence heuristique. |
| `backend/app/services/matching/language_matcher.py` | 6 | Ce fichier matche langues et niveaux. Il convertit les niveaux normalises en credits visibles dans les details d'audit. |
| `backend/app/services/matching/responsibility_matcher.py` | 16 | Ce fichier matche les responsabilites du job avec missions et preuves RAG. Il contient les seuils et heuristiques les plus sensibles au vocabulaire metier. |
| `backend/app/services/matching/skill_matcher.py` | 13 | Ce fichier matche competences techniques et soft skills. Il alimente la categorie la plus importante du scoring global. |
| `backend/app/services/normalization/__init__.py` | 0 | Ce fichier marque le package normalization. Il regroupe les fonctions qui rendent textes, dates, langues, titres et competences comparables. |
| `backend/app/services/normalization/date_normalizer.py` | 4 | Ce fichier normalise dates et mois bilingues. Les calculs d'experience l'utilisent pour transformer du texte CV en periodes comparables. |
| `backend/app/services/normalization/education_normalizer.py` | 0 | Ce fichier normalise les niveaux de formation. Les extracteurs et le matcher education l'utilisent pour comparer les diplomes. |
| `backend/app/services/normalization/job_title_normalizer.py` | 2 | Ce fichier normalise les intitules de poste. Il soutient la pertinence d'experience et limite les variantes lexicales. |
| `backend/app/services/normalization/language_normalizer.py` | 0 | Ce fichier normalise langues et niveaux. Les extracteurs et le matcher langues l'utilisent pour comparer CV et exigences. |
| `backend/app/services/normalization/skill_normalizer.py` | 5 | Ce fichier normalise competences et alias. Il est appele par extraction, matching et enrichissement raw-text. |
| `backend/app/services/normalization/text_normalizer.py` | 0 | Ce fichier fournit la normalisation textuelle commune. Tous les matchers s'en servent pour rendre les comparaisons lexicales reproductibles. |
| `backend/app/services/orchestration/__init__.py` | 0 | Ce fichier marque le package orchestration. Il regroupe les pipelines qui assemblent parsing, LLM, RAG, scoring et jobs async. |
| `backend/app/services/orchestration/analyze_cv_pipeline.py` | 0 | Ce fichier assemble parsing et extraction d'un CV. Le BatchRankingPipeline l'appelle pour traiter chaque candidat. |
| `backend/app/services/orchestration/analyze_job_pipeline.py` | 0 | Ce fichier assemble parsing et extraction d'une fiche de poste. Le BatchRankingPipeline l'appelle avant d'analyser les CV. |
| `backend/app/services/orchestration/batch_ranking_pipeline.py` | 10 | Ce fichier orchestre l'analyse complete. Il relie document parsing, LLM, enrichissement, RAG, scoring, ranking et persistence. |
| `backend/app/services/orchestration/job_manager.py` | 8 | Ce fichier gere les analyses asynchrones en memoire. Les routes ranking l'utilisent pour creer, consulter et annuler des jobs. |
| `backend/app/services/ranking/__init__.py` | 0 | Ce fichier marque le package ranking. Il isole le tri final et la gestion des ex aequo. |
| `backend/app/services/ranking/ranking_engine.py` | 3 | Ce fichier trie les candidats et gere les ex aequo. Il reste separe du scoring pour isoler la presentation du classement. |
| `backend/app/services/retrieval/__init__.py` | 0 | Ce fichier marque le package retrieval. Il regroupe chunking, indexation et recherche semantique. |
| `backend/app/services/retrieval/chunk_builder.py` | 2 | Ce fichier decoupe les sections en chunks. SectionIndexer l'utilise avant d'appeler les embeddings et le vector store. |
| `backend/app/services/retrieval/section_indexer.py` | 3 | Ce fichier indexe les sections de CV dans le vector store. Il relie chunk_builder, embeddings NVIDIA et persistence vectorielle. |
| `backend/app/services/retrieval/semantic_retriever.py` | 2 | Ce fichier recherche les preuves semantiques. Il vectorise la requete job et interroge le vector store pour le scoring. |
| `backend/app/services/rules/__init__.py` | 0 | Ce fichier marque le package rules. Il isole le chargement des vocabulaires metier configurables. |
| `backend/app/services/rules/domain_rules.py` | 3 | Ce fichier charge les regles metier JSON. Les extracteurs et matchers y lisent les vocabulaires configurables. |
| `backend/app/services/scoring/__init__.py` | 0 | Ce fichier marque le package scoring. Il regroupe poids, moteur de score et explications affichees aux utilisateurs. |
| `backend/app/services/scoring/explanation_builder.py` | 0 | Ce fichier transforme les scores par categorie en forces/faiblesses. Le moteur de scoring l'utilise pour rendre le classement explicable. |
| `backend/app/services/scoring/scoring_engine.py` | 12 | Ce fichier combine tous les matchers en score final. Il applique les poids, filtre les categories non applicables et prepare les preuves. |
| `backend/app/services/scoring/weights.py` | 5 | Ce fichier charge et normalise les poids de scoring. ScoringEngine l'utilise pour convertir les categories en contribution finale. |
| `backend/docker-compose.yml` | 0 | Ce fichier decrit le service PostgreSQL local avec pgvector. Il soutient les tests et demonstrations qui utilisent le backend vectoriel SQL. |
| `backend/requirements-dev.txt` | 0 | Ce fichier ajoute les outils de developpement et de test au-dessus du runtime. Il reste separe pour alleger les installations de production. |
| `backend/requirements.txt` | 0 | Ce fichier liste les dependances runtime du backend FastAPI. Il est consomme par les environnements locaux, CI et deploiements Python. |
| `backend/scripts/free_port.py` | 0 | Ce script libere un port local avant lancement. Il aide les scripts de developpement a redemarrer FastAPI sans conflit de processus. |
| `backend/scripts/initialize_databases.py` | 0 | Ce script initialise les migrations de base. Il prepare PostgreSQL/pgvector avant les tests ou l'execution locale du backend. |
| `backend/scripts/render_result_report.py` | 0 | Ce script transforme un resultat JSON en rapport lisible. Il sert a inspecter hors frontend les sorties du classement. |
| `backend/scripts/run_backend.sh` | 0 | Ce script lance le backend en developpement. Il rassemble les etapes shell necessaires pour demarrer FastAPI localement. |
| `backend/tests/conftest.py` | 0 | Ce fichier prepare l'environnement de test backend. Il fixe des variables par defaut et nettoie l'etat partage entre tests. |
| `backend/tests/integration/test_api_ranking.py` | 0 | Ce fichier couvre l'analyse ranking via API avec dependances externes. Il reste separe et conditionnel car NVIDIA/PostgreSQL sont requis. |
| `backend/tests/integration/test_ranking_pipeline.py` | 0 | Ce fichier couvre le pipeline complet avec services externes. Il sert de validation bout-en-bout quand l'environnement d'integration est disponible. |
| `backend/tests/test_health.py` | 0 | Ce fichier verifie la route de sante. Il confirme que l'API expose les informations minimales attendues. |
| `backend/tests/unit/test_api_security_uploads.py` | 0 | Ce fichier contient les tests unitaires pour api security uploads. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_config_env.py` | 0 | Ce fichier contient les tests unitaires pour config env. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_domain_rules.py` | 0 | Ce fichier contient les tests unitaires pour domain rules. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_experience.py` | 0 | Ce fichier contient les tests unitaires pour experience. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_explanation_builder.py` | 0 | Ce fichier contient les tests unitaires pour explanation builder. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_extraction.py` | 0 | Ce fichier contient les tests unitaires pour extraction. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_extraction_coercion.py` | 0 | Ce fichier contient les tests unitaires pour extraction coercion. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_free_port.py` | 0 | Ce fichier contient les tests unitaires pour free port. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_jobs_and_retrieval.py` | 0 | Ce fichier contient les tests unitaires pour jobs and retrieval. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_matching.py` | 0 | Ce fichier contient les tests unitaires pour matching. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_normalization.py` | 0 | Ce fichier contient les tests unitaires pour normalization. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_nvidia_llm.py` | 0 | Ce fichier contient les tests unitaires pour nvidia llm. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_output_validator.py` | 0 | Ce fichier contient les tests unitaires pour output validator. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_ranking.py` | 0 | Ce fichier contient les tests unitaires pour ranking. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_reports_privacy.py` | 0 | Ce fichier contient les tests unitaires pour reports privacy. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_scoring.py` | 0 | Ce fichier contient les tests unitaires pour scoring. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `backend/tests/unit/test_vector_store_pgvector.py` | 0 | Ce fichier contient les tests unitaires pour vector store pgvector. Il protege le comportement existant pendant les refactors sans appeler les services externes. |
| `frontend/index.html` | 0 | Ce fichier est le point d'entree HTML de Vite. Il fournit le conteneur DOM dans lequel React monte l'application SmartRecruit. |
| `frontend/src/App.tsx` | 17 | Ce fichier porte l'experience frontend principale. Il appelle les routes ranking, suit les jobs asynchrones, et presente scores, preuves et details d'audit. |
| `frontend/src/main.tsx` | 0 | Ce fichier monte l'application React dans le DOM. Il relie index.html au composant App qui porte l'interface utilisateur. |
| `frontend/src/styles.css` | 0 | Ce fichier definit la presentation visuelle de l'application. Il transforme les etats et donnees React en interface lisible pour l'analyse de CV. |
| `frontend/src/validation.test.ts` | 0 | Ce fichier verifie la validation frontend des fichiers. Il protege les messages et limites affiches avant l'envoi au backend. |
| `frontend/src/validation.ts` | 0 | Ce fichier valide localement la selection de fichiers. Il duplique les limites utilisateur visibles avant que le backend applique ses propres garde-fous. |
| `frontend/src/vite-env.d.ts` | 0 | Ce fichier expose les types Vite au code TypeScript. Il permet aux modules frontend d'utiliser import.meta.env sans declarations locales. |
| `frontend/vite.config.ts` | 0 | Ce fichier configure Vite pour le frontend React. Il declare le plugin React et les options de serveur/build utilisees par npm. |
| `pyproject.toml` | 0 | Ce fichier centralise la configuration des outils Python. Pytest, coverage, ruff et mypy y lisent leurs conventions communes. |

## Exceptions de format

Les fichiers JSON suivants n'ont pas ete commentes, car JSON ne supporte pas les commentaires et ajouter des champs de documentation modifierait les donnees consommees par le code ou les outils npm/TypeScript:

- `backend/app/data/domain_rules.json`
- `backend/app/data/education_levels.json`
- `backend/app/data/job_title_aliases.json`
- `backend/app/data/language_levels.json`
- `backend/app/data/scoring_weights.json`
- `backend/app/data/skill_aliases.json`
- `frontend/package.json`
- `frontend/tsconfig.json`

## Incoherences remarquees sans correction

- `backend/app/services/ranking/ranking_engine.py` contient deja le libelle mojibake `ex ??quo` dans `rank_label`. Je ne l'ai pas corrige car la mission demandait uniquement des commentaires, sans modification de logique ou de texte fonctionnel.

