#!/usr/bin/env python3
"""
tester_deplacements.py

Vérifie les déplacements de Doly et leurs garde-fous : petits mouvements, refus et arrêts.

À faire au sol, jamais sur une table, avec un mètre de libre autour de lui. Doly guide le test à voix
haute. Un toucher au-dessus de ses yeux l'arrête à tout moment.

Usage, sur le robot :
    ~/doly-env/bin/python tester_deplacements.py
"""

import os
import subprocess
import sys
import tempfile
import threading
import time

import doly_drive as drive
import doly_helper as helper
import doly_touch as touch

# dire.py est dans le projet voisin.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "doly-parle"))
from dire import jouer, service_doly_actif, synthetiser

from corps import Corps

VITESSE = 25  # en pourcentage : un peu plus lent que dans la conversation


def annoncer(texte):
    with tempfile.TemporaryDirectory() as dossier:
        fichier = os.path.join(dossier, "annonce.wav")
        if synthetiser(texte, fichier):
            jouer(fichier)


def position():
    p = drive.get_position()
    return f"x={p.x:.0f} y={p.y:.0f} cap={p.head:.0f}"


def journal(nom, debut, message):
    print(f"[{nom}] {time.monotonic() - debut:.2f} s, {position()} : {message}", flush=True)


def main():
    relancer_service = service_doly_actif()
    if helper.stop_doly_service() < 0:
        print("[erreur] Impossible d'arrêter le service Doly.")
        return 1

    corps = None
    surveiller = True
    touchers = []

    def surveiller_toucher():
        """Un toucher arrête tout, comme dans la conversation."""
        etait_touche = False
        while surveiller:
            touche = touch.is_touched(touch.TouchSide.Left) or touch.is_touched(touch.TouchSide.Right)
            if touche and not etait_touche:
                touchers.append(time.monotonic())
                corps.arreter()
            etait_touche = touche
            time.sleep(0.02)

    try:
        if touch.init() < 0:
            print("[erreur] Capteurs tactiles indisponibles.")
            return 1
        corps = Corps()
        threading.Thread(target=surveiller_toucher, daemon=True).start()
        print(f"[info] Sol : {corps.sol_sous_lui()}, obstacle : {corps.obstacle_devant()}", flush=True)

        annoncer("Attention, je vais rouler un peu. Pose-moi par terre, avec un mètre de libre autour de moi.")
        time.sleep(8)
        if not corps.sol_sous_lui():
            annoncer("Je ne sens pas le sol sous moi. On arrête là.")
            print("[info] Pas de sol au départ : test arrêté", flush=True)
            return 1

        essais = [
            ("avancer de 5 cm", lambda n: drive.go_distance(n, 50, VITESSE, True, True), True, "J'avance de cinq centimètres."),
            ("reculer de 5 cm", lambda n: drive.go_distance(n, 50, VITESSE, False, True), False, "Je recule de cinq centimètres."),
            ("angle -45", lambda n: drive.go_rotate(n, -45, True, VITESSE, True, True), False, "Je tourne vers ma gauche."),
            ("angle +45", lambda n: drive.go_rotate(n, 45, True, VITESSE, True, True), False, "Je tourne vers ma droite."),
        ]
        for nom, commande, devant, annonce in essais:
            annoncer(annonce)
            time.sleep(0.5)
            debut = time.monotonic()
            journal(nom, debut, corps.rouler(commande, devant))
            time.sleep(1)

        annoncer("Soulève-moi et garde-moi en l'air. Je vais refuser de rouler.")
        time.sleep(6)
        debut = time.monotonic()
        journal("refus en l'air", debut, corps.se_deplacer("avancer_10_cm"))

        annoncer("Repose-moi par terre, et mets ta main juste devant moi. Je vais refuser d'avancer.")
        time.sleep(7)
        debut = time.monotonic()
        print(f"[info] Sol : {corps.sol_sous_lui()}, obstacle : {corps.obstacle_devant()} mm", flush=True)
        journal("refus obstacle", debut, corps.se_deplacer("avancer_10_cm"))

        annoncer("Retire ta main. Quand je vais rouler, soulève-moi. Je dois m'arrêter tout seul.")
        time.sleep(3)
        annoncer("J'y vais.")
        debut = time.monotonic()
        journal("soulevé en roulant", debut, corps.rouler(lambda n: drive.go_distance(n, 300, VITESSE, True, True), True))

        annoncer("Repose-moi par terre. Quand je vais rouler, touche-moi au-dessus des yeux. Je dois m'arrêter.")
        time.sleep(6)
        if corps.sol_sous_lui():
            annoncer("J'y vais.")
            debut = time.monotonic()
            journal("toucher en roulant", debut, corps.rouler(lambda n: drive.go_distance(n, 300, VITESSE, False, True), False))
        else:
            print("[info] Pas de sol : essai du toucher sauté", flush=True)
        time.sleep(0.5)
        annoncer("C'est terminé, merci.")
    finally:
        surveiller = False
        if corps:
            corps.fermer()
        touch.dispose()
        if relancer_service:
            subprocess.run(["sudo", "-n", "systemctl", "start", "doly"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
