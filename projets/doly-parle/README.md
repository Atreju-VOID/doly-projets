# Doly parle français

Fait dire à Doly la phrase de ton choix en français, sans Internet, avec la voix Piper `fr_FR-siwis-medium`.

## Installer la voix

Une seule fois, sur Doly, avec Internet (environ 60 Mo) :

```bash
cd ~/doly-projets/projets/doly-parle
bash installer_voix.sh
```

## Lancer

```bash
python3 dire.py "Bonjour, je m'appelle Doly."
```

## Résultat attendu

Sa personnalité d'origine s'arrête et ses yeux peuvent se figer. Doly dit la phrase au bout de quelques secondes, puis sa personnalité repart toute seule.

## Bon à savoir

- **Moteur :** Piper est installé avec le logiciel de Doly (`/.doly/libs/piper/lib`), avec son dictionnaire français. Seule la voix est à télécharger, car les 3 voix de `doly_tts` sont en anglais.
- **Vitesse mesurée sur le robot :** 0,5 s de calcul pour une phrase courte et 4,2 s pour 10,6 s de parole, plus 1,1 s de chargement de la voix à chaque lancement.
- **Mémoire :** 240 Mo pendant le calcul, sur 766 Mo libres quand sa personnalité est arrêtée.
- **Son :** le script passe par `plughw:0,0`, qui convertit le format tout seul. Le périphérique `default` refuse l'utilisateur `doly`, car le verrou de son mixage appartient à `root`.
- **Licence de la voix :** données « siwis » sous CC BY 4.0, d'après la [fiche de la voix](https://huggingface.co/rhasspy/piper-voices/blob/main/fr/fr_FR/siwis/medium/MODEL_CARD).
