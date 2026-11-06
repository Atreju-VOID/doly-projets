#!/usr/bin/env python3
"""
corps.py

Le corps de Doly pendant la conversation.

Les yeux et les LED montrent s'il écoute, réfléchit ou parle. Claude peut aussi lui faire changer
d'expression, bouger les bras ou se déplacer, mais seulement avec les gestes prévus ici et leurs
limites fixes. Les déplacements sont surveillés en continu : vide, obstacle, toucher et durée.
"""

import random
import threading
import time

import doly_arm as arm
import doly_battery as batterie
import doly_drive as drive
import doly_edge as edge
import doly_eye as eye
import doly_fan as fan
import doly_helper as helper
import doly_led as led
import doly_tof as tof
from doly_color import Color, ColorCode

COULEUR_DES_ETATS = {
    "repos": ColorCode.Black,
    "ecoute": ColorCode.Green,
    "reflexion": ColorCode.Orange,
    "parole": ColorCode.SkyBlue,
}

EXPRESSIONS = {
    "joie": eye.expressions.HAPPY,
    "grande_joie": eye.expressions.DELIGHTED,
    "amour": eye.expressions.HEARTS,
    "surprise": eye.expressions.SHOCKED,
    "confusion": eye.expressions.PUZZLED,
    "timidite": eye.expressions.SHY,
    "tristesse": eye.expressions.DISAPPOINTED,
    "fatigue": eye.expressions.SLEEPY,
}

ANGLE_MAX = 150  # limite volontairement plus basse que le maximum du SDK (240)
VITESSE_BRAS = 30  # en pourcentage
DELAI_MOUVEMENT = 4  # secondes au maximum pour un mouvement de bras
BAS = 0
HAUT = 120
MI_HAUTEUR = 70

# Chaque geste est une suite de mouvements : (côté, angle).
GESTES = {
    "baisser_les_bras": [(arm.ArmSide.Both, BAS)],
    "lever_les_bras": [(arm.ArmSide.Both, HAUT), (arm.ArmSide.Both, BAS)],
    "lever_le_bras_gauche": [(arm.ArmSide.Left, HAUT), (arm.ArmSide.Left, BAS)],
    "lever_le_bras_droit": [(arm.ArmSide.Right, HAUT), (arm.ArmSide.Right, BAS)],
    "saluer": [(arm.ArmSide.Right, HAUT), (arm.ArmSide.Right, MI_HAUTEUR), (arm.ArmSide.Right, HAUT),
               (arm.ArmSide.Right, MI_HAUTEUR), (arm.ArmSide.Right, BAS)],
}

VITESSE_ROUES = 30  # en pourcentage
DELAI_DEPLACEMENT = 8  # secondes au maximum pour un déplacement
OBSTACLE_AU_DEPART = 150  # mm : il refuse d'avancer si un obstacle est plus proche
OBSTACLE_EN_ROUTE = 60  # mm : il s'arrête si un obstacle est plus proche
BATTERIE_MIN = 10  # pour cent : en dessous, il refuse de se déplacer
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
        "description": "Montre une émotion avec les yeux de Doly pendant quelques secondes.",
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


class Corps:
    def __init__(self):
        # Sa personnalité d'origine étant arrêtée, c'est à nous de refroidir le processeur :
        # le mode automatique du ventilateur vise à le garder sous 70 °C.
        rc = fan.init(True)
        if rc < 0:
            raise RuntimeError(f"ventilateur indisponible (code {rc})")
        rc = eye.init(ColorCode.Blue, ColorCode.White)
        if rc < 0:
            raise RuntimeError(f"yeux indisponibles (code {rc})")
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
        self.numero = 0
        self.numero_geste = 0  # un nouveau numéro annule le geste en cours
        self.numero_deplacement = 0  # un nouveau numéro signale qu'un toucher a demandé l'arrêt
        self.deplacements_restants = MAX_DEPLACEMENTS_PAR_PHRASE
        self.en_vie = True
        self.passer_a("repos")
        threading.Thread(target=self._vivre, daemon=True).start()

    def _suivant(self):
        self.numero = (self.numero + 1) % 60000
        return self.numero

    def passer_a(self, etat):
        if etat == self.etat:
            return
        self.etat = etat
        activite = led.LedActivity()
        activite.mainColor = Color.from_code(COULEUR_DES_ETATS[etat])
        activite.fade_time = 0
        led.process_activity(self._suivant(), led.LedSide.Both, activite)
        if etat == "ecoute":
            self.deplacements_restants = MAX_DEPLACEMENTS_PAR_PHRASE
            eye.set_animation(self._suivant(), eye.expressions.ATTENTION)
        elif etat == "reflexion":
            eye.set_animation(self._suivant(), eye.expressions.THINK)
        elif eye.is_animating():
            eye.abort()

    def _vivre(self):
        """Fait cligner les yeux au repos et quand il parle, et prolonge l'air pensif quand il réfléchit."""
        prochain_clignement = time.monotonic() + 2
        while self.en_vie:
            time.sleep(0.1)
            if eye.is_animating():
                continue
            if self.etat == "reflexion":
                eye.set_animation(self._suivant(), eye.expressions.THINK)
            elif self.etat in ("repos", "parole") and time.monotonic() > prochain_clignement:
                eye.set_animation(self._suivant(), eye.expressions.BLINK)
                prochain_clignement = time.monotonic() + random.uniform(2.5, 6)

    def _jouer_geste(self, mouvements, numero_geste):
        for cote, angle in mouvements:
            if numero_geste != self.numero_geste:
                return
            if arm.set_angle(self._suivant(), cote, VITESSE_BRAS, min(angle, ANGLE_MAX)) < 0:
                print(f"[erreur] Mouvement de bras refusé : {cote}, {angle}", flush=True)
                return
            depart = time.monotonic()
            time.sleep(0.05)
            while arm.get_state(cote) == arm.ArmState.Running and time.monotonic() - depart < DELAI_MOUVEMENT:
                if numero_geste != self.numero_geste:
                    return
                time.sleep(0.05)

    def sol_sous_lui(self):
        """Vrai si les 4 capteurs de vide voient le sol. Testé : High au sol, Low quand on le soulève."""
        return all(capteur.state == edge.GpioState.High for capteur in edge.get_sensors())

    def obstacle_devant(self):
        """Renvoie la distance en mm de l'obstacle le plus proche, ou None si rien n'est à portée."""
        mesures = [donnee.range_mm for donnee in tof.get_sensors_data()
                   if donnee.error == tof.TofError.NoError and donnee.range_mm >= 0]
        return min(mesures) if mesures else None

    def rouler(self, commande, surveiller_devant):
        """Lance une commande de déplacement et la surveille. Renvoie un message pour Claude."""
        self.numero_deplacement += 1
        numero_deplacement = self.numero_deplacement
        if not commande(self._suivant()):
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

    def se_deplacer(self, nom):
        if self.deplacements_restants <= 0:
            return "Refusé : trop de déplacements d'un coup."
        if batterie.get_capacity() < BATTERIE_MIN:
            return "Refusé : ma batterie est trop faible."
        if not self.sol_sous_lui():
            return "Refusé : je ne sens pas le sol sous moi."
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

    def arreter(self):
        """Arrête immédiatement tout mouvement : un toucher a toujours la priorité."""
        self.numero_geste += 1
        self.numero_deplacement += 1
        arm.abort(arm.ArmSide.Both)
        drive.abort()

    def executer(self, outil, entree):
        """Exécute un outil demandé par Claude. Renvoie (message pour Claude, est-ce une erreur)."""
        if outil == "se_deplacer" and entree.get("deplacement") in DEPLACEMENTS:
            return self.se_deplacer(entree["deplacement"]), False
        if outil == "exprimer" and entree.get("emotion") in EXPRESSIONS:
            eye.set_animation(self._suivant(), EXPRESSIONS[entree["emotion"]])
            return "fait", False
        if outil == "bouger_les_bras" and entree.get("geste") in GESTES:
            self.numero_geste += 1
            threading.Thread(
                target=self._jouer_geste, args=(GESTES[entree["geste"]], self.numero_geste), daemon=True
            ).start()
            return "geste en cours", False
        return f"Outil ou valeur inconnus : {outil} {entree}", True

    def fermer(self):
        self.en_vie = False
        self.arreter()
        self.passer_a("repos")
        arm.set_angle(self._suivant(), arm.ArmSide.Both, VITESSE_BRAS, BAS)
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
