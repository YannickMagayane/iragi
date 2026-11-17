Architecture du projet
======================

Iragi est organisé en modules Python avec des responsabilités distinctes. Les
modules ``scan``, ``pdf`` et ``reconcile`` peuvent être utilisés séparément ;
``all`` coordonne leurs opérations pour les analyses combinées. La CLI appelle
les mêmes API publiques.

Organisation du dépôt
---------------------

.. code-block:: text

   iragi/                         package Python installable
   ├── core/                      modèles, configuration, erreurs, accès distant
   ├── scan/                      lecteurs, profilage, contrats, nettoyage, dérive, rapports
   ├── pdf/                       extraction, tableaux, outils OCR, modèles
   ├── reconcile/                 clés, normalisation, conflits, consensus
   ├── all/                       analyse combinée et traitements par lots
   └── cli/                       interface en ligne de commande
   tests/                         tests automatisés et jeux de données
   examples/                      intégrations Python et notebook
   benchmarks/                    outil, résultats JSON et graphiques SVG
   docs/source/                   documentation Sphinx et référence API
   bin/                           scripts de développement et de publication
   .github/workflows/             CI et publication du package
   bench_suite.py                 point d'entrée du benchmark
   pyproject.toml                 métadonnées et configuration des outils

Responsabilités des modules
----------------------------

``iragi.core`` fournit les modèles partagés, la configuration, les exceptions
et le téléchargement des entrées distantes. ``iragi.scan`` lit les formats
tabulaires et réalise le profilage, la validation par contrats, le nettoyage,
la détection de dérive et la génération de rapports. ``iragi.pdf`` extrait le
texte et les tableaux ; les fonctions OCR s'appuient sur des dépendances
optionnelles. ``iragi.reconcile`` rapproche des sources et signale les clés
orphelines et les conflits. ``iragi.all`` orchestre ces fonctionnalités sans
remplacer leurs API autonomes, et ``iragi.cli`` expose les parcours dans le
terminal.

Flux de traitement
------------------

.. code-block:: text

   fichier ou URL
       ├── entrée tabulaire ──> scan.readers ───> scan ──> rapports
       ├── document PDF ──────> pdf ───────────> tables ──> scan (optionnel)
       └── plusieurs sources ──────────────────> reconcile
                                                  ↑
                         all coordonne les parcours combinés

Les lecteurs par blocs limitent la quantité de lignes lues simultanément. Le
comptage exact des doublons conserve toutefois des empreintes pour les lignes
distinctes ; la mémoire totale dépend donc aussi de la cardinalité et des
structures créées par l'analyse. Le streaming ne garantit pas une borne fixe
de mémoire.

Dépendances
-----------

Le socle installe les dépendances nécessaires aux fonctionnalités tabulaires.
Les dépendances PDF et OCR sont optionnelles et s'installent avec les extras
``pdf`` et ``ocr`` ; ``all`` installe l'ensemble des extras pris en charge.
Voir :doc:`readme` pour l'installation et les exemples d'utilisation, et
:doc:`api/modules` pour les modules documentés.
