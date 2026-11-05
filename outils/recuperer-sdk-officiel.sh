#!/usr/bin/env bash
# Télécharge (ou met à jour) le SDK officiel de Doly dans le dossier sdk-officiel/.
#
# Source : https://github.com/robotdoly/DOLY-DIY (licence CC BY-NC-SA 4.0)
# Seul le dossier SDK/ est récupéré (environ 18 Mo) : pas les fichiers 3D ni les PDF.
#
# sdk-officiel/ est une copie de référence, en lecture seule : ne la modifie pas,
# elle est écrasée à chaque mise à jour. Elle est ignorée par git.
#
# Inutile de lancer ce script sur Doly : le SDK y est déjà installé.
set -euo pipefail

DEPOT="https://github.com/robotdoly/DOLY-DIY.git"
RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CIBLE="$RACINE/sdk-officiel"

if [ -d "$CIBLE/.git" ]; then
  echo "Mise à jour du SDK officiel dans $CIBLE ..."
  BRANCHE="$(git -C "$CIBLE" rev-parse --abbrev-ref HEAD)"
  git -C "$CIBLE" fetch --quiet --depth 1 origin "$BRANCHE"
  git -C "$CIBLE" reset --quiet --hard FETCH_HEAD
else
  echo "Téléchargement du SDK officiel dans $CIBLE ..."
  git clone --quiet --depth 1 --filter=blob:none --sparse "$DEPOT" "$CIBLE"
  git -C "$CIBLE" sparse-checkout set SDK
fi

echo "SDK officiel à jour : $(git -C "$CIBLE" log -1 --format='commit %h du %cs (%s)')"
