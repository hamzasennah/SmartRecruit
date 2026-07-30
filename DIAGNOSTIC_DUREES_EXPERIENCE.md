# Diagnostic des durees d'experience

## 1. Anomalie observee

Le cas qui a revele le probleme est le CV de Sounia OaKKI. Le texte extrait du PDF contient notamment :

- `Data Analyst (Depuis 22/04/2024)`
- `Support IT JO Paris 2024 (De 15/05/2023 a 19/04/2024)`
- `Stage | Data Analyst (De 27/06/2022 a 26/12/2022)`

Avant correction, une experience ecrite sous la forme `Depuis 22/04/2024` pouvait etre mal exploitee si le LLM ne remplissait pas explicitement `end_date` avec `Present`. Le calculateur attendait une date de debut et une date de fin parsees separement. Si la fin etait absente, la mention `Depuis` n'etait pas utilisee pour deduire que le poste est toujours en cours.

La valeur attendue au 30/07/2026 est :

- `Data Analyst (Depuis 22/04/2024)` -> 28 mois.
- `Support IT JO Paris 2024 (De 15/05/2023 a 19/04/2024)` -> 12 mois.
- `Stage | Data Analyst (De 27/06/2022 a 26/12/2022)` -> date parseable, mais non compte comme experience professionnelle car les stages sont filtres avant le matching.

## 2. Cause racine

La cause n'etait pas le modele d'embedding ni PostgreSQL. Le probleme se trouvait dans la couche de normalisation et de calcul des dates :

1. `Depuis ...` et `since ...` etaient seulement nettoyes comme prefixes, mais pas interpretes comme poste en cours quand `end_date` etait vide.
2. Une plage complete stockee dans un seul champ, par exemple `Mar 2022 - Juil 2022` ou `June 2025 - Present`, n'etait pas separee avant le calcul.
3. Les formats jour/mois/annee et certaines abreviations francaises avec point, par exemple `janv. 2024`, n'etaient pas couverts proprement.
4. Les dates avec seulement l'annee etaient parsees avec un mois central par defaut, mais sans decision explicite selon le role de la date. Le calcul devait choisir janvier pour une date de debut annuelle et decembre pour une date de fin annuelle.
5. Il n'y avait pas de validation de plausibilite pour empecher une duree manifestement impossible de passer comme valeur fiable.

## 3. Correction appliquee

Les corrections ont ete faites a la source, sans regle specifique a un candidat.

- `backend/app/services/normalization/date_normalizer.py`
  - Reconnaissance plus complete des mois francais et anglais.
  - Support des dates `JJ/MM/AAAA`, `AAAA-MM-JJ`, `MM/AAAA`, `AAAA/MM`, mois textuels et annees seules.
  - Support des mentions de poste en cours : `present`, `en cours`, `a ce jour`, `actuellement`, `ongoing`, etc.
  - Detection des marqueurs de debut en cours : `Depuis ...`, `Since ...`, `a partir de ...`.

- `backend/app/services/experience/duration_calculator.py`
  - Separation automatique des plages de dates quand elles arrivent dans un seul champ.
  - Interpretation de `Depuis ...` sans date de fin comme une experience terminee au mois courant.
  - Ajustement explicite des annees seules : janvier pour un debut, decembre pour une fin.
  - Centralisation du calcul : `duration_months` est derive du meme objet `ExperienceDuration`.
  - Signalement des durees non plausibles au lieu de les compter.

- `backend/tests/unit/test_experience.py`
  - Ajout de tests sur des formats varies, pas seulement sur le CV qui a revele l'anomalie.

## 4. Validation

Les tests unitaires ciblent maintenant les cas suivants :

| Cas teste | Resultat attendu |
|---|---:|
| `janvier 2021` -> `mars 2023` | 27 mois |
| `Mar 2022` -> `Juil 2022` | 5 mois |
| `Depuis 22/04/2024` -> `Present` | 13 mois au 01/04/2025 |
| `Depuis 22/04/2024` sans date de fin | 13 mois au 01/04/2025 |
| `Mar 2022 - Juil 2022` dans un seul champ | 5 mois |
| `June 2025 - Present` | 14 mois au 01/07/2026 |
| `2021` -> `2022` | 24 mois, marque comme estimation |
| `janv. 2024` -> `aout 2024` | 8 mois |
| `04/22/2024` -> `Present` | 13 mois au 01/04/2025 |
| `1900` -> `Present` | erreur de plausibilite, non compte |

Validation executee :

```text
python -m pytest tests\unit\test_experience.py -q
12 passed
```

Verification directe sur le cas source au 30/07/2026 :

```text
Depuis 22/04/2024 | None => 28 mois
De 15/05/2023 | 19/04/2024 => 12 mois
De 27/06/2022 | 26/12/2022 => 7 mois, mais stage exclu du matching professionnel
```

