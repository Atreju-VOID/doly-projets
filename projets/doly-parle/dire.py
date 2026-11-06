#!/usr/bin/env python3
"""
dire.py

Fait dire une phrase à Doly en français, avec la voix Piper fr_FR-siwis-medium.

Usage, sur le robot :
    python3 dire.py "Bonjour, je m'appelle Doly."
"""

import array
import math
import os
import subprocess
import sys
import tempfile
import wave

import doly_helper as helper

# Le moteur Piper est déjà installé avec le logiciel de Doly.
DOSSIER_PIPER = "/.doly/libs/piper/lib"
VOIX = os.path.expanduser("~/doly-voix/fr_FR-siwis-medium.onnx")
# Accès direct à la carte son : le périphérique ALSA "default" refuse l'utilisateur doly,
# car le verrou de son mixage appartient à root.
CARTE_SON = "plughw:0,0"


def service_doly_actif():
    return subprocess.run(["systemctl", "is-active", "--quiet", "doly"]).returncode == 0


def synthetiser(texte, fichier_wav):
    commande = [
        DOSSIER_PIPER + "/piper",
        "--model", VOIX,
        "--espeak_data", DOSSIER_PIPER + "/espeak-ng-data",
        "--output_file", fichier_wav,
        "--quiet",
    ]
    env = dict(os.environ, LD_LIBRARY_PATH=DOSSIER_PIPER)
    resultat = subprocess.run(commande, input=texte.encode("utf-8"), env=env, capture_output=True)
    if resultat.returncode != 0:
        print(f"[erreur] Piper a échoué : {resultat.stderr.decode('utf-8', 'replace')}")
        return False
    return True


def jouer(fichier_wav):
    resultat = subprocess.run(["aplay", "-D", CARTE_SON, "-q", fichier_wav], capture_output=True)
    if resultat.returncode != 0:
        print(f"[erreur] Lecture impossible : {resultat.stderr.decode('utf-8', 'replace')}")
        return False
    return True


def creer_bip(chemin):
    taux = 22050
    echantillons = array.array(
        "h", (int(8000 * math.sin(2 * math.pi * 880 * i / taux)) for i in range(taux // 6))
    )
    with wave.open(chemin, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taux)
        w.writeframes(echantillons.tobytes())


def main():
    texte = " ".join(sys.argv[1:]).strip()
    if not texte:
        print("Usage : python3 dire.py \"Bonjour, je m'appelle Doly.\"")
        return 2

    if not os.path.isfile(VOIX):
        print("[erreur] Voix introuvable. Lance d'abord : bash installer_voix.sh")
        return 1

    # Sa personnalité d'origine occupe le haut-parleur : on l'arrête le temps de parler.
    relancer_service = service_doly_actif()
    if helper.stop_doly_service() < 0:
        print("[erreur] Impossible d'arrêter le service Doly.")
        return 1

    try:
        with tempfile.TemporaryDirectory() as dossier:
            fichier_wav = os.path.join(dossier, "phrase.wav")
            if not synthetiser(texte, fichier_wav) or not jouer(fichier_wav):
                return 1
    finally:
        if relancer_service:
            subprocess.run(["sudo", "-n", "systemctl", "start", "doly"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
