# Guide LaTeX SmartRecruit

Le document technique principal est [SmartRecruit_Documentation_Complete.tex](SmartRecruit_Documentation_Complete.tex).

## Usage

La compilation LaTeX sert uniquement a produire un PDF de documentation. L'application SmartRecruit ne depend pas de LaTeX pour l'installation, le demarrage, les tests ou l'analyse de CV.

## Prerequis

Installer une distribution LaTeX compatible:

- Windows: MiKTeX ou TeX Live.
- Linux/macOS: TeX Live ou MacTeX.
- En ligne: Overleaf.

Le compilateur choisi doit etre disponible dans le terminal utilise pour produire le PDF.

## Compilation

Compiler [SmartRecruit_Documentation_Complete.tex](SmartRecruit_Documentation_Complete.tex) depuis le dossier `docs/` avec le compilateur LaTeX disponible sur la machine. Deux passes de compilation stabilisent la table des matieres et les references.

Le README racine contient uniquement les commandes applicatives du projet. Les commandes LaTeX restent dans ce guide.

## Fichiers Generes

La compilation produit typiquement:

- `SmartRecruit_Documentation_Complete.pdf`
- `*.aux`
- `*.log`
- `*.out`
- `*.toc`

Ces fichiers sont des artefacts locaux et ne doivent pas etre versionnes.
