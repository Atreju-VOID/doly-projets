#!/usr/bin/env python3
"""
tester_bras.py

Vérifie que les bras de Doly bougent comme prévu, lentement et sur une petite amplitude.

Doly annonce le test à voix haute. Garde les doigts loin de ses bras, et touche-le pour tout arrêter.

Usage, sur le robot :
    ~/doly-env/bin/python tester_bras.py
"""

import os
import subprocess
import sys
import tempfile
import time

import doly_arm as arm
import doly_helper as helper
import doly_touch as touch

# dire.py est dans le projet voisin.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "doly-parle"))
from dire import jouer, service_doly_actif, synthetiser

VITESSE = 15  # en pourcentage : volontairement lent
DELAI = 8  # secondes au maximum pour un mouvement
ETAPES = [
    ("les deux bras, un peu", arm.ArmSide.Both, 30),
    ("les deux bras, un peu plus", arm.ArmSide.Both, 60),
    ("retour en bas", arm.ArmSide.Both, 0),
    ("le bras droit seul", arm.ArmSide.Right, 60),
    ("retour en bas", arm.ArmSide.Right, 0),
    ("le bras gauche seul", arm.ArmSide.Left, 60),
    ("retour en bas", arm.ArmSide.Left, 0),
]


def annoncer(texte):
    with tempfile.TemporaryDirectory() as dossier:
        fichier = os.path.join(dossier, "annonce.wav")
        if synthetiser(texte, fichier):
            jouer(fichier)


def capteur_touche():
    return touch.is_touched(touch.TouchSide.Left) or touch.is_touched(touch.TouchSide.Right)


def angles():
    return " ".join(f"{a.side.name}={a.angle:.0f}" for a in arm.get_current_angle(arm.ArmSide.Both))


def bouger(numero, cote, angle):
    """Renvoie False si un toucher a demandé l'arrêt."""
    rc = arm.set_angle(numero, cote, VITESSE, angle)
    if rc < 0:
        print(f"[erreur] Mouvement refusé (code {rc})", flush=True)
        return False
    depart = time.monotonic()
    time.sleep(0.1)
    while arm.get_state(cote) == arm.ArmState.Running and time.monotonic() - depart < DELAI:
        if capteur_touche():
            arm.abort(arm.ArmSide.Both)
            print("[info] Arrêt demandé par un toucher", flush=True)
            return False
        time.sleep(0.05)
    print(f"[info] {time.monotonic() - depart:.1f} s, état {arm.get_state(cote).name}, angles : {angles()}", flush=True)
    return True


def main():
    relancer_service = service_doly_actif()
    if helper.stop_doly_service() < 0:
        print("[erreur] Impossible d'arrêter le service Doly.")
        return 1
    try:
        # Le SDK exige la lecture des réglages pour que les bras obéissent à leur calibrage.
        if helper.read_settings() < 0 or touch.init() < 0 or arm.init() < 0:
            print("[erreur] Bras ou capteurs indisponibles.")
            return 1
        print(f"[info] Angles au départ : {angles()}", flush=True)
        annoncer("Attention, je vais bouger les bras doucement. Touche-moi pour tout arrêter.")
        for numero, (nom, cote, angle) in enumerate(ETAPES, 1):
            print(f"[etape {numero}] {nom} : {angle} degrés", flush=True)
            if not bouger(numero, cote, angle):
                break
            time.sleep(1)
        else:
            annoncer("C'est terminé.")
    finally:
        arm.set_angle(99, arm.ArmSide.Both, VITESSE, 0)
        time.sleep(1)
        arm.dispose()
        touch.dispose()
        if relancer_service:
            subprocess.run(["sudo", "-n", "systemctl", "start", "doly"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
