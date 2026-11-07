#!/usr/bin/env python3
"""
arreter_moteurs.py

Arrête les moteurs quand l'appli est morte sans avoir pu le faire elle-même. systemd le lance juste après sa fin
(ExecStopPost, dans doly-francais.service).

Mesuré sur le robot : si le programme qui fait rouler Doly est figé, ou même tué, les chenilles continuent de tourner, car
leur commande reste en place dans le composant qui pilote les moteurs. Elles ne s'arrêtent qu'avec drive.abort().

Quand l'appli se ferme normalement, elle a déjà tout arrêté : ce programme ne touche alors à rien.
"""

import os
import sys
import time

import doly_arm as arm
import doly_drive as drive
import doly_helper as helper

VITESSE_BAISSE = 25  # pour cent : doucement, un bras est peut-être resté en l'air
DELAI_BAISSE = 4  # secondes au maximum, comme pour les autres mouvements de bras


def arreter_les_moteurs():
    helper.read_settings()
    rc, *decalages_imu = helper.get_imu_offsets()
    if rc < 0 or drive.init(*decalages_imu) < 0:
        print("[garde] Roues indisponibles : je ne peux pas les arrêter", flush=True)
    else:
        drive.abort()
        drive.dispose(True)
    if arm.init() < 0:
        print("[garde] Bras indisponibles : je ne peux pas les baisser", flush=True)
    else:
        arm.set_angle(1, arm.ArmSide.Both, VITESSE_BAISSE, 0)
        fin = time.monotonic() + DELAI_BAISSE
        time.sleep(0.05)
        while arm.get_state(arm.ArmSide.Both) == arm.ArmState.Running and time.monotonic() < fin:
            time.sleep(0.05)
        arm.dispose()
    print("[garde] Moteurs arrêtés après la fin anormale de l'appli", flush=True)


def main():
    resultat = os.environ.get("SERVICE_RESULT", "")  # fixé par systemd pour ExecStopPost
    if resultat == "success" and "--toujours" not in sys.argv:
        return 0
    print(f"[garde] Fin anormale de l'appli : {resultat or 'lancement à la main'}", flush=True)
    arreter_les_moteurs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
