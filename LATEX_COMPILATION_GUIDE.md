# Guide de compilation du document LaTeX

## Vue d'ensemble

Le fichier `SmartRecruit_Documentation_Complete.tex` est un document LaTeX complet et prêt à compiler en PDF. Ce guide vous aide à générer le PDF final.

## Option 1 : Compilation avec Overleaf (Recommandé - Plus simple)

Overleaf est un éditeur LaTeX en ligne qui ne nécessite aucune installation locale.

### Étapes

1. **Accéder à Overleaf**
   - Aller sur https://www.overleaf.com/
   - Créer un compte (gratuit) ou se connecter

2. **Créer un nouveau projet**
   - Cliquer sur "New Project"
   - Choisir "Blank Project" ou "Upload Project"

3. **Uploader le fichier**
   - Si "Blank Project" : Créer un nouveau fichier et copier-coller le contenu de `SmartRecruit_Documentation_Complete.tex`
   - Si "Upload Project" : Uploader directement le fichier `.tex`

4. **Compiler**
   - Dans l'interface Overleaf, cliquer sur le bouton "Compile" (vert)
   - Le PDF est généré automatiquement et s'affiche à droite
   - Attendre ~30-60 secondes pour la première compilation

5. **Télécharger le PDF**
   - Cliquer sur le bouton "Download PDF" (flèche vers le bas)
   - Le fichier `SmartRecruit_Documentation_Complete.pdf` est téléchargé

### Avantages
- ✅ Aucune installation locale requise
- ✅ Support automatique de tous les packages LaTeX
- ✅ Interface intuitive
- ✅ Compilation rapide
- ✅ Historique et versioning des documents

### Inconvénients
- ⚠️ Nécessite une connexion Internet
- ⚠️ Les fichiers sont stockés sur les serveurs Overleaf

---

## Option 2 : Compilation locale sur Windows

### Prérequis

Vous devez installer une distribution LaTeX. Sur Windows, les options principales sont :

#### A. MiKTeX (Recommandé pour Windows)

1. **Télécharger et installer MiKTeX**
   - Aller sur https://miktex.org/download
   - Télécharger l'installateur Windows
   - Exécuter l'installation

2. **Vérifier l'installation**
   - Ouvrir PowerShell ou Invite de commandes
   - Taper : `pdflatex --version`
   - Si le numéro de version s'affiche, l'installation a réussi

3. **Compiler le document**
   ```powershell
   cd C:\Users\pc\SmartRecruit
   pdflatex -interaction=nonstopmode SmartRecruit_Documentation_Complete.tex
   ```

4. **Attendre la compilation**
   - La compilation prend 30-60 secondes (2-3 passes)
   - MiKTeX télécharge automatiquement les packages manquants
   - À la fin, le fichier `SmartRecruit_Documentation_Complete.pdf` est créé

#### B. TeX Live (Alternative, plus lourd)

1. **Télécharger et installer TeX Live**
   - Aller sur https://www.tug.org/texlive/
   - Télécharger l'installeur Windows
   - Exécuter l'installation (prend ~1 GB d'espace)

2. **Compiler** (même commande que MiKTeX)

#### C. Portable MiKTeX (Sans installation)

Si vous ne pouvez pas installer :
1. Télécharger MiKTeX Portable
2. Extraire l'archive
3. Compiler via `pdflatex` directement

### Compilation détaillée

#### Simple : Compilation unique
```powershell
cd C:\Users\pc\SmartRecruit
pdflatex SmartRecruit_Documentation_Complete.tex
```

#### Complète : Avec table of contents et références (Recommandé)
```powershell
cd C:\Users\pc\SmartRecruit

# Première pass
pdflatex -interaction=nonstopmode SmartRecruit_Documentation_Complete.tex

# Deuxième pass (pour table of contents)
pdflatex -interaction=nonstopmode SmartRecruit_Documentation_Complete.tex
```

#### Avec la-ui optimale (XeLaTeX recommandé pour français)
```powershell
cd C:\Users\pc\SmartRecruit

# Première pass
xelatex -interaction=nonstopmode SmartRecruit_Documentation_Complete.tex

# Deuxième pass
xelatex -interaction=nonstopmode SmartRecruit_Documentation_Complete.tex
```

### Où trouver le PDF généré

Le fichier `SmartRecruit_Documentation_Complete.pdf` sera créé dans le répertoire `c:\Users\pc\SmartRecruit\`.

### Fichiers temporaires

LaTeX génère des fichiers temporaires :
- `*.aux` - Références auxiliaires
- `*.log` - Fichier de log (utile pour déboguer)
- `*.out` - Table of contents (naviga dans le PDF)
- `*.toc` - Table des matières (utilisée pour génération PDF)

Ces fichiers peuvent être supprimés après compilation si souhaité.

---

## Option 3 : Compilation via VS Code (Avancé)

### Prérequis
- LaTeX installé (MiKTeX ou TeX Live)
- Extension VS Code : "LaTeX Workshop" (James W. Finley)

### Étapes

1. **Installer l'extension**
   - Ouvrir VS Code
   - Extensions → Chercher "LaTeX Workshop"
   - Cliquer "Install"

2. **Ouvrir le fichier**
   - Fichier → Ouvrir : `SmartRecruit_Documentation_Complete.tex`

3. **Compiler**
   - Utiliser le raccourci : `Ctrl+Alt+B` (Build LaTeX)
   - Ou cliquer sur "TeXify" en bas à droite

4. **Visualiser**
   - Le PDF s'ouvre automatiquement dans un viewer intégré
   - Utiliser `Ctrl+Alt+V` pour basculer entre source et PDF

### Avantages
- ✅ Éditeur intégré (VS Code)
- ✅ Syntax highlighting LaTeX
- ✅ Auto-compilation à chaque save
- ✅ Synchronisation source ↔ PDF

---

## Dépannage

### Erreur : "pdflatex : Le terme «pdflatex» n'est pas reconnu"

**Cause** : LaTeX n'est pas installé ou pas dans le PATH

**Solution** :
1. Installer MiKTeX ou TeX Live
2. Redémarrer PowerShell/CMD après installation
3. Vérifier : `pdflatex --version`

### Erreur : "File XXX.sty not found"

**Cause** : Un package LaTeX manque

**Solution** :
- MiKTeX : Les packages se téléchargent automatiquement. Réessayer la compilation.
- TeX Live : Installer les packages manuellement via le gestionnaire.

### Le PDF n'affiche pas les caractères français

**Cause** : Encodage UTF-8 non appliqué

**Solution** :
- Utiliser `xelatex` au lieu de `pdflatex`
- Ou `lualatex`

Commande :
```powershell
xelatex -interaction=nonstopmode SmartRecruit_Documentation_Complete.tex
```

### La compilation est très lente

**Cause** : Première compilation avec download de packages

**Solution** :
- C'est normal la première fois. Les passes suivantes sont plus rapides.
- MiKTeX télécharge les packages à la demande.

### Erreur sur la table of contents

**Cause** : Table of contents n'est pas à jour après première compilation

**Solution** :
- Compiler deux fois (voir section "Compilation complète" ci-dessus)

---

## Résultat attendu

Après compilation réussie, un fichier **`SmartRecruit_Documentation_Complete.pdf`** sera créé avec :

- ✅ 12 chapitres numérotés
- ✅ Table of contents interactive (cliquable)
- ✅ En-têtes et pieds de page
- ✅ Code source colorisé et lisible
- ✅ Tableaux professionnels
- ✅ Navigation par bookmarks
- ✅ Hyperlinks internes
- ✅ Numérotation des pages
- ✅ Références croisées

---

## Taille estimée du PDF

- ~80-120 pages selon la version LaTeX
- ~5-10 MB (avec images si ajoutées)

---

## Maintenance du document

Si vous modifiez le fichier `.tex` :

1. Éditer `SmartRecruit_Documentation_Complete.tex` avec un éditeur texte
2. Recompiler via l'une des méthodes ci-dessus
3. Le PDF est régénéré

### Points à vérifier après modification

- Synthaxe LaTeX correcte
- Accolades `{}` équilibrées
- Commandes `\` valides
- Encoding UTF-8 préservé

---

## Ressources complémentaires

- **Overleaf Documentation** : https://www.overleaf.com/learn
- **CTAN (LaTeX Packages)** : https://ctan.org/
- **MiKTeX Help** : https://docs.miktex.org/
- **TeX Live Help** : https://www.tug.org/texlive/

---

## Résumé des étapes rapides

| Méthode | Temps d'installation | Temps de compilation | Difficulté |
|---------|----------------------|-----------------------|------------|
| Overleaf | 5 min (créer compte) | 1 min | Facile |
| MiKTeX local | 15-30 min | 30-60 sec | Moyen |
| TeX Live local | 30-60 min | 30-60 sec | Moyen |
| VS Code | 30 min | 30-60 sec | Avancé |

**Recommandation finale** : Commencer par Overleaf si aucune installation. Si utilisation régulière, installer MiKTeX pour plus de contrôle.

---

**Bon à savoir** : Le document LaTeX est valide et complet. Aucune modification ou package supplémentaire n'est généralement nécessaire.
