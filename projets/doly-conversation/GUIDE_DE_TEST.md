# Guide de test des nouvelles fonctions

Ce guide vérifie tout ce qui ne peut se voir ou s'entendre qu'en vrai, à côté du robot. Compte environ 30 minutes. À refaire après un changement dans les réactions, les jeux ou les animations.

## Avant de commencer

Sur Doly, en SSH, depuis le dossier où se trouve le code :

```bash
sudo systemctl stop doly-francais
cd ~/doly-projets/projets/doly-conversation
```

Chaque partie se lance avec une commande. Doly explique à voix haute ce qu'il faut faire, et le résultat s'écrit à l'écran. **Un appui franc au-dessus de ses yeux arrête ses mouvements.**

Commence **sur une surface stable, sans rouler** : seule la dernière partie le fait rouler, et elle se fait au sol.

## Les parties

| Commande | À vérifier |
|---|---|
| `~/doly-env/bin/python tester_fonctions.py yeux` | Tu lis « 1 » à ta gauche et « 2 » à ta droite. L'heure se lit dans le bon sens. Soleil, pluie, neige, gâteau et plage s'affichent. Ses yeux normaux reviennent à la fin, sans image restée bloquée. |
| `~/doly-env/bin/python tester_fonctions.py sons` | Ses petits sons, ses bruitages et la musique sont au même niveau que sa voix, pas trop forts. |
| `~/doly-env/bin/python tester_fonctions.py cotes` | Un œil s'allume : appuie au-dessus, sans attendre la fin de sa phrase, deux fois. Le résultat affiché donne le même côté pour l'œil allumé et le capteur touché. Le défi éclair en dépend. |
| `~/doly-env/bin/python tester_fonctions.py toucher` | Trois temps, 2 minutes en tout. Des tapes espacées : il est content, et de plus en plus. Des tapes très rapides : il s'agace, de plus en plus. Un doigt gardé posé sans parler : un bip, puis il apprécie, et il finit par s'agacer. |
| `~/doly-env/bin/python tester_fonctions.py chocs` | Une poussette légère : petite réaction. Plus forte : grande réaction. Le côté annoncé à l'écran correspond à celui de la poussette. Il ne réagit à rien quand tu ne le touches pas. |
| `~/doly-env/bin/python tester_fonctions.py soulever` | Il réagit quand tu le soulèves, et il est soulagé quand tu le reposes. Il réagit aussi si tu ne soulèves qu'un côté. |
| `~/doly-env/bin/python tester_fonctions.py main` | Ses yeux se tournent du côté de ta main, sans aucun son. Au milieu, il fait une expression selon son humeur. Le champ des capteurs est étroit : passe bien devant un œil, à moins de 13 cm. |
| `~/doly-env/bin/python tester_fonctions.py bras` | Les gestes ne sont ni trop brusques ni trop rapides. Un toucher arrête les bras, qui redescendent doucement environ 4 secondes plus tard. |
| `~/doly-env/bin/python tester_fonctions.py photo` | L'œil en forme d'appareil photo et le déclic. Le chemin de la photo s'affiche, à ouvrir ensuite pour vérifier qu'elle est à l'endroit et nette. |
| `~/doly-env/bin/python tester_fonctions.py minuteur` | Le compte à rebours sur ses yeux, puis l'annonce et la sonnerie. Un toucher arrête la sonnerie. |
| `~/doly-env/bin/python tester_fonctions.py roue` | La partie se joue en touchant sa tête. Les fruits tournent, le gauche s'arrête en premier. |
| `~/doly-env/bin/python tester_fonctions.py defi` | Un œil s'allume, tu appuies franchement au-dessus. Le temps de réponse est jouable et se raccourcit. Le mauvais œil coûte aussitôt une vie, sur 3. Un doigt resté posé ne compte pas. Le score final tient dans sa case. |
| `~/doly-env/bin/python tester_fonctions.py dodo` | Il s'endort. Appuyer avant qu'il ronfle fait perdre. Ensuite, il ouvre parfois un œil et arrête de ronfler : une main immobile n'est pas vue, une main qui bouge l'est. La réglette `BOUGE_TROP` de `jeux.py` est à ajuster si besoin. |
| `~/doly-env/bin/python tester_fonctions.py tope` | Il lève le bras, et réagit quand tu tapes dedans. Puis il boude quand il est fâché, sans lever le bras. |
| `~/doly-env/bin/python tester_fonctions.py scenes` | **Au sol, un mètre de libre autour de lui.** Il danse et fait du sport en roulant un peu. Un toucher arrête tout. Le soulever l'arrête aussi. |

## La vraie conversation

Sans passer par l'appli installée :

```bash
~/doly-env/bin/python converser.py --mains-libres
```

Essaie ces phrases, après « Hé Doly » :

- « Quel temps fait-il ? », « Et demain à Lyon ? » : il répond avec de vraies valeurs, et ses yeux montrent la météo.
- « Quelle heure est-il ? », « Montre-moi l'heure sur tes yeux. »
- « Mets un minuteur de 10 secondes. »
- « Prends une photo. »
- « On joue à la roue. », « Tope là ! »
- « Tu es vraiment trop fort. », « T'es nul. », « Sois méchant. », « Je te parie que tu ne peux pas me battre. », « Je suis triste. » : son ton et ses yeux changent, sans jamais être blessants.
- « Es-tu fâché ? » : sa réponse suit son humeur.
- « Fais le chat. », « Imagine que tu es à la plage. », « Aujourd'hui, c'est mon anniversaire. »
- « Change la couleur de tes yeux en vert. »
- « Va dormir. », puis « Hé Doly ».
- « Danse ! », au sol seulement.

Essaie aussi avec le doigt : pose-le, attends le bip, parle sans le lever, puis lève-le. Il doit répondre à ta phrase. Si tu gardes le doigt posé sans parler, il doit apprécier, sans dire « Je n'ai rien compris ».

La reconnaissance vocale se trompe parfois, surtout sur les mots qui se prononcent pareil, comme « en verre » pour « en vert » : Claude doit deviner le sens.

Ctrl+C l'arrête.

## La solidité

Ces tests relancent l'appli, et **Doly redit « Je t'écoute ! » à chaque fois**. Au bout de 3 gels, sa personnalité d'origine reprend : elle peut rouler, alors laisse-le au sol, sur sa base ou dans tes mains.

**Une appli figée.** Avec l'appli installée, qui tourne :

```bash
sudo kill -STOP $(systemctl show doly-francais -p MainPID --value)
```

Environ 30 s plus tard, le journal indique `Watchdog timeout`, puis `[garde] Moteurs arrêtés`, et Doly redit « Je t'écoute ! » 15 à 20 s après. Pour vérifier le matériel : dis « Hé Doly, lève les bras », passe ta main devant un œil, et tape sa tête.

**Un micro figé :**

```bash
sudo kill -STOP $(pgrep -x arecord | head -1)
```

Environ 20 s plus tard, `[garde] Plus de signe de vie`, puis la même relance. Il ne doit y avoir aucun gel pendant un jeu, une longue réponse ou un doigt gardé posé.

**Le repli :** fais 3 gels d'affilée de l'appli, en attendant chaque fois qu'elle soit prête. Sa personnalité d'origine doit reprendre seule. Pour revenir ensuite à l'appli :

```bash
sudo systemctl reset-failed doly-francais
sudo systemctl start doly-francais
```

**Sa place :** `python3 mesurer_base.py --duree 120`, en le retirant de sa base puis en l'y remettant : voir les valeurs attendues dans le [README](README.md). Attends 20 s, puis demande « Hé Doly, est-ce que tu es sur ta base ? ». Compare aussi avec la ligne `[batterie]` du journal, qui donne sa place chaque minute.

**L'alerte de batterie :** retire-le de sa base et laisse-le à l'écoute, ce qui prend plusieurs heures depuis une batterie pleine. À 30 %, il doit dire « Ma batterie est faible ». Pose-le alors sur sa base : la LED rouge s'allume dessous, le journal indique `sur sa base` et un courant positif, et l'alerte ne se répète pas.

**Le bilan :** `python3 resumer_journal.py`. « Sur la dernière heure » n'apparaît qu'après une heure et demie d'écoute. Le chiffre reste normal s'il a monté pendant une conversation : c'est un chiffre qui monte encore au repos qui serait inquiétant.

## Après le test

Pour relancer l'appli installée :

```bash
sudo systemctl start doly-francais
```

Elle dit « Je t'écoute ! » une quinzaine de secondes plus tard. Elle n'attend sa personnalité d'origine que dans les 5 minutes qui suivent l'allumage.
