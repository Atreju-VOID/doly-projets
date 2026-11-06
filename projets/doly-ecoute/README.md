# Doly écoute en français

Teste la reconnaissance vocale de Doly, sans Internet, avec Vosk et son petit modèle français : tu touches Doly, tu parles, il répète ce qu'il a compris.

Ce projet utilise `dire.py` du projet [doly-parle](../doly-parle/), dont la voix doit être installée.

## Installer

Une seule fois, sur Doly, avec Internet (environ 45 Mo) :

```bash
cd ~/doly-projets/projets/doly-ecoute
bash installer_ecoute.sh
```

## Lancer

```bash
~/doly-env/bin/python tester_phrases.py
```

## Résultat attendu

Doly explique le test à voix haute, puis lit 6 phrases. Pour chacune, pose un doigt sur la zone tactile au-dessus de ses yeux, répète la phrase après le bip, puis lève le doigt. Il dit « J'ai compris : … ». Le test dure 2 à 3 minutes, et sa personnalité d'origine repart à la fin.

Les enregistrements et les résultats restent sur le robot, dans `~/doly-ecoute`.

## Résultats du premier essai

Dans une pièce calme, à environ 50 cm, sur 6 phrases courtes, soit 50 mots : aucune erreur de compréhension, à part « Doly » écrit « dolly ». Le score affiché par le test était de 18 %, à tort : pour les phrases 1 et 6, j'ai dit autre chose que la phrase lue, et le test compare avec la phrase lue. C'est un petit échantillon : Vosk annonce 19 à 27 % d'erreurs sur des données plus difficiles.

## Bon à savoir

- **« Doly » :** le modèle l'écrit « dolly », car ce nom n'est pas dans son vocabulaire.
- **Mémoire :** 225 Mo au maximum, sur 766 Mo libres quand sa personnalité est arrêtée.
- **Vitesse :** avec un seul reconnaisseur, 1 à 2,2 s de calcul pour 3 à 4 s de parole, sauf la première phrase, qui prend 3,9 s. Avec un nouveau reconnaisseur par phrase, c'était 3 à 4,5 s.
- **En direct :** alimenter le reconnaisseur pendant qu'on parle laisserait moins de 0,4 s de calcul au moment où le doigt se lève, d'après une simulation sur les enregistrements. Reste à le vérifier en conditions réelles.
- **Micro :** les deux canaux sont identiques, donc le script enregistre en mono à 16 kHz.
