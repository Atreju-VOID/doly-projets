# doly-projets : instructions pour Claude

Dépôt de projets personnels pour le robot **Doly** (Limitbit, créé par Levent Erenler).
L'utilisateur parle français : réponds, commente le code et écris la documentation en français.

## Sources officielles : à consulter avant d'écrire du code

- Dépôt officiel : https://github.com/robotdoly/DOLY-DIY (licence CC BY-NC-SA 4.0, usage non commercial).
- En début de session, lance `outils/recuperer-sdk-officiel.sh` : il télécharge ou met à jour le dossier `SDK/` officiel dans `sdk-officiel/` (ignoré par git, à ne jamais modifier ni commiter).
- Où chercher dans `sdk-officiel/SDK/` :
  - `examples/python/<Module>/example.py` : l'exemple officiel de chaque module, le meilleur point de départ.
  - `docs/python/docs/api/*.md` : référence de l'API Python (fonctions, enums, codes de retour).
  - `docs/python/docs/modules/*.md` : explications et exemples minimaux.
  - `docs/AI_Integration_Developer_FAQ.md` : micros (ALSA), caméra, extensions matérielles, bus I2C.
  - `include/*.h` : en-têtes C++, la description la plus précise du comportement des fonctions.
- N'invente jamais une fonction du SDK : vérifie son nom et sa signature dans `api/*.md` ou dans les exemples.
- Ne recopie pas de gros morceaux des sources officielles dans ce dépôt (il est public) : fais-y référence. Si tu reprends un exemple officiel, cite la source et sa licence.

## Le robot

- Raspberry Pi CM4 (4 cœurs à 1,5 GHz), Raspberry Pi OS 64 bits (aarch64), Python 3.11. Le SDK Python est préinstallé sur le robot : rien à installer.
- Mémoire de ce robot : 907 Mo. Le service Doly en occupe 300 à 500 ; une fois arrêté, il reste environ 770 Mo libres. Pas de gros modèle d'IA sur le robot : la reconnaissance vocale tient avec Vosk (225 Mo, voir `projets/doly-ecoute/`), mais le cerveau passera par Internet ou par un autre ordinateur.
- Modules Python (`import doly_xxx`) :
  - mouvement : `doly_drive` (déplacements), `doly_arm` (bras), `doly_servo` (2 sorties servo pour les add-ons) ;
  - affichage : `doly_eye` (yeux animés, expressions, images), `doly_lcd` (accès direct aux deux écrans), `doly_led` (LED RGB gauche et droite) ;
  - son : `doly_sound` (lecture de fichiers audio), `doly_tts` (synthèse vocale, 3 voix `VoiceModel.Model1..3`, toutes en anglais ; pour le français, voir `projets/doly-parle/`) ;
  - capteurs : `doly_camera` (caméra 8 MP Sony IMX219, l'exemple officiel utilise OpenCV), `doly_tof` (proximité gauche et droite, gestes de la main), `doly_edge` (détection du vide tout autour du robot, pour ne pas tomber de la table), `doly_touch` (tactile gauche et droite), `doly_imu` (accéléromètre et gyroscope), `doly_battery` (niveau de batterie) ;
  - divers : `doly_helper` (réglages, arrêt du service Doly), `doly_fan` (ventilateur), `doly_io` (6 GPIO), `doly_color` (`Color`, `ColorCode`), `doly_vcontent` (`VContent`, images).
- Micros : à utiliser via ALSA (ils ne sont pas dans le SDK). Pas d'annulation d'écho matérielle : il faut une solution logicielle, ou couper le micro quand Doly parle. Testé avec `arecord -D plughw:0,0`, service arrêté : les deux canaux sont strictement identiques, donc enregistre en mono, et retire le décalage continu avant d'analyser le son.
- Son hors SDK : pas de serveur audio, et le service Doly monopolise la carte son tant qu'il tourne. Pour `aplay`, utilise `plughw:0,0` : `default` refuse l'utilisateur `doly`, car le verrou de son mixage appartient à `root`.
- Vérifié sur le robot en v1.014 :
  - `doly_edge` : `High` au sol et `Low` en l'air, valable dès l'initialisation. Une surface sombre peut sembler être du vide.
  - `doly_tof` : voit de 2 à 20 cm environ, et renvoie -1 ou une erreur quand rien n'est à portée.
  - `doly_battery` : `get_capacity()` renvoie 0 pendant environ 0,3 s après `init()`.
  - `doly_arm` : le premier angle lu peut être faux (251° au repos). Les suivants sont justes.
  - `doly_drive` : un angle négatif le fait tourner vers sa gauche. `abort()` met les roues en état d'erreur.
- Une fois le service Doly arrêté, rien ne pilote le ventilateur : appelle `fan.init(True)` dans toute appli qui tourne longtemps.
- Extensions : 6 GPIO, Qwiic/I2C sur `/dev/i2c-6` (les autres bus I2C sont internes), UART, USB, 2 sorties servo. Alimentation 5 V utilisateur : 1,5 A en continu.

## Règles pour le code qui tourne sur Doly

- Arrête toujours le service Doly avant d'accéder au matériel, comme dans les exemples officiels : `helper.stop_doly_service()` (un retour < 0 signifie un échec). Sinon, ton script et la personnalité par défaut se disputent le matériel.
- Schéma des modules qui ont un `init` (la plupart, sauf `doly_camera`, `doly_helper`, `doly_io`, `doly_color` et `doly_vcontent`) : `init` → écouteurs (optionnel) → commandes → lecture de l'état → `dispose()`. Appelle `dispose()` dans un `finally` pour libérer le matériel même en cas d'erreur.
- Vérifie les codes de retour (< 0 = erreur) et affiche des messages clairs en français.
- Les clés API et autres secrets vont dans un fichier `.env` (ignoré par git), jamais dans le code. Sur le robot, la clé Claude est dans `~/.config/doly/.env`, écrite par `projets/doly-conversation/enregistrer_cle.sh`. Ne demande jamais de clé dans la conversation.
- Depuis une session cloud, Claude n'a pas accès au robot : c'est l'utilisateur qui teste sur Doly. Dis-lui exactement quoi lancer et ce qu'il doit voir ou entendre. Pour les déplacements, conseille de tester au sol plutôt que sur une table.
- Depuis le PC de l'utilisateur, Claude peut se connecter au robot avec la clé SSH dédiée : `ssh -i ~/.ssh/doly_ed25519 doly@doly`, ou l'adresse IP du robot si le nom ne répond pas. Préviens l'utilisateur avant de faire parler ou bouger le robot.
- Tout nouveau mouvement passe d'abord par un test guidé, avec l'utilisateur à côté, comme dans `projets/doly-conversation/`. Le code qui fait rouler le robot passe par `Corps.rouler`, qui surveille le vide, les obstacles, les touchers et la durée.
- Le service Doly repart tout seul au démarrage, et le robot installe aussi ses mises à jour à ce moment-là. Évite `apt upgrade` sur le robot : installe les paquets Python dans un environnement virtuel.

## Organisation du dépôt

- `projets/<nom-du-projet>/` : un dossier par projet, avec un `README.md` (but, lancement, résultat attendu). Ajoute chaque nouveau projet à la liste du `README.md` principal.
- `outils/` : scripts utilitaires.
- Sur Doly, l'utilisateur récupère le dépôt avec `git clone`, puis les nouveautés avec `git pull`.
