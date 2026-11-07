#!/usr/bin/env python3
"""
base.py

Sait si Doly est sur sa base, d'après le courant de sa batterie, lu sur le INA219 (voir ina219.py). Le SDK ne le dit pas.

Mesuré sur le robot, en moyenne sur 15 s (tension du shunt) :
- hors de sa base : de -4 à -9 mV, à l'écoute, en parlant ou en bougeant ; -4,7 mV micro coupé ; -3,5 mV en dormant ;
- sur sa base : de -0,2 à 0 mV, batterie pleine ; de +1 à +2,7 mV juste après une petite décharge ; +5 mV à 83 % et +4,2 mV à 27 %.

Le pourcentage du SDK suit la tension : il bondit sur la base (de 83 à 96 %) et chute sous l'effort. Seul le courant dit si la batterie charge.

La lecture n'est jamais une certitude : si elle échoue, si elle n'a pas encore assez de mesures ou si elle tombe entre les
deux seuils, la réponse est « je ne sais pas » (None), et l'appli garde son comportement le plus prudent.
"""

import collections
import threading
import time

from ina219 import Ina219

FENETRE = 20  # lectures, une par seconde : un pic de consommation ne doit pas décider
PERIODE = 1.0  # secondes
SEUIL_SUR_BASE = -1.5  # mV : au-dessus, il est sur sa base
SEUIL_HORS_BASE = -2.5  # mV : en dessous, il n'y est pas. Entre les deux, on ne sait pas.
SEUIL_CHARGE = 0.5  # mV : au-dessus, la batterie charge vraiment. Pleine, sur sa base, elle reste autour de 0.
DELAI_MAX = 5  # secondes sans nouvelle lecture avant de dire qu'on ne sait plus


class Base:
    def __init__(self, creer_capteur=Ina219, horloge=time.monotonic):
        self.creer_capteur = creer_capteur
        self.horloge = horloge
        self.lectures = collections.deque(maxlen=FENETRE)
        self.derniere = None
        self.erreur_signalee = False

    def noter(self, valeur):
        """Une nouvelle lecture, ou None si elle a échoué : on repart alors de zéro, pour ne pas décider sur du vieux."""
        if valeur is None:
            self.lectures.clear()
        else:
            self.lectures.append(valeur)
            self.derniere = self.horloge()

    def moyenne(self):
        lectures = list(self.lectures)  # une copie : le fil de lecture continue de remplir
        if len(lectures) < FENETRE or self.derniere is None or self.horloge() - self.derniere > DELAI_MAX:
            return None
        return sum(lectures) / len(lectures)

    def sur_base(self):
        """True s'il est sur sa base, False s'il n'y est pas, None si on ne sait pas."""
        moyenne = self.moyenne()
        if moyenne is None or SEUIL_HORS_BASE < moyenne < SEUIL_SUR_BASE:
            return None
        return moyenne >= SEUIL_SUR_BASE

    def en_charge(self):
        """Vrai seulement si la batterie charge vraiment. En cas de doute, faux : il s'éteindra à temps."""
        moyenne = self.moyenne()
        return moyenne is not None and moyenne >= SEUIL_CHARGE

    def pour_claude(self):
        """Une phrase pour Claude, ou None si on ne sait pas : mieux vaut ne rien lui dire que de l'induire en erreur."""
        etat = self.sur_base()
        if etat is None:
            return None
        if not etat:
            return "Tu n'es pas sur ta base de charge."
        return "Tu es sur ta base de charge, et ta batterie charge." if self.en_charge() else "Tu es sur ta base de charge."

    def pour_le_journal(self):
        moyenne = self.moyenne()
        if moyenne is None:
            return "base inconnue"
        etat = self.sur_base()
        texte = "base inconnue" if etat is None else "sur sa base" if etat else "hors de sa base"
        return f"{texte}, {moyenne:+.2f} mV"

    def _boucle(self):
        capteur = None
        while True:
            try:
                if capteur is None:
                    capteur = self.creer_capteur()
                self.noter(capteur.courant_mv())
                self.erreur_signalee = False
            except OSError as erreur:
                self.noter(None)
                capteur = None
                if not self.erreur_signalee:
                    self.erreur_signalee = True
                    print(f"[info] Courant de la batterie illisible, je fais comme si je ne savais pas où je suis : {erreur}", flush=True)
            time.sleep(PERIODE)

    def demarrer(self):
        threading.Thread(target=self._boucle, daemon=True).start()
