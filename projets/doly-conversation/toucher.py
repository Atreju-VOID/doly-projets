#!/usr/bin/env python3
"""
toucher.py

Les capteurs tactiles au-dessus des yeux de Doly.

Mesuré sur le robot : le SDK lit les capteurs toutes les 50 ms environ, et une tape dure de 0,05 à 0,46 s. Quand Doly écoute,
le programme ne regarde les capteurs que toutes les 100 ms : il raterait les tapes les plus brèves. Une tape signalée par le
SDK compte donc encore un court instant, le temps que le programme la voie.
"""

import time

import doly_touch as touch

DUREE_D_UNE_TAPE = 0.15  # secondes pendant lesquelles un appui reste visible, même si le doigt est déjà levé

_dernier_evenement = None
_dernier_appui = None
_appui_a_gauche = False


def _au_toucher(cote, etat):
    # Appelé par un fil interne du SDK.
    global _dernier_evenement, _dernier_appui, _appui_a_gauche
    _dernier_evenement = time.monotonic()
    if etat == touch.TouchState.Down:
        _dernier_appui = _dernier_evenement
        _appui_a_gauche = cote == touch.TouchSide.Left


def demarrer():
    """À appeler juste après touch.init()."""
    touch.on_touch(_au_toucher)


def arreter():
    touch.clear_listeners()


def doigt_pose():
    return touch.is_touched(touch.TouchSide.Left) or touch.is_touched(touch.TouchSide.Right)


def _appui_recent():
    return _dernier_appui is not None and time.monotonic() - _dernier_appui < DUREE_D_UNE_TAPE


def capteur_touche():
    """Vrai si un doigt est posé, ou si une tape vient d'avoir lieu."""
    return doigt_pose() or _appui_recent()


def touche_a_gauche():
    """Vrai si le capteur gauche est touché, ou s'il vient de l'être."""
    return touch.is_touched(touch.TouchSide.Left) or (_appui_a_gauche and _appui_recent())


def dernier_evenement():
    """L'instant du dernier contact posé ou levé, ou None s'il n'y en a pas encore eu."""
    return _dernier_evenement
