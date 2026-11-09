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
  - `doly_battery` : `get_capacity()` renvoie 0 pendant environ 0,3 s après `init()`. La fin de décharge est brutale : 27 minutes de 30 % à la coupure, dont 5 seulement à partir de 16 %, robot à l'écoute. Aucune fonction n'indique si le robot charge : voir le INA219.
  - INA219, adresse `0x41` de `/dev/i2c-3` : le bus est accessible à l'utilisateur `doly`. Le SDK y lit les registres `0x02` et `0x04` environ toutes les 150 ms, par lectures groupées (`I2C_RDWR`) où personne ne peut s'intercaler : `projets/doly-conversation/ina219.py` fait pareil. Configuration `0x399f`, calibrage `0x1000`, si bien que le courant brut vaut le registre du shunt. **Tension du shunt, moyenne sur 15 s :** hors de sa base, de -4 à -9 mV, -4,7 micro coupé, -3,5 endormi ; sur sa base, de -0,2 à 0 batterie pleine, de +1 à +2,7 après une petite décharge. Le signe « positif » de la FAQ ne suffit donc pas : pleine, sur sa base, la moyenne est légèrement négative. Sur la base, la tension de la batterie monte (4,17 V contre 4,08 V juste après l'en avoir retiré), d'où un niveau affiché plus haut, de 94 à 100 %. Le pourcentage suit la tension : de 83 à 96 % et de 27 à 38 % en le posant sur sa base (+5 et +4,2 mV), et de 94 à 86 % en 20 s, processeur à fond.
  - Consommation, en mV sur le shunt : repos 4,4, écrans et LED au maximum 5,8, demi-tours sur place 6,8 (pointes à 44), 4 cœurs à fond 12 à 13. Ces 4 cœurs : 74,5 °C en 80 s avec `fan.init(True)`, 66 °C stables avec `fan.init(False)` et `fan.set_fan_speed(100)`. Pour vider la batterie plus vite, c'est le processeur qui compte, pas les chenilles.
  - `doly_drive` : **figé ou tué pendant un déplacement, le programme laisse les chenilles tourner.** Elles sont sur les sorties 13 et 14 du PCA9685 (`0x40`, 18 % pour une vitesse de 20). Seuls `drive.init` puis `drive.abort` les arrêtent, en 1 s environ avec le lancement de Python. Les sorties 6 à 11 sont à 100 % au repos.
  - `doly_arm` : tué en plein mouvement, le bras s'arrête en quelques degrés, reste en place, et n'est pas sur le PCA9685. 120° en environ 1,2 s à la vitesse 10.
  - `doly_arm` : le premier angle lu peut être faux (251° au repos). Les suivants sont justes.
  - `doly_drive` : un angle négatif le fait tourner vers sa gauche. `abort()` met les roues en état d'erreur.
  - `doly_lcd` et `doly_eye` partagent le même écran : après `eye.init`, `lcd.init` renvoie 1. Le module des yeux ne redessine rien au repos, donc une image écrite avec `lcd.write_lcd` reste affichée jusqu'à la prochaine animation. Environ 50 images par seconde sur les deux écrans, pour 8 % d'un cœur. `lcd.to_lcd_buffer(octets, True)` convertit 240 x 240 x 4 octets en 86 400 octets.
  - Côtés : `Left` est la gauche de Doly, donc ta droite quand tu lui fais face. Vérifié avec l'utilisateur sur les écrans, les capteurs tactiles et les capteurs de proximité.
  - `eye.set_background_image` n'accepte que `VContent.get_image(chemin, False, True)` : sans opacité, sur 12 bits. Le module des yeux doit être au repos, sinon `RuntimeError`.
  - `doly_eye` : un écart de 10 points de l'iris (`ATTENTION LEFT`) ne se voit pas ; `LOOK LEFT` se voit.
  - `doly_touch` : un capteur sur GPIO, sans réglage de sensibilité, que le SDK lit environ toutes les 50 ms. Une tape vue dure de 0,05 à 0,46 s. **À chaque bip, après un repos de 3 s : une tape très courte est vue 1 fois sur 8, un appui franc 7 fois sur 8.** Des tapes très rapides : 2 contacts vus en 12 s. Un jeu de réflexes doit donc demander un appui franc, et pardonner une tape ratée. Un doigt gardé posé tient au moins 45 s, et le SDK envoie `TouchActivity.Disturb` toutes les 2,53 s.
  - `doly_tof` : une lecture dure de 25 à 100 ms selon les essais. Le champ est étroit : une main est vue à 25-50 mm juste devant un capteur, à peine ailleurs. Main immobile vers 90 mm : les mesures varient de 85 à 96 mm. Main qui bouge : 20 mm d'écart en 0,1 s.
  - `doly_edge` : sur sa base, certains capteurs restent à `Low`, donc `sol_sous_lui` est faux.
  - `doly_imu` : juste après `init`, le robot étant immobile, un faux `ShockExtreme` a été reçu : ignore les premières secondes. Une tape sur la tête ressemble à un choc (`ShockMedium` à `ShockHard`), avec une direction `Up` ou `Down`, et une seule poussette donne plusieurs chocs à moins de 0,35 s d'écart, et des `Move`. Les événements arrivent au plus toutes les 0,3 s environ : ils ne comptent pas les tapes et n'en donnent pas le côté.
  - `doly_camera` : en 1920 x 1080, la taille des photos d'origine, le capteur ne lit que le centre de l'image ; 3280 x 2464 donne tout le grand angle. L'exposition est stable dès la première image : attendre davantage n'éclaircit pas une photo prise le soir. La caméra et OpenCV prennent environ 150 Mo tant qu'ils sont ouverts : `projets/doly-conversation/photo.py` les garde dans un programme à part.
- Fichiers d'origine, lisibles sur le robot, à ne pas recopier dans ce dépôt :
  - `/.doly/config/animations/*.xml` : les animations, en blocs de la programmation par blocs. Le champ `start` vaut 1 pour « après la fin du bloc précédent » et 0 pour « tout de suite ». `projets/doly-conversation/animations.py` les rejoue.
  - `/.doly/images/animations/*.seq` : des images 240 x 240 de 4 octets par point, compressées en une trame LZ4 (voir `ecran.py`). `/.doly/config/eye/eyeanimations.xml` : les expressions des yeux.
  - `/.doly/sounds/` : `sound`, `sfx`, `animal`, `music` et `wuw`, en WAV. Leur niveau est proche de celui de la voix Piper.
  - `/.doly/config/settings.xml` : les réglages, dont **la position de la maison, à ne jamais publier ni afficher**, et le numéro de série. Ne le recopie jamais en entier.
- Une fois le service Doly arrêté, rien ne pilote le ventilateur : appelle `fan.init(True)` dans toute appli qui tourne longtemps.
- Mot d'éveil : un second reconnaisseur Vosk limité à une grammaire (`["hé dolly", "[unk]"]`) consomme 15 % d'un cœur. « Doly » seul se déclenche à tort, par exemple sur « joli » : il faut les deux mots. Il s'arrête souvent à la virgule après « Hé Doly » : garde le micro ouvert pour ne pas perdre la suite. `SetWords(True)` donne la fin exacte du mot, et permet de ne transcrire que ce qui suit, sans chercher « dolly » dans le texte, où il n'est pas toujours retrouvé.
- Vosk confond les mots qui se prononcent presque pareil : « vert » devient « verre », « l'heure » devient « leur », et « tope là » devient « allez hop là ». Claude n'a changé la couleur de ses yeux qu'une fois cette confusion signalée dans ses consignes.
- Vosk 0.3.45 (celui du robot) : `SetEndpointerDelays` n'existe pas. Juste après `Result()`, `PartialResult()` renvoie `{"text": ""}`, sans champ `partial`. Le texte provisoire a du retard sur la parole, alors que le volume réagit tout de suite : au calme, le micro est vers 100 à 150 (valeur efficace, décalage continu retiré), et la voix le plus souvent au-dessus de 500. `Reset()` ne libère pas la mémoire : à l'écoute, elle monte d'environ 25 Mo pendant 10 minutes, puis Vosk reconstruit son traitement et elle ne monte plus. Sur 3 h 32 : l'appli passe de 254 à 486 Mo pendant la première heure de conversation et de scènes, ne bouge plus pendant 2 h 10 de repos, puis gagne 3 Mo sur une dizaine de phrases.
- Vitesse de Vosk, mesurée le 9 novembre avec `tester_comprehension.py` : 0,42 s de calcul pour 1 s de son à 1 m, 0,53 à 3 m, 0,87 télé allumée (jusqu'à 1,5 sur une phrase) et 1,00 pour une voix moins familière. Il est aussi lent la première fois qu'il entend des mots, avec un reconnaisseur neuf : 4,5 s pour 4,7 s de son, puis 0,8 s pour la même phrase avec le même reconnaisseur, après `Reset()`. Le réchauffer avec 7 phrases ne fait gagner que 15 à 20 % sur des phrases nouvelles. Quand il va moins vite que la parole, le son s'accumule : `micro.py` le garde dans une file (`[micro] file_max=` dans le journal), au lieu de le perdre. Piper qui calcule pendant l'écoute le ralentit encore : 9,6 s de retard mesurées.
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
- Si `doly-francais.service` est installé, il prend la main après chaque démarrage (voir `projets/doly-conversation/`). Arrête-le avant tout autre script qui utilise le matériel, le micro ou le son : `sudo systemctl stop doly-francais`.

## Pièges vérifiés pour une appli qui tourne en permanence

Tous ont été observés sur ce robot :

- **Ordre de démarrage :** `doly_update.service` démarre après `multi-user.target`. Un service installé dans cette cible ne doit pas déclarer `After=doly_update.service` : la boucle d'ordre fait supprimer le service en silence au démarrage. Il faut attendre le service Doly depuis le programme.
- **`/dev/shm` :** le système y efface les fichiers de l'utilisateur `doly` environ 10 s après la fermeture de sa dernière session, par exemple une connexion SSH (`RemoveIPC`). Un service utilise plutôt `RuntimeDirectory=`.
- **Micro dans un tuyau :** `arecord` lancé avec `stdout=PIPE` peut se bloquer sur un tuyau plein si plus personne ne lit, et `wait()` ne revient alors jamais. Ferme `stdout` entre `terminate()` et `wait()`, sauf si un autre fil lit le tuyau jusqu'au bout.
- **DNS :** sur ce réseau, les deux questions (IPv4 et IPv6) envoyées en même temps peuvent faire perdre 5 s. `RES_OPTIONS="single-request timeout:1"`, posé pour la seule appli, évite ce délai.
- **Date :** l'horloge n'est pas à l'heure dans les premières secondes, et le robot peut rester allumé plusieurs jours. Lis la date à chaque appel, jamais une seule fois au lancement.
- **Démarrage avec `Type=notify` :** `multi-user.target` attend `READY=1`, et le service Doly démarre après cette cible. Il faut donc envoyer `READY=1` avant de l'attendre, sinon tout le démarrage se bloque jusqu'à la fin de l'attente.
- **Un programme tué ne fait plus rien :** ni `finally`, ni relance du service d'origine. Le repli passe donc par `OnFailure=doly.service`, qui ne se déclenche qu'une fois les 3 essais épuisés. Après une relance automatique, le service d'origine ne revient pas tout seul : l'attendre empêcherait aussi d'atteindre 3 échecs en 5 minutes. `doly.service` est désactivé et lancé par `doly_update`, et ses horodatages sont perdus une fois qu'il est arrêté.
- **`pkill -f` dans une commande SSH :** même avec `[m]otif`, il tue la commande si le texte exact apparaît ailleurs sur la même ligne. Lis le résultat avant de demander quoi que ce soit à l'utilisateur.
- **Vérifier qu'une appli vit :** « service actif » ne suffit pas, un programme figé reste actif : c'est le rôle de `garde.py`. Toute nouvelle boucle ou attente longue du fil principal doit appeler `garde.vivant()` ou passer par `garde.activite(nom, durée maximale)`, sinon elle sera prise pour un gel après 20 s. Regarde aussi dans le journal si ses messages réguliers continuent d'arriver, par exemple `[batterie]` toutes les minutes, ou lance `resumer_journal.py`. Le journal survit aux redémarrages : `journalctl -b -1` montre la fin du démarrage précédent, à condition de se méfier de ses heures, car l'horloge repart de la dernière heure connue à l'allumage.
- **Arrêter et relancer l'appli :** `systemctl stop doly-francais` relance un instant la personnalité d'origine si elle tournait au démarrage de l'appli. Après `systemctl start doly-francais`, l'appli attend cette personnalité seulement dans les 5 minutes qui suivent l'allumage (`--attendre-origine`), puis Doly dit à voix haute « Je t'écoute ! », en 15 s environ. Préviens l'utilisateur. Pour tester le service sans toucher à l'installation, on peut créer une copie dans `/run/systemd/system/`, qui disparaît au redémarrage.
- **Conversation avec Claude :** le `system` et les `tools` ne doivent pas changer pendant une conversation : l'API refuse (erreur 400) de relire les blocs de réflexion si le début a changé, sur les comptes récents. L'heure et l'humeur partent donc dans un message `{"role": "system"}` ajouté après chaque phrase.

## Organisation du dépôt

- `projets/<nom-du-projet>/` : un dossier par projet, avec un `README.md` (but, lancement, résultat attendu). Ajoute chaque nouveau projet à la liste du `README.md` principal.
- `outils/` : scripts utilitaires.
- Sur Doly, l'utilisateur récupère le dépôt avec `git clone`, puis les nouveautés avec `git pull`.
