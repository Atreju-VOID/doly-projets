#!/usr/bin/env bash
# Installe le démarrage automatique de la conversation mains libres.
#
# À chaque allumage, Doly démarre normalement, installe ses éventuelles mises à jour, puis cette appli
# prend la main. Le micro reste alors ouvert en permanence.
#
# Pour tout désactiver : sudo systemctl disable --now doly-francais
set -euo pipefail

DOSSIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

sudo cp "$DOSSIER/doly-francais.service" /etc/systemd/system/doly-francais.service
sudo systemctl daemon-reload
sudo systemctl enable doly-francais
echo "Démarrage automatique installé : il prendra effet au prochain allumage."
