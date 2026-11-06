#!/usr/bin/env python3
"""
ecran.py

Affiche des images, du texte et les animations d'origine sur les deux écrans de Doly, à la place de ses yeux.

Les animations d'origine sont dans /.doly/images/animations : ce sont des images 240 x 240 de 4 octets par point,
compressées en LZ4 par blocs de 4 Mo. Elles ne sont pas copiées dans ce dépôt, le programme les lit sur le robot.

Le module des yeux ne redessine rien quand il n'anime pas (vérifié sur le robot) : une image écrite reste affichée
jusqu'à la prochaine animation. Corps met donc ses clignements en pause tant que l'écran est occupé.
"""

import ctypes
import struct
import threading
import time

import numpy as np

import doly_lcd as lcd
from doly_vcontent import VContent

DOSSIER_IMAGES = "/.doly/images"
DOSSIER_SEQUENCES = DOSSIER_IMAGES + "/animations"
COTE = 240  # les écrans font 240 x 240 points
OCTETS_PAR_IMAGE = COTE * COTE * 4
IMAGES_PAR_SECONDE = 15
TAILLE_BLOC_LZ4 = 4 * 1024 * 1024

# Police de 5 x 7 points, pour écrire sans charger OpenCV en mémoire. Les accents ne sont pas prévus.
POLICE = {
    "0": "01110 10001 10011 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111", "3": "11111 00010 00100 00010 00001 10001 01110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11100 10010 10001 10001 10001 10010 11100",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 10001 11001 10101 10011 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 10001 01010 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "!": "00100 00100 00100 00100 00100 00000 00100", ":": "00000 00100 00100 00000 00100 00100 00000",
    "-": "00000 00000 00000 11111 00000 00000 00000", " ": "00000 00000 00000 00000 00000 00000 00000",
}

_liblz4 = None


def _decompresser_bloc(bloc, tampon):
    """Décompresse un bloc LZ4 avec la bibliothèque du système, bien plus rapide que du Python."""
    global _liblz4
    if _liblz4 is None:
        _liblz4 = ctypes.CDLL("liblz4.so.1")
    taille = _liblz4.LZ4_decompress_safe(bloc, tampon, len(bloc), len(tampon))
    if taille < 0:
        raise ValueError("bloc LZ4 illisible")
    return tampon.raw[:taille]


def lire_blocs(chemin):
    """Renvoie les blocs décompressés d'une séquence, l'un après l'autre, pour ne pas tout garder en mémoire."""
    with open(chemin, "rb") as fichier:
        donnees = fichier.read()
    if donnees[:4] != b"\x04\x22\x4d\x18":
        raise ValueError(f"{chemin} n'est pas au format attendu")
    drapeaux = donnees[4]
    position = 7 + (8 if drapeaux & 0x08 else 0) + (4 if drapeaux & 0x01 else 0)
    tampon = ctypes.create_string_buffer(TAILLE_BLOC_LZ4)
    while True:
        taille = struct.unpack_from("<I", donnees, position)[0]
        position += 4
        if taille == 0:
            return
        brut = taille & 0x80000000
        taille &= 0x7FFFFFFF
        bloc = donnees[position:position + taille]
        yield bloc if brut else _decompresser_bloc(bloc, tampon)
        position += taille + (4 if drapeaux & 0x10 else 0)


def lire_images(chemin):
    """Renvoie les images d'une séquence, l'une après l'autre (240 x 240, rouge, vert, bleu, opacité)."""
    reste = b""
    for bloc in lire_blocs(chemin):
        donnees = reste + bloc
        fin = len(donnees) - len(donnees) % OCTETS_PAR_IMAGE
        for debut in range(0, fin, OCTETS_PAR_IMAGE):
            yield donnees[debut:debut + OCTETS_PAR_IMAGE]
        reste = donnees[fin:]


def charger_png(chemin):
    """Charge un PNG avec opacité. Renvoie un tableau (hauteur, largeur, 4)."""
    image = VContent.get_image(chemin, True, False)
    if not image.is_ready():
        raise ValueError(f"image illisible : {chemin}")
    return np.frombuffer(image.get_frame_bytes(0), dtype=np.uint8).reshape(image.height, image.width, 4)


def fond_uni(rouge, vert, bleu):
    fond = np.zeros((COTE, COTE, 4), dtype=np.uint8)
    fond[:, :] = (rouge, vert, bleu, 255)
    return fond


def poser(fond, dessus, x=None, y=None):
    """Pose une image sur une autre en tenant compte de l'opacité. Centrée par défaut."""
    hauteur, largeur = dessus.shape[:2]
    x = (fond.shape[1] - largeur) // 2 if x is None else x
    y = (fond.shape[0] - hauteur) // 2 if y is None else y
    sortie = fond.copy()
    zone = sortie[y:y + hauteur, x:x + largeur, :3].astype(np.uint16)
    opacite = dessus[:, :, 3:].astype(np.uint16)
    zone = (dessus[:, :, :3].astype(np.uint16) * opacite + zone * (255 - opacite)) // 255
    sortie[y:y + hauteur, x:x + largeur, :3] = zone.astype(np.uint8)
    return sortie


def ecrire(fond, texte, couleur=(255, 255, 255), centre_y=COTE // 2, largeur_max=200, hauteur_max=130):
    """Écrit un texte en gros points, centré. L'écran est rond : il reste dans le cercle tant qu'il tient dans la limite."""
    colonnes = 6 * len(texte) - 1
    echelle = max(1, min(largeur_max // colonnes, hauteur_max // 7))
    x0 = (COTE - colonnes * echelle) // 2
    y0 = centre_y - 7 * echelle // 2
    sortie = fond.copy()
    marge = 1 if echelle > 3 else 0  # un petit espace entre les points donne l'aspect d'un panneau lumineux
    for rang, lettre in enumerate(texte.upper()):
        for ligne, motif in enumerate(POLICE.get(lettre, POLICE[" "]).split()):
            for colonne, point in enumerate(motif):
                if point == "1":
                    gauche = x0 + (rang * 6 + colonne) * echelle
                    haut = y0 + ligne * echelle
                    sortie[haut:haut + echelle - marge, gauche:gauche + echelle - marge, :3] = couleur
    return sortie


def disque(fond, couleur, rayon=75):
    """Dessine un grand disque au centre d'une image."""
    sortie = fond.copy()
    ys, xs = np.ogrid[:COTE, :COTE]
    masque = (xs - COTE // 2) ** 2 + (ys - COTE // 2) ** 2 <= rayon * rayon
    sortie[masque, 0], sortie[masque, 1], sortie[masque, 2] = couleur
    return sortie


def pour_ecran(image):
    """Convertit une image (240, 240, 4) au format de l'écran."""
    return lcd.to_lcd_buffer(image.tobytes(), True)


class Ecran:
    """Une seule chose affichée à la fois. Corps rend les yeux à leur vie normale quand c'est fini."""

    def __init__(self, corps):
        self.corps = corps
        self.numero = 0
        self.fil = None
        self.verrouille = False  # un jeu garde l'écran entre deux affichages
        self.erreur_signalee = False

    def en_cours(self):
        return self.verrouille or (self.fil is not None and self.fil.is_alive())

    def arreter(self):
        """Arrête ce qui est affiché et rend les yeux à Doly."""
        etait_en_cours = self.en_cours()
        self.numero += 1
        fil = self.fil
        if fil is not None and fil is not threading.current_thread():
            fil.join(0.5)
        self.verrouille = False
        if etait_en_cours:
            self.corps.rendre_ecran()

    def verrouiller(self):
        """Prend l'écran jusqu'à liberer() : pour les jeux, qui affichent image après image."""
        self.arreter()
        self.corps.prendre_ecran()
        self.verrouille = True

    def liberer(self):
        self.verrouille = False
        self.corps.rendre_ecran()

    def afficher(self, gauche, droite=None):
        """Affiche une image déjà convertie par pour_ecran(), sur l'œil gauche et l'œil droit de Doly. Sans droite, la même.

        Sa gauche est à ta droite quand tu le regardes : les animations d'origine le montrent, leurs yeux convergent."""
        for cote, image in ((lcd.LcdSide.Left, gauche), (lcd.LcdSide.Right, gauche if droite is None else droite)):
            rc = lcd.write_lcd(cote, image)
            if rc < 0 and not self.erreur_signalee:  # une seule fois : il y a quinze images par seconde
                self.erreur_signalee = True
                print(f"[ecran] Écriture refusée par l'écran (code {rc})", flush=True)

    def afficher_a_lire(self, premier, second):
        """Affiche deux images dans le sens de la lecture, pour une personne en face de Doly."""
        self.afficher(second, premier)

    def _lancer(self, cible, *arguments):
        self.arreter()
        numero = self.numero = self.numero + 1
        self.corps.prendre_ecran()
        self.fil = threading.Thread(target=self._derouler, args=(cible, numero) + arguments, daemon=True)
        self.fil.start()

    def _derouler(self, cible, numero, *arguments):
        try:
            cible(numero, *arguments)
        except Exception as erreur:  # un affichage raté ne doit jamais faire tomber la conversation
            print(f"[ecran] {type(erreur).__name__} {erreur}", flush=True)
        if numero == self.numero:
            self.corps.rendre_ecran()

    def jouer_sequences(self, noms, duree, fond=None):
        """Joue en boucle des séquences de /.doly/images/animations pendant une durée, sans attendre la fin.

        fond : couleur (r, v, b) sous les séquences qui ont de la transparence."""
        self._lancer(self._jouer_sequences, noms, duree, fond)

    def _images_pretes(self, nom, fond):
        for brut in lire_images(f"{DOSSIER_SEQUENCES}/{nom}.seq"):
            if fond is None:
                yield lcd.to_lcd_buffer(brut, True)
            else:
                image = np.frombuffer(brut, dtype=np.uint8).reshape(COTE, COTE, 4)
                yield pour_ecran(poser(fond, image))

    def _jouer_sequences(self, numero, noms, duree, fond):
        fond_image = None if fond is None else fond_uni(*fond)
        fin = time.monotonic() + duree
        prochaine = time.monotonic()
        while time.monotonic() < fin:
            for nom in noms:
                for image in self._images_pretes(nom, fond_image):
                    if numero != self.numero:
                        return
                    if time.monotonic() >= fin:
                        return
                    self.afficher(image)
                    prochaine = max(prochaine + 1 / IMAGES_PAR_SECONDE, time.monotonic())
                    time.sleep(max(0, prochaine - time.monotonic()))

    def montrer_texte(self, premier, second, duree, couleur=(0, 220, 255)):
        """Écrit deux textes sur les yeux, dans le sens de la lecture, pendant une durée, sans attendre la fin."""
        self._lancer(self._montrer_texte, premier, second, duree, couleur)

    def _montrer_texte(self, numero, premier, second, duree, couleur):
        noir = fond_uni(0, 0, 0)
        self.afficher_a_lire(pour_ecran(ecrire(noir, premier, couleur)), pour_ecran(ecrire(noir, second, couleur)))
        fin = time.monotonic() + duree
        while time.monotonic() < fin and numero == self.numero:
            time.sleep(0.05)

    def compte_a_rebours(self, restant, duree, couleur=(255, 200, 0)):
        """Affiche le temps donné par la fonction restant(), les minutes puis les secondes."""
        self._lancer(self._compte_a_rebours, restant, duree, couleur)

    def _compte_a_rebours(self, numero, restant, duree, couleur):
        noir = fond_uni(0, 0, 0)
        fin = time.monotonic() + duree
        dernier = None
        while time.monotonic() < fin and numero == self.numero:
            secondes = max(0, int(restant() + 0.99))
            if secondes != dernier:
                dernier = secondes
                minutes, reste = divmod(secondes, 60)
                self.afficher_a_lire(pour_ecran(ecrire(noir, f"{minutes:02d}", couleur)),
                                     pour_ecran(ecrire(noir, f"{reste:02d}", couleur)))
            time.sleep(0.05)
