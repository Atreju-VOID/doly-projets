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

- Raspberry Pi CM4, Raspberry Pi OS 64 bits (aarch64), Python 3.11. Le SDK Python est préinstallé sur le robot : rien à installer.
- Modules Python (`import doly_xxx`) :
  - mouvement : `doly_drive` (déplacements), `doly_arm` (bras), `doly_servo` (2 sorties servo pour les add-ons) ;
  - affichage : `doly_eye` (yeux animés, expressions, images), `doly_lcd` (accès direct aux deux écrans), `doly_led` (LED RGB gauche et droite) ;
  - son : `doly_sound` (lecture de fichiers audio), `doly_tts` (synthèse vocale, 3 voix `VoiceModel.Model1..3`, langue non documentée, à vérifier sur le robot) ;
  - capteurs : `doly_camera` (caméra 8 MP Sony IMX219, l'exemple officiel utilise OpenCV), `doly_tof` (proximité gauche et droite, gestes de la main), `doly_edge` (détection du vide tout autour du robot, pour ne pas tomber de la table), `doly_touch` (tactile gauche et droite), `doly_imu` (accéléromètre et gyroscope), `doly_battery` (niveau de batterie) ;
  - divers : `doly_helper` (réglages, arrêt du service Doly), `doly_fan` (ventilateur), `doly_io` (6 GPIO), `doly_color` (`Color`, `ColorCode`), `doly_vcontent` (`VContent`, images).
- Micros : à utiliser via ALSA (ils ne sont pas dans le SDK). Pas d'annulation d'écho matérielle : il faut une solution logicielle, ou couper le micro quand Doly parle.
- Extensions : 6 GPIO, Qwiic/I2C sur `/dev/i2c-6` (les autres bus I2C sont internes), UART, USB, 2 sorties servo. Alimentation 5 V utilisateur : 1,5 A en continu.

## Règles pour le code qui tourne sur Doly

- Arrête toujours le service Doly avant d'accéder au matériel, comme dans les exemples officiels : `helper.stop_doly_service()` (un retour < 0 signifie un échec). Sinon, ton script et la personnalité par défaut se disputent le matériel.
- Schéma des modules qui ont un `init` (la plupart, sauf `doly_camera`, `doly_helper`, `doly_io`, `doly_color` et `doly_vcontent`) : `init` → écouteurs (optionnel) → commandes → lecture de l'état → `dispose()`. Appelle `dispose()` dans un `finally` pour libérer le matériel même en cas d'erreur.
- Vérifie les codes de retour (< 0 = erreur) et affiche des messages clairs en français.
- Les clés API et autres secrets vont dans un fichier `.env` (ignoré par git), jamais dans le code.
- Depuis une session cloud, Claude n'a pas accès au robot : c'est l'utilisateur qui teste sur Doly. Dis-lui exactement quoi lancer et ce qu'il doit voir ou entendre. Pour les déplacements, conseille de tester au sol plutôt que sur une table.

## Organisation du dépôt

- `projets/<nom-du-projet>/` : un dossier par projet, avec un `README.md` (but, lancement, résultat attendu). Ajoute chaque nouveau projet à la liste du `README.md` principal.
- `outils/` : scripts utilitaires.
- Sur Doly, l'utilisateur récupère le dépôt avec `git clone`, puis les nouveautés avec `git pull`.
