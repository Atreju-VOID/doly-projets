#!/usr/bin/env python3
"""
mesurer_base.py

Mesure le courant de la batterie, pour vérifier si on peut savoir que Doly est sur sa base. Il ne fait que lire le INA219 :
rien ne bouge, rien ne sonne, aucun réglage du composant n'est écrit, et il peut tourner pendant que l'appli est lancée.

Usage, sur le robot :
    python3 mesurer_base.py                  # 60 s, une lecture par seconde
    python3 mesurer_base.py --duree 300
"""

import argparse
import statistics
import time

from ina219 import Ina219


def main():
    analyse = argparse.ArgumentParser(description="Mesure le courant de la batterie, sans rien écrire.")
    analyse.add_argument("--duree", type=int, default=60, help="secondes de mesure")
    analyse.add_argument("--silencieux", action="store_true", help="n'écrit que le résumé")
    options = analyse.parse_args()
    capteur = Ina219()
    print(f"Registres : configuration {capteur.configuration():#06x}, calibrage {capteur.calibrage():#06x}", flush=True)
    courants, tensions = [], []
    for seconde in range(options.duree):
        courant, tension = capteur.courant_mv(), capteur.tension_v()
        courants.append(courant)
        tensions.append(tension)
        if not options.silencieux:
            print(f"{seconde:4d} s  shunt {courant:+7.2f} mV  batterie {tension:.3f} V", flush=True)
        time.sleep(1)
    print(f"Résumé sur {len(courants)} s : shunt moyen {statistics.mean(courants):+.2f} mV "
          f"(de {min(courants):+.2f} à {max(courants):+.2f}), batterie {statistics.mean(tensions):.3f} V")
    capteur.fermer()


if __name__ == "__main__":
    main()
