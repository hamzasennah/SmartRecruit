# Documentation SmartRecruit

Ce dossier contient la documentation detaillee du projet. Le point d'entree rapide reste le [README racine](../README.md).

## Documents

- [SmartRecruit_Documentation_Complete.tex](SmartRecruit_Documentation_Complete.tex): document LaTeX technique principal. Il couvre l'architecture, les dossiers, les fichiers, le pipeline, le scoring et les composants backend/frontend.
- [LATEX_COMPILATION_GUIDE.md](LATEX_COMPILATION_GUIDE.md): guide court pour compiler le document LaTeX si une distribution LaTeX est installee.
- [code_comments_report.md](code_comments_report.md): rapport genere lors de la documentation du code par commentaires. Il liste les fichiers commentes et les roles ajoutes.
- [documentation_audit.md](documentation_audit.md): audit des documents existants, actions prises, et preuves de verification des commandes documentees.
- [../MISE_A_JOUR_PGVECTOR.md](../MISE_A_JOUR_PGVECTOR.md): verification fonctionnelle et mise a jour documentaire apres le passage a pgvector.

## Documents Consolides

Les anciens documents LaTeX partiels ont ete retires pour eviter plusieurs sources de verite concurrentes:

- `docs/smartrecruit_explanation_complete.tex`
- `docs/backend_explication.tex`
- `backend/docs/backend_explanation.tex`

Leur contenu etait recouvert par le document principal `SmartRecruit_Documentation_Complete.tex` et par les commentaires ajoutes dans le code.

## Mise A Jour

Quand le code change:

1. Mettre a jour le README racine uniquement pour les commandes, prerequis et limites utiles au demarrage.
2. Garder les details fichier par fichier dans le LaTeX ou dans les commentaires de code.
3. Verifier les commandes documentees avant de les presenter comme valides.
