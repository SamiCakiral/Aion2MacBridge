# Aion2MacBridge

**Faire tourner AION 2 sur un Mac Apple Silicon avec CrossOver, Rosetta et la connexion Steam native.**

J’ai tout fait pour pouvoir jouer à AION 2 sur Mac. Comme je n’avais pas trouvé de solution qui fonctionnait sur ma configuration, j’ai cherché et expérimenté avec l’aide de l’IA jusqu’à réussir à lancer le jeu et à jouer. Voici le patch et la marche à suivre pour reproduire cette configuration.

Ce projet s’appuie sur le travail de [NotProton](https://github.com/NotProtonNot/NotProton). Il ajoute une construction locale du patch de chargement pour le moteur Intel et des scripts qui choisissent explicitement Rosetta, tout en utilisant la session Steam du Mac. **Aucune copie supplémentaire du jeu n’est nécessaire.**

## Ce qui a été validé

Le propriétaire du dépôt a confirmé pouvoir jouer sur sa configuration le 9 octobre 2026 :

| Composant | Configuration testée |
| --- | --- |
| Mac | Apple Silicon M4 Max, 64 Go de mémoire |
| macOS | 27.0, build 26A428 |
| CrossOver Preview | 27.0.0.41069, archive du 6 octobre 2026 |
| NotProton | 1.0.3 ; sources du patch au commit `599ebf6a4cfa52b46c03299170ccbde8f8fe2205` |
| Jeu | AION 2 sur Steam, App ID `3393110` |
| Exécution | Moteur x86_64 de CrossOver via Rosetta, Steam natif connecté |

L’initialisation de l’API Steam et son état connecté ont également été vérifiés. Le chemin ARM/FEX utilisé lors des premiers essais échouait ; choisir le chemin Intel et préparer son pont Steam a permis le lancement fonctionnel. Cela ne démontre pas une cause unique pour tous les échecs ARM, ni une compatibilité avec tous les Mac ou toutes les futures mises à jour.

**Les scripts ci-dessous sont une mise au propre du prototype utilisé.** La construction du patch est comparée au binaire du prototype ; la procédure complète avec une nouvelle installation reste à confirmer sur d’autres machines. Aucun remplacement des fichiers du jeu ou de son anti-triche n’est réalisé.

## Prérequis

1. Un Mac Apple Silicon avec Rosetta installé.
2. Une installation légitime de CrossOver Preview **27.0.0.41069 du 6 octobre 2026**. Le constructeur refuse une autre DLL : le patch est spécifique à cette version. Obtenir CrossOver sur [CodeWeavers](https://www.codeweavers.com/preview/).
3. [NotProton](https://github.com/NotProtonNot/NotProton) installé et configuré avec ce moteur CrossOver. Son dossier de support doit contenir `runners/current` et `bridge`, dont `bridge/x86_64-unix/lsteamclient.so`.
4. Steam **natif pour macOS**, déjà connecté, avec AION 2 installé et l’outil de compatibilité NotProton sélectionné pour le jeu. Accepter soi-même les éventuelles conditions et demandes de connexion dans Steam.
5. Python 3.10 ou ultérieur, les outils de ligne de commande Apple (`xcode-select --install`) et LLVM fournissant `ld.lld` et `llvm-objcopy`.

Avec Homebrew, LLVM peut être installé par `brew install llvm lld`. Si les exécutables ne sont pas dans le même dossier, ajouter les deux dossiers à `PATH` puis omettre `--llvm-bin` ci-dessous. L’essai original utilisait les outils `ld.lld` et `llvm-objcopy` de llvm-mingw 20261006 ; un résultat différent avec un autre compilateur sera signalé.

## 1. Récupérer les scripts et construire le patch

```sh
git clone https://github.com/SamiCakiral/Aion2MacBridge.git
cd Aion2MacBridge
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python build_patch.py --llvm-bin "$(brew --prefix llvm)/bin"
```

Si `ld.lld` a été installé séparément, utiliser plutôt :

```sh
export PATH="$(brew --prefix llvm)/bin:$(brew --prefix lld)/bin:$PATH"
.venv/bin/python build_patch.py
```

La DLL CrossOver d’origine reste dans l’application et n’est pas modifiée pendant cette étape. La DLL modifiée est produite **sur votre Mac** dans `build/ntdll.dll` ; elle n’est pas distribuée sur GitHub.

Le hash SHA-256 attendu du résultat testé est :

```text
e5ef486376a9c2cac9ff0cac8867c96a8c85f725174363f754b92ca23f6fab56
```

Si le constructeur indique que le résultat diffère, ne le considérer pas comme le binaire validé. Vérifier les versions des outils avant de lancer le jeu.

## 2. Préparer la petite bouteille dédiée

Fermer les jeux et applications utilisant le **même moteur NotProton** avant cette étape. Garder Steam natif connecté. Ne pas ouvrir Steam Windows : une autre connexion au même compte peut remplacer la session native.

```sh
.venv/bin/python bridge.py setup
```

Cette commande crée `~/Library/Application Support/Aion2MacBridge/pfx`, initialise Wine et y installe les composants du pont Steam déjà fournis par NotProton. Le prototype occupait environ **511 Mio** hors jeu ; l’espace nécessaire varie. Elle ne copie ni ne télécharge AION 2 et refuse de réinitialiser une bouteille existante.

Si le jeu était déjà installé dans une bouteille CrossOver et n’apparaît pas dans la bibliothèque native, le rendre accessible à Steam natif avant la suite. Sur la machine testée, le dossier `Steam/steamapps/common/AION2` était un lien symbolique vers l’installation CrossOver existante. Ce lien seul ne remplace pas l’enregistrement du jeu dans Steam : vérifier que Steam natif reconnaît l’installation avant de lancer une installation ou un téléchargement. Les scripts ne modifient pas cet enregistrement automatiquement.

## 3. Jouer

Avec Steam natif ouvert et connecté, lancer :

```sh
.venv/bin/python bridge.py capture
.venv/bin/python bridge.py launch
```

La première commande demande un lancement à Steam et récupère ses paramètres d’authentification récents dans un fichier local privé. Elle restaure ensuite le script NotProton d’origine. Si Steam affiche une boîte de dialogue, la traiter pendant cette étape, puis relancer `capture` si nécessaire.

La seconde démarre **le jeu existant** avec le moteur Intel de CrossOver et le pont Steam natif. Garder ce terminal ouvert pendant la partie. Pour une nouvelle session, refaire les deux commandes : les paramètres de lancement expirent et ne doivent pas être réutilisés le lendemain.

La capture contient des données de connexion temporaires. **Ne jamais publier le dossier local d’état, les arguments de lancement ou les journaux privés.** Aucun de ces fichiers n’est stocké dans le dépôt.

## Fonctionnement et restauration

Le script prépare temporairement deux fichiers du moteur NotProton : la DLL x64 `ntdll.dll` modifiée et la bibliothèque x64 `lsteamclient.so`. La bouteille dédiée reçoit le pont Steam. Le jeu est ensuite exécuté directement par `lib/wine/x86_64-unix/wine`, évitant la sélection ARM automatique.

Les fichiers du moteur sont sauvegardés avant modification et restaurés à la sortie normale, sur interruption du terminal et sur les erreurs prises en charge. **Ne pas lancer d’autres applications avec ce moteur pendant la partie.** Une coupure de courant ou un arrêt forcé peut empêcher la restauration automatique ; après avoir fermé le jeu, utiliser :

```sh
.venv/bin/python bridge.py recover
```

La restauration utilise une sauvegarde locale durable. Elle ne supprime pas la bouteille ni les sauvegardes du jeu. Ne pas lancer `recover` pendant une partie.

Pour utiliser des chemins différents, passer `--runner`, `--bridge`, `--prefix`, `--state` ou `--patch`. Utiliser les mêmes options pour `setup`, `capture`, `launch` et `recover`. Voir `bridge.py --help` et `build_patch.py --help`. Ne pas utiliser une bouteille ARM existante comme `--prefix` : la bouteille doit être initialisée avec le moteur Intel.

## Si le jeu ne démarre pas

- **Steam ne fournit pas de lancement :** vérifier sa fenêtre et que NotProton est sélectionné pour AION 2. Un ancien lancement peut être encore actif ; l’arrêter depuis Steam avant de refaire `capture`. Ne pas se déconnecter du compte.
- **DLL non prise en charge :** vérifier la version exacte de CrossOver Preview et utiliser sa DLL x64 d’origine pour construire le patch.
- **Transaction inachevée :** fermer le jeu puis exécuter `recover` avec les mêmes chemins.
- **Bouteille déjà existante :** ne pas refaire `setup` ; utiliser `capture` puis `launch`. Si la préparation initiale a échoué, conserver ses journaux et examiner le problème avant de recréer une bouteille.
- **Crash :** les journaux locaux sont dans `~/Library/Application Support/Aion2MacBridge/state`. Les examiner localement ; retirer les identifiants et paramètres d’authentification de tout extrait partagé.

## Crédits et licence

Le pont Steam et le détournement du chargeur viennent de **NotProton**, sans lequel cette solution n’existerait pas. L’apport de ce dépôt est la construction du patch Intel avec la convention d’appel Windows explicite et l’orchestration de la configuration qui a fonctionné pour AION 2.

Voir [NOTICE.md](NOTICE.md) pour le commit d’origine et la provenance des fichiers. Code distribué sous **GPL-3.0** ; voir [LICENSE](LICENSE). CrossOver, Steam, Rosetta et AION 2 restent des dépendances externes.
