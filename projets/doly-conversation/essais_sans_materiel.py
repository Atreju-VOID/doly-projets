#!/usr/bin/env python3
"""
essais_sans_materiel.py

Vérifie la logique des fonctions de Doly avec des imitations du matériel (faux_materiel.py) : rien ne bouge, rien ne
sonne et rien ne part sur Internet. Ces essais lisent les animations d'origine, il faut donc les lancer sur le robot.

Ils ne remplacent pas le test guidé (tester_fonctions.py) : ils ne disent rien des vrais capteurs, des sons ni de l'aspect.

Usage, sur le robot :
    ~/doly-env/bin/python essais_sans_materiel.py
    ~/doly-env/bin/python essais_sans_materiel.py --images /tmp/images   # enregistre aussi les écrans des jeux en PNG
"""

import argparse
import glob
import json
import os
import random
import shutil
import sys
import tempfile
import threading
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "doly-parle"))

import faux_materiel
from faux_materiel import FausseVoix, Reglages, appels, journal

faux_materiel.installer()

import numpy as np

import animations
import capacites
import base as module_base
import corps as module_corps
import garde
import resumer_journal
import sante
import ecran as module_ecran
import humeur as module_humeur
import jeux
import meteo
import reactions as module_reactions
from animations import Animateur, charger
from capacites import Capacites, Minuteur, dire_duree
from corps import Corps
from humeur import COMBATIF, EMPATHIQUE, JOYEUX, MECHANT, Humeur
from reactions import Reactions, c_est_la_nuit

reussis = 0
rates = []
DOSSIER_IMAGES = None
DOSSIER_ESSAI = tempfile.mkdtemp(prefix="doly-essai-")
# Aucun essai ne doit toucher aux vrais fichiers du robot.
module_corps.FICHIER_STYLE = os.path.join(DOSSIER_ESSAI, "style.json")
jeux.FICHIER_RECORDS = os.path.join(DOSSIER_ESSAI, "records.json")
FICHIER_HUMEUR = os.path.join(DOSSIER_ESSAI, "humeur.json")


def verifier(condition, description):
    global reussis
    if condition:
        reussis += 1
    else:
        rates.append(description)
        print(f"  ÉCHEC : {description}", flush=True)


def titre(texte):
    print(f"\n--- {texte}", flush=True)


def nouveau_corps():
    """Un corps neuf, et le monde remis à zéro."""
    journal.clear()
    Reglages.touche_gauche = Reglages.touche_droite = False
    Reglages.distance_gauche = Reglages.distance_droite = None
    Reglages.sol = True
    Reglages.batterie = 80
    corps = Corps()
    voix = FausseVoix()
    corps.animateur.jouer_son = voix.jouer_son
    return corps, voix


class FausseHorloge:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def essai_humeur():
    titre("Humeur")
    horloge = FausseHorloge()
    humeur = Humeur(fichier=FICHIER_HUMEUR, horloge=horloge)
    verifier(humeur.courante() == (JOYEUX, 1), "joyeux par défaut")
    for _ in range(3):
        humeur.evenement("insulte")
    verifier(humeur.courante()[0] == MECHANT and humeur.courante()[1] == 3, "des insultes le rendent méchant, niveau 3")
    verifier("pour rire" in humeur.pour_claude(), "la consigne méchante dit que c'est pour rire")
    horloge.t += 6000
    verifier(humeur.courante() == (JOYEUX, 1), "il redevient joyeux avec le temps")
    humeur.evenement("defi")
    verifier(humeur.courante()[0] == COMBATIF, "un défi le rend combatif")
    humeur.evenement("tristesse")
    verifier(humeur.courante()[0] == EMPATHIQUE, "une personne triste le rend empathique")
    humeur.demander(MECHANT)
    for _ in range(5):
        humeur.evenement("compliment")
    verifier(humeur.courante()[0] == MECHANT, "une humeur demandée tient malgré les compliments")
    humeur.scores = {h: 0.0 for h in module_humeur.HUMEURS}
    humeur.evenement("tristesse")
    verifier(humeur.courante()[0] == EMPATHIQUE, "une personne triste passe avant une humeur demandée")
    for _ in range(5):
        humeur.evenement("insulte")
    humeur.evenement("tristesse")
    verifier(humeur.courante()[0] == EMPATHIQUE, "une personne triste passe avant une grande colère")
    humeur.scores = {h: 0.0 for h in module_humeur.HUMEURS}
    humeur.demander(MECHANT)
    horloge.t += module_humeur.DUREE_DEMANDE + 1
    verifier(humeur.courante()[0] != MECHANT or humeur.scores[MECHANT] >= 1, "la demande finit par expirer")
    humeur.caractere = module_humeur.CARACTERE_GROGNON - 1
    horloge.t += 20000
    verifier(humeur.courante() == (MECHANT, 1), "un mauvais caractère le rend grognon par défaut")
    humeur.enregistrer()
    relue = Humeur(fichier=FICHIER_HUMEUR, horloge=horloge)
    verifier(relue.caractere < 0, "le caractère est retrouvé au redémarrage")
    with open(FICHIER_HUMEUR, "w") as f:
        f.write("pas du json")
    verifier(Humeur(fichier=FICHIER_HUMEUR).caractere == 0, "un fichier abîmé est ignoré")
    os.remove(FICHIER_HUMEUR)


def essai_meteo():
    titre("Météo")
    donnees = {
        "current": {"temperature_2m": 12.4, "apparent_temperature": 10.6, "weather_code": 61, "wind_speed_10m": 19.5, "is_day": 0},
        "daily": {"weather_code": [0, 3, 95], "temperature_2m_max": [15.2, 14.0, 12.0],
                  "temperature_2m_min": [8.1, 7.0, 6.0], "precipitation_probability_max": [10, None, 80]},
    }
    texte, sequence = meteo.resumer(donnees, "maintenant")
    verifier("pluie faible" in texte and "12 degrés" in texte and "à la maison" in texte, f"maintenant : {texte}")
    verifier(sequence == "weather/rain_n", "la nuit, la séquence de nuit")
    texte, sequence = meteo.resumer(donnees, "demain", "Lyon")
    verifier("Demain à Lyon" in texte and "ciel couvert" in texte and "risque" not in texte, f"demain : {texte}")
    verifier(sequence == "weather/cloudy", "demain, séquence de jour")
    texte, sequence = meteo.resumer(donnees, "apres_demain")
    verifier("orage" in texte and "80 pour cent" in texte and sequence == "weather/storm", f"après-demain : {texte}")
    verifier(meteo.sequence_pour(0, False) == "weather/night", "ciel dégagé la nuit")
    for code in meteo.CODES:
        for de_jour in (True, False):
            nom = meteo.sequence_pour(code, de_jour)
            verifier(os.path.exists(f"/.doly/images/animations/{nom}.seq"), f"séquence du code {code} : {nom}")
    # La position vient d'un faux fichier de réglages : ni la vraie position, ni Internet.
    fichier_ville = os.path.join(DOSSIER_ESSAI, "ville.json")
    meteo.ville_retenue.__defaults__ = (fichier_ville,)
    faux = os.path.join(DOSSIER_ESSAI, "reglages.xml")
    with open(faux, "w") as f:
        f.write('<Settings><Location Latitude="12.3456" Longitude="-1.2345"/></Settings>')
    meteo.position_des_reglages.__defaults__ = (faux,)
    verifier(meteo.lieu_a_utiliser("") == ("", 12.3, -1.2), "la position est arrondie avant de partir sur Internet")
    meteo.position_des_reglages.__defaults__ = (os.path.join(DOSSIER_ESSAI, "absent.xml"),)
    try:
        meteo.lieu_a_utiliser("")
        verifier(False, "sans position, il doit demander la ville")
    except meteo.ErreurMeteo as erreur:
        verifier("ville" in str(erreur), "sans position, il demande la ville")
    meteo.retenir_ville({"nom": "Lyon", "latitude": 45.7, "longitude": 4.8}, fichier_ville)
    verifier(meteo.lieu_a_utiliser("")[0] == "Lyon", "une ville retenue passe avant les réglages")
    os.remove(fichier_ville)


def essai_animations():
    titre("Animations d'origine, toutes, sans roues")
    fichiers = [os.path.basename(f)[:-4] for f in glob.glob(animations.DOSSIER_ANIMATIONS + "/*.xml")]
    fichiers.remove("animationlist")
    verifier(len(fichiers) > 100, f"{len(fichiers)} animations trouvées")

    corps, voix = nouveau_corps()
    voix.duree_son = 0.0
    Reglages.duree_bras = 0.0
    Reglages.duree_yeux = 0.0
    inconnus = set()
    types_connus = {"eye_animations", "sound", "delay_ms", "arm_set_angle", "led", "led_animation", "repeat",
                    "eye_background", "drive_distance", "drive_rotate_left", "drive_rotate_right", "speak"}
    for nom in fichiers:
        blocs = charger(nom)
        verifier(blocs is not None, f"lecture de {nom}")

        def parcourir(liste):
            for bloc in liste:
                if bloc.type not in types_connus and not bloc.type.startswith("led_animation"):
                    inconnus.add(bloc.type)
                for enfants in bloc.enfants.values():
                    parcourir(enfants)
        parcourir(blocs or [])
    verifier(not inconnus, f"types de blocs inconnus : {inconnus}")

    # Toutes les expressions des yeux que le code demande doivent exister sur le robot.
    import xml.etree.ElementTree as ET
    racine = ET.fromstring(open("/.doly/config/eye/eyeanimations.xml", encoding="utf-8-sig").read())
    connues = {a.get("Name") for a in racine}
    demandees = {"AWAKE L", "AWAKE R", "SLEEP", "BLINK", "ATTENTION", "THINK"}
    for regards in module_reactions.REGARDS_AU_REPOS.values():
        demandees.update(regards)
    demandees.update(module_reactions.REGARDS_MAIN.values())
    demandees.update({"LOOK LEFT", "LOOK RIGHT"})
    petites = [module_reactions._secoue, module_reactions._pique_combative, module_reactions._souleve,
               module_reactions._repose, capacites._ecoute_douce]
    petites += [choix for choix in module_corps.EXPRESSIONS.values() if callable(choix)]
    for fabrique in petites:
        for bloc in fabrique():
            if bloc.type == "eye_animations":
                demandees.add(bloc.champs["animation"])
            elif bloc.type == "sound":
                verifier(os.path.exists(animations.chemin_son(bloc.champs["type_id"], bloc.champs["name"])),
                         f"son : {bloc.champs['name']}")
            elif bloc.type == "rien":
                verifier(False, f"famille de sons vide dans {fabrique.__name__}")
    verifier(demandees <= connues, f"expressions inconnues : {demandees - connues}")
    for nom in fichiers:
        def parcourir_yeux(liste):
            for bloc in liste:
                if bloc.type == "eye_animations":
                    verifier(bloc.champs["animation"] in connues, f"{nom} : {bloc.champs['animation']}")
                for enfants in bloc.enfants.values():
                    parcourir_yeux(enfants)
        parcourir_yeux(charger(nom) or [])
    # Tous les noms d'animations utilisés dans le code doivent exister.
    utilisees = set(module_reactions.COLERE + module_reactions.GRANDE_COLERE)
    for sequence in module_reactions.CHOCS_PAR_DIRECTION.values():
        utilisees.update(sequence)
    for choix in module_corps.EXPRESSIONS.values():
        if not callable(choix):
            utilisees.update(choix)
    for choix in capacites.SCENES_QUI_ROULENT.values():
        utilisees.update(choix)
    utilisees.update(capacites.SCENES_SUR_PLACE.values())
    utilisees.update({"petting1", "petting2", "petting3", "annoy1", "annoy1_l", "annoy1_r", "annoy2_l", "annoy2_r", "love_1",
                      "compliment_1", "compliment_5", "rudeness_1", "rudeness_7", "bad_robot_1", "alarm", "photo", "sleep",
                      "wakeup", "eye_color", "led_color", "happy_1", "happy_2", "doly_lost_1", "angry1_2", "fist_ready",
                      "fist_ready_angry", "fist_bump", "fist_bump_angry", "high_five_ready", "five_ready_angry", "high_five",
                      "five_angry"})
    absentes = sorted(n for n in utilisees if n not in fichiers)
    verifier(not absentes, f"animations absentes : {absentes}")

    # Toutes les animations à la suite prendraient trop de temps : elles tournent en parallèle, chacune avec son lecteur.
    resultats = {}

    def jouer(nom):
        animateur = Animateur(corps)
        animateur.jouer_son = voix.jouer_son
        depart = time.monotonic()
        animateur.jouer(nom, roues=False)
        animateur.attendre_fin(120)
        resultats[nom] = time.monotonic() - depart

    fils = [threading.Thread(target=jouer, args=(nom,)) for nom in fichiers]
    for fil in fils:
        fil.start()
    for fil in fils:
        fil.join()
    plus_longues = sorted(resultats.items(), key=lambda e: -e[1])[:6]
    print("  plus longues (sans durée réelle des sons) :", [(n, round(d, 1)) for n, d in plus_longues], flush=True)
    verifier(len(resultats) == len(fichiers), "toutes les animations ont fini")
    verifier(not appels("drive", "go_distance") and not appels("drive", "go_rotate"), "aucune commande de roues")
    angles = [a[2][2] for a in appels("arm", "set_angle")]
    vitesses = [a[2][1] for a in appels("arm", "set_angle")]
    verifier(angles and max(angles) <= animations.ANGLE_MAX, f"angles limités (max {max(angles)})")
    verifier(max(vitesses) <= animations.VITESSE_BRAS_MAX, f"vitesses limitées (max {max(vitesses)})")
    sons_manquants = [s for s in voix.sons if not os.path.exists(s)]
    verifier(not sons_manquants, f"sons introuvables : {sons_manquants[:3]}")
    print(f"  {len(voix.sons)} sons et {len(angles)} mouvements de bras demandés", flush=True)
    corps.fermer()


def essai_lecture_precise():
    titre("Ordre des blocs et arrêt")
    corps, voix = nouveau_corps()
    voix.duree_son = 0.0
    Reglages.duree_bras = 0.2
    Reglages.duree_yeux = 0.0
    # go_forward : le son, le clignement et les roues démarrent ensemble.
    corps.animateur.jouer("go_forward", roues=True)
    corps.animateur.attendre_fin(5)
    roues = appels("drive", "go_distance")
    verifier(len(roues) == 1 and roues[0][2][0] == 100 and roues[0][2][2] is True, f"go_forward avance de 100 mm : {roues}")
    journal.clear()
    corps.animateur.jouer("go_back", roues=True)
    corps.animateur.attendre_fin(5)
    roues = appels("drive", "go_distance")
    verifier(len(roues) == 1 and roues[0][2][2] is False, "go_back recule")
    journal.clear()
    corps.animateur.jouer("go_left", roues=True)
    corps.animateur.attendre_fin(5)
    roues = appels("drive", "go_rotate")
    verifier(len(roues) == 1 and roues[0][2][0] < 0, f"go_left tourne vers la gauche, avec un angle négatif : {roues}")

    # hand_up_l : l'œil et le bras gauche d'abord, le bras redescend à la fin.
    journal.clear()
    corps.animateur.jouer("hand_up_l", roues=False)
    time.sleep(0.15)
    verifier(appels("arm", "set_angle")[0][2][0] == "Left" and appels("arm", "set_angle")[0][2][2] == 90, "le bras gauche se lève")
    corps.animateur.attendre_fin(15)
    verifier(appels("arm", "set_angle")[-1][2][2] == 0 and not corps.bras_en_l_air(), "le bras finit en bas")

    # Un toucher arrête tout, et le bras ne redescend qu'après une pause.
    journal.clear()
    corps.animateur.jouer("policeman", roues=False)
    time.sleep(0.3)
    verifier(corps.animateur.en_cours(), "policeman tourne")
    verifier(corps.bras_en_l_air(), "bras en l'air pendant policeman")
    corps.arreter()
    verifier(not corps.animateur.en_cours(), "arrêt immédiat de l'animation")
    verifier(appels("arm", "abort") and appels("drive", "abort"), "les moteurs reçoivent l'arrêt")
    verifier(corps.bras_a_baisser, "le bras resté en l'air est à baisser")
    journal.clear()
    time.sleep(0.5)
    verifier(not appels("arm", "set_angle"), "il ne redescend pas tout de suite après un toucher")
    corps.dernier_arret -= module_corps.ATTENTE_AVANT_DE_BAISSER
    time.sleep(0.4)
    verifier(appels("arm", "set_angle") and not corps.bras_a_baisser, "puis il redescend tout seul")

    # Les garde-fous des déplacements restent actifs dans une scène.
    journal.clear()
    Reglages.sol = False
    message = corps.animation_avec_roues("rock")
    corps.animateur.attendre_fin(20)
    verifier("sans rouler" in message and "sol" in message, f"sans sol, il danse sur place : {message}")
    verifier(not appels("drive", "go_distance"), "et les roues ne tournent pas")
    Reglages.sol = True
    Reglages.batterie = 10
    message = corps.animation_avec_roues("rock")
    corps.animateur.attendre_fin(20)
    verifier("batterie" in message and not appels("drive", "go_distance"), f"batterie faible : {message}")
    Reglages.batterie = 80
    Reglages.distance_gauche = 50
    message = corps.animation_avec_roues("rock")
    corps.animateur.attendre_fin(20)
    verifier("obstacle" in message and not appels("drive", "go_distance"), f"obstacle : {message}")
    Reglages.distance_gauche = None
    journal.clear()
    corps.deplacements_restants = 1
    message = corps.animation_avec_roues("rock")
    corps.animateur.attendre_fin(20)
    verifier(appels("drive", "go_distance") and corps.deplacements_restants == 0, "une scène compte comme un déplacement")
    journal.clear()
    message = corps.animation_avec_roues("rock")
    corps.animateur.attendre_fin(20)
    verifier("beaucoup" in message or "trop" in message, f"limite de déplacements : {message}")
    verifier(not appels("drive", "go_distance"), "et les roues ne tournent plus")
    corps.deplacements_restants = 5

    # Le vide qui apparaît en pleine scène arrête les roues pour toute la suite.
    journal.clear()
    Reglages.duree_roues = 0.3
    corps.animateur.jouer("rock", roues=True)
    time.sleep(0.1)
    Reglages.sol = False
    corps.animateur.attendre_fin(20)
    Reglages.duree_roues = 0.05
    verifier(appels("drive", "abort") and "sol" in (corps.animateur.dernier_incident or ""),
             f"le vide stoppe les roues : {corps.animateur.dernier_incident}")
    Reglages.sol = True
    corps.fermer()


def essai_ecran():
    titre("Écrans")
    sequences = glob.glob(module_ecran.DOSSIER_SEQUENCES + "/*.seq") + glob.glob(module_ecran.DOSSIER_SEQUENCES + "/weather/*.seq")
    utilisees = {"bcake", "confetti", "i_summer", "i_exercise", "i_book", "i_vr"}
    for chemin in sequences:
        nom = os.path.basename(chemin)[:-4]
        if nom in utilisees or "weather" in chemin:
            nombre = sum(1 for _ in module_ecran.lire_images(chemin))
            verifier(nombre > 10, f"{nom} : {nombre} images")
    # Le texte doit rester dans l'écran rond.
    noir = module_ecran.fond_uni(0, 0, 0)
    for texte in ("88", "NOV", "12", "BRAVO"):
        image = module_ecran.ecrire(noir, texte, (255, 255, 255))
        ys, xs = np.nonzero(image[:, :, 0])
        rayon = np.sqrt((xs - 120) ** 2 + (ys - 120) ** 2).max()
        verifier(rayon <= 120, f"{texte} tient dans le cercle (rayon {rayon:.0f})")
    corps, voix = nouveau_corps()
    corps.ecran.jouer_sequences(["weather/sunny"], 0.3)
    time.sleep(0.1)
    verifier(corps.occupe(), "l'écran est occupé pendant l'affichage")
    verifier(Reglages.ecrans.get("Left") is not None and Reglages.ecrans["Left"] == Reglages.ecrans["Right"], "les deux yeux sont écrits")
    journal.clear()
    time.sleep(0.4)
    verifier(not corps.occupe(), "l'écran est libéré à la fin")
    verifier(appels("eye", "set_animation"), "les yeux reviennent à la fin")
    corps.ecran.montrer_texte("12", "34", 5)
    time.sleep(0.1)
    corps.arreter()
    verifier(not corps.occupe(), "un toucher coupe l'affichage")
    minuteur = Minuteur()
    minuteur.demarrer(125)
    corps.ecran.compte_a_rebours(minuteur.restant, 0.2)
    time.sleep(0.3)
    verifier(not corps.occupe(), "le compte à rebours s'arrête seul")
    corps.fermer()


class Monde:
    """Fait tourner les réactions sans leur fil : les essais font les tours eux-mêmes."""

    def __init__(self):
        self.corps, self.voix = nouveau_corps()
        self.horloge = FausseHorloge()
        self.humeur = Humeur(fichier=FICHIER_HUMEUR, horloge=self.horloge)
        self.repos = True
        self.reactions = Reactions(self.corps, self.humeur, lambda: self.repos, horloge=self.horloge)
        self.reactions.debut = self.horloge() - 100
        self.reactions.calme_depuis = self.horloge() - 100
        self.reactions.heures_de_sommeil = (25, 25)  # jamais la nuit dans les essais, sauf demande
        self.reactions.prochaine_idee = self.horloge() + 100000
        Reglages.duree_yeux = 0.0
        Reglages.duree_bras = 0.0

    def tours(self, nombre=6):
        for _ in range(nombre):
            self.reactions._un_tour()

    def geste(self, geste, direction="Front"):
        self.reactions._au_geste(getattr(Reglages.ImuGesture, geste), getattr(Reglages.GestureDirection, direction))
        self.tours(1)  # il attend de voir si le capteur tactile signale une tape
        self.horloge.t += module_reactions.DELAI_GESTE + 0.01
        self.tours(1)

    def attendre(self):
        self.corps.animateur.attendre_fin(30)

    def fin(self):
        self.corps.fermer()


def essai_reactions():
    titre("Réactions spontanées")
    monde = Monde()
    # Les caresses vont crescendo.
    joues = []
    original = monde.corps.animateur.jouer
    monde.corps.animateur.jouer = lambda nom, roues=False: (joues.append((nom, roues)), original(nom, roues=roues))[1]
    for _ in range(3):
        monde.reactions.tape(True)
        monde.horloge.t += 3
        monde.attendre()
    verifier([j[0] for j in joues] == ["petting1", "petting1", "petting2"], f"caresses : {joues}")
    verifier(all(j[1] is False for j in joues), "jamais de roues")
    verifier(monde.humeur.courante()[0] == JOYEUX, "les caresses le rendent joyeux")

    # Les tapes rapides l'agacent.
    joues.clear()
    monde.horloge.t += 30
    monde.reactions.tapes.clear()
    for _ in range(5):
        monde.reactions.tape(True)
        monde.horloge.t += 0.3
        monde.attendre()
    verifier([j[0] for j in joues][-2:] == ["annoy1_l", "annoy2_l"], f"tapes rapides à gauche, de plus en plus agacé : {[j[0] for j in joues]}")
    verifier(monde.humeur.scores[MECHANT] > 0, "ça l'agace")

    # Les chocs dépendent de leur force et de la direction.
    joues.clear()
    monde.horloge.t += 100000
    monde.tours(1)  # en vrai, un tour passe dix fois par seconde
    monde.horloge.t += 3
    monde.humeur.scores = {h: 0.0 for h in module_humeur.HUMEURS}
    monde.geste("ShockLight", "Left")
    monde.attendre()
    verifier(joues[-1][0] == "shock_l_1", f"petit choc à gauche : {joues}")
    monde.tours(1)
    monde.reactions.calme_depuis -= 2  # pour vérifier le seul écart entre deux réactions
    monde.horloge.t += 0.5
    monde.geste("ShockHard", "Front")
    verifier(len(joues) == 1, "pas deux réactions coup sur coup")
    monde.horloge.t += 5
    monde.humeur.scores = {h: 0.0 for h in module_humeur.HUMEURS}
    monde.geste("ShockExtreme", "Front")
    monde.attendre()
    verifier(joues[-1][0] == "shock_bf_3", f"gros choc de face : {joues}")
    monde.tours(1)
    monde.horloge.t += 5
    monde.humeur.demander(MECHANT)
    monde.geste("ShockLight", "Up")
    monde.attendre()
    verifier(joues[-1][0].startswith("angry"), f"méchant, un choc le met en colère : {joues[-1]}")
    verifier(not appels("drive", "go_distance") and not appels("drive", "go_rotate"), "aucune roue dans les réactions")
    monde.fin()

    # Il ne réagit pas quand il est occupé, ni juste après avoir bougé.
    monde = Monde()
    monde.repos = False
    monde.geste("ShockHard", "Front")
    verifier(not monde.corps.animateur.en_cours(), "occupé : pas de réaction")
    monde.repos = True
    monde.reactions._un_tour()
    monde.geste("ShockHard", "Front")
    verifier(not monde.corps.animateur.en_cours(), "juste après une activité : pas de réaction, sa centrale s'agite encore")
    monde.horloge.t += 3
    monde.geste("ShockHard", "Front")
    verifier(monde.corps.animateur.en_cours(), "ensuite, il réagit")
    monde.attendre()
    monde.fin()

    # Mesuré sur le robot : une tape sur la tête secoue le robot. Ce n'est pas un choc.
    monde = Monde()
    monde.reactions.dernier_toucher = lambda: monde.horloge()
    monde.geste("ShockHard", "Up")
    verifier(not monde.corps.animateur.en_cours(), "un choc au moment d'un toucher : pas de réaction de choc")
    monde.reactions.dernier_toucher = lambda: None
    monde.fin()

    # Mesuré sur le robot : le capteur tactile rate les tapes très rapides, mais la centrale inertielle les sent.
    monde = Monde()
    joues = []
    original = monde.corps.animateur.jouer
    monde.corps.animateur.jouer = lambda nom, roues=False: (joues.append(nom), original(nom, roues=roues))[1]
    monde.geste("ShockMedium", "Up")
    verifier(joues == ["shock_ud_2"], f"un premier choc : {joues}")
    monde.attendre()
    monde.tours(1)
    monde.horloge.t += 0.4
    monde.geste("ShockHard", "Up")
    verifier(len(joues) == 1, "deux chocs : il attend encore")
    monde.horloge.t += 0.4
    monde.geste("ShockMedium", "Back")
    verifier(joues[-1] == "annoy1", f"plusieurs chocs rapprochés : il est embêté, sans le grand choc : {joues}")
    monde.attendre()
    # Tant qu'on continue, il réagit à chaque fois, et il se fâche de plus en plus.
    for _ in range(6):
        monde.tours(1)
        monde.horloge.t += 0.7
        monde.geste("ShockMedium", "Up")
        monde.attendre()
    verifier(joues[2] == "annoy2" or joues[2] in module_reactions.COLERE, f"il se fâche de plus en plus : {joues}")
    verifier(len(joues) == 8 and joues[-1] in module_reactions.GRANDE_COLERE, f"il réagit à chaque série de tapes : {joues}")
    verifier(not appels("drive", "go_distance") and not appels("drive", "go_rotate"), "sans jamais rouler")
    # Mesuré sur le robot : une seule poussette donne plusieurs chocs, tout près les uns des autres, et des « Move ».
    monde.fin()
    monde = Monde()
    joues = []
    original = monde.corps.animateur.jouer
    monde.corps.animateur.jouer = lambda nom, roues=False: (joues.append(nom), original(nom, roues=roues))[1]
    for geste, direction in (("Move", "Left"), ("Move", "Back"), ("Move", "Left")):
        monde.geste(geste, direction)
    verifier(not joues, "de simples mouvements : pas de réaction")
    for _ in range(3):
        monde.reactions._au_geste(Reglages.ImuGesture.ShockHard, Reglages.GestureDirection.Left)
        monde.horloge.t += 0.1
    monde.tours(1)
    monde.horloge.t += module_reactions.DELAI_GESTE + 0.01
    monde.tours(1)
    verifier(joues == ["shock_l_3"], f"une poussette, plusieurs chocs : une seule réaction de choc : {joues}")
    monde.attendre()
    monde.fin()

    # Un doigt gardé posé sans parler : il apprécie, puis il s'agace, tant que le doigt reste là.
    monde = Monde()
    joues = []
    original = monde.corps.animateur.jouer
    monde.corps.animateur.jouer = lambda nom, roues=False: (joues.append(nom), original(nom, roues=roues))[1]
    temps = {"appels": 0}

    def encore_touche():
        temps["appels"] += 1
        monde.horloge.t += 2.0
        return temps["appels"] <= 25  # le doigt reste 50 secondes

    module_reactions.time.sleep, sommeil = (lambda _: None), module_reactions.time.sleep
    monde.reactions.appui_long(encore_touche)
    module_reactions.time.sleep = sommeil
    verifier(joues[:4] == ["petting3", "love_1", "annoy1", "annoy2"], f"appui long, dans l'ordre : {joues}")
    verifier(joues[4] in module_reactions.COLERE and joues[5] in module_reactions.GRANDE_COLERE, f"puis la colère : {joues}")
    verifier(monde.humeur.scores[MECHANT] > 0, "ça finit par l'agacer")
    # Déjà fâché, il passe directement à l'agacement.
    joues.clear()
    monde.humeur.demander(MECHANT)
    temps["appels"] = 24
    monde.reactions.appui_long(encore_touche)
    verifier(joues[:1] == ["annoy1"], f"appui long, déjà fâché : {joues}")
    # Rien de coincé sur le capteur ne doit bloquer la conversation : elle surveille la batterie.
    module_reactions.time.sleep, sommeil = (lambda _: None), module_reactions.time.sleep
    temps["appels"] = -100000
    monde.reactions.appui_long(encore_touche)
    module_reactions.time.sleep = sommeil
    verifier(temps["appels"] < -100000 + 100, f"l'appui long s'arrête au bout d'un moment : {temps}")
    monde.attendre()
    monde.fin()

    # Le faux choc du démarrage est ignoré.
    monde = Monde()
    monde.reactions.debut = monde.horloge()
    monde.geste("ShockExtreme", "Up")
    verifier(not monde.corps.animateur.en_cours(), "pas de réaction au faux choc du démarrage")
    monde.fin()

    # On le soulève, on le repose.
    monde = Monde()
    monde.tours()
    Reglages.sol = False
    monde.tours(2)
    verifier(not monde.corps.animateur.en_cours(), "il attend confirmation avant de dire qu'on le soulève")
    monde.horloge.t += 0.5
    monde.tours(2)
    verifier(monde.corps.animateur.en_cours(), "soulevé : il réagit")
    monde.attendre()
    monde.horloge.t += 5
    monde.geste("ShockLight", "Up")
    verifier(not monde.corps.animateur.en_cours(), "porté, les secousses ne sont pas des chocs")
    Reglages.sol = True
    monde.tours(2)
    verifier(monde.corps.animateur.en_cours(), "reposé : il réagit")
    monde.attendre()
    monde.fin()

    # Un seul côté soulevé.
    monde = Monde()
    GapDirection = sys.modules["doly_edge"].GapDirection
    monde.tours()
    monde.reactions._au_vide(GapDirection.Front_Left)
    monde.tours(1)
    verifier(not monde.corps.animateur.en_cours(), "il attend de voir si on le soulève en entier")
    monde.horloge.t += 0.5
    monde.tours(1)
    verifier(monde.corps.animateur.en_cours(), "un côté soulevé : il réagit")
    monde.attendre()
    verifier(not appels("drive", "go_distance"), "sans reculer, même si l'animation d'origine le fait")
    monde.tours(1)
    monde.horloge.t += 3
    monde.reactions._au_vide(GapDirection.Back)
    monde.horloge.t += 0.5
    monde.tours(1)
    verifier(not monde.corps.animateur.en_cours(), "pas de nouvelle réaction tout de suite")
    monde.horloge.t += 20
    monde.reactions._au_vide(GapDirection.All)
    monde.horloge.t += 0.5
    monde.tours(1)
    verifier(not monde.corps.animateur.en_cours(), "soulevé en entier : ce n'est pas cette réaction")
    # Les capteurs lâchent l'un après l'autre : si tous finissent par lâcher, seule la réaction « soulevé » se joue.
    monde.tours(2)
    monde.horloge.t += 20
    monde.reactions._au_vide(GapDirection.Front_Left)
    Reglages.sol = False
    monde.horloge.t += 0.5
    monde.tours(1)
    verifier(not monde.corps.animateur.en_cours(), "soulevé en entier : pas de réaction à un seul côté")
    Reglages.sol = True
    monde.fin()

    # Sur une surface sombre, les capteurs ne voient jamais le sol : aucune réaction en boucle.
    Reglages.sol = False
    monde = Monde()
    Reglages.sol = False
    monde.tours(20)
    verifier(not monde.corps.animateur.en_cours(), "sol sombre au démarrage : pas de réaction")
    monde.fin()

    # Une main qui s'approche : un regard, sans son.
    monde = Monde()
    monde.tours()
    journal.clear()
    Reglages.distance_gauche = 60
    monde.tours()
    regards = [a[2][0] for a in appels("eye", "set_animation")]
    verifier(regards == ["LOOK LEFT"], f"main à gauche : {regards}")
    verifier(not monde.voix.sons, "pas de son pour une main")
    journal.clear()
    monde.horloge.t += 10
    monde.tours()
    verifier(not appels("eye", "set_animation"), "la main reste là : pas de nouvelle réaction")
    # Elle passe de l'autre côté sans s'éloigner : il la suit des yeux.
    Reglages.distance_gauche = None
    Reglages.distance_droite = 60
    monde.tours()
    verifier([a[2][0] for a in appels("eye", "set_animation")] == ["LOOK RIGHT"], "il suit la main à droite")
    journal.clear()
    Reglages.distance_droite = None
    monde.tours()
    monde.horloge.t += 10
    Reglages.distance_gauche = Reglages.distance_droite = 60
    monde.tours()
    verifier([a[2][0] for a in appels("eye", "set_animation")] == ["GET BIGGER"], "main au milieu")
    Reglages.distance_gauche = Reglages.distance_droite = None
    monde.fin()

    # Un objet déjà là au démarrage n'est pas une main.
    Reglages.distance_gauche = 50
    monde = Monde()
    Reglages.distance_gauche = 50
    journal.clear()
    monde.tours(10)
    verifier(not appels("eye", "set_animation"), "objet déjà présent : pas de réaction")
    monde.fin()

    # La nuit.
    verifier(c_est_la_nuit(23, 22, 8) and c_est_la_nuit(3, 22, 8) and not c_est_la_nuit(12, 22, 8), "la nuit de 22 h à 8 h")
    verifier(c_est_la_nuit(14, 13, 15) and not c_est_la_nuit(16, 13, 15), "une sieste de 13 h à 15 h")
    monde = Monde()
    heure = time.localtime().tm_hour
    monde.reactions.heures_de_sommeil = (heure, (heure + 1) % 24)
    monde.reactions.derniere_interaction = monde.horloge() - 10000
    monde.tours(1)
    verifier(monde.corps.dort, "la nuit, sans interaction, il s'endort")
    verifier(not monde.voix.sons, "sans bruit")
    monde.geste("ShockLight", "Front")
    verifier(monde.corps.dort, "un frôlement ne le réveille pas")
    monde.reactions.tape(True)
    verifier(not monde.corps.dort, "une tape le réveille")
    monde.attendre()
    monde.fin()


def essai_capacites():
    titre("Outils de Claude")
    noms = [o["name"] for o in capacites.OUTILS]
    verifier(len(noms) == len(set(noms)), "pas d'outil en double")
    json.dumps(capacites.OUTILS)
    for outil in capacites.OUTILS:
        schema = outil["input_schema"]
        verifier(outil.get("strict") and schema["additionalProperties"] is False and set(schema["required"]) == set(schema["properties"]),
                 f"schéma strict de {outil['name']}")
    corps, voix = nouveau_corps()
    humeur = Humeur(fichier=FICHIER_HUMEUR)
    capa = Capacites(corps, voix, humeur)
    etat = capa.etat_pour_claude()
    verifier("Batterie : 80 pour cent" in etat and "joyeux" in etat and "Heure :" in etat and "Date :" in etat, etat)

    def outil(nom, **entree):
        message, erreur = capa.executer(nom, entree)
        corps.animateur.attendre_fin(30)
        return message, erreur

    verifier(outil("inconnu")[1] is True, "outil inconnu : une erreur")
    verifier(outil("minuteur", action="consulter", secondes=0)[0].startswith("Il n'y a pas"), "pas de minuteur au départ")
    verifier("5 minutes" in outil("minuteur", action="demarrer", secondes=300)[0], "minuteur de 5 minutes")
    verifier("reste 5 minutes" in outil("minuteur", action="consulter", secondes=0)[0]
             or "reste 4 minutes" in outil("minuteur", action="consulter", secondes=0)[0], "temps restant")
    verifier("minuteur" in capa.etat_pour_claude(), "Claude sait qu'un minuteur tourne")
    verifier(outil("minuteur", action="annuler", secondes=0)[0] == "Minuteur annulé.", "annulation")
    verifier(outil("minuteur", action="demarrer", secondes=99999)[0].startswith("Refusé"), "durée refusée")
    verifier(dire_duree(3900) == "1 heure 5 minutes" and dire_duree(45) == "45 secondes" and dire_duree(1) == "1 seconde",
             "durées à voix haute")
    minuteur = Minuteur()
    minuteur.demarrer(0.05)
    verifier(not minuteur.echu(), "minuteur en cours")
    time.sleep(0.06)
    verifier(minuteur.echu(), "minuteur échu")

    for evenement in capacites.EVENEMENTS:
        message, erreur = outil("ressentir", evenement=evenement)
        verifier(not erreur and message.startswith("Ton humeur"), f"ressentir {evenement} : {message[:40]}")
    humeur.scores = {h: 0.0 for h in module_humeur.HUMEURS}
    humeur.demandee = None
    verifier("empathique" in outil("ressentir", evenement="tristesse")[0], "tristesse : empathique")
    verifier("méchant" in outil("ressentir", evenement="demande_mechant")[0], "demande : méchant")
    humeur.demandee = None

    for scene in capacites.SCENES:
        journal.clear()
        message, erreur = outil("jouer_scene", scene=scene)
        verifier(not erreur, f"scène {scene} : {message}")
        corps.ecran.arreter()
        roues = appels("drive", "go_distance") + appels("drive", "go_rotate")
        if scene not in capacites.SCENES_QUI_ROULENT:
            verifier(not roues, f"{scene} ne roule pas")
    verifier(corps.dort is False, "se_reveiller réveille")
    for animal in capacites.ANIMAUX:
        voix.sons.clear()
        outil("imiter_animal", animal=animal)
        verifier(voix.sons and os.path.exists(voix.sons[0]), f"cri : {animal}")
    for quoi in ("heure", "date"):
        verifier(outil("montrer_sur_les_yeux", quoi=quoi)[0].startswith("C'est affiché."), f"montrer {quoi}")
        corps.ecran.arreter()
    verifier("pas de minuteur" in outil("montrer_sur_les_yeux", quoi="minuteur")[0], "montrer un minuteur absent")
    for couleur in capacites.COULEURS.values():
        verifier(hasattr(sys.modules["doly_color"].ColorCode, couleur), f"couleur {couleur}")
    verifier(outil("changer_couleur", partie="yeux", couleur="rouge")[0] == "C'est fait.", "yeux rouges")
    verifier(appels("eye", "set_iris"), "l'iris change")
    verifier(corps.style["yeux"] == "Red", "le style est retenu")
    verifier(outil("changer_couleur", partie="led", couleur="vert")[0] == "C'est fait.", "LED vertes")
    verifier(outil("changer_forme_des_yeux", forme="numerique")[0] == "C'est fait.", "yeux numériques")
    autre = Corps()
    verifier(autre.style["yeux"] == "Red" and autre.style["forme"] == "Digi", "le style est relu au démarrage")
    os.remove(module_corps.FICHIER_STYLE)
    # Une valeur fantaisiste dans le fichier ne doit rien casser.
    with open(module_corps.FICHIER_STYLE, "w") as f:
        json.dump({"yeux": "Fuchsia", "forme": "Red", "fond": 3, "led": "Classic", "autre": "x"}, f)
    autre = Corps()
    verifier(autre.style == {"yeux": "Blue", "fond": "White", "forme": "Classic", "led": "Black"}, f"style inconnu ignoré : {autre.style}")
    with open(module_corps.FICHIER_STYLE, "w") as f:
        json.dump([1, 2], f)
    verifier(Corps().style["yeux"] == "Blue", "style qui n'est pas un dictionnaire : ignoré")
    os.remove(module_corps.FICHIER_STYLE)
    # Un outil qui plante donne un résultat d'erreur au lieu de couper la réponse.
    ancien_meteo = capacites.service_meteo.meteo
    def meteo_en_panne(*_):
        raise OSError("panne")
    capacites.service_meteo.meteo = meteo_en_panne
    message, erreur = capa.executer("meteo", {"ville": "", "quand": "maintenant", "retenir_ville": False})
    verifier(erreur is True and "échoué" in message, f"outil en panne : {message}")
    capacites.service_meteo.meteo = ancien_meteo
    verifier(capa.executer("jouer", {"jeu": "roue"})[1] is False and capa.jeu_demande == "roue", "un jeu est demandé")
    capa.oublier_jeu()
    verifier(capa.executer("jouer", {"jeu": "morpion"})[1] is True, "jeu inconnu : une erreur")
    corps.fermer()


class Joueur(threading.Thread):
    """Simule une personne : suit un scénario d'actions (une fonction appelée dans un fil à part)."""

    def __init__(self, scenario):
        super().__init__(daemon=True)
        self.scenario = scenario
        self.start()

    def run(self):
        self.scenario()


def tapoter(gauche=True, droite=False, duree=0.05):
    Reglages.touche_gauche, Reglages.touche_droite = gauche, droite
    time.sleep(duree)
    Reglages.touche_gauche = Reglages.touche_droite = False


def photo_ecrans(nom):
    """Enregistre ce que montrent les écrans, pour le regarder ensuite."""
    if not DOSSIER_IMAGES:
        return
    import cv2

    images = []
    for cote in ("Left", "Right"):
        brut = Reglages.ecrans.get(cote)
        if brut is None or len(brut) != 240 * 240 * 4:
            continue
        images.append(np.frombuffer(brut, dtype=np.uint8).reshape(240, 240, 4)[:, :, 2::-1])
    if images:
        cv2.imwrite(os.path.join(DOSSIER_IMAGES, nom + ".png"), np.hstack(images))


def essai_jeux():
    titre("Jeux")
    random.seed(3)
    verifier(os.path.isdir(jeux.DOSSIER_IMAGES + "/casino"), "images des jeux présentes")
    paires = sum(1 for _ in range(4000) if len(set(jeux.tirer_fruits())) == 1)
    verifier(800 < paires < 1600, f"la roue donne une paire environ 3 fois sur 10 ({paires}/4000)")

    # La roue : 5 manches, puis fin.
    corps, voix = nouveau_corps()
    humeur = Humeur(fichier=FICHIER_HUMEUR)
    partie = jeux.Partie(corps, voix, humeur)

    def lancer_les_roues():
        for manche in range(jeux.MANCHES_ROUE):
            time.sleep(0.3)
            photo_ecrans("roue_pret")
            tapoter()
            time.sleep(1.0)
            photo_ecrans("roue_rotation")
            time.sleep(2.0)
            photo_ecrans("roue_resultat")
            time.sleep(1.5)

    voix.duree_phrase = 0.1
    Joueur(lancer_les_roues)
    ancien_tirage = jeux.tirer_fruits
    tirages = iter([("cherries", "cherries"), ("apple", "banana"), ("lemon", "lemon"), ("apple", "banana"), ("apple", "banana")])
    jeux.tirer_fruits = lambda: next(tirages)
    resume = jeux.jouer_roue(partie)
    jeux.tirer_fruits = ancien_tirage
    verifier("2 fois sur 5" in resume, f"la roue : {resume}")
    verifier(not corps.ecran.en_cours(), "l'écran est rendu à la fin de la roue")
    verifier(any("jackpot" in s for s in voix.sons) and any("slot looser" in s for s in voix.sons), "sons de la roue")

    # Personne ne joue : la partie finit toute seule.
    ancien = jeux.Partie.attendre_toucher.__defaults__
    jeux.Partie.attendre_toucher.__defaults__ = (0.1,)
    resume = jeux.jouer_roue(partie)
    verifier(resume == "La roue : personne n'a joué.", f"la roue sans joueur : {resume}")
    resume = jeux.jouer_defi(partie)
    verifier(resume == "Le défi éclair : personne n'a joué.", f"le défi sans joueur : {resume}")
    verifier(not corps.ecran.en_cours(), "l'écran est rendu sans joueur")
    jeux.Partie.attendre_toucher.__defaults__ = ancien

    # Le défi éclair : la personne réussit tant que l'écran le lui dit, puis ne répond plus.
    def repondre_au_defi():
        time.sleep(0.3)
        photo_ecrans("defi_debut")
        tapoter()
        time.sleep(1.2)
        fin = time.monotonic() + 8
        points = 0
        while time.monotonic() < fin and points < 7:
            gauche = Reglages.ecrans.get("Left")
            droite = Reglages.ecrans.get("Right")
            if gauche is not None and droite is not None and (gauche != vide or droite != vide):
                if points == 2:
                    photo_ecrans("defi_cible")
                tapoter(gauche != vide, droite != vide, 0.05)
                points += 1
                time.sleep(0.05)
            time.sleep(0.01)

    decor = module_ecran.charger_png(jeux.DOSSIER_IMAGES + "/match/retro_3.png")
    vide = module_ecran.pour_ecran(decor)
    Joueur(repondre_au_defi)
    ancien_pause = (jeux.PAUSE_MIN, jeux.PAUSE_MAX)
    jeux.PAUSE_MIN, jeux.PAUSE_MAX = 0.1, 0.15
    jeux.PAUSE_AVANT_DEFI = 1.0  # les joueurs simulés ci-dessous comptent sur ce délai
    resume = jeux.jouer_defi(partie)
    jeux.PAUSE_MIN, jeux.PAUSE_MAX = ancien_pause
    photo_ecrans("defi_score")
    verifier("7 points" in resume and "niveau 2" in resume, f"le défi : {resume}")
    verifier(jeux.lire_records().get("defi_eclair") == 7, "le record est retenu")
    verifier(jeux.FICHIER_RECORDS.startswith(DOSSIER_ESSAI), "les essais n'écrivent pas le vrai fichier des records")
    verifier(not corps.ecran.en_cours(), "l'écran est rendu à la fin du défi")
    verifier(jeux.temps_du_niveau(1) == jeux.TEMPS_DEPART and jeux.temps_du_niveau(50) == jeux.TEMPS_MIN, "le temps diminue, jusqu'à un minimum")

    # Un doigt resté posé depuis la cible précédente ne donne pas de point (vu en vrai : un point « en 0,00 s »).
    Reglages.touche_gauche = True
    verifier(jeux.attendre_reponse(partie, True, False, 0.1) == "trop_tard", "un doigt resté posé ne compte pas")
    verifier(jeux.attendre_reponse(partie, False, True, 0.1) == "trop_tard", "ni comme bonne réponse, ni comme erreur")

    def lever_puis_retoucher():
        time.sleep(0.05)
        Reglages.touche_gauche = False
        time.sleep(0.05)
        Reglages.touche_gauche = True

    Joueur(lever_puis_retoucher)
    verifier(jeux.attendre_reponse(partie, True, False, 1) == "bon", "un nouveau contact après l'avoir levé compte")
    Reglages.touche_gauche = False

    def toucher_le_mauvais_cote():
        time.sleep(0.05)
        Reglages.touche_droite = True

    Joueur(toucher_le_mauvais_cote)
    verifier(jeux.attendre_reponse(partie, True, False, 1) == "faux", "le mauvais côté est une erreur")
    Reglages.touche_droite = False

    # Une cible ratée coûte une vie, et la partie s'arrête à la dernière.
    def lancer_puis_ne_plus_repondre():
        time.sleep(0.2)
        tapoter()

    temps_depart = jeux.TEMPS_DEPART
    jeux.TEMPS_DEPART = 0.2
    voix.phrases.clear()
    Joueur(lancer_puis_ne_plus_repondre)
    resume = jeux.jouer_defi(partie)
    jeux.TEMPS_DEPART = temps_depart
    verifier("Le défi éclair : 0 points" in resume, f"le défi perdu : {resume}")
    verifier(sum("Raté" in p for p in voix.phrases) == jeux.VIES_DEFI - 1 and any("Dernière vie" in p for p in voix.phrases),
             "il annonce les vies qui restent, et s'arrête à la dernière")

    # Doly dort : appuyer avant qu'il ronfle perd.
    anciens = (jeux.ENTRE_DEUX_REGARDS_MIN, jeux.ENTRE_DEUX_REGARDS_MAX)
    anciens_endormissement = (jeux.ENDORMISSEMENT_MIN, jeux.ENDORMISSEMENT_MAX)
    jeux.ENTRE_DEUX_REGARDS_MIN, jeux.ENTRE_DEUX_REGARDS_MAX = 100, 100
    voix.sons.clear()

    def toucher_trop_tot():
        while not corps.dort:
            time.sleep(0.01)
        time.sleep(0.1)
        tapoter()

    Joueur(toucher_trop_tot)
    resume = jeux.jouer_doly_dort(partie)
    verifier("trop tôt" in resume, f"Doly dort, toucher trop tôt : {resume}")
    verifier(not any("sleep" in s for s in voix.sons), "il n'a pas encore ronflé")
    verifier(not corps.dort, "il se réveille après un toucher trop tôt")

    # Toucher sans bouger, une fois qu'il ronfle, gagne.
    jeux.ENDORMISSEMENT_MIN, jeux.ENDORMISSEMENT_MAX = 0.2, 0.3

    def toucher_sans_se_faire_voir():
        while not any("sleep" in s for s in voix.sons):
            time.sleep(0.01)
        time.sleep(0.2)
        tapoter()

    Joueur(toucher_sans_se_faire_voir)
    resume = jeux.jouer_doly_dort(partie)
    verifier("tu as gagné" in resume, f"Doly dort : {resume}")
    verifier(not corps.dort, "il se réveille à la fin")

    # Bouger pendant qu'il regarde perd.
    jeux.ENTRE_DEUX_REGARDS_MIN, jeux.ENTRE_DEUX_REGARDS_MAX = 0.2, 0.3

    def bouger_quand_il_regarde():
        while not corps.dort:
            time.sleep(0.01)
        distance = 150
        while corps.dort:
            Reglages.distance_gauche = distance
            distance = 150 if distance < 20 else distance - 15
            time.sleep(0.1)
        Reglages.distance_gauche = None

    Joueur(bouger_quand_il_regarde)
    resume = jeux.jouer_doly_dort(partie)
    Reglages.distance_gauche = None
    verifier("Doly t'a vu" in resume, f"Doly dort, main qui bouge : {resume}")

    # Une main immobile ne se fait pas voir.
    Reglages.distance_gauche = 100
    vu = jeux.regard_en_coin(partie)
    verifier(not vu, "main immobile : il ne voit rien")
    Reglages.distance_gauche = None
    verifier(not jeux.regard_en_coin(partie), "aucune main : il ne voit rien")
    jeux.ENTRE_DEUX_REGARDS_MIN, jeux.ENTRE_DEUX_REGARDS_MAX = anciens
    jeux.ENDORMISSEMENT_MIN, jeux.ENDORMISSEMENT_MAX = anciens_endormissement

    # Taper dans la main.
    journal.clear()
    Joueur(lambda: (time.sleep(1.0), tapoter()))
    resume = jeux.taper_dans_la_main(partie)
    verifier(resume == "Tu as tapé dans la main de Doly.", f"tope là : {resume}")
    leve = [a[2] for a in appels("arm", "set_angle")]
    verifier(leve[0][0] == "Right" and leve[0][2] == 90 and leve[-1][2] == 0, f"le bras se lève puis redescend : {leve}")
    verifier(not corps.bras_tendu and not corps.bras_en_l_air(), "le bras n'est plus tendu à la fin")
    ancien = jeux.ATTENTE_MAIN
    jeux.ATTENTE_MAIN = 0.3
    resume = jeux.taper_dans_la_main(partie, check=True)
    jeux.ATTENTE_MAIN = ancien
    verifier(resume == "Personne n'a tapé dans la main de Doly.", f"check sans main : {resume}")
    humeur.demander(MECHANT)
    journal.clear()
    resume = jeux.taper_dans_la_main(partie)
    verifier("boudé" in resume, f"il boude : {resume}")
    verifier(all(a[2][2] == 0 for a in appels("arm", "set_angle")), "de mauvaise humeur, il ne lève même pas le bras")
    humeur.demandee = None

    # Un jeu qui plante ne fait pas tomber la conversation.
    capa = Capacites(corps, voix, humeur)
    jeux.JEUX["roue"], ancien = (lambda partie: 1 / 0), jeux.JEUX["roue"]
    capacites.JEUX["roue"] = jeux.JEUX["roue"]
    capa.jeu_demande = "roue"
    verifier(capa.lancer_jeu_demande() is True and "planter" in capa.resultats[-1], "un jeu qui plante est rattrapé")
    jeux.JEUX["roue"] = capacites.JEUX["roue"] = ancien
    verifier(not capa.en_jeu, "plus en jeu après")
    corps.fermer()


def essai_toucher():
    titre("Capteurs tactiles")
    import doly_touch as touch
    import toucher

    Reglages.touche_gauche = Reglages.touche_droite = False
    time.sleep(toucher.DUREE_D_UNE_TAPE + 0.02)
    verifier(not toucher.capteur_touche(), "pas de toucher au départ")
    # Une tape très brève, finie avant que le programme regarde : elle reste visible un court instant.
    toucher._au_toucher(touch.TouchSide.Left, touch.TouchState.Down)
    toucher._au_toucher(touch.TouchSide.Left, touch.TouchState.Up)
    verifier(toucher.capteur_touche() and toucher.capteur_touche(), "une tape reste visible, même lue plusieurs fois")
    verifier(toucher.touche_a_gauche(), "et on sait de quel côté elle venait")
    verifier(not toucher.doigt_pose(), "mais aucun doigt n'est posé")
    verifier(toucher.dernier_evenement() is not None, "son instant est retenu")
    time.sleep(toucher.DUREE_D_UNE_TAPE + 0.02)
    verifier(not toucher.capteur_touche() and not toucher.touche_a_gauche(), "puis elle disparaît")
    Reglages.touche_droite = True
    verifier(toucher.capteur_touche() and not toucher.touche_a_gauche(), "un doigt à droite")
    Reglages.touche_droite = False


def essai_cerveau():
    titre("Cerveau, avec un faux Claude")
    os.environ.setdefault("ANTHROPIC_API_KEY", "essai-sans-reseau")  # jamais envoyée : le client est remplacé
    import converser

    class Bloc:
        def __init__(self, type_de_bloc, **champs):
            self.type = type_de_bloc
            self.__dict__.update(champs)

    class Reponse:
        def __init__(self, contenu, arret="end_turn"):
            self.content = contenu
            self.stop_reason = arret
            self.usage = Bloc("usage", input_tokens=1, output_tokens=1, cache_read_input_tokens=0, cache_creation_input_tokens=0)

    class Flux:
        def __init__(self, reponse):
            self.reponse = reponse
            self.text_stream = [b.text for b in reponse.content if b.type == "text"]

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def get_final_message(self):
            return self.reponse

    corps, voix = nouveau_corps()
    capa = Capacites(corps, voix, Humeur(fichier=FICHIER_HUMEUR))
    cerveau = converser.Cerveau("essai", capa)
    reponses = []
    envois = []

    def stream(**demande):
        envois.append(demande)
        return Flux(reponses.pop(0))

    cerveau.client = Bloc("client", messages=Bloc("messages", stream=stream))
    dites = []
    reponses.append(Reponse([Bloc("text", text="Bonjour.")]))
    cerveau.repondre("salut", dites.append, lambda: True)
    roles = [m["role"] for m in cerveau.messages]
    verifier(roles == ["user", "system", "assistant"], f"ordre des messages : {roles}")
    verifier(cerveau.messages[1]["content"].startswith("Informations du robot"), "l'état suit la phrase")
    # Une réponse vide ne doit pas laisser un message système suivi d'un message user.
    reponses.append(Reponse([]))
    cerveau.repondre("rien", dites.append, lambda: True)
    verifier(len(cerveau.messages) == 3, f"tour vide retiré : {[m['role'] for m in cerveau.messages]}")
    # Une réponse vide après un outil reste valable : l'historique finit par le résultat de l'outil.
    reponses.append(Reponse([Bloc("tool_use", id="1", name="minuteur", input={"action": "consulter", "secondes": 0})], "tool_use"))
    reponses.append(Reponse([]))
    cerveau.repondre("il reste combien", dites.append, lambda: True)
    verifier([m["role"] for m in cerveau.messages[3:]] == ["user", "system", "assistant", "user"], "historique après un outil")
    verifier(len({d["system"] for d in envois}) == 1, "les consignes ne changent jamais pendant la conversation")
    verifier(all(d["tools"] is capacites.OUTILS for d in envois), "les outils ne changent jamais pendant la conversation")
    cerveau.oublier()
    verifier(cerveau.messages == [] and cerveau.echanges == 0, "oublier repart à zéro")
    corps.fermer()


def essai_conversation():
    titre("Boucle de conversation")
    os.environ.setdefault("ANTHROPIC_API_KEY", "essai-sans-reseau")
    import converser

    # On remplace seulement ce qui parle au monde extérieur : le micro et Claude.
    class FausseOreille:
        def __init__(self):
            self.a_dire = []
            self.guets = 0
            self.muet = False
            self.micro_bloque = False

        def guetter(self, duree_max, au_reveil, interrompre=lambda: False):
            self.guets += 1
            fin = time.monotonic() + min(duree_max, 0.15)
            while time.monotonic() < fin:
                if converser.capteur_touche():
                    return "toucher", ""
                if interrompre():
                    return "rien", ""
                if not self.micro_bloque:
                    garde.vivant()  # comme le vrai micro, à chaque bloc de son reçu
                time.sleep(0.01)
            if self.a_dire:
                au_reveil()
                return "eveil", self.a_dire.pop(0)
            return "rien", ""

        def ecouter_jusqu_au_silence(self, delai):
            time.sleep(0.02)
            if converser.capteur_touche():
                return "toucher", ""
            return ("phrase", self.a_dire.pop(0)) if self.a_dire else ("rien", "")

        def ecouter_tant_que_touche(self, silence_max=None):
            debut = time.monotonic()
            while converser.capteur_touche():
                if self.muet and silence_max is not None and time.monotonic() - debut > silence_max:
                    garde.vivant()
                    return None, time.monotonic() - debut, time.monotonic()
                time.sleep(0.01)
            garde.vivant()
            return "phrase dite au toucher", time.monotonic() - debut + 0.5, time.monotonic()

    class FauxCerveau:
        def __init__(self, capa):
            self.capa = capa
            self.recues = []
            self.premier_mot = 0.1
            self.outils_a_lancer = {}
            self.oublis = 0

        def oublier(self):
            self.oublis += 1

        def repondre(self, texte, dire, actif):
            self.recues.append(texte)
            dire("Réponse.")
            for nom, entree in self.outils_a_lancer.pop(texte, []):
                self.capa.executer(nom, entree)

    corps, voix = nouveau_corps()
    humeur = Humeur(fichier=FICHIER_HUMEUR)
    capa = Capacites(corps, voix, humeur)
    oreille = FausseOreille()
    cerveau = FauxCerveau(capa)
    conversation = converser.Conversation(voix, oreille, cerveau, corps, capa, discret=True)
    reactions = Reactions(corps, humeur, conversation.au_repos)
    reactions.heures_de_sommeil = (25, 25)
    capa.reactions = reactions
    conversation.reactions = reactions
    reactions.debut -= 100
    reactions.demarrer()
    converser.CONTROLE_BATTERIE = 0.2
    resultat = {}
    Reglages.duree_yeux = 0.02

    # Le service d'origine n'est pas lancé ici : on évite d'appeler systemctl à chaque contrôle.
    converser.service_doly_actif = lambda: False

    fil = threading.Thread(target=lambda: resultat.update(fin=conversation.mains_libres()), daemon=True)
    # Le chien de garde regarde ce fil pendant tout l'essai : aucune activité normale ne doit le faire réagir.
    chien = garde._garde
    chien.fil_surveille = fil
    chien.patience = 2.5  # à l'échelle de cet essai : un toucher long y dure 1,8 s, et 15 s au plus en vrai pour 20 s de patience
    chien.dernier_signe = time.monotonic()
    fausses_alarmes = []
    surveiller_le_chien = threading.Event()
    surveiller_le_chien.set()

    def observer_le_chien():
        while True:
            if surveiller_le_chien.is_set() and not chien.doit_repondre():
                pile = traceback.extract_stack(sys._current_frames()[fil.ident])
                fausses_alarmes.append(" < ".join(f"{cadre.name}:{cadre.lineno}" for cadre in reversed(pile[-4:])))
            time.sleep(0.05)

    threading.Thread(target=observer_le_chien, daemon=True).start()
    fil.start()
    time.sleep(0.3)
    verifier(voix.phrases and "hé Doly" in voix.phrases[0], "il accueille")

    # Le mot d'éveil et une phrase.
    oreille.a_dire.append("quelle heure est-il")
    time.sleep(0.5)
    verifier(cerveau.recues == ["quelle heure est-il"], f"phrase reçue : {cerveau.recues}")

    # Pendant un toucher, les réactions aux chocs sont suspendues : une tape secoue le robot.
    time.sleep(0.3)
    verifier(conversation.au_repos(), "au repos avant le toucher")
    Reglages.touche_droite = True
    verifier(not conversation.au_repos(), "pas au repos pendant un toucher")
    Reglages.touche_droite = False
    time.sleep(0.2)

    # Une tape brève, c'est une caresse : elle n'envoie rien à Claude.
    time.sleep(0.3)
    recues = len(cerveau.recues)
    voix.sons.clear()
    tapoter(True, False, 0.4)  # mesuré sur le robot : une tape normale dure jusqu'à 0,46 s
    time.sleep(1.2)
    verifier(len(cerveau.recues) == recues, "une tape n'envoie rien à Claude")
    verifier(voix.sons, f"une tape fait réagir Doly : {voix.sons[:1]}")

    # Un toucher long, c'est pour parler : le doigt reste posé après la limite d'une tape, assez longtemps pour une phrase.
    toucher_long = converser.DUREE_TAPE + converser.DUREE_MIN
    tapoter(True, False, toucher_long)
    time.sleep(0.5)
    verifier(cerveau.recues[-1] == "phrase dite au toucher", f"un toucher long : {cerveau.recues[-1:]}")

    # « Ne m'écoute plus » : une tape ne rouvre pas le micro, un toucher long oui.
    time.sleep(0.2)
    oreille.a_dire.append("ne m'écoute plus")
    time.sleep(0.6)
    guets = oreille.guets
    tapoter(True, False, 0.1)
    time.sleep(0.6)
    verifier(oreille.guets == guets, "après une caresse, le micro reste fermé")
    time.sleep(chien.patience + 0.3)  # micro fermé exprès, plus longtemps que la patience du chien de garde
    tapoter(True, False, toucher_long)
    time.sleep(0.8)
    verifier(oreille.guets > guets, "un toucher long rouvre le micro")

    # Un contact qui saute un instant sous le doigt reste un toucher long.
    recues = len(cerveau.recues)
    voix.sons.clear()

    def contact_qui_saute():
        Reglages.touche_gauche = True
        time.sleep(0.15)
        Reglages.touche_gauche = False
        time.sleep(0.05)
        Reglages.touche_gauche = True
        time.sleep(toucher_long)
        Reglages.touche_gauche = False

    contact_qui_saute()
    time.sleep(0.5)
    verifier(len(cerveau.recues) == recues + 1 and cerveau.recues[-1] == "phrase dite au toucher", f"contact qui saute : {cerveau.recues[-1:]}")
    time.sleep(0.3)

    # Un doigt gardé posé sans parler : il réagit, et rien ne part vers Claude.
    converser.SILENCE_AVANT_CALIN = 0.2
    oreille.muet = True
    recues = len(cerveau.recues)
    voix.sons.clear()
    Reglages.touche_gauche = True
    time.sleep(1.8)
    verifier(chien.en_cours is not None and chien.en_cours[0] == "doigt gardé posé", f"doigt gardé posé : activité connue : {chien.en_cours}")
    verifier(any("relieve" in s for s in voix.sons) or voix.sons, f"doigt posé sans parler : il réagit : {voix.sons[:1]}")
    Reglages.touche_gauche = False
    time.sleep(0.5)
    corps.animateur.attendre_fin(20)
    verifier(len(cerveau.recues) == recues, "rien n'est envoyé à Claude")
    verifier(corps.etat == "repos", f"il retourne au repos : {corps.etat}")
    oreille.muet = False
    converser.SILENCE_AVANT_CALIN = 2.5
    time.sleep(0.3)

    # S'il s'endort, il n'écoute pas la suite : cela lui rouvrirait les yeux.
    cerveau.outils_a_lancer["va dormir"] = [("jouer_scene", {"scene": "dormir"})]
    oreille.a_dire.append("va dormir")
    time.sleep(0.5)
    corps.animateur.attendre_fin(20)  # l'animation d'endormissement dure quelques secondes
    time.sleep(0.5)
    verifier(corps.dort and corps.etat == "repos", f"il dort, au repos : {corps.dort}, {corps.etat}")
    oreille.a_dire.append("réveille toi")
    time.sleep(0.6)
    verifier(not corps.dort, "son nom le réveille")
    time.sleep(0.4)

    # Un jeu démarre après la phrase, et la conversation sait comment il a fini.
    joue = threading.Event()
    ancien = capacites.JEUX["roue"]
    capacites.JEUX["roue"] = lambda partie: (joue.set(), time.sleep(chien.patience + 0.3), "La roue : essai.")[2]  # un long jeu
    cerveau.outils_a_lancer["on joue"] = [("jouer", {"jeu": "roue"})]
    oreille.a_dire.append("on joue")
    joue.wait(3)
    verifier(joue.is_set(), "le jeu a démarré")
    time.sleep(chien.patience + 0.5)
    capacites.JEUX["roue"] = ancien
    time.sleep(0.2)
    verifier("La roue : essai." in capa.etat_pour_claude(), "Claude reçoit le résultat du jeu")

    # Le minuteur coupe le micro et sonne, puis un toucher arrête la sonnerie sans lancer d'écoute.
    Reglages.duree_bras = 0.05
    voix.sons.clear()
    capa.minuteur.demarrer(0.1)
    time.sleep(0.6)
    verifier(any("minuteur" in p and "terminé" in p for p in voix.phrases), "il annonce la fin du minuteur")
    verifier(any("alarm" in s for s in voix.sons), f"il sonne : {voix.sons[:2]}")
    verifier(corps.animateur.en_cours() or voix.parle(), "la sonnerie est en cours")
    recues = len(cerveau.recues)
    tapoter(True, False, 0.3)
    time.sleep(0.6)
    verifier(not capa.minuteur.actif(), "le minuteur est terminé")
    verifier(len(cerveau.recues) == recues, "ce toucher n'a rien envoyé à Claude")

    # Aucune activité normale n'a fait taire le chien de garde.
    surveiller_le_chien.clear()
    verifier(not fausses_alarmes, f"pas de fausse alarme du chien de garde pendant le scénario : {len(fausses_alarmes)} {fausses_alarmes[:3]}")

    # Le micro ne donne plus de son : cette fois, il réagit.
    time.sleep(0.3)
    oreille.micro_bloque = True
    verifier(chien.doit_repondre(), "juste après le blocage, il répond encore")
    time.sleep(chien.patience + 0.3)
    verifier(not chien.doit_repondre(), "un micro qui ne donne plus de son fait taire le chien de garde")
    oreille.micro_bloque = False
    time.sleep(0.3)
    verifier(chien.doit_repondre(), "il répond de nouveau si le son revient")

    # La batterie vide éteint toujours le robot, même après tout ça.
    Reglages.batterie = 10
    time.sleep(1.0)
    verifier(resultat.get("fin") == "eteindre", f"batterie vide : {resultat}")
    chien.fil_surveille = threading.main_thread()
    chien.patience = garde.PATIENCE
    Reglages.batterie = 80
    reactions.arreter()
    corps.fermer()


def essai_garde():
    titre("Chien de garde")
    horloge = FausseHorloge()
    envois = []
    piles = []
    chien = garde.Garde(envoyer=envois.append, horloge=horloge, patience=20, ecrire_pile=lambda: piles.append(1))

    chien.un_tour()
    verifier(envois == ["WATCHDOG=1"], f"il répond à systemd tant que tout va bien : {envois}")
    horloge.t += 19
    chien.un_tour()
    verifier(len(envois) == 2, "il répond encore juste avant la limite")
    horloge.t += 2
    chien.un_tour()
    verifier(len(envois) == 2, "après 20 s sans signe de vie, il ne répond plus")
    verifier(piles == [1], "il écrit une fois où le programme est bloqué")
    horloge.t += 5
    chien.un_tour()
    verifier(len(envois) == 2 and piles == [1], "il reste muet, sans répéter son message")
    chien.vivant()
    chien.un_tour()
    verifier(len(envois) == 3 and not chien.en_alerte, "un retard passager ne tue pas l'appli s'il reprend à temps")

    # Une chose longue et normale, dans son délai.
    with chien.activite("jeu", 900):
        horloge.t += 800
        chien.un_tour()
        verifier(len(envois) == 4, "un long jeu ne le fait pas taire")
        with chien.activite("parole", 100):
            horloge.t += 50
            verifier(chien.doit_repondre(), "une activité dans une autre")
        verifier(chien.en_cours[0] == "jeu", "l'activité précédente reprend")
        horloge.t += 101
        chien.un_tour()
        verifier(len(envois) == 4 and chien.en_alerte, "un jeu qui dépasse sa durée maximale est un gel")
    verifier(chien.doit_repondre(), "la fin d'une activité est un signe de vie")
    chien.un_tour()

    # Un autre fil ne doit pas pouvoir cacher un gel du fil principal.
    horloge.t += 100
    chien.fil_surveille = threading.current_thread()
    chien.dernier_signe = horloge.t - 100
    fil = threading.Thread(target=chien.vivant)
    fil.start()
    fil.join()
    verifier(not chien.doit_repondre(), "un autre fil ne compte pas comme un signe de vie")

    def activite_dans_un_autre_fil():
        with chien.activite("depuis un autre fil", 1000):
            pass

    fil = threading.Thread(target=activite_dans_un_autre_fil)
    fil.start()
    fil.join()
    verifier(chien.en_cours is None and not chien.doit_repondre(), "ni une activité venue d'un autre fil")
    chien.vivant()
    verifier(chien.doit_repondre(), "le fil surveillé, lui, compte")

    # Hors du service, il n'y a personne à prévenir, et rien ne doit planter.
    socket_avant = os.environ.pop("NOTIFY_SOCKET", None)
    verifier(garde.envoyer_a_systemd("READY=1") is False, "hors du service, rien n'est envoyé")
    if socket_avant:
        os.environ["NOTIFY_SOCKET"] = socket_avant

    # Le vrai message, sur un vrai socket.
    import socket as module_socket
    chemin = os.path.join(DOSSIER_ESSAI, "notify")
    recepteur = module_socket.socket(module_socket.AF_UNIX, module_socket.SOCK_DGRAM)
    recepteur.bind(chemin)
    recepteur.settimeout(1)
    os.environ["NOTIFY_SOCKET"] = chemin
    verifier(garde.envoyer_a_systemd("READY=1") and recepteur.recv(100) == b"READY=1", "le message arrive sur le socket")
    os.environ["NOTIFY_SOCKET"] = "/inexistant/socket"
    verifier(garde.envoyer_a_systemd("WATCHDOG=1") is False, "un socket absent ne fait pas planter")
    del os.environ["NOTIFY_SOCKET"]
    recepteur.close()

    # Le vrai code du micro : un bloc de son reçu est un signe de vie, un read() bloqué ne l'est pas.
    os.environ.setdefault("ANTHROPIC_API_KEY", "essai-sans-reseau")
    import converser
    bloque = threading.Event()
    lectures = []

    class FauxTuyau:
        def read(self, taille):
            lectures.append(taille)
            if len(lectures) > 3:
                bloque.set()
                time.sleep(60)  # comme arecord figé
            return b"\0" * taille

    class FauxMicro:
        stdout = FauxTuyau()

    class FauxGuetteur:
        def Reset(self):
            pass

        def AcceptWaveform(self, bloc):
            return False

        def PartialResult(self):
            return '{"partial": ""}'

    oreille = object.__new__(converser.Oreille)
    oreille.guetteur = FauxGuetteur()
    oreille.duree_guettee = 0.0
    oreille._ouvrir_micro = lambda: FauxMicro()
    vrai_chien = garde._garde
    fil = threading.Thread(target=oreille.guetter, args=(1000, lambda: None), daemon=True)
    vrai_chien.fil_surveille = fil
    vrai_chien.patience = 0.3
    vrai_chien.dernier_signe = time.monotonic() - 100
    verifier(not vrai_chien.doit_repondre(), "avant le micro, plus de signe de vie")
    fil.start()
    bloque.wait(3)
    verifier(vrai_chien.doit_repondre(), "un bloc de son reçu dans guetter est un signe de vie")
    time.sleep(0.5)
    verifier(fil.is_alive() and not vrai_chien.doit_repondre(), "arecord bloqué dans guetter : plus de signe de vie")
    vrai_chien.fil_surveille = threading.main_thread()
    vrai_chien.patience = garde.PATIENCE

    # L'attente du logiciel d'origine : assez courte pour que le repli après 3 échecs en 5 minutes reste possible.
    attente = converser.attente_de_l_origine
    verifier(attente(False, 0, 10) == 290, "à l'allumage, il attend le logiciel d'origine, 5 minutes au plus après l'allumage")
    verifier(attente(True, 0, 10) == 0, "il n'attend pas un logiciel déjà là")
    verifier(attente(False, 1, 60) == 0, "après une relance automatique, il n'attend pas un logiciel qui ne reviendra pas")
    verifier(attente(False, 0, 4000) == 0, "longtemps après l'allumage, il n'attend pas")
    temps_d_un_cycle = 6 + converser.PREPARATION_MAX + 30 + 5 + 10  # lancement, préparation, WatchdogSec, moteurs, RestartSec (mesurés)
    verifier(3 * temps_d_un_cycle <= 300, f"un blocage à chaque préparation fait 3 échecs en 5 minutes : {3 * temps_d_un_cycle} s")
    verifier(garde.PATIENCE + garde.PERIODE < 30, "le fil répond plusieurs fois pendant le délai de systemd")
    os.environ["DOLY_UNITE"] = "unite-qui-n-existe-pas.service"
    verifier(converser.nombre_de_relances() == 0, "une unité inconnue compte pour 0 relance")
    del os.environ["DOLY_UNITE"]
    verifier(converser.nombre_de_relances() == 0, "sans unité, 0 relance")


def essai_base():
    titre("Sur sa base ou non")
    horloge = FausseHorloge()
    base = module_base.Base(horloge=horloge)
    verifier(base.sur_base() is None and not base.en_charge() and base.pour_claude() is None, "au début, il ne sait pas")

    def remplir(valeur):
        for _ in range(module_base.FENETRE):
            horloge.t += 1
            base.noter(valeur)

    for _ in range(module_base.FENETRE - 1):
        base.noter(-5.0)
    verifier(base.sur_base() is None, "pas assez de lectures : il ne sait pas")
    # Les valeurs mesurées sur le robot, en moyenne.
    for valeur, sur_base, charge, texte in [(-6.5, False, False, "hors de sa base, à l'écoute"),
                                            (-4.7, False, False, "hors de sa base, micro coupé"),
                                            (-3.5, False, False, "hors de sa base, endormi"),
                                            (-2.0, None, False, "entre les deux seuils"),
                                            (-0.2, True, False, "sur sa base, batterie pleine"),
                                            (0.0, True, False, "sur sa base, batterie pleine"),
                                            (1.5, True, True, "sur sa base, en charge"),
                                            (2.7, True, True, "sur sa base, en charge")]:
        remplir(valeur)
        verifier(base.sur_base() is sur_base and base.en_charge() is charge, f"{texte} ({valeur} mV) : {base.sur_base()}, {base.en_charge()}")
    remplir(-5.0)
    base.noter(40.0)
    verifier(base.sur_base() is False, "un seul pic ne fait pas croire qu'il est sur sa base")
    remplir(1.5)
    for _ in range(3):
        base.noter(-12.0)
    verifier(base.sur_base() is True, "un pic de consommation ne fait pas croire qu'il est parti")
    remplir(1.5)
    verifier("charge" in base.pour_claude() and "Tu es sur ta base" in base.pour_claude(), base.pour_claude())
    verifier("sur sa base, +1.50 mV" == base.pour_le_journal(), base.pour_le_journal())
    remplir(0.0)
    verifier(base.pour_claude() == "Tu es sur ta base de charge.", f"pleine, on ne dit pas qu'elle charge : {base.pour_claude()}")
    remplir(-6.0)
    verifier("pas sur ta base" in base.pour_claude() and "hors de sa base" in base.pour_le_journal(), base.pour_claude())
    remplir(-2.0)
    verifier(base.pour_claude() is None and "inconnue" in base.pour_le_journal(), "en cas de doute, on ne dit rien à Claude")
    remplir(1.5)
    base.noter(None)
    verifier(base.sur_base() is None and not base.en_charge(), "une lecture ratée : il ne sait plus")
    remplir(1.5)
    horloge.t += module_base.DELAI_MAX + 1
    verifier(base.sur_base() is None and not base.en_charge(), "des lectures trop anciennes : il ne sait plus")

    # Le capteur manque, ou lâche en route : l'appli continue comme avant, sans planter.
    class CapteurEnPanne:
        def __init__(self):
            raise OSError("pas de bus")

    base = module_base.Base(creer_capteur=CapteurEnPanne)
    base.demarrer()
    time.sleep(0.1)
    verifier(base.sur_base() is None and base.erreur_signalee, "sans capteur, il ne sait pas et il le signale une fois")

    # Ce que cela change dans la conversation, avec le vrai contrôle de la batterie.
    os.environ.setdefault("ANTHROPIC_API_KEY", "essai-sans-reseau")
    import converser

    class FausseBase(capacites.BaseInconnue):
        def __init__(self):
            self.place, self.charge = None, False

        def sur_base(self):
            return self.place

        def en_charge(self):
            return self.charge

    corps, voix = nouveau_corps()
    converser.service_doly_actif = lambda: False
    fausse_base = FausseBase()
    capa = Capacites(corps, voix, Humeur(fichier=FICHIER_HUMEUR), base=fausse_base)
    conversation = converser.Conversation(voix, None, None, corps, capa, discret=True)

    def controler(batterie, place, charge):
        Reglages.batterie = batterie
        fausse_base.place, fausse_base.charge = place, charge
        conversation.dernier_controle = -1000
        voix.phrases.clear()
        return conversation.surveiller(), list(voix.phrases)

    eteindre, phrases = controler(28, None, False)
    verifier(phrases == [converser.BATTERIE_FAIBLE] and not eteindre, "base inconnue : il prévient, comme avant")
    eteindre, phrases = controler(28, None, False)
    verifier(phrases == [], "il ne le répète pas toutes les minutes")
    eteindre, phrases = controler(28, True, True)
    verifier(phrases == [], "posé sur sa base : plus d'alerte")
    eteindre, phrases = controler(28, False, False)
    verifier(phrases == [converser.BATTERIE_FAIBLE], "retiré de sa base trop tôt : il prévient de nouveau")
    conversation.alerte_donnee = False
    eteindre, phrases = controler(28, True, False)
    verifier(phrases == [], "sur sa base, batterie pleine ou non : pas d'alerte")

    conversation.lectures_critiques = 0
    verifier(controler(10, True, True)[0] is False and controler(10, True, True)[0] is False, "il charge vraiment : pas d'extinction à 10 %")
    verifier(controler(10, False, False)[0] is False and controler(10, False, False)[0] is True, "hors de sa base : extinction après 2 lectures")
    conversation.lectures_critiques = 0
    verifier(controler(10, True, False)[0] is False and controler(10, True, False)[0] is True, "posé sur sa base sans charger : extinction, c'est le plus prudent")
    conversation.lectures_critiques = 0
    verifier(controler(10, None, False)[0] is False and controler(10, None, False)[0] is True, "lecture douteuse : extinction, comme avant")
    conversation.lectures_critiques = 0
    controler(10, True, True)
    verifier(controler(10, False, False)[0] is False, "le décompte repart de zéro s'il chargeait entre-temps")
    conversation.lectures_critiques = 0
    capa_sans_base = Capacites(corps, voix, Humeur(fichier=FICHIER_HUMEUR))
    verifier("base" not in capa_sans_base.etat_pour_claude(), "sans information, rien sur la base pour Claude")
    verifier(capa_sans_base.base.pour_le_journal() == "base inconnue", "le journal dit qu'il ne sait pas")
    vraie_base = module_base.Base(horloge=horloge)
    capa_avec_base = Capacites(corps, voix, Humeur(fichier=FICHIER_HUMEUR), base=vraie_base)
    for _ in range(module_base.FENETRE):
        vraie_base.noter(1.5)
    etat = capa_avec_base.etat_pour_claude()
    verifier("Tu es sur ta base de charge, et ta batterie charge." in etat and "Batterie : " in etat, etat)
    for phrase in ("Date", "Heure", "Batterie"):
        verifier(phrase in etat, f"le reste du message est là : {etat}")
    Reglages.batterie = 80
    corps.fermer()

    # L'appli qui repart arrête des chenilles qui tourneraient encore.
    journal.clear()
    corps = Corps()
    verifier(appels("drive", "abort"), "au démarrage, l'appli arrête les chenilles")
    corps.fermer()

    # La fin anormale de l'appli arrête les moteurs ; une fin normale n'y touche pas.
    import arreter_moteurs
    journal.clear()
    os.environ["SERVICE_RESULT"] = "success"
    arreter_moteurs.main()
    verifier(not journal, "fin normale : il ne touche à rien")
    for resultat in ("watchdog", "signal", "exit-code", "core-dump", "timeout"):
        journal.clear()
        os.environ["SERVICE_RESULT"] = resultat
        arreter_moteurs.main()
        verifier(appels("drive", "abort") and appels("arm", "set_angle"), f"fin anormale ({resultat}) : moteurs arrêtés et bras baissés")
    del os.environ["SERVICE_RESULT"]


def essai_sante():
    titre("Relevé de santé")
    mesures = sante.mesurer(time.monotonic() - 100, os.getpid())
    verifier(all(valeur is not None for valeur in mesures.values()), f"tout se lit sur le robot : {mesures}")
    verifier(0 < mesures["appli"] < 900 and 0 < mesures["dispo"] < 907, f"mémoires plausibles : {mesures}")
    verifier(0 < mesures["temp"] < 100, f"température plausible : {mesures['temp']}")
    verifier(99 < mesures["appli_depuis"] < 200, f"durée de fonctionnement : {mesures['appli_depuis']}")
    ligne = sante.ligne_de_sante(mesures)
    import re
    verifier(re.fullmatch(r"\[sante\]( \w+=[\d.]+(Mo|C|s)?){8}", ligne), f"que des nombres : {ligne}")
    vide = {cle: None for cle in mesures}
    verifier(sante.ligne_de_sante(vide).count("?") == 8, "une valeur illisible n'empêche pas d'écrire la ligne")
    verifier(sante.memoire_du_programme(99999999) is None, "un programme disparu ne fait pas planter")
    verifier(sante.memoire_du_systeme("/inexistant") == (None, None), "un fichier illisible ne fait pas planter")
    verifier(sante._premier_nombre("/inexistant") is None, "une température illisible ne fait pas planter")
    verifier(sante.PERIODE == 600, "un relevé toutes les 10 minutes")

    titre("Résumé du journal")
    relevé = "[sante] appli={}Mo piper=90Mo dispo={}Mo echange=1Mo temp={}C charge=1.20 appli_depuis={}s robot_depuis=200s"
    entrees = [
        # Un premier lancement, de 10 minutes, qui finit par un gel.
        ("A", 1, 100.0, "[info] Préparation, modèle essai ..."),
        ("A", 1, 110.0, "[info] Prêt."),
        ("A", 1, 170.0, "[batterie] 90 %, hors de sa base, -5.00 mV"),
        ("A", 1, 200.0, "overrun!!! (at least 250.5 ms long)"),
        ("A", 1, 300.0, "overrun!!! (at least 50.0 ms long)"),
        ("A", 1, 400.0, "[erreur] pas de connexion"),
        ("A", 1, 500.0, "[erreur] pas de connexion"),
        ("A", 1, 700.0, "[garde] Plus de signe de vie depuis 21 s. systemd va me relancer."),
        ("A", None, 730.0, "doly-francais.service: Watchdog timeout (limit 30s)!"),
        ("A", None, 745.0, "doly-francais.service: Scheduled restart job, restart counter is at 1."),
        # Un deuxième, plus long, avec des relevés.
        ("A", 2, 750.0, "[info] Prêt."),
        ("A", 2, 751.0, relevé.format(300, 320, "50.5", 1)),
        ("A", 2, 751.0 + 3600, relevé.format(310, 300, "55.0", 3601)),
        ("A", 2, 751.0 + 7200, relevé.format(320, 310, "52.0", 7201)),
        ("A", 2, 8000.0, "[mesure] fin de ta phrase puis premier son : 2.00 s (transcription 0.10 s, premier mot de Claude 1.00 s)"),
        ("A", 2, 8100.0, "Traceback (most recent call last):"),
        ("A", None, 8110.0, "doly-francais.service: Start request repeated too quickly."),
        # Un autre démarrage : ses secondes repartent de zéro, et l'horloge du jour n'intervient pas.
        ("B", 1, 5.0, "[info] Prêt."),
        ("B", 1, 65.0, "[batterie] 80 %"),
        ("B", 1, 125.0, "[batterie] 81 %, sur sa base, +1.50 mV"),
        ("B", 1, 185.0, "[batterie] 82 %, base inconnue"),
    ]
    resume = resumer_journal.resumer(entrees)
    verifier(len(resume["seances"]) == 3, f"3 lancements : {resume['seances']}")
    verifier(resume["seances"][0]["fin"] == 700.0, "un lancement finit à sa dernière ligne, pas au message de systemd")
    verifier(resume["coupures"] == 2 and resume["coupures_longues"] == 1 and resume["coupure_max"] == 250.5, f"coupures : {resume}")
    verifier(resume["erreurs"] == {"pas de connexion": 2}, f"erreurs : {resume['erreurs']}")
    verifier(resume["gels"] == 1 and resume["alertes_garde"] == 1, "un gel")
    verifier(resume["relances"] == 1 and resume["abandons"] == 1 and resume["plantages"] == 1, f"relances : {resume}")
    verifier(resume["phrases"] == 1, "une phrase")
    texte = resumer_journal.en_francais(resume)
    verifier("3 lancement(s)" in texte and "2 h 02 d'affilée" in texte, texte)
    verifier("de 300 à 320 Mo" in texte and "Sur la dernière heure : +10 Mo" in texte, texte)
    # Une heure de conversation puis une heure sans bouger : la dernière heure ne doit plus rien montrer.
    plateau = [("C", 1, 5.0, "[info] Prêt."),
               ("C", 1, 2000.0, relevé.format(400, 300, "50.0", 1995)),
               ("C", 1, 5400.0, relevé.format(486, 210, "50.0", 5395)),
               ("C", 1, 9000.0, relevé.format(486, 212, "50.0", 8995))]
    verifier("Sur la dernière heure : +0 Mo" in resumer_journal.en_francais(resumer_journal.resumer(plateau)), "un plateau se voit")
    trop_court = [("C", 1, 5.0, "[info] Prêt."),
                  ("C", 1, 600.0, relevé.format(254, 440, "50.0", 595)),
                  ("C", 1, 2500.0, relevé.format(300, 400, "50.0", 2495))]
    verifier("dernière heure" not in resumer_journal.en_francais(resumer_journal.resumer(trop_court)), "pas de chiffre sur moins d'une heure")
    verifier("la mémoire disponible de 320 à 310 Mo" in texte, texte)
    verifier("55 °C" in texte, texte)
    verifier("Coupures du micro : 2, dont 1 de plus de 0.2 s, jusqu'à 0.25 s." in texte, texte)
    verifier("pas de connexion (2 fois)" in texte, texte)
    verifier("Gels détectés par le chien de garde : 1." in texte and "Redémarrages automatiques : 1." in texte, texte)
    verifier("personnalité d'origine : 1 fois" in texte, texte)
    verifier("Sa place : 1 min sur sa base, 1 min hors de sa base." in texte, texte)
    verifier("Batterie : 80 % au plus bas." in texte, texte)
    lignes = [json.dumps({"_BOOT_ID": "A", "_PID": "1", "__MONOTONIC_TIMESTAMP": "2000000", "MESSAGE": "[info] Prêt."}),
              "pas du json",
              json.dumps({"_BOOT_ID": "A", "_PID": "1", "__MONOTONIC_TIMESTAMP": "5000000", "MESSAGE": [91, 98, 93, 255]})]
    entrees_lues = list(resumer_journal.lire_entrees(lignes))
    verifier(len(entrees_lues) == 2 and entrees_lues[0][2] == 2.0, f"lecture du JSON du journal : {entrees_lues}")
    verifier(entrees_lues[1][3].startswith("[b]"), f"un message qui n'est pas de l'UTF-8 ne fait pas planter : {entrees_lues[1]}")
    sans_rien = resumer_journal.en_francais(resumer_journal.resumer([]))
    verifier("aucun lancement" in sans_rien and "Erreurs : aucune" in sans_rien, sans_rien)
    # Les erreurs affichées ne viennent que de messages fixes : les phrases dites n'ont pas d'étiquette [erreur].
    avec_phrase = resumer_journal.resumer([("A", 1, 1.0, "[toi] ma phrase secrète"), ("A", 1, 2.0, "[info] Prêt."), ("A", 1, 3.0, "[toi] autre chose")])
    verifier("secrète" not in resumer_journal.en_francais(avec_phrase), "les phrases dites n'apparaissent jamais dans le résumé")


def main():
    global DOSSIER_IMAGES
    analyse = argparse.ArgumentParser(description="Essais sans matériel.")
    analyse.add_argument("--images", help="dossier où enregistrer les écrans des jeux")
    analyse.add_argument("essais", nargs="*", help="noms des essais à lancer (par défaut, tous)")
    options = analyse.parse_args()
    if options.images:
        os.makedirs(options.images, exist_ok=True)
        DOSSIER_IMAGES = options.images
    tous = {
        "humeur": essai_humeur, "meteo": essai_meteo, "animations": essai_animations, "lecture": essai_lecture_precise,
        "ecran": essai_ecran, "reactions": essai_reactions, "capacites": essai_capacites, "jeux": essai_jeux,
        "toucher": essai_toucher, "cerveau": essai_cerveau, "conversation": essai_conversation, "garde": essai_garde,
        "sante": essai_sante, "base": essai_base,
    }
    for nom, essai in tous.items():
        if options.essais and nom not in options.essais:
            continue
        try:
            essai()
        except Exception:
            rates.append(f"{nom} : plantage")
            traceback.print_exc()
    shutil.rmtree(DOSSIER_ESSAI, ignore_errors=True)
    print(f"\n{reussis} vérifications réussies, {len(rates)} échecs", flush=True)
    for raison in rates:
        print("  -", raison)
    # Des fils d'animation peuvent encore dormir : on ne les attend pas.
    os._exit(1 if rates else 0)


if __name__ == "__main__":
    main()
