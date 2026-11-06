#!/usr/bin/env bash
# Enregistre la clé API Anthropic sur le robot, sans l'afficher.
#
# Elle va dans ~/.config/doly/.env, lisible uniquement par l'utilisateur doly.
# Ce fichier est hors du dépôt : la clé ne peut donc pas partir sur GitHub.
set -euo pipefail

FICHIER="$HOME/.config/doly/.env"

echo "Colle ta clé API, puis appuie sur Entrée."
echo "Rien ne s'affiche pendant la saisie, c'est normal."
read -rs -p "Clé API : " CLE
echo

case "$CLE" in
  sk-ant-*) ;;
  *)
    echo "Cela ne ressemble pas à une clé API : elle doit commencer par sk-ant-. Rien n'a été enregistré."
    exit 1
    ;;
esac

umask 077
mkdir -p "$(dirname "$FICHIER")"
printf 'ANTHROPIC_API_KEY=%s\n' "$CLE" > "$FICHIER"
chmod 600 "$FICHIER"
echo "C'est bon : la clé est enregistrée. Tu peux revenir à la conversation."
