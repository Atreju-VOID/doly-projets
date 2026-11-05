# Mes projets Doly

Projets et scripts pour mon robot [Doly](https://doly.ai) (Limitbit), écrits avec Claude.

## Installer sur le robot

La première fois, sur Doly (en SSH) :

```bash
git clone https://github.com/Atreju-VOID/doly-projets.git
cd doly-projets
```

Si `git` n'est pas installé sur Doly : `sudo apt install git`.

Ensuite, pour récupérer les nouveautés :

```bash
cd ~/doly-projets
git pull
```

Chaque projet est dans `projets/<nom>/`, avec un README qui explique comment le lancer.

## Projets

_Aucun pour l'instant._

## Sources officielles

Le SDK officiel est déjà installé sur Doly, rien à ajouter. Sa documentation et ses exemples sont dans le dépôt officiel [robotdoly/DOLY-DIY](https://github.com/robotdoly/DOLY-DIY) (licence CC BY-NC-SA 4.0).

Pour en avoir une copie locale sur un ordinateur (dans `sdk-officiel/`) :

```bash
./outils/recuperer-sdk-officiel.sh
```
