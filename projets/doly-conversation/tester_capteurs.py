#!/usr/bin/env python3
"""
tester_capteurs.py

Vérifie ce que renvoient les capteurs de vide et d'obstacle de Doly. Les roues ne bougent pas.

Doly guide le test à voix haute : pose-le au sol, soulève-le, repose-le, puis passe ta main devant lui.

Usage, sur le robot :
    ~/doly-env/bin/python tester_capteurs.py
"""

import collections
import os
import subprocess
import sys
import tempfile
import time

import doly_edge as edge
import doly_helper as helper
import doly_tof as tof

# dire.py est dans le projet voisin.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "doly-parle"))
from dire import jouer, service_doly_actif, synthetiser

PHASES = [
    ("au sol", "Pose-moi par terre, puis ne me touche plus.", 8),
    ("souleve", "Maintenant, soulève-moi et garde-moi en l'air.", 7),
    ("repose", "Repose-moi par terre.", 7),
]


def annoncer(texte):
    with tempfile.TemporaryDirectory() as dossier:
        fichier = os.path.join(dossier, "annonce.wav")
        if synthetiser(texte, fichier):
            jouer(fichier)


def nom(valeur):
    return str(valeur).split(".")[-1]


def lire_vide(duree):
    """Lit les capteurs de vide pendant la durée donnée et compte les combinaisons d'états."""
    comptes = collections.Counter()
    fin = time.monotonic() + duree
    while time.monotonic() < fin:
        comptes[" ".join(f"{nom(s.id)}={nom(s.state)}" for s in edge.get_sensors())] += 1
        time.sleep(0.05)
    return comptes


def main():
    relancer_service = service_doly_actif()
    if helper.stop_doly_service() < 0:
        print("[erreur] Impossible d'arrêter le service Doly.")
        return 1
    debut = time.monotonic()
    evenements = []
    try:
        rc_vide = edge.init()
        rc_obstacle = tof.init()
        if rc_vide < 0 or rc_obstacle < 0:
            print(f"[erreur] Capteurs indisponibles (vide {rc_vide}, obstacle {rc_obstacle}).")
            return 1
        edge.on_gap_detect(lambda sens: evenements.append((time.monotonic() - debut, "vide", nom(sens))))

        for phase, consigne, delai in PHASES:
            print(f"[phase] {phase}", flush=True)
            annoncer(consigne)
            time.sleep(delai)
            print(f"[{phase}] {lire_vide(2).most_common()}", flush=True)

        print("[phase] obstacle", flush=True)
        annoncer("Approche doucement ta main devant mes yeux, puis éloigne-la.")
        mesures = collections.defaultdict(list)
        erreurs = collections.Counter()
        fin = time.monotonic() + 8
        while time.monotonic() < fin:
            for donnee in tof.get_sensors_data():
                erreurs[f"{nom(donnee.side)}:{nom(donnee.error)}"] += 1
                if donnee.range_mm >= 0:
                    mesures[nom(donnee.side)].append(donnee.range_mm)
            time.sleep(0.05)
        for cote, valeurs in mesures.items():
            print(f"[obstacle] {cote} : {len(valeurs)} mesures, de {min(valeurs)} à {max(valeurs)} mm", flush=True)
        print(f"[obstacle] états : {erreurs.most_common()}", flush=True)
        print(f"[evenements de vide] {[(round(t, 1), s, d) for t, s, d in evenements]}", flush=True)
        annoncer("C'est terminé, merci.")
    finally:
        edge.clear_callbacks()
        edge.dispose()
        tof.dispose()
        if relancer_service:
            subprocess.run(["sudo", "-n", "systemctl", "start", "doly"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
