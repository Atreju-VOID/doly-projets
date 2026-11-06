# Doly converse en français

Conversation à voix haute avec Doly : tu touches, tu parles, Claude réfléchit, Doly répond.

La voix française ([doly-parle](../doly-parle/)) et la reconnaissance vocale ([doly-ecoute](../doly-ecoute/)) tournent sur le robot. Seul le texte compris part sur Internet, vers Claude.

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
- **Lui couper la parole :** touche-le pendant qu'il parle.
- **Terminer :** dis « au revoir », ou ne le touche plus pendant 5 minutes. Sa personnalité d'origine repart alors toute seule.

Pendant la conversation, il ne bouge pas et ses yeux peuvent rester figés.

## Bon à savoir

- **Modèle :** `claude-haiku-5-5`, avec `effort` bloqué sur `low`. Les deux se règlent en haut de `converser.py`.
- **Délai mesuré sur le robot :** le premier son arrive 1,8 à 1,9 s après le doigt levé, dont 0,5 s de transcription et 0,7 à 1 s avant le premier mot de Claude.
- **Coût :** avec Haiku 5.5 (0,10 $ / 0,50 $ par million de tokens), un échange consomme environ 500 tokens envoyés et 50 à 100 reçus, soit environ 0,01 centime. Le nombre de tokens envoyés grandit avec la conversation. Au-delà de 20 échanges, Doly repart d'une conversation neuve.
- **Crédits épuisés :** Doly dit qu'il n'a plus de crédit, et rien de plus n'est facturé tant que la recharge automatique reste désactivée.
- **Mémoire :** environ 500 Mo occupés en tout pendant la conversation, sur 907 Mo, et il en reste environ 400 de disponibles. Les réglages de chaque brique sont dans les README voisins.
- **Son :** rien n'est enregistré sur le disque pendant la conversation.
- **Limites actuelles :** Doly ne peut ni bouger, ni voir, ni aller sur Internet, et il le dit quand on le lui demande.
