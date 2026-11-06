#!/usr/bin/env bash
# Installe le SDK officiel de Claude dans ~/doly-env.
#
# À lancer sur le robot, une fois les projets doly-parle et doly-ecoute installés.
set -euo pipefail

"$HOME/doly-env/bin/pip" install --quiet --disable-pip-version-check anthropic
"$HOME/doly-env/bin/python" -c "import anthropic; print('SDK Claude', anthropic.__version__)"
