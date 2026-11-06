#!/usr/bin/env bash
# Prépare sur Doly la reconnaissance vocale française locale avec Vosk.
#
# Crée ~/doly-env (environnement Python) et ~/doly-modeles (environ 45 Mo à télécharger).
# Modèle : vosk-model-small-fr-0.22, licence Apache 2.0 (https://alphacephei.com/vosk/models)
set -euo pipefail

ENVIRONNEMENT="$HOME/doly-env"
DOSSIER_MODELES="$HOME/doly-modeles"
MODELE="vosk-model-small-fr-0.22"

if [ ! -d "$ENVIRONNEMENT" ]; then
  echo "Création de l'environnement Python dans $ENVIRONNEMENT ..."
  python3 -m venv --system-site-packages "$ENVIRONNEMENT"
fi

echo "Installation de Vosk ..."
"$ENVIRONNEMENT/bin/pip" install --quiet --disable-pip-version-check vosk

if [ ! -d "$DOSSIER_MODELES/$MODELE" ]; then
  echo "Téléchargement du modèle français ..."
  mkdir -p "$DOSSIER_MODELES"
  curl -fsSL --retry 2 -o "$DOSSIER_MODELES/$MODELE.zip" "https://alphacephei.com/vosk/models/$MODELE.zip"
  python3 -m zipfile -e "$DOSSIER_MODELES/$MODELE.zip" "$DOSSIER_MODELES/"
  rm "$DOSSIER_MODELES/$MODELE.zip"
fi

"$ENVIRONNEMENT/bin/python" -c "import vosk, doly_touch"
echo "Prêt : Vosk et le modèle français sont installés."
