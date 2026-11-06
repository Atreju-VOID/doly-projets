#!/usr/bin/env python3
"""
animations.py

Rejoue les animations d'origine de Doly, rangées sur le robot dans /.doly/config/animations.

Ces fichiers décrivent une suite de blocs : yeux, sons, LED, bras et roues. Ils ne sont pas copiés dans ce dépôt :
le programme les lit sur le robot. Si l'un d'eux disparaît après une mise à jour, l'animation est simplement sautée.

Chaque bloc démarre soit tout de suite, soit quand le bloc précédent est fini (le champ « start » vaut 1), comme dans
la programmation par blocs de Doly (https://doly.ai/blockly/).

Les roues ne tournent que si on le demande, et toujours à travers Corps.rouler, qui surveille le vide, les obstacles,
les touchers et la durée. Les angles et les vitesses des bras sont limités.
"""

import glob
import os
import random
import threading
import time
import xml.etree.ElementTree as ET

import doly_arm as arm
import doly_drive as drive
import doly_eye as eye
import doly_led as led
from doly_color import Color
from doly_vcontent import VContent

DOSSIER_ANIMATIONS = "/.doly/config/animations"
DOSSIER_SONS = "/.doly/sounds"
SOUS_DOSSIERS_SONS = {"DOLY": "sound", "SFX": "sfx", "MUSIC": "music", "WUW": "wuw", "ANIMAL": "animal"}
ESPACE_DE_NOMS = "{https://developers.google.com/blockly/xml}"

ANGLE_MAX = 150  # limite volontairement plus basse que le maximum du SDK (240), et que certaines animations d'origine
VITESSE_BRAS = 30  # en pourcentage, quand le fichier n'en donne pas
VITESSE_BRAS_MAX = 60  # les animations d'origine montent à 100
VITESSE_ROUES = 20  # en pourcentage, quand le fichier n'en donne pas
VITESSE_ROUES_MIN = 10  # les animations d'origine descendent à 1. Essayé au sol avec les 6 scènes qui roulent : il bouge bien
VITESSE_ROUES_MAX = 30
DISTANCE_MAX = 200  # mm pour un seul bloc de déplacement
REPETITIONS_MAX = 20
ATTENTE_MAX_BLOC = 15  # secondes au maximum pour attendre la fin d'un bloc
ATTENTE_MAX_SON = 40  # un son attend que Doly ait fini de parler, et une musique dure 13 s

COTES_BRAS = {"0": arm.ArmSide.Both, "1": arm.ArmSide.Left, "2": arm.ArmSide.Right}
COTES_LED = {"0": led.LedSide.Both, "1": led.LedSide.Left, "2": led.LedSide.Right}
BLOCS_DE_ROUES = {"drive_distance", "drive_rotate_left", "drive_rotate_right"}


class Bloc:
    """Un bloc d'animation. immediat : il démarre sans attendre la fin du bloc précédent."""

    def __init__(self, type_de_bloc, champs=None, enfants=None, immediat=None):
        self.type = type_de_bloc
        self.champs = champs or {}
        self.enfants = enfants or {}
        self.immediat = self.champs.get("start", "0") == "0" if immediat is None else immediat

    def __repr__(self):
        return f"Bloc({self.type}, {self.champs})"


def _lire_bloc(element):
    champs = {champ.get("name"): champ.text for champ in element.findall(ESPACE_DE_NOMS + "field")}
    enfants = {
        suite.get("name"): [_lire_bloc(e) for e in suite.findall(ESPACE_DE_NOMS + "block")]
        for suite in element.findall(ESPACE_DE_NOMS + "statement")
    }
    return Bloc(element.get("type"), champs, enfants)


def charger(nom, dossier=DOSSIER_ANIMATIONS):
    """Lit une animation d'origine. Renvoie sa liste de blocs, ou None si le fichier est absent ou illisible."""
    try:
        racine = ET.parse(os.path.join(dossier, nom + ".xml")).getroot()
    except (OSError, ET.ParseError) as erreur:
        print(f"[animation] {nom} illisible : {erreur}", flush=True)
        return None
    return [_lire_bloc(e) for e in racine.findall(ESPACE_DE_NOMS + "block") if e.get("type") != "start_animation"]


def chemin_son(famille, nom):
    """Chemin d'un son d'origine, par exemple ("DOLY", "ANGRY (12)") ou ("SFX", "CAMERA CLICK")."""
    return os.path.join(DOSSIER_SONS, SOUS_DOSSIERS_SONS[famille], nom.lower() + ".wav")


def sons_de_la_famille(prefixe, dossier="sound"):
    """Noms des sons d'une même famille, par exemple "ATTACK" donne ["ATTACK (1)", "ATTACK (2)", ...]."""
    motif = os.path.join(DOSSIER_SONS, dossier, glob.escape(prefixe.lower()) + "*.wav")
    return [os.path.basename(f)[:-4].upper() for f in glob.glob(motif)]


# Petites animations écrites ici, avec les mêmes blocs que celles d'origine.


def yeux(nom, immediat=False):
    return Bloc("eye_animations", {"animation": nom}, immediat=immediat)


def son(famille, nom, immediat=True):
    return Bloc("sound", {"type_id": famille, "name": nom}, immediat=immediat)


def son_au_hasard(prefixe, immediat=True):
    """Un son pris au hasard dans sa famille. Sans son disponible, le bloc ne fait rien."""
    noms = sons_de_la_famille(prefixe)
    return son("DOLY", random.choice(noms), immediat) if noms else Bloc("rien", immediat=True)


def bras(cote, angle, vitesse=VITESSE_BRAS, immediat=True):
    return Bloc("arm_set_angle", {"side": cote, "angle": str(angle), "speed": str(vitesse)}, immediat=immediat)


def attente(millisecondes, immediat=False):
    return Bloc("delay_ms", {"delay_ms": str(millisecondes)}, immediat=immediat)


def couleur(valeur, immediat=True):
    return Bloc("led", {"color_main": valeur, "side": "0"}, immediat=immediat)


class Lecture:
    """Le déroulement d'une animation : elle s'arrête dès qu'une autre lecture prend sa place."""

    def __init__(self, animateur, numero, roues):
        self.animateur = animateur
        self.numero = numero
        self.roues = roues
        self.incident = None  # raison pour laquelle les roues se sont arrêtées
        self.fils = []

    def annulee(self):
        return self.numero != self.animateur.numero

    def dormir(self, secondes):
        """Attend sans bloquer l'annulation. Renvoie False si la lecture a été annulée pendant ce temps."""
        fin = time.monotonic() + secondes
        while time.monotonic() < fin:
            if self.annulee():
                return False
            time.sleep(min(0.02, max(0.001, fin - time.monotonic())))
        return not self.annulee()

    def attendre(self, fini, delai=ATTENTE_MAX_BLOC):
        fin = time.monotonic() + delai
        while not fini() and time.monotonic() < fin:
            if self.annulee():
                return
            time.sleep(0.01)

    def lancer_fil(self, cible, *arguments):
        fil = threading.Thread(target=cible, args=arguments, daemon=True)
        self.fils.append(fil)
        fil.start()
        return fil


class Animateur:
    """Joue une seule animation à la fois. Une nouvelle remplace la précédente."""

    def __init__(self, corps):
        self.corps = corps
        self.jouer_son = None  # branché sur la voix : renvoie un événement signalé quand le son est fini
        self.numero = 0
        self.fil = None
        self.verrou_roues = threading.Lock()
        self.dernier_incident = None

    def en_cours(self):
        return self.fil is not None and self.fil.is_alive()

    def attendre_fin(self, delai=60):
        fin = time.monotonic() + delai
        while self.en_cours() and time.monotonic() < fin:
            time.sleep(0.02)

    def arreter(self):
        """Annule l'animation en cours, sans toucher au matériel : c'est Corps.arreter qui arrête les moteurs."""
        self.numero += 1
        fil = self.fil
        if fil is not None and fil is not threading.current_thread():
            fil.join(0.5)

    def jouer(self, nom, roues=False):
        """Lance une animation d'origine sans attendre sa fin. Renvoie False si elle n'existe pas."""
        blocs = charger(nom)
        return blocs is not None and self.jouer_blocs(blocs, roues, nom)

    def jouer_blocs(self, blocs, roues=False, nom="?"):
        self.arreter()
        numero = self.numero = self.numero + 1
        self.dernier_incident = None
        self.fil = threading.Thread(target=self._derouler, args=(blocs, numero, roues, nom), daemon=True)
        self.fil.start()
        return True

    def _derouler(self, blocs, numero, roues, nom):
        lecture = Lecture(self, numero, roues)
        try:
            self._sequence(blocs, lecture)
            for fil in lecture.fils:
                fil.join(ATTENTE_MAX_SON)
        except Exception as erreur:  # une animation ratée ne doit jamais faire tomber la conversation
            print(f"[animation] {nom} : {type(erreur).__name__} {erreur}", flush=True)
        self.dernier_incident = lecture.incident
        if not lecture.annulee():
            self.corps.fin_animation()

    def _sequence(self, blocs, lecture):
        """Déroule une suite de blocs, puis attend qu'ils soient tous finis."""
        en_cours = []
        precedent = None
        for bloc in blocs:
            if lecture.annulee():
                return
            if precedent is not None and not bloc.immediat:
                lecture.attendre(*precedent)
            precedent = self._lancer(bloc, lecture)
            en_cours.append(precedent)
        for tache in en_cours:
            lecture.attendre(*tache)

    def _lancer(self, bloc, lecture):
        """Démarre un bloc. Renvoie (fonction qui dit s'il est fini, attente maximale)."""
        fonction = {
            "eye_animations": self._yeux,
            "sound": self._son,
            "delay_ms": self._attente,
            "arm_set_angle": self._bras,
            "led": self._led,
            "led_animation": self._led_animation,
            "repeat": self._repeter,
            "eye_background": self._fond_des_yeux,
            "drive_distance": self._roues,
            "drive_rotate_left": self._roues,
            "drive_rotate_right": self._roues,
        }.get(bloc.type)
        tache = fonction(bloc, lecture) if fonction else (lambda: True, 0)
        suite = bloc.enfants.get("complete_statement")
        if suite:
            lecture.lancer_fil(self._suite_apres, tache, suite, lecture)
        return tache

    def _suite_apres(self, tache, suite, lecture):
        lecture.attendre(*tache)
        self._sequence(suite, lecture)

    def _yeux(self, bloc, lecture):
        if eye.set_animation(self.corps.suivant(), bloc.champs["animation"]) < 0:
            return lambda: True, 0
        debut = time.monotonic()
        return lambda: time.monotonic() - debut > 0.05 and not eye.is_animating(), ATTENTE_MAX_BLOC

    def _son(self, bloc, lecture):
        chemin = chemin_son(bloc.champs["type_id"], bloc.champs["name"])
        if not self.jouer_son or not os.path.exists(chemin):
            return lambda: True, 0
        return self.jouer_son(chemin).is_set, ATTENTE_MAX_SON

    def _attente(self, bloc, lecture):
        fin = time.monotonic() + int(bloc.champs["delay_ms"]) / 1000
        return lambda: time.monotonic() >= fin, ATTENTE_MAX_BLOC

    def _bras(self, bloc, lecture):
        cote = COTES_BRAS[bloc.champs.get("side", "0")]
        angle = min(max(int(bloc.champs["angle"]), 0), ANGLE_MAX)
        vitesse = min(max(int(bloc.champs.get("speed") or VITESSE_BRAS), 1), VITESSE_BRAS_MAX)
        frein = bloc.champs.get("brake", "0") == "1"
        if arm.set_angle(self.corps.suivant(), cote, vitesse, angle, frein) < 0:
            return lambda: True, 0
        self.corps.noter_bras(cote, angle)
        debut = time.monotonic()
        return lambda: time.monotonic() - debut > 0.05 and arm.get_state(cote) != arm.ArmState.Running, ATTENTE_MAX_BLOC

    def _une_couleur(self, cote, principale, estompee=None, duree_ms=0):
        activite = led.LedActivity()
        activite.mainColor = Color.hex_to_rgb(principale)
        if estompee:
            activite.fadeColor = Color.hex_to_rgb(estompee)
            activite.fade_time = duree_ms
        else:
            activite.fade_time = 0
        led.process_activity(self.corps.suivant(), cote, activite)

    def _led(self, bloc, lecture):
        self._une_couleur(COTES_LED[bloc.champs.get("side", "0")], bloc.champs["color_main"])
        return lambda: True, 0

    def _led_animation(self, bloc, lecture):
        fils = []
        for nom, cote in (("led_left", led.LedSide.Left), ("led_right", led.LedSide.Right)):
            fils.append(lecture.lancer_fil(self._suite_de_couleurs, bloc.enfants.get(nom, []), cote, lecture))
        return lambda: not any(fil.is_alive() for fil in fils), ATTENTE_MAX_BLOC

    def _suite_de_couleurs(self, etapes, cote, lecture):
        for etape in etapes:
            duree = int(etape.champs.get("led_time", 0))
            self._une_couleur(cote, etape.champs["color_main"], etape.champs.get("color_fade"), duree)
            if not lecture.dormir(duree / 1000):
                return

    def _repeter(self, bloc, lecture):
        fois = min(int(bloc.champs.get("times", 1)), REPETITIONS_MAX)
        fil = lecture.lancer_fil(self._boucle, bloc.enfants.get("repeat_statement", []), fois, lecture)
        return lambda: not fil.is_alive(), ATTENTE_MAX_SON

    def _boucle(self, blocs, fois, lecture):
        for _ in range(fois):
            if lecture.annulee():
                return
            self._sequence(blocs, lecture)

    def _fond_des_yeux(self, bloc, lecture):
        if bloc.champs.get("type") == "IMAGE":
            # Essayé sur le robot : le fond des yeux n'accepte que du rouge, vert, bleu sans opacité, converti sur 12 bits.
            image = VContent.get_image(f"/.doly/images/background/{bloc.champs['style'].lower()}.png", False, True)
            if image.is_ready():
                self.corps.poser_fond_des_yeux(image)
        return lambda: True, 0

    def _roues(self, bloc, lecture):
        if not lecture.roues or lecture.incident:
            return lambda: True, 0
        fil = lecture.lancer_fil(self._rouler, bloc, lecture)
        return lambda: not fil.is_alive(), ATTENTE_MAX_BLOC

    def _rouler(self, bloc, lecture):
        champs = bloc.champs
        vitesse = min(max(int(champs.get("speed") or VITESSE_ROUES), VITESSE_ROUES_MIN), VITESSE_ROUES_MAX)
        frein = champs.get("brake", "0") == "1"
        acceleration = int(champs.get("accel") or 0)
        en_avant = champs.get("direction", "1") != "0"
        if bloc.type == "drive_distance":
            distance = min(int(champs["distance"]), DISTANCE_MAX)
            commande = lambda n: drive.go_distance(n, distance, vitesse, en_avant, frein, acceleration)
            surveiller_devant = en_avant
        else:
            # Testé au sol : un angle négatif le fait tourner vers sa gauche.
            angle = float(champs["driveRotate"]) * (-1 if bloc.type == "drive_rotate_left" else 1)
            depuis_le_centre = champs.get("isCenter", "TRUE") == "TRUE"
            commande = lambda n: drive.go_rotate(n, angle, depuis_le_centre, vitesse, en_avant, frein, acceleration)
            surveiller_devant = False
        # Le SDK ne fait qu'un déplacement à la fois : ceux qui démarrent ensemble passent l'un après l'autre.
        with self.verrou_roues:
            if lecture.annulee() or lecture.incident:
                return
            message = self.corps.rouler(commande, surveiller_devant)
        if message != "Déplacement terminé.":
            lecture.incident = message
