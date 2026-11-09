#!/usr/bin/env python3
"""
faux_materiel.py

Remplace les modules matériels de Doly par des imitations, pour vérifier la logique sans rien faire bouger ni sonner.
À importer avant corps.py. Les imitations notent les commandes reçues dans `journal` et se pilotent depuis les essais.

Le paramètre vrais de installer() laisse certains modules réels, par exemple les yeux et les LED pour un essai visible.
Les bras et les roues ne devraient jamais en faire partie sans personne à côté du robot.
"""

import enum
import sys
import threading
import time
import types

journal = []  # (module, fonction, arguments)


def noter(module, fonction, *arguments):
    journal.append((module, fonction, arguments))


def appels(module, fonction=None):
    """Les commandes reçues par une imitation."""
    return [e for e in journal if e[0] == module and (fonction is None or e[1] == fonction)]


class Reglages:
    """Ce que les imitations répondent : les essais le changent pour simuler le monde réel."""
    duree_bras = 0.1
    duree_roues = 0.05
    duree_yeux = 0.1
    touche_gauche = False
    touche_droite = False
    distance_gauche = None
    distance_droite = None
    sol = True  # les 4 capteurs de vide voient le sol
    batterie = 80
    ecrans = {}  # dernière image écrite sur chaque écran


def _module(nom, **elements):
    module = types.ModuleType(nom)
    for cle, valeur in elements.items():
        setattr(module, cle, valeur)
    sys.modules[nom] = module
    return module


def _sans_effet(module, fonction, retour=0):
    def appel(*arguments, **options):
        noter(module, fonction, *arguments)
        return retour
    return appel


def _enum(nom, *valeurs):
    return enum.Enum(nom, valeurs, start=0)


def _faux_bras():
    ArmSide = _enum("ArmSide", "Both", "Left", "Right")
    ArmState = _enum("ArmState", "Running", "Completed", "Error")
    fin = {"mouvement": 0.0}

    def set_angle(numero, cote, vitesse, angle, frein=False):
        noter("arm", "set_angle", cote.name, vitesse, angle, frein)
        fin["mouvement"] = time.monotonic() + Reglages.duree_bras
        return 0

    def abort(cote):
        noter("arm", "abort", cote.name)
        fin["mouvement"] = 0.0

    _module("doly_arm", ArmSide=ArmSide, ArmState=ArmState, init=_sans_effet("arm", "init"),
            dispose=_sans_effet("arm", "dispose"), set_angle=set_angle, abort=abort,
            get_state=lambda cote: ArmState.Running if time.monotonic() < fin["mouvement"] else ArmState.Completed)


def _fausses_roues():
    DriveState = _enum("DriveState", "Running", "Completed", "Error")
    fin = {"mouvement": 0.0}

    def go_distance(numero, millimetres, vitesse, en_avant, frein=False, acceleration=0):
        noter("drive", "go_distance", millimetres, vitesse, en_avant, frein, acceleration)
        fin["mouvement"] = time.monotonic() + Reglages.duree_roues
        return True

    def go_rotate(numero, angle, centre, vitesse, en_avant, frein=False, acceleration=0):
        noter("drive", "go_rotate", angle, centre, vitesse, en_avant, frein, acceleration)
        fin["mouvement"] = time.monotonic() + Reglages.duree_roues
        return True

    def abort():
        noter("drive", "abort")
        fin["mouvement"] = 0.0

    _module("doly_drive", DriveState=DriveState, init=_sans_effet("drive", "init"), dispose=_sans_effet("drive", "dispose"),
            go_distance=go_distance, go_rotate=go_rotate, abort=abort,
            get_state=lambda: DriveState.Running if time.monotonic() < fin["mouvement"] else DriveState.Completed)


def _couleurs():
    ColorCode = _enum("ColorCode", "Black", "White", "Gray", "Salmon", "Red", "DarkRed", "Pink", "Orange", "Gold", "Yellow",
                      "Purple", "Magenta", "Lime", "Green", "DarkGreen", "Cyan", "SkyBlue", "Blue", "DarkBlue", "Brown")

    class Color:
        @staticmethod
        def from_code(code):
            return code

        @staticmethod
        def hex_to_rgb(valeur):
            return valeur

    _module("doly_color", ColorCode=ColorCode, Color=Color)


def _faux_yeux():
    fin = {"animation": 0.0}

    class Expressions:
        def __getattr__(self, nom):
            return nom.replace("_", " ")

    def set_animation(numero, nom):
        noter("eye", "set_animation", nom)
        fin["animation"] = time.monotonic() + Reglages.duree_yeux
        return 0

    def abort():
        noter("eye", "abort")
        fin["animation"] = 0.0

    _module("doly_eye", expressions=Expressions(), EyeSide=_enum("EyeSide", "Both", "Left", "Right"),
            IrisShape=_enum("IrisShape", "Classic", "Modern", "Space", "Orbit", "Glow", "Digi"),
            init=_sans_effet("eye", "init"), dispose=_sans_effet("eye", "dispose"), abort=abort, set_animation=set_animation,
            is_animating=lambda: time.monotonic() < fin["animation"], set_iris=_sans_effet("eye", "set_iris"),
            set_background=_sans_effet("eye", "set_background"),
            set_background_image=_sans_effet("eye", "set_background_image"))


def _faux_ecrans():
    LcdSide = _enum("LcdSide", "Left", "Right")

    def write_lcd(cote, tampon):
        Reglages.ecrans[cote.name] = tampon
        noter("lcd", "write_lcd", cote.name)
        return 0

    # Les images restent en 4 octets par point : les essais peuvent les enregistrer pour les regarder.
    _module("doly_lcd", LcdSide=LcdSide, write_lcd=write_lcd, to_lcd_buffer=lambda tampon, rgba=False: bytes(tampon),
            set_brightness=_sans_effet("lcd", "set_brightness"))


def _fausses_led():
    class LedActivity:
        mainColor = None
        fadeColor = None
        fade_time = 0

    _module("doly_led", LedSide=_enum("LedSide", "Both", "Left", "Right"), LedActivity=LedActivity,
            init=_sans_effet("led", "init"), dispose=_sans_effet("led", "dispose"),
            process_activity=_sans_effet("led", "process_activity"))


def _faux_capteurs():
    GpioState = _enum("GpioState", "Low", "High")
    TofSide = _enum("TofSide", "Left", "Right")
    TofError = _enum("TofError", "NoError", "MaxConvergence")
    TouchSide = _enum("TouchSide", "Both", "Left", "Right")

    class Valeur:
        def __init__(self, **champs):
            self.__dict__.update(champs)

    def lire_distance():
        donnees = []
        for cote, distance in ((TofSide.Left, Reglages.distance_gauche), (TofSide.Right, Reglages.distance_droite)):
            donnees.append(Valeur(side=cote, range_mm=-1 if distance is None else distance,
                                  error=TofError.MaxConvergence if distance is None else TofError.NoError))
        return donnees

    def is_touched(cote):
        return Reglages.touche_gauche if cote == TouchSide.Left else Reglages.touche_droite

    _module("doly_edge", GpioState=GpioState, init=_sans_effet("edge", "init"), dispose=_sans_effet("edge", "dispose"),
            get_sensors=lambda: [Valeur(state=GpioState.High if Reglages.sol else GpioState.Low) for _ in range(4)],
            GapDirection=_enum("GapDirection", "Front", "Front_Left", "Front_Right", "Back", "Back_Left", "Back_Right",
                               "Left", "Right", "Cross_Left", "Cross_Right", "All"),
            on_gap_detect=lambda fonction: None, clear_listeners=lambda: None)
    _module("doly_tof", TofSide=TofSide, TofError=TofError, init=_sans_effet("tof", "init"),
            dispose=_sans_effet("tof", "dispose"), get_sensors_data=lire_distance)
    _module("doly_touch", TouchSide=TouchSide, TouchState=_enum("TouchState", "Up", "Down"), init=_sans_effet("touch", "init"),
            dispose=_sans_effet("touch", "dispose"), is_touched=is_touched, on_touch=lambda fonction: None,
            clear_listeners=lambda: None)
    Reglages.ImuGesture = _enum("ImuGesture", "Undefined", "Move", "LongShake", "ShortShake", "Vibrate", "VibrateExtreme",
                                "ShockLight", "ShockMedium", "ShockHard", "ShockExtreme")
    Reglages.GestureDirection = _enum("GestureDirection", "Left", "Right", "Up", "Down", "Front", "Back")
    Reglages.au_geste = None

    def on_gesture(fonction):
        Reglages.au_geste = fonction

    _module("doly_imu", ImuGesture=Reglages.ImuGesture, GestureDirection=Reglages.GestureDirection, on_gesture=on_gesture,
            clear_listeners=lambda: None)
    _module("doly_battery", init=_sans_effet("battery", "init"), dispose=_sans_effet("battery", "dispose"),
            get_capacity=lambda: Reglages.batterie)


def _divers():
    _module("doly_fan", init=_sans_effet("fan", "init"), dispose=_sans_effet("fan", "dispose"))
    _module("doly_helper", read_settings=_sans_effet("helper", "read_settings"),
            get_imu_offsets=lambda: (0, 0, 0, 0, 0, 0, 0), stop_doly_service=_sans_effet("helper", "stop", 1))


IMITATIONS = {
    "bras": _faux_bras, "roues": _fausses_roues, "couleurs": _couleurs, "yeux": _faux_yeux, "ecrans": _faux_ecrans,
    "led": _fausses_led, "capteurs": _faux_capteurs, "divers": _divers,
}


def installer(vrais=()):
    """Installe les imitations, sauf celles de la liste vrais, par exemple ("yeux", "ecrans", "led", "couleurs")."""
    for nom, imitation in IMITATIONS.items():
        if nom not in vrais:
            imitation()


class FausseVoix:
    """Fait comme la voix de Doly, sans aucun son. Les phrases et les sons sont notés."""

    def __init__(self, duree_phrase=0.05, duree_son=0.02):
        self.duree_phrase = duree_phrase
        self.duree_son = duree_son
        self.phrases = []
        self.sons = []
        self.fin = 0.0
        self.generation = 0
        self.premier_son = None
        self.son_d_attente = "attente.wav"  # le petit son joué quand Claude tarde

    def _occuper(self, duree):
        self.fin = max(self.fin, time.monotonic()) + duree

    def dire(self, phrase, generation=None):
        if phrase and (generation is None or generation == self.generation):
            self.phrases.append(phrase)
            self.premier_son = self.premier_son or time.monotonic()
            self._occuper(self.duree_phrase)

    def jouer_son(self, chemin):
        self.sons.append(chemin)
        fini = threading.Event()
        self._occuper(self.duree_son)
        threading.Timer(max(0, self.fin - time.monotonic()), fini.set).start()
        return fini

    def parle(self):
        return time.monotonic() < self.fin

    def attendre_fin(self):
        while self.parle():
            time.sleep(0.005)

    def interrompre(self):
        self.generation += 1
        self.fin = 0.0

    def jouer_bip(self):
        pass

    def fermer(self):
        pass
