# Doly converse en français

Conversation à voix haute avec Doly : tu touches, tu parles, Claude réfléchit, Doly répond. Ses yeux et ses LED suivent la conversation, et il peut faire des gestes et se déplacer quand on le lui demande.

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
| Batterie sous 10 % | Il refuse de rouler | Non |

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

## Tests guidés

Ces trois scripts sont à lancer sur le robot, à côté de lui. Doly explique chaque étape à voix haute.

| Script | Ce qu'il vérifie | Où |
|---|---|---|
| `tester_bras.py` | Les bras, lentement et jusqu'à 60° | Sur une surface stable |
| `tester_capteurs.py` | Les capteurs de vide et d'obstacle, sans bouger les roues | Au sol |
| `tester_deplacements.py` | Les petits déplacements, les refus et les arrêts | Au sol, un mètre de libre |

## Bon à savoir

- **Modèle :** `claude-haiku-5-5`, avec `effort` bloqué sur `low`. Les deux se règlent en haut de `converser.py`.
- **Délai mesuré sur le robot :** le premier son arrive environ 2 s après le doigt levé pour une réponse simple, et 2,5 à 6 s quand il y a des gestes ou un premier appel à froid.
- **Coût :** avec Haiku 5.5 (0,10 $ / 0,50 $ par million de tokens), un échange consomme environ 1 500 à 2 500 tokens envoyés, à cause des outils, et il peut y avoir plusieurs appels par phrase. Comptez environ 0,03 centime par échange. Au-delà de 20 échanges, Doly repart d'une conversation neuve.
- **Crédits épuisés :** Doly dit qu'il n'a plus de crédit, et rien de plus n'est facturé tant que la recharge automatique reste désactivée.
- **Ventilateur :** la personnalité d'origine étant arrêtée, le script active le mode automatique, qui vise à garder le processeur sous 70 °C.
- **Mémoire :** environ 400 Mo restent disponibles sur 907 Mo pendant la conversation.
- **Son :** rien n'est enregistré sur le disque pendant la conversation.
- **Limites actuelles :** Doly ne voit pas, ne va pas sur Internet, et il le dit quand on le lui demande.
