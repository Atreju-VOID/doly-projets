#!/usr/bin/env bash
# Télécharge sur Doly la voix française fr_FR-siwis-medium (environ 60 Mo).
#
# Source : https://huggingface.co/rhasspy/piper-voices
# La voix n'est pas dans ce dépôt, car elle est trop lourde.
set -euo pipefail

DOSSIER="$HOME/doly-voix"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium"

mkdir -p "$DOSSIER"
cd "$DOSSIER"

for fichier in fr_FR-siwis-medium.onnx fr_FR-siwis-medium.onnx.json; do
  if [ ! -f "$fichier" ]; then
    echo "Téléchargement de $fichier ..."
    curl -fsSL --retry 2 -o "$fichier.part" "$BASE/$fichier"
    mv "$fichier.part" "$fichier"
  fi
done

md5sum --quiet -c <<EMPREINTES
20e876e8c839e9b11a26085858f2300c  fr_FR-siwis-medium.onnx
a407e7e6901feb79c2ea2a5466076cce  fr_FR-siwis-medium.onnx.json
EMPREINTES

echo "Voix prête dans $DOSSIER"
