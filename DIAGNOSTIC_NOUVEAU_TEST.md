# Diagnostic du nouveau test SmartRecruit

## Contexte du test

Documents analyses:

- Fiche de poste: `besoin Data Analyst (IEJ ou IE1).pdf`
- CV: `Najlae_HMIMINA_CV.pdf`, `BI ANALYST.pdf`, `Sounia OaKKI.pdf`, `CV Firdawsse_Ahchouche.pdf`, `CV Adnane Mehdaoui-1.pdf`

La fiche de poste contient un besoin Data Analyst avec:

- competences obligatoires: Power BI, Excel, Snowflake, dashboard, KPI, Azure;
- competences souhaitees: Foundry, project management, business needs, supply chain, SPM, iTMS;
- langues: francais et anglais;
- experience: 1 a 3 ans, donc le backend convertit le minimum en 12 mois.

## Diagnostic honnete

Le classement technique fonctionnait, mais plusieurs scores etaient fausses ou trop durs pour de mauvaises raisons.

Premier probleme: certaines dates de CV n'etaient pas comprises. Exemple: `Depuis 22/04/2024` et les dates completes au format jour/mois/annee n'etaient pas parsees comme des periodes exploitables. Une experience Data Analyst actuelle pouvait donc tomber a 0 mois pertinents.

Deuxieme probleme: les langues presentes sans niveau explicite etaient marquees comme trouvees mais pouvaient recevoir 0 point si la fiche demandait un niveau courant. Ce comportement etait trop brutal: un CV qui mentionne francais et anglais ne doit pas afficher ces langues comme absentes.

Troisieme probleme: la pertinence d'une experience regardait surtout les titres preferes extraits de la fiche, mais pas assez le titre principal du poste ni les outils visibles dans les missions. Une mission Data Analyst avec Power BI, Excel, dashboard ou KPI pouvait donc etre sous-exploitee si le JSON du LLM ne rangeait pas parfaitement ces outils dans `skills_used`.

Quatrieme probleme: une limite applicative `MAX_CV_FILES` existait encore dans le backend, le frontend et la documentation. Elle contredisait la logique du projet: le nombre de CV ne doit pas etre limite arbitrairement; seules les tailles fichier et totale doivent proteger l'upload.

## Corrections appliquees

Les corrections ne remplacent pas les appels NVIDIA et ne creent pas de modele alternatif. Elles corrigent les etapes deterministes autour du pipeline:

- le parsing des dates accepte maintenant `Depuis 22/04/2024`, `22/04/2024`, `2024-04-22`, les mois francais/anglais et `Present`;
- le calcul d'experience considere ces dates completes comme des dates precises;
- la pertinence d'experience utilise le titre principal du job, les titres preferes, les competences explicitement ecrites dans les missions et la similarite des responsabilites;
- les langues mentionnees sans niveau recoivent un credit partiel au lieu d'un 0 artificiel;
- la limite `MAX_CV_FILES` a ete retiree du backend, du frontend, du README, de `.env.example` et de la documentation LaTeX;
- les tests unitaires couvrent maintenant ces cas pour eviter une regression.

## Ce qui reste volontairement strict

Un score faible peut etre correct si la fiche exige des outils tres precis:

- Snowflake ne doit pas etre donne si le CV parle seulement de base de donnees ou SQL;
- Azure ne doit pas etre donne si le CV parle seulement de cloud sans mention directe;
- Foundry, SPM et iTMS sont des criteres souhaites; leur absence ne doit pas devenir une faiblesse principale forte;
- les stages ne doivent pas etre comptes comme experience professionnelle principale si le prompt et les regles projet demandent de les exclure.

## Verification du RAG

Le RAG reste base sur les appels reels:

1. extraction du texte par PyMuPDF / DOCX / TXT;
2. segmentation en sections;
3. extraction structuree par NVIDIA LLM;
4. enrichissement par preuves explicitement presentes dans le texte brut;
5. creation de chunks;
6. embeddings NVIDIA;
7. stockage des vecteurs dans PostgreSQL / pgvector;
8. recherche semantique par similarite cosinus;
9. scoring explicable avec preuves et details d'audit.

Chaque analyse utilise un namespace temporaire propre. Les vecteurs temporaires sont supprimes en fin d'analyse, donc les resultats precedents ne sont pas reutilises pour classer un nouveau lot de CV.

## Fichiers corriges

- `backend/app/services/normalization/date_normalizer.py`
- `backend/app/services/experience/duration_calculator.py`
- `backend/app/services/experience/relevance_calculator.py`
- `backend/app/services/matching/language_matcher.py`
- `backend/app/services/documents/upload_manager.py`
- `backend/app/config.py`
- `backend/app/core/config_validation.py`
- `frontend/src/validation.ts`
- `README.md`
- `backend/.env.example`
- `docs/SmartRecruit_Documentation_Complete.tex`

## Validation

Les tests automatises backend et frontend doivent confirmer:

- parsing des dates completes;
- calcul des mois pertinents pour une experience Data Analyst actuelle;
- credit partiel quand une langue est mentionnee sans niveau;
- absence de limite arbitraire sur le nombre de CV;
- conservation des controles de taille et de format.
