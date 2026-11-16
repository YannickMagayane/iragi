# Iragi

<p align="center">
  <strong>Inspecter. Extraire. Analyser.</strong><br>
  <em>Toolkit Python modulaire pour l'inspection de qualité de données et l'extraction de documents.</em>
</p>

<p align="center">
  <a href="#objectifs"><img src="https://img.shields.io/badge/Python-3.14%2B-blue.svg" alt="Python 3.14+"></a>
  <a href="#installation"><img src="https://img.shields.io/badge/Version-0.1.0-green.svg" alt="Version 0.1.0"></a>
  <a href="#licence"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="Licence MIT"></a>
  <a href="#documentation"><img src="https://img.shields.io/badge/Docs-Sphinx-orange.svg" alt="Documentation Sphinx"></a>
  <a href="#architecture-modulaire"><img src="https://img.shields.io/badge/Architecture-Modular-purple.svg" alt="Architecture modulaire"></a>
</p>

---

**Iragi** est un package Python modulaire dédié à l'inspection, à l'extraction et à l'analyse de fichiers. Il réunit deux moteurs indépendants — **Scan** et **PDF** — et propose un troisième module, **All**, qui orchestre leur fonctionnement dans un pipeline unifié.

L'objectif est de fournir une bibliothèque réutilisable dans des scripts Python, des applications Django ou FastAPI, des outils Data et des workflows d'automatisation, tout en offrant une interface en ligne de commande (CLI) simple et puissante.

> **Principe de conception clé :** chaque moteur doit pouvoir être utilisé seul. Le module `iragi.all` coordonne les moteurs existants sans recopier leur logique métier.

---

## Sommaire

- [Objectifs](#objectifs)
- [Fonctionnalités](#fonctionnalités)
  - [1. iragi.scan — Inspection et qualité](#1-iragiscan--inspection-et-qualité-des-fichiers)
  - [2. iragi.pdf — Extraction de documents PDF](#2-iragipdf--extraction-de-documents-pdf)
  - [3. iragi.all — Orchestration et pipeline](#3-iragiall--orchestration-des-moteurs)
- [Architecture modulaire](#architecture-modulaire)
- [Installation](#installation)
- [Utilisation en Python](#utilisation-en-python)
  - [Inspection avec Scan](#inspection-dun-fichier-avec-scan)
  - [Extraction PDF](#extraction-dun-pdf)
  - [Pipeline unifié avec All](#analyse-combinée-avec-all)
- [Interface CLI](#interface-cli)
- [Rapports](#rapports)
- [Documentation Sphinx](#documentation-sphinx)
- [Architecture du projet](#architecture-du-projet)
- [Socle technologique & Potentiel](#socle-technologique--fort-potentiel)
- [Principes de conception](#principes-de-conception)
- [Feuille de route](#feuille-de-route)
- [Contribution](#contribution)
- [Licence](#licence)

---

## Objectifs

Iragi vise à simplifier trois opérations fréquentes dans les projets logiciels et Data :

1. **Inspecter des fichiers** pour comprendre leur structure, leur contenu et leur qualité.
2. **Extraire des informations de documents PDF**, notamment le texte, les tableaux et les métadonnées.
3. **Enchaîner extraction et contrôle qualité** afin de produire un résultat exploitable et un rapport cohérent.

Iragi n'est pas conçu comme une application web autonome. C'est d'abord un **package Python**, avec une CLI intégrée. Il doit pouvoir être incorporé à d'autres applications sans imposer un framework particulier (Django, FastAPI, Flask, notebooks ou scripts autonomes).

---

## Fonctionnalités

### 1. `iragi.scan` — Inspection et qualité des fichiers

Le moteur Scan analyse les fichiers structurés ou textuels afin d'en comprendre le contenu et de détecter les anomalies et problèmes courants de qualité.

**Formats ciblés :**
- **CSV** (séparateurs automatiques, encodages variés)
- **Excel** (`.xlsx`, `.xls` selon dépendances)
- **JSON** (objets, tableaux tabulaires, JSON Lines)
- **TXT** et logs techniques
- Autres formats tabulaires ajoutés progressivement

**Capacités principales :**
- **Détection de format** et lecture intelligente du fichier.
- **Inspection structurelle :** comptage des lignes, colonnes, feuilles et types de données.
- **Profilage des colonnes :** détection des types inférés, unicité, cardinalité.
- **Contrôle de complétude :** valeurs manquantes, vides ou nulles.
- **Détection des doublons :** lignes redondantes ou quasi-doublons.
- **Détection des types incohérents :** formats de dates invalides, anomalies numériques.
- **Repérage d'anomalies statistiques :** outliers via méthode IQR configurable.
- **Statistiques descriptives :** moyennes, médianes, min/max, percentiles.
- **Score indicatif de qualité :** score pondéré et explicable sur 100 avec détail des pénalités.
- **Recommandations exploitables :** conseils de nettoyage et d'assainissement ciblés.
- **Nettoyage explicite :** aucune mutation destructive du fichier source ; production de nouveaux artefacts nettoyés.

### 2. `iragi.pdf` — Extraction de documents PDF

Le moteur PDF se concentre sur l'extraction, la structuration et la numérisation du contenu des documents PDF.

**Capacités principales :**
- **Extraction textuelle :** flux de texte structuré par page, paragraphe et bloc.
- **Extraction tabulaire :** extraction et conversion directe des grilles de données tabulaires vers des DataFrames / CSV.
- **Métadonnées :** titre, auteur, date de création, producteur, nombre de pages.
- **Traitement par lots (Batch) :** traitement efficace de répertoires de PDF entiers.
- **Détection des pages scannées :** identification automatique des pages nécessitant une reconnaissance optique.
- **OCR facultatif :** reconnaissance optique de caractères pour documents numérisés via Tesseract.
- **Exports multi-formats :** exports directs en JSON, CSV, Excel ou Markdown.

### 3. `iragi.all` — Orchestration des moteurs

Le module All combine les moteurs Scan et PDF dans un pipeline unifié et cohérent.

**Workflow type :**
1. Réception d'un document PDF (e.g. facture, relevé, rapport d'audit).
2. Extraction du texte, des métadonnées et des tableaux via `iragi.pdf`.
3. Structuration des données tabulaires extraites en objets intermédiaires.
4. Transmission automatique de ces données au moteur `iragi.scan`.
5. Audit de conformité et calcul du score de qualité des données extraites.
6. Génération d'un rapport consolidé traçable (JSON, HTML ou console).

---

## Architecture modulaire

Les trois modules sont conçus pour être importés et exécutés en toute indépendance.

| Module | Responsabilité | Utilisation autonome | Dépendances spécifiques |
|---|---|---|---|
| `iragi.scan` | Inspection et qualité des fichiers | **Oui** | `pandas`, `openpyxl` |
| `iragi.pdf` | Extraction de texte, tables et OCR | **Oui** | `pypdf`, `pdfplumber`, `pytesseract` (opt) |
| `iragi.all` | Orchestration et pipeline combiné | **Oui** | scan + pdf |

Cette séparation offre des avantages concrets :
- Intégrer `iragi.scan` dans un projet Django existant sans installer les dépendances PDF lourdes.
- Employer `iragi.pdf` dans un simple script de conversion documentaire.
- Tirer parti de `iragi.all` pour bâtir des pipelines de données bout-en-bout.
- Tester et faire évoluer chaque moteur de manière isolée.

---

## Installation

Iragi propose une installation minimale ultra-légère complétée par des extras optionnels :

```bash
# Installation minimale (moteur Scan seul)
pip install iragi

# Installation avec le moteur PDF
pip install "iragi[pdf]"

# Installation avec le support OCR pour documents scannés
pip install "iragi[ocr]"

# Installation complète (Scan + PDF + OCR + CLI complète)
pip install "iragi[all]"
```

---

## Utilisation en Python

### Inspection d'un fichier avec Scan

```python
from iragi.core.models import DataInspectionResult
from iragi import scan

# Inspection d'un fichier tabulaire
result: DataInspectionResult = scan("clients.csv")

# Affichage des métriques clés
print(f"Lignes : {result.row_count}, Colonnes : {result.column_count}")
print(f"Score de qualité : {result.quality_score.total_score}/100")
print("Recommandations :", result.recommendations)

# Parcours des colonnes profilées
for col in result.column_profiles:
    print(f"- {col.name} ({col.inferred_type}) : {col.missing_count} valeurs manquantes")
```

### Extraction d'un PDF

```python
from iragi.pdf import extract, extract_tables

# Extraction du document et de ses métadonnées
document = extract("rapport_annuel.pdf")
print("Titre :", document.metadata.get("title"))
print("Pages :", len(document.pages))

# Extraction des tableaux sous forme tabulaire
tables = extract_tables("rapport_annuel.pdf")
for idx, table in enumerate(tables):
    print(f"Tableau #{idx + 1} ({len(table.rows)} lignes)")
```

### Analyse combinée avec All

```python
from iragi import analyze

# Pipeline unifié extraction + audit de qualité
result = analyze("factures_q3.pdf")

print("Score de qualité global :", result.quality_report.quality_score.total_score)
print("Données tabulaires extraites :", len(result.extracted_data.tables))
print("Anomalies détectées :", result.quality_report.potential_outliers_count)
```

---

## Interface CLI

Iragi dispose d'une interface en ligne de commande moderne et intuitive construite avec `typer` et mise en forme avec `rich`.

```bash
# Inspection de fichiers tabulaires
iragi scan data.csv
iragi scan data.xlsx --sheet "Ventes"
iragi scan data.json --output report.json

# Extraction PDF
iragi pdf text document.pdf
iragi pdf tables document.pdf --format csv --output ./tables/
iragi pdf metadata document.pdf

# Pipeline complet
iragi all document.pdf
iragi all document.pdf --report html --output ./reports/audit.html
```

---

## Rapports

Iragi permet d'exporter les résultats dans différents formats pour convenir à tous les usages :

- **JSON :** Structure complète sérialisable pour pipelines CI/CD, APIs REST ou Django/FastAPI.
- **HTML :** Rapports interactifs lisibles dans un navigateur, avec graphiques et tableaux clairs.
- **CSV / Excel :** Export direct des données extraites ou nettoyées.

Chaque rapport garantit une traçabilité rigoureuse : empreinte du fichier source, date et heure d'analyse, paramètres de configuration appliqués et détail des pénalités du score de qualité.

---

## Documentation Sphinx

La documentation technique est générée automatiquement à partir des docstrings au format Sphinx.

### Génération locale

Pour générer la documentation HTML du projet :

```bash
# Génération standard
bin/docs

# Nettoyage et régénération complète
bin/docs --clean -E -a
```

La documentation compilée est générée dans `docs/build/html/index.html`.

---

## Architecture du projet

```text
iragi/
├── bin/
│   ├── _common.sh            # Configuration commune de l'environnement
│   └── docs                  # Script de génération de la documentation Sphinx
├── docs/
│   ├── source/
│   │   ├── conf.py           # Configuration Sphinx & extensions
│   │   ├── index.rst         # Point d'entrée de la documentation
│   │   └── api/              # Documentation automatique des modules
│   └── build/                # Documentation HTML compilée
├── iragi/
│   ├── __init__.py           # Point d'entrée du package
│   ├── core/                 # Modèles de données, configuration et exceptions
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   └── models.py
│   ├── scan/                 # Moteur d'inspection et de qualité
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   └── profiler.py
│   ├── pdf/                  # Moteur d'extraction PDF
│   │   ├── __init__.py
│   │   ├── extractor.py
│   │   └── tables.py
│   ├── all/                  # Orchestration du pipeline
│   │   ├── __init__.py
│   │   └── pipeline.py
│   ├── reports/              # Générateurs de rapports (HTML, JSON)
│   └── cli/                  # Commandes CLI Typer
├── tests/                    # Tests unitaires et d'intégration
├── examples/                 # Exemples d'utilisation
├── pyproject.toml            # Métadonnées et dépendances du projet
└── README.md
```

---

## Socle technologique & Fort Potentiel

**Iragi** a été conçu dès le premier jour pour répondre aux exigences des environnements de production les plus stricts : rapidité d'exécution, fiabilité mathématique et extensibilité totale.

Plutôt qu'un simple script ou un notebook jetable, **Iragi est une véritable infrastructure logicielle** construite sur un assemblage réfléchi de briques de pointe :

- **Noyau d'ingestion & calcul haute performance :** Propulsé par **Python 3.14+**, **Pandas 2+** et **NumPy**, le moteur de Scan ingère et traite des millions de cellules en un clin d'œil, calculant avec une précision rigoureuse les écarts statistiques, matrices d'incohérences et métriques de qualité (IQR, cardinalités, doublons).
- **Moteur d'extraction documentaire universel :** En combinant l'extrême rapidité de **PyMuPDF** pour le texte et les métadonnées avec la précision chirurgicale de **pdfplumber** pour la reconstruction tabulaire, Iragi extrait et structure fidèlement les documents les plus complexes, tout en intégrant des mécanismes prédictifs pour l'OCR (**Tesseract** / **Pillow**).
- **Expérience développeur & Interface riche :** Une CLI moderne et fluide animée par **Typer** et **Rich**, offrant des diagnostics visuels colorés et lisibles directement dans votre terminal sans configuration préalable.
- **Rapports & Restitution dynamique :** Moteur de templating **Jinja2** permettant la génération instantanée de synthèses JSON ou de rapports HTML exploitables par les décideurs métiers.
- **Assurance qualité & Robustesse industrielle :** Couverture complète par des tests automatisés stricts (**pytest**), documentation Sphinx exhaustive et intégration continue garantissant zéro régression.

### Un potentiel d'extension illimité

Grâce à son architecture découplée et composable, **Iragi s'intègre en quelques lignes de code** au cœur de vos projets stratégiques :
- **Pipelines ETL & Data Lakes :** Validation automatique des schémas et de la qualité des données avant ingestion dans vos entrepôts.
- **Applications Web & Microservices (Django / FastAPI) :** Analyse à la volée des uploads utilisateurs avec retour immédiat sur la conformité des fichiers.
- **Agents IA & LLM RAG :** Préparation, nettoyage et découpage de documents tabulaires et PDF pour alimenter des bases vectorielles avec des données d'une pureté irréprochable.

---

## Principes de conception

1. **Modularité stricte :** Scan, PDF et All ont des responsabilités distinctes et des cycles de vie indépendants.
2. **Priorité à l'API Python :** La CLI n'est qu'un client léger consommant les modules Python publics.
3. **Indépendance vis-à-vis des frameworks :** Utilisable nativement dans un script, Django, FastAPI ou Jupyter.
4. **Immuabilité des données sources :** Aucune modification destructive par défaut.
5. **Score explicable et traçable :** Tout score de qualité expose la formule et les pénalités appliquées.
6. **Gestion explicite des erreurs :** Aucune exception masquée silencieusement.
7. **Dépendances optionnelles :** Un utilisateur de `iragi.scan` ne télécharge pas les dépendances de rendu PDF ou OCR.
8. **Documentation exhaustive :** Chaque fonction, classe et module est documenté selon le standard Sphinx avec exemples.

---

## Feuille de route

### Phase 1 — Fondations
- [x] Initialiser le dépôt et `pyproject.toml`.
- [x] Définir les exceptions et les objets de résultat communs (`iragi.core`).
- [x] Mettre en place les tests unitaires et l'intégration continue (`.github/workflows/ci.yml`).
- [x] Configurer la génération de documentation Sphinx (`bin/docs`).
- [x] Créer une première CLI de base.

### Phase 2 — Moteur Scan
- [x] Lire les fichiers CSV.
- [x] Lire les fichiers Excel.
- [x] Lire les fichiers JSON.
- [x] Ajouter le profilage des colonnes.
- [x] Détecter les valeurs manquantes et les doublons.
- [x] Ajouter les validations de types et de formats.
- [x] Produire un premier rapport JSON.

### Phase 3 — Moteur PDF
- [x] Extraire le texte avec PyMuPDF.
- [x] Lire les métadonnées.
- [x] Extraire les tableaux avec pdfplumber.
- [x] Ajouter la détection des PDF nécessitant un OCR.
- [x] Ajouter l'OCR comme dépendance optionnelle.
- [x] Ajouter les exports structurés.

### Phase 4 — Orchestration All
- [x] Définir le pipeline commun.
- [x] Connecter les résultats du moteur PDF au moteur Scan.
- [x] Produire un rapport global.
- [x] Ajouter le traitement par lots.

### Phase 5 — Stabilisation et publication
- [x] Vérifier la disponibilité du nom `iragi` sur PyPI (disponible).
- [x] Compléter les tests unitaires et d'intégration.
- [x] Documenter les API publiques au fur et à mesure.
- [x] Ajouter des exemples d'intégration Django et FastAPI.
- [x] Vérifier les dépendances et les métadonnées du package.
- [x] Publier la version v0.1.0 sur PyPI.

---

## Contribution

Les contributions sont les bienvenues ! Pour proposer une fonctionnalité ou un correctif :

1. Ouvrez une issue pour échanger sur la conception et l'intérêt de la modification.
2. Respectez l'isolation stricte entre moteurs et les conventions de docstrings Sphinx.
3. Ajoutez les tests correspondants sous `tests/`.
4. Vérifiez que la documentation se génère sans avertissement (`bin/docs`).

---

## Licence

Ce projet est distribué sous licence [MIT](LICENSE).

---

<p align="center">
  <strong>Iragi — Inspecter. Extraire. Analyser.</strong>
</p>
