# Diagnostic final - anomalies KPI, experience et preuves

## Contexte verifie

Le test concerne la fiche `besoin Data Analyst (IEJ ou IE1).pdf` et les CV du dossier `C:/Users/pc/Desktop/test 2`.
Le systeme utilise toujours les appels NVIDIA pour le LLM et les embeddings, puis stocke les chunks vectorises dans PostgreSQL. Aucune logique de remplacement de modele, aucun faux appel et aucun score force n'ont ete ajoutes.

Le journal `backend/storage/model_audit.jsonl` montre les appels reels vers:

- `https://integrate.api.nvidia.com/v1/chat/completions` pour le LLM;
- `https://integrate.api.nvidia.com/v1/embeddings` pour les embeddings;
- le modele LLM configure: `meta/llama-3.1-8b-instruct`;
- le modele embedding configure: `nvidia/llama-nemotron-embed-1b-v2`.

Ce journal est volontairement metadata-only: il garde endpoint, modele, statut, latence, contexte et parametres, mais pas les prompts complets ni les CV complets.

## Anomalie 1 - `KPIs` non reconnu comme `kpi`

### Symptome

Dans le CV de Najlae Hmimina, le PDF contient explicitement:

```text
Developed measures and KPIs using the DAX language.
```

Pourtant, le rapport indiquait parfois `kpi` dans les competences obligatoires manquantes.

### Origine

Origine principale: code de normalisation et de detection explicite.

Le systeme cherchait `kpi`, mais pas la forme plurielle `kpis`. La verification raw-text utilise des frontieres de mots strictes; donc `kpis` ne validait pas automatiquement `kpi`.

Ce n'etait pas un probleme de RAG ni de PostgreSQL: le texte etait bien extrait, mais l'alias manquait dans les regles de normalisation.

### Correction appliquee

Fichiers modifies:

- `backend/app/data/skill_aliases.json`
- `backend/app/data/domain_rules.json`
- `backend/app/services/extraction/prompts.py`
- `backend/tests/unit/test_extraction.py`

Corrections:

- ajout de `kpis` et variantes anglaises/francaises vers la competence canonique `kpi`;
- ajout de ces variantes dans les regles raw-text CV;
- ajout de ces variantes dans les regles de fiche de poste;
- ajout de ces variantes dans le groupe conceptuel dashboard/reporting;
- precision du prompt pour demander au LLM de ramener les pluriels explicites vers une forme canonique atomique.

### Verification

Une verification directe sur le PDF `Najlae_HMIMINA_CV.pdf` detecte maintenant:

```text
kpi, azure, dashboard, excel, power bi
```

Le test unitaire ajoute confirme que le texte `Developed measures and KPIs...` enrichit correctement le CV avec `kpi`.

## Anomalie 2 - CV Adnane et competences marquees manquantes

### Symptome

Le rapport indique que le CV Adnane contient `Power BI`, mais pas `excel`, `dashboard`, `kpi`, `azure` ou `snowflake`.

### Verification source

Le texte extrait de `CV Adnane Mehdaoui-1.pdf` contient `Power BI`.
Les recherches exactes dans le texte extrait n'ont pas trouve:

```text
kpi, kpis, excel, dashboard, azure, snowflake
```

### Conclusion

Pour ce PDF precis, ce n'est pas une anomalie du matcher: le systeme ne doit pas attribuer ces competences si elles ne sont pas explicitement presentes dans le texte extrait.

## Anomalie 3 - stages comptes comme experience professionnelle

### Symptome

Certains stages pouvaient encore influencer la duree d'experience lorsque le LLM extrayait un poste et des dates, mais que le marqueur `internship`, `stage` ou `PFE` etait place sur une ligne voisine plutot que dans le titre extrait.

### Origine

Origine mixte:

- le prompt interdit deja de transformer les stages en experience professionnelle;
- le code de securite regardait le titre, les missions et une fenetre autour de la date;
- cette fenetre ne capturait pas toujours la ligne voisine contenant `Final Year Internship`.

### Correction appliquee

Fichier modifie:

- `backend/app/services/extraction/cv_extractor.py`

La detection verifie maintenant aussi le contexte par lignes autour des dates d'experience.
Si une date d'experience est voisine d'un marqueur de stage, l'experience est exclue de la liste professionnelle.

### Verification

Le test unitaire ajoute avec:

```text
February 2025 - July 2025
Data Analyst / BI Developer - Final Year Internship
```

confirme que cette experience n'est plus comptee comme experience professionnelle.

## Checklist exhaustive

- Extraction texte PDF verifiee avec PyMuPDF.
- Detection explicite de `KPIs` verifiee depuis le texte brut.
- Enrichissement raw-text des competences verifie par test unitaire.
- Filtrage des stages voisins des dates verifie par test unitaire.
- Aucun fallback de modele ajoute.
- Aucun cache de resultat ajoute.
- Aucun score force ajoute.
- PostgreSQL reste utilise pour les chunks/vector store.
- Les appels NVIDIA restent les seuls appels modele.

## Tests executes

Tests cibles:

```powershell
cd C:\Users\pc\SmartRecruit\backend
.\.venv\Scripts\python.exe -m pytest tests\unit\test_extraction.py tests\unit\test_matching.py -q
```

Resultat:

```text
33 passed
```

Suite complete:

```powershell
cd C:\Users\pc\SmartRecruit\backend
.\.venv\Scripts\python.exe -m pytest -q
```

Resultat:

```text
108 passed, 2 skipped
```

Les 2 tests ignores sont les tests d'integration qui demandent une configuration NVIDIA API + PostgreSQL active dans l'environnement d'execution.

## Conclusion

Le probleme `KPIs` etait une vraie anomalie de code: le texte etait present, mais la normalisation ne couvrait pas le pluriel. Cette anomalie est corrigee et testee.

Le cas Adnane n'est pas une erreur pour les competences absentes: le texte extrait ne contient pas `excel`, `dashboard`, `kpi`, `azure` ou `snowflake`.

Le filtrage des stages a ete renforce pour eviter de compter une experience de stage comme experience professionnelle pertinente.
