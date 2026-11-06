# Doly converse en français

Conversation à voix haute avec Doly : tu le touches ou tu dis « Hé Doly », tu parles, Claude réfléchit, Doly répond. Ses yeux et ses LED suivent la conversation, et il peut faire des gestes et se déplacer quand on le lui demande.

La voix française ([doly-parle](../doly-parle/)) et la reconnaissance vocale ([doly-ecoute](../doly-ecoute/)) tournent sur le robot. Seul le texte compris part sur Internet, vers Claude.

## Sécurité

**Pose Doly au sol, jamais sur une table,** avec un mètre de libre autour de lui, loin d'un escalier et sans câble autour. **Un toucher au-dessus de ses yeux arrête tout mouvement.**

Il ne se déplace que si on le lui demande clairement, et seulement avec les mouvements prévus dans `corps.py` : 10 ou 20 cm, un quart de tour ou un demi-tour, 5 au maximum par demande.

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

- **Lui parler :** pose un doigt sur la zone tactile au-dessus de ses yeux, parle après le bip, puis lève le doigt.
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
- **« Ne m'écoute plus » :** il coupe son micro jusqu'au prochain toucher.
- **« Reprends ta personnalité » :** il rend la main à sa personnalité d'origine.

**Ce qui part sur Internet :** l'écoute de « Hé Doly » se fait sur le robot, et rien ne sort tant qu'il ne l'a pas entendu. Ensuite, seul le texte de ta phrase part vers Claude, ainsi que ce que tu dis dans les 5 secondes qui suivent sa réponse. Ce qui a été dit avant « Hé Doly » n'est ni transcrit, ni envoyé. Si Doly se réveille par erreur, ce qui suit partira quand même : dis « ne m'écoute plus » si cela arrive trop souvent.

## Démarrage automatique

Pour que Doly démarre en français à chaque allumage :

```bash
bash installer_demarrage.sh
```

Après l'allumage, sa personnalité d'origine démarre et installe ses éventuelles mises à jour, puis l'appli prend la main. Il dit « Je t'écoute ! » environ 40 secondes après le redémarrage.

Pour tout désactiver et retrouver sa personnalité d'origine :

```bash
sudo systemctl disable --now doly-francais
```

Pour lancer un autre script sur le robot sans le désactiver, arrête d'abord l'appli. Elle repartira au prochain allumage :

```bash
sudo systemctl stop doly-francais
```

**Avant de l'installer, à savoir :**

- **Micro :** il reste ouvert en permanence, sauf quand Doly parle ou après « ne m'écoute plus ». Le son reste en mémoire vive, 8 secondes au plus, et aucun fichier de son n'est écrit sur le disque. Tes phrases n'apparaissent pas dans le journal du robot.
- **Sa personnalité d'origine :** elle ne tourne plus, sauf si tu la demandes ou si l'appli échoue 3 fois en 5 minutes. Elle reprend alors la main toute seule.
- **Sa batterie :** il ne retourne pas seul sur sa base. À 30 %, il demande qu'on l'y pose, et il s'éteint une vingtaine de minutes plus tard. Sous 15 %, confirmé par 2 lectures à une minute d'écart, il s'éteint, et il faut ensuite le rallumer à la main. Le SDK n'indique pas s'il est en train de charger, et le niveau affiché semble plus haut sur la base : sa lecture est passée de 47 % à 34 % en une minute, sans doute à sa sortie de la base. Sous 15 %, il s'éteint aussi sur sa base, alors laisse-le charger avant de le rallumer. Ces seuils viennent de deux décharges mesurées. L'alerte et l'extinction ont été vérifiées une fois sur le robot : annonces entendues, et arrêt propre confirmé par le journal, à 12 %.
- **Ses mises à jour :** l'appli laisse d'abord démarrer sa personnalité d'origine pour ne pas les gêner, mais ce mode n'a pas encore été observé pendant une vraie mise à jour.
- **Si Doly ne réagit plus du tout :** redémarre-le. Si le problème revient, regarde le journal avec la commande ci-dessous.

```bash
sudo journalctl -u doly-francais -b --no-pager | tail -30
```

## Tests guidés

Ces trois scripts sont à lancer sur le robot, à côté de lui. Doly explique chaque étape à voix haute.

| Script | Ce qu'il vérifie | Où |
|---|---|---|
| `tester_bras.py` | Les bras, lentement et jusqu'à 60° | Sur une surface stable |
| `tester_capteurs.py` | Les capteurs de vide et d'obstacle, sans bouger les roues | Au sol |
| `tester_deplacements.py` | Les petits déplacements, les refus et les arrêts | Au sol, un mètre de libre |

## Bon à savoir

- **Modèle :** `claude-haiku-5-5`, avec `effort` bloqué sur `low`. Les deux se règlent en haut de `converser.py`.
- **Délai mesuré sur le robot :** le premier son arrive environ 2 s après le doigt levé pour une réponse simple, et 2,5 à 6 s quand il y a des gestes ou un premier appel à froid. En mains libres, ajoute environ 1 s, le temps qu'il comprenne que ta phrase est finie.
- **Autonomie à l'écoute :** de 38 % à la coupure en 42 minutes lors d'une décharge, de 34 % à l'extinction en 27 minutes lors d'une autre. Elle n'a jamais été mesurée depuis une charge complète.
- **Coût :** avec Haiku 5.5 (0,10 $ / 0,50 $ par million de tokens), un échange consomme environ 1 500 à 2 500 tokens envoyés, à cause des outils, et il peut y avoir plusieurs appels par phrase. Comptez environ 0,03 centime par échange. Au-delà de 20 échanges, Doly repart d'une conversation neuve.
- **Crédits épuisés :** Doly dit qu'il n'a plus de crédit, et rien de plus n'est facturé tant que la recharge automatique reste désactivée.
- **Ventilateur :** la personnalité d'origine étant arrêtée, le script active le mode automatique, qui vise à garder le processeur sous 70 °C.
- **Mémoire :** à l'écoute, environ 320 Mo restent disponibles sur 907 Mo, et autour de 200 Mo après une longue conversation. L'appli gagne environ 25 Mo pendant ses 10 premières minutes d'écoute, à cause de Vosk, puis reste stable : aucune hausse pendant les 16 minutes suivantes. Elle n'a pas encore été mesurée sur plusieurs heures.
- **Son :** rien n'est enregistré sur le disque pendant la conversation.
- **Limites actuelles :** Doly ne voit pas, ne va pas sur Internet, et il le dit quand on le lui demande.
