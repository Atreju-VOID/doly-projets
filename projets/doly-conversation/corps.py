#!/usr/bin/env python3
"""
corps.py

Le corps de Doly pendant la conversation.

Les yeux et les LED montrent s'il écoute, réfléchit ou parle. Claude peut aussi lui faire changer
d'expression, bouger les bras ou se déplacer, mais seulement avec les gestes prévus ici et leurs
limites fixes. Les déplacements sont surveillés en continu : vide, obstacle, toucher et durée.
"""

import json
import os
import random
import threading
import time
import xml.etree.ElementTree as ET

import doly_arm as arm
import doly_battery as batterie
import doly_drive as drive
import doly_edge as edge
import doly_eye as eye
import doly_fan as fan
import doly_helper as helper
import doly_lcd as lcd
import doly_led as led
import doly_tof as tof
from doly_color import Color, ColorCode

from animations import ANGLE_MAX, VITESSE_BRAS, Animateur, attente, bras, son_au_hasard, yeux
from ecran import Ecran

COULEUR_DES_ETATS = {
    "repos": ColorCode.Black,
    "ecoute": ColorCode.Green,
    "reflexion": ColorCode.Orange,
    "parole": ColorCode.SkyBlue,
}

DELAI_MOUVEMENT = 4  # secondes au maximum pour un mouvement de bras
BAS = 0
HAUT = 120
MI_HAUTEUR = 70
ATTENTE_AVANT_DE_BAISSER = 4  # secondes après un toucher qui a laissé un bras en l'air

# Chaque geste est une suite de mouvements : (côté, angle).
GESTES = {
    "baisser_les_bras": [(arm.ArmSide.Both, BAS)],
    "lever_les_bras": [(arm.ArmSide.Both, HAUT), (arm.ArmSide.Both, BAS)],
    "lever_le_bras_gauche": [(arm.ArmSide.Left, HAUT), (arm.ArmSide.Left, BAS)],
    "lever_le_bras_droit": [(arm.ArmSide.Right, HAUT), (arm.ArmSide.Right, BAS)],
    "saluer": [(arm.ArmSide.Right, HAUT), (arm.ArmSide.Right, MI_HAUTEUR), (arm.ArmSide.Right, HAUT),
               (arm.ArmSide.Right, MI_HAUTEUR), (arm.ArmSide.Right, BAS)],
}


def air_de_defi():
    return [yeux("HOSTILE"), son_au_hasard("PROVOKE"), bras("0", 70, 40), attente(900), bras("0", BAS, 40, immediat=False)]


# Une émotion joue une animation d'origine prise au hasard, ou une petite animation écrite ici. Jamais de roues.
EXPRESSIONS = {
    "joie": ["happy_1", "happy_2", "happy_3"],
    "grande_joie": ["excited_1"],
    "amour": ["love_1"],
    "surprise": lambda: [yeux("SHOCKED"), son_au_hasard("SHOCK")],
    "confusion": ["confuse_2"],
    "timidite": lambda: [yeux("SHY"), son_au_hasard("ADMIRE")],
    "tristesse": ["sad_1", "sad_2"],
    "pleurs": ["cry_1", "cry_2", "cry_3"],
    "fatigue": lambda: [yeux("SLEEPY"), son_au_hasard("YAWN")],
    "colere": ["angry1_1", "angry1_2", "angry1_3", "angry1_4"],
    "peur": ["fear_1", "fear_2", "fear_3"],
    "fierte": ["doly_win_1"],
    "deception": ["doly_lost_1"],
    "rire": lambda: [yeux("HAPPY"), son_au_hasard("LAUGH")],
    "defi": air_de_defi,
    "ennui": lambda: [yeux("BLUE"), son_au_hasard("SAD")],
}

VITESSE_ROUES = 30  # en pourcentage
DELAI_DEPLACEMENT = 8  # secondes au maximum pour un déplacement
OBSTACLE_AU_DEPART = 150  # mm : il refuse d'avancer si un obstacle est plus proche
OBSTACLE_EN_ROUTE = 60  # mm : il s'arrête si un obstacle est plus proche
BATTERIE_MIN = 20  # pour cent : en dessous, il refuse de se déplacer, car l'effort pourrait le couper net
MAX_DEPLACEMENTS_PAR_PHRASE = 5

# Testé au sol : un angle négatif le fait tourner vers sa gauche.
DEPLACEMENTS = {
    "avancer_10_cm": {"distance": 100, "en_avant": True},
    "avancer_20_cm": {"distance": 200, "en_avant": True},
    "reculer_10_cm": {"distance": 100, "en_avant": False},
    "reculer_20_cm": {"distance": 200, "en_avant": False},
    "tourner_a_gauche": {"angle": -90},
    "tourner_a_droite": {"angle": 90},
    "faire_demi_tour": {"angle": 180},
}

FICHIER_STYLE = os.path.expanduser("~/.config/doly/style.json")
REGLAGES_DU_ROBOT = "/.doly/config/settings.xml"
LUMINOSITE_PAR_DEFAUT = 6  # sur 10
LUMINOSITE_SOMMEIL = 1
DELAI_YEUX_LIBRES = 0.3  # secondes au maximum pour qu'une animation des yeux s'arrête

OUTILS = [
    {
        "name": "se_deplacer",
        "description": "Fait rouler Doly de 10 ou 20 cm, ou le fait tourner sur place. Répond si le déplacement a "
                       "réussi, ou pourquoi il a été refusé ou arrêté.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"deplacement": {"type": "string", "enum": sorted(DEPLACEMENTS)}},
            "required": ["deplacement"],
            "additionalProperties": False,
        },
    },
    {
        "name": "exprimer",
        "description": "Montre une émotion avec les yeux, les LED et un petit son de Doly, pendant quelques secondes.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"emotion": {"type": "string", "enum": sorted(EXPRESSIONS)}},
            "required": ["emotion"],
            "additionalProperties": False,
        },
    },
    {
        "name": "bouger_les_bras",
        "description": "Fait un geste avec les bras de Doly. Le geste se fait pendant que Doly parle.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"geste": {"type": "string", "enum": sorted(GESTES)}},
            "required": ["geste"],
            "additionalProperties": False,
        },
    },
]


def lire_luminosite(chemin=REGLAGES_DU_ROBOT):
    """Lit la luminosité des écrans choisie dans l'appli officielle."""
    try:
        return int(ET.parse(chemin).getroot().find("Lcd").get("Brightness"))
    except (OSError, ET.ParseError, AttributeError, TypeError, ValueError):
        return LUMINOSITE_PAR_DEFAUT


class Corps:
    def __init__(self):
        # Sa personnalité d'origine étant arrêtée, c'est à nous de refroidir le processeur :
        # le mode automatique du ventilateur vise à le garder sous 70 °C.
        rc = fan.init(True)
        if rc < 0:
            raise RuntimeError(f"ventilateur indisponible (code {rc})")
        self.style = self._lire_style()
        rc = eye.init(getattr(ColorCode, self.style["yeux"]), getattr(ColorCode, self.style["fond"]))
        if rc < 0:
            raise RuntimeError(f"yeux indisponibles (code {rc})")
        if self.style["forme"] != "Classic":
            eye.set_iris(getattr(eye.IrisShape, self.style["forme"]), getattr(ColorCode, self.style["yeux"]), eye.EyeSide.Both)
        self.luminosite = lire_luminosite()
        lcd.set_brightness(self.luminosite)
        rc = led.init()
        if rc < 0:
            raise RuntimeError(f"LED indisponibles (code {rc})")
        # Le SDK exige la lecture des réglages pour que les bras obéissent à leur calibrage.
        if helper.read_settings() < 0 or arm.init() < 0:
            raise RuntimeError("bras indisponibles")
        if edge.init() < 0 or tof.init() < 0 or batterie.init() < 0:
            raise RuntimeError("capteurs de sécurité indisponibles")
        rc, *decalages_imu = helper.get_imu_offsets()
        if rc < 0 or drive.init(*decalages_imu) < 0:
            raise RuntimeError("roues indisponibles")
        self.etat = None
        self.verrou_proximite = threading.Lock()
        self.numero = 0
        self.numero_geste = 0  # un nouveau numéro annule le geste en cours
        self.numero_deplacement = 0  # un nouveau numéro signale qu'un toucher a demandé l'arrêt
        self.deplacements_restants = MAX_DEPLACEMENTS_PAR_PHRASE
        self.en_vie = True
        self.dort = False
        self.angles_bras = {arm.ArmSide.Left: BAS, arm.ArmSide.Right: BAS}
        self.bras_a_baisser = False
        self.bras_tendu = False  # un bras reste levé exprès : il attend qu'on tape dedans
        self.fil_geste = None
        self.yeux_reserves = False
        self.dernier_arret = 0.0
        self.image_de_fond = None  # garde en mémoire l'image posée sur le fond des yeux
        self.animateur = Animateur(self)
        self.ecran = Ecran(self)
        self.passer_a("repos")
        threading.Thread(target=self._vivre, daemon=True).start()

    def suivant(self):
        self.numero = (self.numero + 1) % 60000
        return self.numero

    def occupe(self):
        """Vrai si une animation ou un affichage garde la main sur les yeux et les LED."""
        return self.animateur.en_cours() or self.ecran.en_cours()

    def passer_a(self, etat):
        if etat == self.etat:
            return
        self.etat = etat
        if etat == "ecoute":
            self.deplacements_restants = MAX_DEPLACEMENTS_PAR_PHRASE
        # Une animation en cours garde la main : l'état s'appliquera à sa fin.
        if not self.occupe():
            self._appliquer_etat()

    def _appliquer_led(self):
        activite = led.LedActivity()
        couleur = COULEUR_DES_ETATS[self.etat]
        if self.etat == "repos" and self.style["led"] != "Black":
            couleur = getattr(ColorCode, self.style["led"])
        activite.mainColor = Color.from_code(couleur)
        activite.fade_time = 0
        led.process_activity(self.suivant(), led.LedSide.Both, activite)

    def _appliquer_etat(self):
        self._appliquer_led()
        if self.etat == "ecoute":
            eye.set_animation(self.suivant(), eye.expressions.ATTENTION)
        elif self.etat == "reflexion":
            eye.set_animation(self.suivant(), eye.expressions.THINK)
        elif eye.is_animating():
            eye.abort()

    def fin_animation(self):
        """Appelé par l'animateur à la fin normale d'une animation."""
        self._retirer_fond_des_yeux()
        geste_en_cours = self.fil_geste is not None and self.fil_geste.is_alive()
        if self.bras_en_l_air() and not self.bras_tendu and not geste_en_cours:
            self._baisser_les_bras()
        if not self.ecran.en_cours():
            self._appliquer_etat()

    def prendre_ecran(self):
        """Avant d'écrire directement sur les écrans : arrête ce que les yeux sont en train d'animer."""
        if eye.is_animating():
            eye.abort()

    def rendre_ecran(self):
        """Redonne ses yeux à Doly après un affichage."""
        if self.animateur.en_cours():
            return
        if self.dort:
            self._appliquer_led()
            eye.set_animation(self.suivant(), eye.expressions.SLEEP)
        elif self.etat in ("repos", "parole"):
            self._appliquer_led()  # l'état a pu changer pendant l'affichage
            eye.set_animation(self.suivant(), eye.expressions.BLINK)
        else:
            self._appliquer_etat()

    def regard(self, nom):
        """Une expression des yeux seuls, sans son ni mouvement : elle ne gêne pas l'écoute. Renvoie True si elle a démarré."""
        if self.occupe() or self.dort or self.yeux_reserves or eye.is_animating():
            return False
        return eye.set_animation(self.suivant(), nom) >= 0

    def ouvrir_un_oeil(self, nom):
        """Pendant son sommeil : ouvre un œil, puis le referme, avec AWAKE L ou AWAKE R."""
        eye.set_animation(self.suivant(), nom)

    def _vivre(self):
        """Fait cligner les yeux au repos et quand il parle, et prolonge l'air pensif quand il réfléchit."""
        prochain_clignement = time.monotonic() + 2
        while self.en_vie:
            time.sleep(0.1)
            if self.occupe() or self.dort or self.yeux_reserves or eye.is_animating():
                continue
            maintenant = time.monotonic()
            if (self.bras_a_baisser and self.etat in ("repos", "parole")
                    and maintenant - self.dernier_arret > ATTENTE_AVANT_DE_BAISSER):
                self._baisser_les_bras()
            if self.etat == "reflexion":
                eye.set_animation(self.suivant(), eye.expressions.THINK)
            elif self.etat in ("repos", "parole") and maintenant > prochain_clignement:
                eye.set_animation(self.suivant(), eye.expressions.BLINK)
                prochain_clignement = maintenant + random.uniform(2.5, 6)

    def noter_bras(self, cote, angle):
        """Retient la position demandée, pour savoir si un bras reste en l'air."""
        if cote == arm.ArmSide.Both:
            self.angles_bras[arm.ArmSide.Left] = self.angles_bras[arm.ArmSide.Right] = angle
        else:
            self.angles_bras[cote] = angle

    def bras_en_l_air(self):
        return any(angle > 5 for angle in self.angles_bras.values())

    def _baisser_les_bras(self):
        self.bras_a_baisser = False
        if arm.set_angle(self.suivant(), arm.ArmSide.Both, VITESSE_BRAS, BAS) >= 0:
            self.noter_bras(arm.ArmSide.Both, BAS)

    def _jouer_geste(self, mouvements, numero_geste):
        for cote, angle in mouvements:
            if numero_geste != self.numero_geste:
                return
            if arm.set_angle(self.suivant(), cote, VITESSE_BRAS, min(angle, ANGLE_MAX)) < 0:
                print(f"[erreur] Mouvement de bras refusé : {cote}, {angle}", flush=True)
                return
            self.noter_bras(cote, angle)
            depart = time.monotonic()
            time.sleep(0.05)
            while arm.get_state(cote) == arm.ArmState.Running and time.monotonic() - depart < DELAI_MOUVEMENT:
                if numero_geste != self.numero_geste:
                    return
                time.sleep(0.05)

    def tendre_un_bras(self, cote=arm.ArmSide.Right, angle=90, vitesse=40):
        """Lève un bras et le laisse en l'air, pour qu'on tape dedans. relacher_le_bras() lui rend sa liberté."""
        if arm.set_angle(self.suivant(), cote, vitesse, min(angle, ANGLE_MAX)) >= 0:
            self.noter_bras(cote, angle)
            self.bras_tendu = True

    def relacher_le_bras(self):
        self.bras_tendu = False

    def en_mouvement(self):
        return drive.get_state() == drive.DriveState.Running or arm.get_state(arm.ArmSide.Both) == arm.ArmState.Running

    def batterie(self):
        return batterie.get_capacity()

    def sol_sous_lui(self):
        """Vrai si les 4 capteurs de vide voient le sol. Testé : High au sol, Low quand on le soulève."""
        return all(capteur.state == edge.GpioState.High for capteur in edge.get_sensors())

    def en_l_air(self):
        """Vrai si aucun capteur de vide ne voit le sol. Sur sa base, seuls certains d'entre eux le voient."""
        return all(capteur.state == edge.GpioState.Low for capteur in edge.get_sensors())

    def distances(self):
        """Renvoie la distance en mm vue par chaque capteur de proximité (gauche, droite), ou None si rien n'est à portée."""
        # Une lecture dure 100 ms, et les réactions et les déplacements peuvent en demander en même temps.
        with self.verrou_proximite:
            donnees = tof.get_sensors_data()
        mesures = {donnee.side: donnee.range_mm for donnee in donnees
                   if donnee.error == tof.TofError.NoError and donnee.range_mm >= 0}
        return mesures.get(tof.TofSide.Left), mesures.get(tof.TofSide.Right)

    def obstacle_devant(self):
        """Renvoie la distance en mm de l'obstacle le plus proche, ou None si rien n'est à portée."""
        mesures = [distance for distance in self.distances() if distance is not None]
        return min(mesures) if mesures else None

    def rouler(self, commande, surveiller_devant):
        """Lance une commande de déplacement et la surveille. Renvoie un message pour Claude."""
        self.numero_deplacement += 1
        numero_deplacement = self.numero_deplacement
        if not commande(self.suivant()):
            return "Déplacement refusé par les moteurs."
        depart = time.monotonic()
        tours = 0
        time.sleep(0.05)
        while drive.get_state() == drive.DriveState.Running:
            if numero_deplacement != self.numero_deplacement:
                return "Arrêté par un toucher."
            if not self.sol_sous_lui():
                drive.abort()
                return "Arrêté : je ne sens plus le sol sous moi."
            tours += 1
            if surveiller_devant and tours % 5 == 0:
                distance = self.obstacle_devant()
                if distance is not None and distance < OBSTACLE_EN_ROUTE:
                    drive.abort()
                    return "Arrêté : il y a un obstacle juste devant moi."
            if time.monotonic() - depart > DELAI_DEPLACEMENT:
                drive.abort()
                return "Arrêté : le déplacement prenait trop de temps."
            time.sleep(0.02)
        # L'arrêt demandé par un toucher met aussi les roues en état d'erreur : on le regarde d'abord.
        if numero_deplacement != self.numero_deplacement:
            return "Arrêté par un toucher."
        if drive.get_state() == drive.DriveState.Error:
            return "Arrêté : quelque chose gêne mes chenilles."
        return "Déplacement terminé."

    def raison_de_ne_pas_rouler(self):
        """Renvoie pourquoi il ne doit pas rouler en ce moment, ou None si tout va bien."""
        if self.deplacements_restants <= 0:
            return "trop de déplacements d'un coup"
        if batterie.get_capacity() < BATTERIE_MIN:
            return "ma batterie est trop faible"
        if not self.sol_sous_lui():
            return "je ne sens pas le sol sous moi"
        return None

    def se_deplacer(self, nom):
        raison = self.raison_de_ne_pas_rouler()
        if raison:
            return f"Refusé : {raison}."
        self.deplacements_restants -= 1
        deplacement = DEPLACEMENTS[nom]
        if "angle" in deplacement:
            return self.rouler(
                lambda numero: drive.go_rotate(numero, deplacement["angle"], True, VITESSE_ROUES, True, True), False
            )
        en_avant = deplacement["en_avant"]
        if en_avant:
            distance = self.obstacle_devant()
            if distance is not None and distance < OBSTACLE_AU_DEPART:
                return "Refusé : il y a un obstacle devant moi."
        return self.rouler(
            lambda numero: drive.go_distance(numero, deplacement["distance"], VITESSE_ROUES, en_avant, True), en_avant
        )

    def animation_avec_roues(self, nom):
        """Une animation demandée à voix haute, qui peut rouler un peu. Renvoie un message pour Claude."""
        raison = self.raison_de_ne_pas_rouler()
        if raison is None:
            distance = self.obstacle_devant()
            if distance is not None and distance < OBSTACLE_AU_DEPART:
                raison = "il y a un obstacle devant moi"
        if raison:
            self.animateur.jouer(nom, roues=False)
            return f"Fait sur place, sans rouler : {raison}."
        self.deplacements_restants -= 1
        self.animateur.jouer(nom, roues=True)
        return "C'est parti."

    def exprimer(self, emotion):
        choix = EXPRESSIONS[emotion]
        if callable(choix):
            self.animateur.jouer_blocs(choix(), roues=False, nom=emotion)
        else:
            self.animateur.jouer(random.choice(choix), roues=False)

    def dormir(self, silencieux=False, tamiser=True):
        """Ferme les yeux jusqu'au réveil. Le micro reste ouvert : « Hé Doly » ou un toucher le réveillent."""
        self.dort = True
        if silencieux:
            eye.set_animation(self.suivant(), eye.expressions.SLEEP)
        else:
            self.animateur.jouer("sleep", roues=False)
        if tamiser:
            lcd.set_brightness(LUMINOSITE_SOMMEIL)

    def reveiller(self, silencieux=False):
        if not self.dort:
            return
        self.dort = False
        lcd.set_brightness(self.luminosite)
        if silencieux:
            eye.set_animation(self.suivant(), eye.expressions.BLINK)
        else:
            self.animateur.jouer("wakeup", roues=False)

    def _lire_style(self):
        style = {"yeux": "Blue", "fond": "White", "forme": "Classic", "led": "Black"}
        try:
            with open(FICHIER_STYLE) as f:
                lu = json.load(f)
            for cle in style:
                # On ne garde que des noms connus du SDK : un fichier abîmé ne doit pas empêcher Doly de démarrer.
                nom = lu.get(cle)
                enumeration = eye.IrisShape if cle == "forme" else ColorCode
                if isinstance(nom, str) and isinstance(getattr(enumeration, nom, None), enumeration):
                    style[cle] = nom
        except (OSError, ValueError, AttributeError):
            pass
        return style

    def _quand_les_yeux_sont_libres(self, action):
        """Vu sur le robot : le module des yeux refuse de changer une image pendant une animation."""
        self.yeux_reserves = True  # pour que ses clignements ne recommencent pas entre-temps
        try:
            if eye.is_animating():
                eye.abort()
            fin = time.monotonic() + DELAI_YEUX_LIBRES
            while eye.is_animating() and time.monotonic() < fin:
                time.sleep(0.01)
            action()
        except RuntimeError as erreur:
            print(f"[yeux] {erreur}", flush=True)
        finally:
            self.yeux_reserves = False

    def changer_style(self, partie, nom):
        """Change et retient la couleur ou la forme des yeux, ou la couleur des LED au repos."""
        self.style[partie] = nom
        if partie in ("yeux", "forme"):
            forme, couleur = getattr(eye.IrisShape, self.style["forme"]), getattr(ColorCode, self.style["yeux"])
            self._quand_les_yeux_sont_libres(lambda: eye.set_iris(forme, couleur, eye.EyeSide.Both))
        elif partie == "fond":
            self._quand_les_yeux_sont_libres(lambda: eye.set_background(Color.from_code(getattr(ColorCode, nom))))
        try:
            os.makedirs(os.path.dirname(FICHIER_STYLE), exist_ok=True)
            with open(FICHIER_STYLE, "w") as f:
                json.dump(self.style, f)
        except OSError as erreur:
            print(f"[style] enregistrement impossible : {erreur}", flush=True)

    def poser_fond_des_yeux(self, image):
        self.image_de_fond = image
        self._quand_les_yeux_sont_libres(lambda: eye.set_background_image(image, eye.EyeSide.Both))

    def _retirer_fond_des_yeux(self):
        if self.image_de_fond is not None:
            self.image_de_fond = None
            couleur = Color.from_code(getattr(ColorCode, self.style["fond"]))
            self._quand_les_yeux_sont_libres(lambda: eye.set_background(couleur))

    def arreter(self):
        """Arrête immédiatement tout mouvement : un toucher a toujours la priorité."""
        self.numero_geste += 1
        self.numero_deplacement += 1
        animation_coupee = self.animateur.en_cours()
        self.animateur.arreter()
        self.ecran.arreter()
        arm.abort(arm.ArmSide.Both)
        drive.abort()
        self.dernier_arret = time.monotonic()
        self.bras_tendu = False
        self.bras_a_baisser = self.bras_en_l_air()
        self._retirer_fond_des_yeux()
        if animation_coupee and self.etat is not None:
            self._appliquer_etat()

    def executer(self, outil, entree):
        """Exécute un outil demandé par Claude. Renvoie (message pour Claude, est-ce une erreur)."""
        if outil == "se_deplacer" and entree.get("deplacement") in DEPLACEMENTS:
            return self.se_deplacer(entree["deplacement"]), False
        if outil == "exprimer" and entree.get("emotion") in EXPRESSIONS:
            self.exprimer(entree["emotion"])
            return "fait", False
        if outil == "bouger_les_bras" and entree.get("geste") in GESTES:
            self.numero_geste += 1
            self.fil_geste = threading.Thread(
                target=self._jouer_geste, args=(GESTES[entree["geste"]], self.numero_geste), daemon=True
            )
            self.fil_geste.start()
            return "geste en cours", False
        return f"Outil ou valeur inconnus : {outil} {entree}", True

    def fermer(self):
        self.en_vie = False
        self.arreter()
        self.dort = False
        lcd.set_brightness(self.luminosite)
        self.passer_a("repos")
        arm.set_angle(self.suivant(), arm.ArmSide.Both, VITESSE_BRAS, BAS)
        depart = time.monotonic()
        time.sleep(0.05)
        while arm.get_state(arm.ArmSide.Both) == arm.ArmState.Running and time.monotonic() - depart < DELAI_MOUVEMENT:
            time.sleep(0.05)
        arm.dispose()
        led.dispose()
        eye.dispose()
        drive.dispose(True)
        edge.dispose()
        tof.dispose()
        batterie.dispose()
        fan.dispose()
