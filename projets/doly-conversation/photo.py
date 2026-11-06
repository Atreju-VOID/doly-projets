#!/usr/bin/env python3
"""
photo.py

Prend une photo avec la caméra de Doly. Elle reste sur le robot, dans le même dossier que sa personnalité d'origine.

La caméra et OpenCV demandent environ 150 Mo de mémoire : la photo se prend donc dans un programme à part, lancé par
prendre_photo(). Toute la mémoire est rendue à la fin, et un blocage de la caméra ne fige pas la conversation.
Une photo pèse environ 2 Mo.

Usage, sur le robot :
    ~/doly-env/bin/python photo.py /tmp/essai.jpg

Inspiré de l'exemple officiel SDK/examples/python/Camera/example.py (dépôt robotdoly/DOLY-DIY, licence CC BY-NC-SA 4.0).
"""

import os
import subprocess
import sys
import time

DOSSIER_PHOTOS = "/.doly/photos"
# Tout le capteur, pour profiter du grand angle : en 1920 x 1080, la taille de sa personnalité d'origine, le capteur ne
# lit que le centre de l'image.
LARGEUR = 3280
HAUTEUR = 2464
QUALITE_JPEG = 90
REGLAGE_EXPOSITION = 0.3  # secondes laissées à la caméra pour s'adapter à la lumière
DELAI_MAX = 20  # secondes au maximum pour prendre une photo


def prendre_photo(dossier=DOSSIER_PHOTOS):
    """Lance la prise de vue. Renvoie (chemin de la photo, None) ou (None, raison de l'échec)."""
    chemin = os.path.join(dossier, time.strftime("%Y%m%d_%H%M%S") + ".jpg")
    try:
        resultat = subprocess.run([sys.executable, os.path.abspath(__file__), chemin], capture_output=True, text=True,
                                  timeout=DELAI_MAX)
    except subprocess.TimeoutExpired:
        return None, "la caméra ne répond pas"
    if resultat.returncode != 0:
        print(f"[photo] code {resultat.returncode} : {resultat.stdout.strip()[-200:]}", flush=True)
        return None, "la caméra n'a pas réussi"
    return chemin, None


def main():
    import cv2
    import doly_camera

    if len(sys.argv) != 2:
        print("Usage : photo.py chemin.jpg")
        return 2
    camera = doly_camera.PiCamera()
    camera.options.photo_width = LARGEUR
    camera.options.photo_height = HAUTEUR
    camera.options.verbose = False
    if not camera.start_photo():
        print("Caméra indisponible")
        return 1
    try:
        time.sleep(REGLAGE_EXPOSITION)
        camera.capture_photo()  # la première image est souvent trop sombre : on garde la suivante
        image = camera.capture_photo()
    finally:
        camera.stop_photo()
    if image is None:
        print("Lecture de l'image impossible")
        return 1
    if not cv2.imwrite(sys.argv[1], image, [cv2.IMWRITE_JPEG_QUALITY, QUALITE_JPEG]):
        print("Écriture de la photo impossible")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
