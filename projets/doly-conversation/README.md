# Doly converse en français

Conversation à voix haute avec Doly : tu le touches ou tu dis « Hé Doly », tu parles, Claude réfléchit, Doly répond. Ses yeux et ses LED suivent la conversation, et il peut faire des gestes et se déplacer quand on le lui demande. Il reprend aussi en français ce que sait faire sa personnalité d'origine : météo, photos, minuteur, jeux, humeurs et réactions.

La voix française ([doly-parle](../doly-parle/)) et la reconnaissance vocale ([doly-ecoute](../doly-ecoute/)) tournent sur le robot. Seul le texte compris part sur Internet, vers Claude.

## Ce qu'il sait faire

Tout a été essayé en vrai, partie par partie, à côté du robot : voir [GUIDE_DE_TEST.md](GUIDE_DE_TEST.md).

| Tu lui dis | Ce qu'il fait |
|---|---|
| « Quel temps fait-il ? », « Et demain à Lyon ? » | Il donne la vraie météo et la montre sur ses yeux. |
| « Quelle heure est-il ? », « Montre-moi la date. » | Il répond, et l'affiche si tu le demandes. |
| « Mets un minuteur de 5 minutes. » | Il sonne à la fin. Un toucher arrête la sonnerie. |
| « Prends une photo. » | La photo reste sur le robot, dans `/.doly/photos`. |
| « On joue à la roue », « au défi éclair », « à Doly dort ». | Une partie de une à deux minutes, voir plus bas. |
| « Tope là ! », « Fais un check. » | Il lève le bras et attend que tu tapes dedans. |
| « Sois méchant », « Sois joyeux », « Sois combatif », « Sois gentil avec moi ». | Il change d'humeur pour un quart d'heure. |
| « Danse ! », « Fais du sport. » | Il bouge en musique, et roule un peu, au sol uniquement. |
| « Imagine que tu es à la plage. », « C'est mon anniversaire ! » | Il montre une scène sur ses yeux. |
| « Fais le chat. » | Il imite un animal, parmi 30. |
| « Mets tes yeux en vert. », « Prends des yeux numériques. » | Il s'en souvient d'une fois sur l'autre. |
| « Va dormir. » | Il ferme les yeux jusqu'à ce que tu lui parles ou le touches. |

Il connaît aussi son niveau de batterie, il sait s'il est sur sa base, et il répond aux questions sur lui ou sur son humeur.

### Ses humeurs et ses réactions

Doly peut être **joyeux, méchant, combatif ou empathique**, avec trois niveaux. Il est méchant et combatif pour rire : grognon ou fanfaron, sans insulte ni menace. Si quelqu'un va vraiment mal, il redevient doux, quelle que soit son humeur.

Son humeur dépend de la façon dont on le traite, puis revient à la normale. Les compliments et les caresses le rendent joyeux, les insultes et les coups méchant, les défis combatif, et une personne triste empathique. Avec le temps, son caractère garde une trace : trop de méchancetés le rendent grognon par défaut.

Il réagit aussi tout seul, quand il est au repos, avec **ses yeux, ses LED, ses bras et de petits sons, mais jamais avec ses roues ni sa voix** :

| Tu fais | Il réagit |
|---|---|
| Une tape brève sur sa tête | C'est une caresse : plus il y en a, plus il est content. |
| Des tapes très rapides | Il s'agace, de plus en plus. |
| Un doigt gardé posé | Un bip, puis il écoute ce que tu dis. Si tu ne parles pas, il apprécie, puis il finit par s'agacer. |
| Une poussette ou un choc | Une réaction selon la force et le côté. |
| Une secousse | Il a le tournis. |
| Le soulever, le reposer | Il s'inquiète, puis il est soulagé. |
| Soulever un seul côté | Il s'inquiète, et regarde de ce côté. |
| Une main qui s'approche, à moins de 13 cm | Il la regarde, à gauche ou à droite, sans bruit. Au milieu, il fait une expression selon son humeur. |

Le capteur tactile a besoin d'un vrai contact : il voit un appui franc presque à chaque fois, mais rarement une tape très courte après un moment de repos.

La nuit, aux heures réglées dans l'appli officielle (22 h à 8 h par défaut), il s'endort après 10 minutes sans activité, et il se réveille le matin ou si on s'occupe de lui. Le micro reste ouvert, et « Hé Doly » le réveille.

Pour se passer de ces réactions : `converser.py --sans-reactions`.

### Ses jeux

Sa personnalité d'origine a trois jeux, dont les règles ne sont pas publiées. Ceux-ci ont leurs propres règles, et utilisent les images et les sons déjà présents sur le robot.

- **La roue :** chaque œil est une roue de fruits. Touche sa tête pour lancer, 5 manches. Deux fruits pareils gagnent, et deux cerises font le gros lot.
- **Le défi éclair :** appuie vite et franchement au-dessus de l'œil qui s'allume, ou des deux côtés si les deux s'allument. Tu as 3 secondes au début, puis moins à chaque niveau, jusqu'à 1 seconde. Une erreur ou une cible ratée coûte une vie, et tu en as 3. Doly retient ton record.
- **Doly dort :** attends qu'il ronfle, car appuyer plus tôt fait perdre. Approche ensuite ta main, et appuie sur sa tête sans le réveiller. S'il ouvre un œil, il arrête de ronfler et il regarde : ne bouge plus, car il voit une main qui bouge de plus de 2 cm.

### Ce qui n'est pas repris

| Fonction d'origine | Pourquoi |
|---|---|
| Se promener seul, reculer quand une main approche | Tu as choisi qu'il ne roule pas sans qu'on le lui demande. |
| Retourner seul sur sa base | Cette fonction n'est pas dans le SDK. |
| Reconnaître les visages | Ce sont des données personnelles, et il n'est prévu que des photos. |
| Télécommande et programmation par blocs de l'appli | Elles fonctionnent avec sa personnalité d'origine : dis « reprends ta personnalité ». |

## Sécurité

**Pose Doly au sol, jamais sur une table,** avec un mètre de libre autour de lui, loin d'un escalier et sans câble autour. **Un appui franc au-dessus de ses yeux arrête tout mouvement :** le capteur voit mal une tape très courte.

Il ne se déplace que si on le lui demande clairement, et seulement avec les mouvements prévus dans `corps.py` : 10 ou 20 cm, un quart de tour ou un demi-tour, 5 au maximum par demande. Danser, s'amuser et faire du sport comptent pour un déplacement chacun, passent par les mêmes garde-fous, et se font sur place si l'un d'eux refuse. Ses réactions spontanées n'utilisent jamais les roues.

Les bras sont limités à 150° et à 60 % de leur vitesse, même quand une animation d'origine demande davantage. Si un toucher laisse un bras en l'air, il le baisse doucement 4 secondes plus tard.

| Garde-fou | Comportement | Vérifié sur le robot |
|---|---|---|
| Pas de sol sous lui | Il refuse de rouler | Oui, en le soulevant |
| Plus de sol en roulant | Il s'arrête seul | Oui, en le soulevant, jamais sur un vrai bord |
| Obstacle à moins de 15 cm au départ | Il refuse d'avancer | Oui, avec la main |
| Obstacle à moins de 6 cm en roulant | Il s'arrête seul | Non |
| Toucher pendant un mouvement | Il s'arrête | Oui |
| Effort anormal sur les chenilles | Il s'arrête, via le SDK | Non |
| Déplacement trop long (8 s) | Il s'arrête | Non |
| Batterie sous 20 % | Il refuse de rouler | Non |

Les capteurs de vide peuvent prendre une surface sombre pour du vide : il refuse alors de rouler. Les capteurs d'obstacle ne regardent que devant lui, donc rien ne surveille un obstacle quand il recule, à part les chenilles.

## Installer

Il faut d'abord avoir installé `doly-parle` et `doly-ecoute`, et créé une clé API sur [console.anthropic.com](https://console.anthropic.com). Puis, une seule fois, sur Doly :

```bash
cd ~/doly-projets/projets/doly-conversation
bash installer_conversation.sh
bash enregistrer_cle.sh
```

La clé va dans `~/.config/doly/.env`, hors du dépôt, lisible uniquement par l'utilisateur `doly`. Elle ne s'affiche pas pendant la saisie.

## Lancer

```bash
~/doly-env/bin/python converser.py
```

Pour essayer un autre modèle :

```bash
~/doly-env/bin/python converser.py --modele claude-opus-5-5
```

## Résultat attendu

Après environ 5 secondes, Doly dit « Je t'écoute ! ».

- **Lui parler :** pose un doigt sur la zone tactile au-dessus de ses yeux, attends le bip, parle, puis lève le doigt.
- **Ses LED :** vert quand il écoute, orange quand il réfléchit, bleu quand il parle, éteintes au repos.
- **Ses gestes :** il salue, lève les bras et montre ses émotions avec ses yeux.
- **L'interrompre :** touche-le pendant qu'il parle ou bouge.
- **Terminer :** dis « au revoir », ou ne le touche plus pendant 5 minutes. Sa personnalité d'origine repart alors toute seule.

## Mode mains libres

Pour lui parler sans le toucher :

```bash
~/doly-env/bin/python converser.py --mains-libres
```

- **L'appeler :** dis « Hé Doly, lève les bras », d'une traite ou avec une courte pause. Ses LED passent au vert dès qu'il a entendu son nom. Si tu t'arrêtes après « Hé Doly », il fait un bip et attend ta phrase.
- **Continuer :** juste après sa réponse, il écoute encore 5 secondes sans que tu répètes « Hé Doly ».
- **Le toucher :** cela marche toujours, pour lui parler ou pour l'interrompre.
- **« Ne m'écoute plus » :** il coupe son micro jusqu'à ce que tu lui parles en gardant le doigt posé. Une simple caresse ne le rouvre pas.
- **« Reprends ta personnalité » :** il rend la main à sa personnalité d'origine.

**Ce qui part sur Internet :** l'écoute de « Hé Doly » se fait sur le robot, et rien ne sort tant qu'il ne l'a pas entendu. Ensuite, seul le texte de ta phrase part vers Claude, ainsi que ce que tu dis dans les 5 secondes qui suivent sa réponse, et la date, sa batterie et son humeur. Ce qui a été dit avant « Hé Doly » n'est ni transcrit, ni envoyé. Si Doly se réveille par erreur, ce qui suit partira quand même : dis « ne m'écoute plus » si cela arrive trop souvent. Dès qu'il entend son nom, il prépare aussi Claude à répondre vite (voir « Écoute et rapidité ») : cette demande ne contient que la conversation déjà envoyée, jamais ta nouvelle phrase. Le son, lui, ne quitte jamais le robot.

Ses réactions spontanées, ses jeux et ses photos ne sortent pas du robot. Claude ne voit jamais les photos. Pour la météo, seule une position arrondie à environ 10 km, ou le nom de la ville demandée, part vers [Open-Meteo](https://open-meteo.com), un service gratuit pour un usage personnel non commercial, et seulement quand tu demandes la météo (données sous licence CC BY 4.0). Sans ville précisée, il utilise la position enregistrée par l'appli officielle dans les réglages du robot, ou la ville que tu lui as demandé de retenir.

## Écoute et rapidité

**Essayé sur le robot le 9 novembre**, avec le test guidé de [GUIDE_DE_TEST.md](GUIDE_DE_TEST.md#écoute-et-rapidité). Les résultats sont plus bas.

| Changement | Pourquoi | Réglage |
|---|---|---|
| **Le micro est lu sans perte.** Un fil ne fait que lire le micro et ranger le son dans une file, que Vosk vide de son côté (`micro.py`). | Avant, Vosk et le micro étaient lus à tour de rôle : si Vosk prenait du retard, `arecord` perdait du son. 23 coupures sur 165 phrases, jusqu'à 0,75 s, dont 9 dans les 6 s après un « Hé Doly ». Autre cause possible : sur le test de 3 h 32, les 7 coupures sont toutes arrivées pendant des scènes enchaînées, quand l'échange est passé de 17 à 128 Mo. Chaque coupure est donc notée avec l'état de la file, la charge, la mémoire disponible et l'échange, pour départager les deux. | `TAMPON_MICRO`, inutilisé pour l'instant |
| **La mesure part de la vraie fin de ta voix**, le dernier moment où le son était assez fort. Elle dit aussi quand le premier geste ou outil a commencé, et combien d'appels à Claude il a fallu. | En mains libres, la mesure partait du moment où Vosk jugeait ta phrase finie, et oubliait environ 1 s. Quand Claude enchaîne des déplacements sans rien dire d'abord, le premier son arrivait jusqu'à 15 s plus tard : on verra si l'attente vient des gestes ou des allers-retours avec Claude. | |
| **Le cache de Claude se prépare dès « Hé Doly »**, pendant que tu finis ta phrase, ou dès le bip au toucher. Une fois par réveil, et seulement s'il a refroidi, après 4 minutes sans échange. | Premier mot de Claude mesuré à 2,18 s cache froid, contre 1,29 s cache chaud. Les consignes et les outils ont aussi leur propre point de cache : avant, une conversation neuve repartait toujours à froid. | `--sans-prechauffage` |
| **Ses phrases fixes sont gardées sur le disque** : « Je t'écoute ! », « Je n'ai rien compris », les messages d'erreur... | Piper ne les calcule plus qu'une fois, la première fois qu'il les dit. Elles sont refaites seules si leur texte ou la voix changent. | |
| **Un petit son d'attente**, deux notes aiguës et brèves, 0,28 s en tout, si Claude n'a rien dit 2,5 s après l'envoi de ta phrase. Une fois par réponse. | Pour savoir qu'il réfléchit, sans couvrir sa réponse. Il passe aussi quand Claude commence par un geste sans rien dire. | `ATTENTE_AVANT_SON`, `--sans-son-d-attente` |
| **La fin de phrase au volume**, en mains libres : un court silence après ta voix conclut ta phrase, au lieu d'attendre Vosk. **Désactivée** tant que le test n'a pas montré qu'elle ne te coupe pas la parole. | Gagner une partie de la seconde d'attente. | `--fin-au-volume`, 0,7 s par défaut, ou `--fin-au-volume 1.0` |

Les réglages en majuscules sont en haut de `converser.py`, les autres sont des options de lancement.

**Ce que cela ajoute en mémoire :** presque rien, car l'appli monte déjà jusqu'à 489 Mo sur 907. La file du micro garde 10 s de son au plus, soit 320 Ko. Les phrases fixes sont sur le disque, pas en mémoire, et le son d'attente pèse 12 Ko.

**Le préchauffage du cache :** une demande à Claude sans réponse demandée (`max_tokens` à 0), avec les consignes, les outils et la conversation déjà connue. Avec Haiku 5.5, préparer environ 4 700 tokens coûte environ 0,06 centime de dollar, et la vraie phrase relit ensuite ce cache au lieu de l'écrire : en tout, cela ne coûte presque rien de plus. Un réveil par erreur coûte ces 0,06 centime. Si l'API refuse la demande, il arrête de préchauffer jusqu'au prochain lancement, et la conversation continue comme avant. Une phrase dite juste après son nom attend le préchauffage 1,5 s au plus, car un appel lancé en même temps repartirait à froid.

**Ses phrases fixes sur le disque :** dans `~/.cache/doly/phrases`, environ 2 Mo. C'est sa propre voix, rien de ce que tu dis. Chacune est gardée la première fois qu'il la dit. Les préparer toutes d'avance a été essayé : Piper prenait alors le processeur à Vosk pendant qu'il écoutait, et ta première phrase avait 9,6 s de retard. Tu peux supprimer ce dossier : elles seront refaites.

**Le test de compréhension :** `tester_comprehension.py` te fait répéter 10 phrases dans 4 situations (à 1 m, à 3 m, télé allumée, une autre voix), et donne la part des mots compris. Il dira s'il faut un meilleur moteur de reconnaissance. Le grand modèle Vosk français ne tient pas dans sa mémoire, et envoyer le son sur Internet demanderait ton accord : rien n'est changé avant ce test. Les enregistrements restent sur le robot, dans `~/doly-comprehension`, et le programme ne les efface jamais : supprime le dossier pour les effacer.

### Mesuré sur le robot, le 9 novembre

| Situation | Mots compris | Phrases entièrement comprises | « Hé Doly » reconnu | Calcul de Vosk, pour 1 s de son |
|---|---|---|---|---|
| À 1 m | 95 % | 8 sur 10 | 10 sur 10 | 0,42 s |
| À 3 m | 83 % | 6 sur 10 | 10 sur 10 | 0,53 s |
| Télé allumée | 69 % | 2 sur 10 | 10 sur 10 | 0,87 s, et jusqu'à 1,5 s |
| Une autre voix | 53 % | 2 sur 10 | 5 sur 10 | 1,00 s |

- **Vosk ralentit avec le bruit ou une voix qu'il connaît mal**, jusqu'à aller moins vite que la parole. C'est la cause du retard du micro : la file a gardé jusqu'à 3 s de son en attente pendant des conversations normales, sans rien perdre. Avant l'étape 2, ce retard faisait perdre du son. Il ralentit aussi la première fois qu'il entend des mots : 4,5 s de calcul pour 4,7 s de son, puis 0,8 s pour la même phrase. Réchauffer Vosk avec 7 phrases au démarrage ne gagne que 15 à 20 %.
- **Les confusions déjà connues reviennent** : « vert » devient « verre » ou « envers », « mets » devient « mais ».
- **Le préchauffage marche** : la première phrase après un réveil relit les 4 550 tokens préparés dès « Hé Doly ».
- **Délais de réponse** sur une dizaine de phrases, depuis la fin de ta voix : de 3,3 à 4 s pour une réponse simple, jusqu'à 7 s quand Vosk avait 3 s de retard, et 8,4 s avec la météo.
- **Les phrases fixes ne sont plus préparées d'avance** : cela faisait travailler Piper pendant que Vosk écoutait, et la première réponse avait 16,7 s de retard.

## Démarrage automatique

Pour que Doly démarre en français à chaque allumage :

```bash
bash installer_demarrage.sh
```

Après l'allumage, sa personnalité d'origine démarre et installe ses éventuelles mises à jour, puis l'appli prend la main. Il dit « Je t'écoute ! » environ 40 secondes après le redémarrage.

**Après une mise à jour du code,** relance cette commande si `doly-francais.service` a changé : `git pull` ne suffit pas à l'installer.

Pour tout désactiver et retrouver sa personnalité d'origine :

```bash
sudo systemctl disable --now doly-francais
```

Pour lancer un autre script sur le robot sans le désactiver, arrête d'abord l'appli. Elle repartira au prochain allumage, ou avec `sudo systemctl start doly-francais`, sans attendre :

```bash
sudo systemctl stop doly-francais
```

**Avant de l'installer, à savoir :**

- **Micro :** il reste ouvert en permanence, sauf quand Doly parle ou après « ne m'écoute plus ». Le son reste en mémoire vive : 8 secondes au plus pour comprendre « Hé Doly » et la suite d'une traite, et 10 secondes au plus en attente de la reconnaissance vocale. Aucun fichier de ton son n'est écrit sur le disque, sauf pendant le test de compréhension. Tes phrases n'apparaissent pas dans le journal du robot.
- **Sa personnalité d'origine :** elle ne tourne plus, sauf si tu la demandes ou si l'appli échoue 3 fois en 5 minutes. Elle reprend alors la main toute seule.
- **Sa batterie :** il ne retourne pas seul sur sa base. À 30 %, il demande qu'on l'y pose, sauf s'il y est déjà, et il s'éteint une vingtaine de minutes plus tard. Sous 15 %, confirmé par 2 lectures à une minute d'écart, il s'éteint, sauf si la batterie charge vraiment, et il faut ensuite le rallumer à la main. Le niveau affiché est plus haut sur la base : sa lecture est passée de 47 % à 34 % en une minute à sa sortie de la base. S'il ne sait pas où il est, il garde le comportement le plus prudent : il prévient et il s'éteint. Ces seuils viennent de deux décharges mesurées. L'alerte et l'extinction ont été vérifiées une fois sur le robot, avant la détection de la base : annonces entendues, et arrêt propre confirmé par le journal, à 12 %.
- **Ses mises à jour :** l'appli laisse d'abord démarrer sa personnalité d'origine pour ne pas les gêner, mais ce mode n'a pas encore été observé pendant une vraie mise à jour.
- **Si Doly ne réagit plus du tout :** attends une minute, car il repart normalement tout seul (voir « S'il se fige »). Sinon, redémarre-le. Si le problème revient, regarde le journal avec la commande ci-dessous.

```bash
sudo journalctl -u doly-francais -b --no-pager | tail -30
```

## S'il se fige

Un programme figé reste « actif » pour le système : un micro bloqué laissait donc Doly sourd pour toujours. Maintenant, l'appli doit prouver à systemd qu'elle vit (`WatchdogSec`, voir `garde.py`). Cette preuve ne part que si sa boucle principale avance vraiment, donc si du son arrive du micro, ou si elle fait une chose longue et normale dans un délai fixé :

| Activité normale | Durée permise |
|---|---|
| Réponse de Claude, parole, animation ou scène | 10 minutes |
| Jeu | 15 minutes |
| Sonnerie du minuteur | 5 minutes |
| Doigt gardé posé | 2 minutes, puis cela recommence |
| Attente de sa personnalité d'origine, juste après l'allumage | 5 minutes |
| Préparation au démarrage | 45 secondes |

Passé ce délai, ou après 20 s sans signe de vie, elle ne répond plus, écrit où elle est bloquée dans le journal, et systemd la relance. **Doly redit alors « Je t'écoute ! »,** sans qu'on lui demande rien. Mesuré sur le robot avec de vrais gels (`kill -STOP`) :

| Gel | Relance par systemd | De nouveau prêt |
|---|---|---|
| Micro figé, `arecord` bloqué | 46 s | 69 s |
| Appli entière figée | 29 s | 48 à 50 s |

**Après 3 échecs en 5 minutes,** il rend la main à sa personnalité d'origine (`OnFailure`). Essayé : 3 gels d'affilée, et elle a repris 154 s après le début du test, sans aide.

**Les moteurs :** si le programme est figé ou tué en plein déplacement, **les chenilles continuent de tourner**, car leur commande reste en place (18 % mesurés sur les sorties du PCA9685, vitesse 20 %). `arreter_moteurs.py` les arrête donc environ 1 s après la fin anormale de l'appli (`ExecStopPost`), puis il baisse les bras. L'appli les arrête aussi à son démarrage. **Limite :** pendant un gel de toute l'appli, rien ne peut les arrêter avant que systemd la tue, soit 30 s au plus. C'est une raison de plus de le faire rouler au sol, loin d'un escalier. Un micro bloqué ne devrait pas laisser tourner les chenilles, car le SDK reste vivant et le déplacement finit normalement : c'est une déduction, pas une mesure. Un bras coupé en plein mouvement finit le geste de quelques degrés (de 73° à 81° pour 120° demandés), puis reste en place sans tomber, et il est rabaissé.

## Son relevé de santé

Toutes les 10 minutes, il écrit une ligne `[sante]` dans le journal : mémoire de l'appli et de la voix, mémoire disponible, fichier d'échange, température, charge du processeur et durées de fonctionnement. Rien que des nombres : aucune phrase dite. Chaque minute, `[batterie]` donne aussi sa place et le courant.

Pour tout résumer en français simple, sur Doly :

```bash
python3 resumer_journal.py
python3 resumer_journal.py --depuis "2 hours ago"
```

Il donne la durée d'écoute la plus longue, l'évolution de la mémoire, les coupures du micro, les erreurs, les gels et les redémarrages. Les durées ne dépendent pas de l'heure du robot, fausse juste après l'allumage. Il n'affiche jamais ce qui a été dit.

Il donne aussi les délais de réponse : la médiane, 9 sur 10 en dessous de combien, et le plus long, séparément depuis la fin de ta voix et depuis le doigt levé, puis avec et sans geste ou outil, puis le premier mot de Claude, les préchauffages du cache et les petits sons d'attente. Les mesures d'avant l'étape 2 ne comptent pas dans les délais, car en mains libres elles oubliaient environ 1 s. Pour le micro, il dit combien de coupures sont arrivées alors que la file était presque vide, donc alors que Vosk suivait, combien de son a attendu dans la file au plus, et l'échange, la mémoire disponible et la charge au moment des coupures.

**Le test long, le 7 novembre :** 3 h 32 d'écoute d'affilée, sans gel, sans erreur et sans redémarrage, avec 48 phrases. La température n'a pas dépassé 56 °C.

| Moment | Mémoire de l'appli | Mémoire disponible |
|---|---|---|
| Au départ | 254 Mo | 440 Mo |
| Après 1 h et 37 phrases, avec des scènes et des déplacements | 486 Mo | 216 Mo |
| 2 h 10 plus tard, sans parler | 486 Mo | 213 Mo |
| Après une dizaine de phrases de plus | 489 Mo | 234 Mo |

Elle monte donc quand on s'en sert, puis se stabilise, et rien n'indique de fuite sur ces heures. Plusieurs jours ou de très longues conversations n'ont pas été mesurés. Sur ce test, les 7 coupures du micro sont toutes arrivées pendant le plus gros saut de mémoire, quand il enchaînait les phrases et les scènes, et aucune pendant les 2 h 10 de repos.

## Sait-il qu'il est sur sa base ?

Oui, d'après le courant de sa batterie, comme l'explique la documentation du SDK (`base.py`, `ina219.py`). Le composant est seulement lu : aucun réglage n'y est écrit. C'est une déduction, pas un capteur de contact. Mesuré en moyenne sur 15 s, en mV sur le shunt :

| Situation | Courant |
|---|---|
| Hors de sa base, à l'écoute, en parlant ou en bougeant | -4 à -9 |
| Hors de sa base, micro coupé | -4,7 |
| Hors de sa base, endormi | -3,5 |
| Sur sa base, batterie pleine | -0,2 à 0 |
| Sur sa base, juste après une petite décharge | +1 à +2,7 |
| Sur sa base, après une heure hors de sa base (83 %) | +5 |
| Sur sa base, à 27 % | +4,2 |

Sur une moyenne de 20 s, il se dit sur sa base au-dessus de -1,5, hors de sa base en dessous de -2,5, et il ne sait pas entre les deux, ni pendant les 20 premières secondes, ni si la lecture échoue. Il faut donc une vingtaine de secondes pour qu'il s'en aperçoive.

| Ce qu'il sait | Alerte à 30 % | Extinction sous 15 % | Claude |
|---|---|---|---|
| Sur sa base, batterie qui charge | Non | Non | Il le sait |
| Sur sa base, sans charge nette | Non | Oui, par prudence | Il le sait |
| Hors de sa base | Oui | Oui | Il le sait |
| Il ne sait pas | Oui, comme avant | Oui, comme avant | Rien ne lui est dit |

Essayé à trois retraits et trois retours sur la base, et comparé aux gestes faits : tous vus, sans erreur. Claude a répondu juste, sur la base et hors de la base. `doly_battery` reste juste même avec des centaines de lectures par seconde du composant, car le SDK y fait des lectures groupées, où personne ne peut s'intercaler. `python3 mesurer_base.py` affiche le courant en direct.

**Le pourcentage suit la tension de la batterie, pas ce qu'il lui reste vraiment.** Il bondit dès qu'il est posé sur sa base (de 83 à 96 %, de 27 à 38 %), et il chute dès qu'il force (de 94 à 86 % en 20 s, processeur à fond). Un chiffre qui saute ne veut donc rien dire à lui seul.

**La vraie décharge, le 7 novembre :** à 30 %, hors de sa base, il a bien dit « Ma batterie est faible », et il n'a rien répété une fois reposé sur sa base, où la charge a été vue. À l'écoute, il a perdu environ 0,6 point par minute entre 38 et 30 %, contre 0,2 environ au-dessus de 80 %. **Pas essayé en vrai :** il ne s'est pas éteint sous 15 %, et le cas « reste allumé sous 15 % parce qu'il charge » n'est vérifié que par les essais sans matériel.

**Ce qu'il consomme, en mV sur le shunt :** repos 4,4, écrans et LED au maximum 5,8, demi-tours sur place 6,8 en moyenne avec des pointes à 44, processeur à fond 12 à 13. Faire tourner les 4 cœurs le fait monter à 74,5 °C en 80 s avec le ventilateur automatique, mais 66 °C stables avec le ventilateur à fond.

## Tests guidés

Ces trois scripts sont à lancer sur le robot, à côté de lui. Doly explique chaque étape à voix haute.

| Script | Ce qu'il vérifie | Où |
|---|---|---|
| `tester_bras.py` | Les bras, lentement et jusqu'à 60° | Sur une surface stable |
| `tester_capteurs.py` | Les capteurs de vide et d'obstacle, sans bouger les roues | Au sol |
| `tester_deplacements.py` | Les petits déplacements, les refus et les arrêts | Au sol, un mètre de libre |
| `tester_fonctions.py <partie>` | Les yeux, les sons, les réactions, la photo, les jeux et les scènes, voir [GUIDE_DE_TEST.md](GUIDE_DE_TEST.md) | Selon la partie |
| `tester_comprehension.py` | Ce qu'il comprend à 1 m, à 3 m, télé allumée et avec une autre voix, voir « Écoute et rapidité » | Dans une pièce où tu peux t'éloigner de 3 m |

`GUIDE_DE_TEST.md` explique aussi comment refaire les tests de solidité. `essais_sans_materiel.py` vérifie la logique avec des imitations du matériel (`faux_materiel.py`) : rien ne bouge ni ne sonne, et rien ne part sur Internet. `essais_sur_pc.py` lance sur un PC ceux qui n'ont pas besoin du robot.

## Bon à savoir

- **Modèle :** `claude-haiku-5-5`, avec `effort` bloqué sur `low`. Les deux se règlent en haut de `converser.py`.
- **Délai mesuré sur le robot :** le premier son arrive environ 2 s après le doigt levé pour une réponse simple, et 2,5 à 6 s quand il y a des gestes ou un premier appel à froid. En mains libres, ajoute environ 1 s, le temps qu'il comprenne que ta phrase est finie. Sur 165 phrases, le 7 novembre : médiane 2,61 s, 9 sur 10 sous 4,56 s, au plus 9,92 s, sans compter cette seconde. Depuis l'étape 2, la mesure la compte, ainsi que le retard de Vosk : de 3,3 à 4 s pour une réponse simple le 9 novembre, voir « Écoute et rapidité ».
- **Autonomie à l'écoute :** de 38 % à la coupure en 42 minutes lors d'une décharge, de 34 % à l'extinction en 27 minutes lors d'une autre. Elle n'a jamais été mesurée depuis une charge complète.
- **Coût :** avec Haiku 5.5 (0,10 $ / 0,50 $ par million de tokens), les outils et les consignes font environ 4 700 tokens, gardés en cache pendant 5 minutes. D'après les essais, compte environ 0,06 centime de dollar pour la première phrase, puis 0,01 à 0,03 centime par phrase, tant que vous vous parlez à moins de 5 minutes d'écart. Au-delà de 20 échanges, Doly repart d'une conversation neuve. Ses réactions, ses jeux et ses photos ne coûtent rien.
- **Crédits épuisés :** Doly dit qu'il n'a plus de crédit, et rien de plus n'est facturé tant que la recharge automatique reste désactivée.
- **Ventilateur :** la personnalité d'origine étant arrêtée, le script active le mode automatique, qui vise à garder le processeur sous 70 °C.
- **Mémoire :** à l'écoute, environ 320 Mo restent disponibles sur 907 Mo, et autour de 200 Mo après une longue conversation. L'appli gagne environ 25 Mo pendant ses 10 premières minutes d'écoute, à cause de Vosk, puis se stabilise. Avec les réactions et les nouveaux outils, sur un essai de 22 minutes sans vrai micro, elle est montée de 249 à 339 Mo, et au moins 317 Mo sont restés disponibles. Sur plusieurs heures, voir « Son relevé de santé » : jusqu'à 489 Mo, stable au repos.
- **Processeur :** à l'écoute, avec les réactions, environ 24 % d'un cœur sur les quatre. La photo prend environ 3,5 s et pèse 2 Mo.
- **Son :** rien de ce que tu dis n'est enregistré sur le disque pendant la conversation. Seules ses phrases fixes, avec sa propre voix, sont gardées dans `~/.cache/doly/phrases`.
- **Fichiers sur le robot :** son caractère (`humeur.json`), son style (`style.json`), la ville retenue (`ville.json`) et les records (`records.json`) sont dans `~/.config/doly/`, hors du dépôt. Les supprimer les remet à zéro.
- **Limites actuelles :** Doly ne voit pas et ne va pas sur Internet, sauf pour la météo, et il le dit quand on le lui demande.
