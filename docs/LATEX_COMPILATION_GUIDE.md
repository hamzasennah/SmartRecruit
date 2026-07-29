# Guide LaTeX SmartRecruit

Le document technique principal est [SmartRecruit_Documentation_Complete.tex](SmartRecruit_Documentation_Complete.tex).

## Statut De Verification

La compilation LaTeX n'a pas ete executee dans l'environnement actuel: ni `xelatex` ni `pdflatex` ne sont installes localement. Le projet applicatif ne depend pas de LaTeX pour fonctionner; cette etape sert uniquement a produire un PDF de documentation.

## Preparer La Compilation

Installer une distribution LaTeX avant de compiler:

- Windows: MiKTeX ou TeX Live.
- Linux/macOS: TeX Live ou MacTeX.
- En ligne: Overleaf peut compiler le fichier sans installation locale.

Verifier ensuite que le compilateur choisi est disponible dans le terminal avant de lancer la compilation.

## Compilation

Aucune commande de compilation exacte n'est documentee comme validee dans ce depot, car aucun compilateur LaTeX n'est disponible dans l'environnement de verification actuel.

Sur une machine equipee de LaTeX, compiler [SmartRecruit_Documentation_Complete.tex](SmartRecruit_Documentation_Complete.tex) depuis le dossier `docs/` avec le compilateur choisi, puis refaire une passe si la table des matieres ou les references doivent etre stabilisees. Ajouter une commande precise au README seulement apres l'avoir executee avec succes dans l'environnement vise.

## Fichiers Generes

La compilation produit typiquement:

- `SmartRecruit_Documentation_Complete.pdf`
- `*.aux`
- `*.log`
- `*.out`
- `*.toc`

Ces fichiers sont des artefacts locaux et ne doivent pas etre versionnes.
