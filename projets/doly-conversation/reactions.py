#!/usr/bin/env python3
"""
reactions.py

Les réactions spontanées de Doly : caresses, tapes agaçantes, chocs, secousses, quand on le soulève, ou quand une main
s'approche. Son humeur choisit la réaction et change selon la façon dont on le traite.

Il réagit seul avec les yeux, les LED, les bras et de petits sons, mais jamais avec les roues ni la parole. Rien de tout
cela ne part sur Internet, et il ne réagit que lorsqu'il est au repos.
"""

import collections
import random
import threading
import time
import xml.etree.ElementTree as ET

import doly_edge as edge
import doly_imu as imu

from animations import attente, bras, couleur, son_au_hasard, yeux
from corps import REGLAGES_DU_ROBOT
from humeur import COMBATIF, EMPATHIQUE, JOYEUX, MECHANT

PERIODE = 0.1  # secondes entre deux tours de surveillance
TOURS_PAR_LECTURE_VIDE = 2  # capteurs de vide : 5 fois par seconde
TOURS_PAR_LECTURE_MAIN = 3  # capteurs de proximité : une lecture dure 100 ms, environ 3 par seconde suffisent
ATTENTE_AU_DEMARRAGE = 5  # secondes : la centrale inertielle envoie parfois un faux choc juste après son démarrage
CALME_AVANT_CHOC = 1.5  # secondes de calme exigées : ses propres mouvements et ses sons secouent aussi la centrale
CALME_ENTRE_TAPES = 0.3  # secondes de calme exigées quand les chocs s'enchaînent
ECART_REACTIONS = 2.0  # secondes au minimum entre deux réactions aux chocs, à la main ou au sol
# Mesuré sur le robot : une tape sur sa tête le secoue assez pour ressembler à un choc, et le capteur tactile ne voit presque
# aucune tape très rapide (2 sur 12 secondes de tapes), alors que la centrale inertielle les voit toutes.
DELAI_GESTE = 0.25  # secondes : le capteur tactile signale une tape un peu après la centrale, on l'attend
TOUCHER_ET_CHOC = 1.0  # secondes : un choc aussi proche d'un toucher en vient sans doute
MEME_COUP = 0.35  # secondes : des chocs plus rapprochés que ça viennent du même coup
FENETRE_CHOCS = 3.5  # secondes
CHOCS_AGACE = 3  # tant de coups dans la fenêtre : on l'embête, comme avec des tapes rapides
ECART_EMBETE = 0.5  # secondes : tant qu'on l'embête, il réagit dès qu'il a fini sa réaction précédente
FENETRE_ESCALADE = 30  # secondes : plus on l'embête dans ce temps, plus il se fâche
DUREE_MAX_APPUI = 90  # secondes : ensuite, la conversation reprend la main, pour surveiller la batterie
ECART_MAIN = 1.0  # secondes au minimum entre deux regards vers une main
DISTANCE_MAIN = 130  # mm : une main plus proche que ça. Le capteur la voit jusqu'à 20 cm, mais dans un champ étroit.
DISTANCE_MAIN_PARTIE = 160  # mm : au-delà, on considère qu'elle est partie
ECART_LATERAL = 20  # mm d'écart entre les deux capteurs pour dire qu'elle arrive d'un côté
DUREE_CONFIRMATION_AIR = 0.3  # secondes en l'air avant de dire qu'on l'a soulevé
FENETRE_CARESSES = 20  # secondes : plus il y a de caresses dans ce temps, plus il est content
FENETRE_TAPES_RAPIDES = 2.5  # secondes
TAPES_RAPIDES_AGACE = 4  # tant de tapes dans la fenêtre : on l'embête
IDEE_MIN, IDEE_MAX = 40, 120  # secondes entre deux petites expressions au repos
INACTIVITE_AVANT_SOMMEIL = 600  # secondes sans interaction, la nuit, avant de s'endormir
SOMMEIL_PAR_DEFAUT = (22, 8)  # heures, les mêmes que sa personnalité d'origine

NIVEAU_DES_CHOCS = {
    imu.ImuGesture.ShockLight: 1,
    imu.ImuGesture.ShockMedium: 2,
    imu.ImuGesture.ShockHard: 3,
    imu.ImuGesture.ShockExtreme: 3,
}
SECOUSSES = (imu.ImuGesture.LongShake, imu.ImuGesture.ShortShake)
CHOCS_PAR_DIRECTION = {
    imu.GestureDirection.Front: ("shock_bf_1", "shock_bf_2", "shock_bf_3"),
    imu.GestureDirection.Back: ("shock_bf_1", "shock_bf_2", "shock_bf_3"),
    imu.GestureDirection.Left: ("shock_l_1", "shock_lr_2", "shock_l_3"),
    imu.GestureDirection.Right: ("shock_r_1", "shock_lr_2", "shock_r_3"),
    imu.GestureDirection.Up: ("shock_ud_1", "shock_ud_2", "shock_ud_3"),
    imu.GestureDirection.Down: ("shock_ud_1", "shock_ud_2", "shock_ud_3"),
}
# Un côté soulevé ou au-dessus du vide. Le soulever en entier est traité à part.
VIDES_PAR_DIRECTION = {
    edge.GapDirection.Front: "gap_f",
    edge.GapDirection.Front_Left: "gap_fl",
    edge.GapDirection.Front_Right: "gap_fr",
    edge.GapDirection.Back: "gap_b",
    edge.GapDirection.Back_Left: "gap_l",
    edge.GapDirection.Back_Right: "gap_r",
    edge.GapDirection.Left: "gap_l",
    edge.GapDirection.Right: "gap_r",
}
ECART_VIDES = 10.0  # secondes au minimum entre deux réactions à un côté soulevé
ATTENTE_VIDE = 0.4  # secondes avant de réagir à un côté soulevé
COLERE = ("angry1_1", "angry1_2", "angry1_3", "angry1_4")
GRANDE_COLERE = ("angry2_1", "angry2_2", "angry2_3")

# Un doigt gardé posé sans parler : (après combien de secondes, réactions possibles, effet sur son humeur).
APPUI_LONG = (
    (0, ("petting3",), "caresse"),
    (5, ("love_1",), "caresse"),
    (12, ("annoy1",), "embetement"),
    (20, ("annoy2",), "embetement"),
    (30, COLERE, "embetement"),
    (42, GRANDE_COLERE, "embetement"),
    (54, GRANDE_COLERE, "embetement"),
    (66, GRANDE_COLERE, "embetement"),
    (78, GRANDE_COLERE, "embetement"),
)
APPUI_LONG_FACHE = (
    (0, ("annoy1",), "embetement"),
    (6, ("annoy2",), "embetement"),
    (14, COLERE, "embetement"),
    (24, GRANDE_COLERE, "embetement"),
    (36, GRANDE_COLERE, "embetement"),
    (48, GRANDE_COLERE, "embetement"),
    (60, GRANDE_COLERE, "embetement"),
    (72, GRANDE_COLERE, "embetement"),
)

REGARDS_AU_REPOS = {
    JOYEUX: ("LOOK LEFT", "LOOK RIGHT", "LOOK UP", "SPARKLING", "CHEERFUL"),
    MECHANT: ("FED UP", "IRRITATED", "IMPATIENT", "ANNOYED"),
    COMBATIF: ("FOCUS", "CONCENTRATE", "HEATED", "SQUINT RL"),
    EMPATHIQUE: ("BLINK SLOW", "SHY", "ADMIRING"),
}
# Une main juste devant lui, au milieu. Sur un côté, il regarde franchement vers elle, quelle que soit son humeur.
REGARDS_MAIN = {JOYEUX: "GET BIGGER", MECHANT: "IRRITATED", COMBATIF: "HOSTILE", EMPATHIQUE: "ADMIRING"}


def lire_heures_de_sommeil(chemin=REGLAGES_DU_ROBOT):
    """Lit les heures de sommeil choisies dans l'appli officielle : (heure de coucher, heure de réveil)."""
    try:
        sommeil = ET.parse(chemin).getroot().find("Sleep")
        return int(sommeil.get("StartH")), int(sommeil.get("EndH"))
    except (OSError, ET.ParseError, AttributeError, TypeError, ValueError):
        return SOMMEIL_PAR_DEFAUT


def c_est_la_nuit(heure, coucher, reveil):
    return coucher <= heure or heure < reveil if coucher > reveil else coucher <= heure < reveil


def _secoue():
    return [yeux("DIZZY L"), son_au_hasard("SHAKE"), yeux("DIZZY R")]


def _pique_combative():
    return [yeux("HOSTILE"), couleur("#ff6600"), son_au_hasard("ATTACK"), bras("0", 70, 50), attente(700),
            bras("0", 0, 50, immediat=False), couleur("#000000", immediat=False)]


def _souleve():
    return [yeux("CAUTIOUS"), son_au_hasard("CARRY")]


def _repose():
    return [yeux("BLINK SLOW"), son_au_hasard("RELIEVE")]


class Reactions:
    def __init__(self, corps, humeur, au_repos, horloge=time.monotonic, dernier_toucher=lambda: None):
        self.corps = corps
        self.humeur = humeur
        self.au_repos = au_repos  # fonction : vrai si Doly ne fait rien d'autre
        self.horloge = horloge
        self.dernier_toucher = dernier_toucher  # fonction : l'instant du dernier toucher, ou None
        self.chocs = collections.deque(maxlen=20)  # instants des derniers chocs, même quand il est occupé à réagir
        self.embetements = collections.deque()
        self.prochain_embetement = 0.0
        self.en_vie = False
        self.fil = None
        self.gestes = collections.deque(maxlen=8)
        self.dernier_geste = None  # (instant, geste, direction), même quand il ne réagit pas : pour taper dans la main
        self.vides = collections.deque(maxlen=8)
        self.prochain_vide = 0.0
        self.tapes = collections.deque()
        self.en_reaction = False
        self.debut = horloge()
        self.calme_depuis = horloge()
        self.prochaine_reaction = 0.0
        self.prochaine_main = 0.0
        self.prochaine_idee = horloge() + random.uniform(IDEE_MIN, IDEE_MAX)
        self.derniere_interaction = horloge()
        self.air_depuis = None
        self.etait_en_l_air = None  # None : pas encore de référence, par exemple après une phase occupée
        self.main_presente = None
        self.regard_main = None
        self.dort_de_nuit = False
        self.heures_de_sommeil = lire_heures_de_sommeil()
        self.tour = 0

    def demarrer(self):
        self.en_vie = True
        self.debut = self.horloge()
        imu.on_gesture(self._au_geste)
        edge.on_gap_detect(self._au_vide)
        self.fil = threading.Thread(target=self._boucle, daemon=True)
        self.fil.start()

    def arreter(self):
        self.en_vie = False
        imu.clear_listeners()
        edge.clear_listeners()
        if self.fil is not None:
            self.fil.join(1)

    def _au_geste(self, geste, direction):
        # Appelé par un fil interne du SDK : on note l'événement, et il est traité dans notre boucle.
        evenement = (self.horloge(), geste, direction)
        self.gestes.append(evenement)
        self.dernier_geste = evenement
        if geste in NIVEAU_DES_CHOCS and not self.corps.en_mouvement():
            # Mesuré sur le robot : une seule poussette le fait vibrer et donne plusieurs chocs de suite.
            if not self.chocs or evenement[0] - self.chocs[-1] >= MEME_COUP:
                self.chocs.append(evenement[0])

    def _au_vide(self, direction):
        self.vides.append((self.horloge(), direction))

    def joue(self):
        """Vrai si l'animation en cours est une de ses réactions spontanées."""
        return self.en_reaction and self.corps.animateur.en_cours()

    def noter_interaction(self):
        """À appeler quand quelqu'un s'occupe de lui : il ne s'endort pas, et il se réveille s'il dormait de nuit."""
        self.derniere_interaction = self.horloge()
        self.dort_de_nuit = False

    def _jouer(self, quoi, raison):
        print(f"[reaction] {raison}", flush=True)
        self.en_reaction = True
        if isinstance(quoi, str):
            self.corps.animateur.jouer(quoi, roues=False)
        else:
            self.corps.animateur.jouer_blocs(quoi, roues=False, nom=raison)

    def _boucle(self):
        while self.en_vie:
            time.sleep(PERIODE)
            try:
                self._un_tour()
            except Exception as erreur:  # une réaction ratée ne doit jamais faire tomber la conversation
                print(f"[reaction] {type(erreur).__name__} {erreur}", flush=True)

    def _un_tour(self):
        maintenant = self.horloge()
        self.tour += 1
        if not self.au_repos() or self.corps.en_mouvement():
            # Il est occupé : ce qui arrive maintenant ne compte pas, et les capteurs repartiront d'une nouvelle référence.
            self.calme_depuis = maintenant
            self.gestes.clear()
            self.vides.clear()
            self.etait_en_l_air = None
            self.main_presente = None
            self.air_depuis = None
            return
        if self.en_reaction:
            self.en_reaction = False
            self.calme_depuis = maintenant
        self._regarder_les_gestes(maintenant)
        self._regarder_les_vides(maintenant)
        if self.tour % TOURS_PAR_LECTURE_VIDE == 0:
            self._regarder_le_sol(maintenant)
        if self.tour % TOURS_PAR_LECTURE_MAIN == 0 and not self.corps.dort:
            self._regarder_la_main(maintenant)
        self._vivre_au_repos(maintenant)

    def _regarder_les_gestes(self, maintenant):
        while self.gestes:
            instant, geste, direction = self.gestes[0]
            if maintenant - instant < DELAI_GESTE:
                return
            self.gestes.popleft()
            toucher = self.dernier_toucher()
            if instant - self.debut < ATTENTE_AU_DEMARRAGE or (toucher is not None and abs(instant - toucher) < TOUCHER_ET_CHOC):
                continue
            if self.corps.en_l_air():
                continue  # on le porte : ce n'est pas un choc
            calme = instant - self.calme_depuis
            if geste in NIVEAU_DES_CHOCS:
                self._au_choc(NIVEAU_DES_CHOCS[geste], direction, maintenant, calme)
            elif (geste in SECOUSSES and calme >= CALME_AVANT_CHOC and not self.corps.dort
                  and maintenant >= self.prochaine_reaction):
                self.humeur.evenement("secousse")
                self.noter_interaction()
                self.prochaine_reaction = maintenant + ECART_REACTIONS
                self._jouer(_secoue(), "secousse")

    def _regarder_les_vides(self, maintenant):
        while self.vides:
            instant, direction = self.vides[0]
            if maintenant - instant < ATTENTE_VIDE:
                return  # quand on le soulève en entier, les capteurs lâchent l'un après l'autre : on laisse le temps de le voir
            self.vides.popleft()
            print(f"[capteur] vide : {direction}", flush=True)
            if instant - self.debut < ATTENTE_AU_DEMARRAGE or instant - self.calme_depuis < CALME_AVANT_CHOC:
                continue
            animation = VIDES_PAR_DIRECTION.get(direction)
            if animation and not self.corps.dort and maintenant >= self.prochain_vide and not self.corps.en_l_air():
                self.prochain_vide = maintenant + ECART_VIDES
                self.prochaine_reaction = maintenant + ECART_REACTIONS
                self.noter_interaction()
                self._jouer(animation, "un côté soulevé")

    def _embete_par_les_chocs(self, maintenant, calme):
        """Plusieurs chocs rapprochés : c'est qu'on l'embête. Renvoie True s'il réagit."""
        if self.corps.dort or calme < CALME_ENTRE_TAPES or maintenant < self.prochain_embetement:
            return False
        if sum(1 for instant in self.chocs if maintenant - instant < FENETRE_CHOCS) < CHOCS_AGACE:
            return False
        self.prochain_embetement = maintenant + ECART_EMBETE
        self.prochaine_reaction = maintenant + ECART_REACTIONS
        self.noter_interaction()
        self._quand_on_l_embete()
        return True

    def _au_choc(self, niveau, direction, maintenant, calme):
        print(f"[capteur] choc de niveau {niveau}, direction {direction}", flush=True)
        if self._embete_par_les_chocs(maintenant, calme):
            return
        if maintenant < self.prochaine_reaction or calme < CALME_AVANT_CHOC:
            return
        if self.corps.dort:
            if niveau >= 2:  # un frôlement ne le réveille pas
                self.noter_interaction()
                self.corps.reveiller()
            return
        self.prochaine_reaction = maintenant + ECART_REACTIONS
        self.noter_interaction()
        self.humeur.evenement(("choc_leger", "choc_moyen", "choc_fort")[niveau - 1])
        humeur, niveau_humeur = self.humeur.courante()
        if humeur == MECHANT and niveau_humeur >= 2:
            self._jouer(random.choice(GRANDE_COLERE if niveau >= 2 else COLERE), f"choc {niveau}, en colère")
        elif humeur == COMBATIF and niveau >= 2:
            self._jouer(_pique_combative(), f"choc {niveau}, combatif")
        else:
            self._jouer(CHOCS_PAR_DIRECTION[direction][niveau - 1], f"choc {niveau}")

    def _regarder_le_sol(self, maintenant):
        en_l_air = self.corps.en_l_air()
        if self.etait_en_l_air is None:
            self.etait_en_l_air = en_l_air
            self.air_depuis = None
            return
        if en_l_air and not self.etait_en_l_air:
            # Confirmé sur quelques lectures, pour ne pas confondre avec une ombre ou un sol sombre sur un capteur.
            if self.air_depuis is None:
                self.air_depuis = maintenant
            elif maintenant - self.air_depuis >= DUREE_CONFIRMATION_AIR:
                self.etait_en_l_air = True
                self.air_depuis = None
                self.noter_interaction()
                self.corps.reveiller(silencieux=True)
                if maintenant >= self.prochaine_reaction:
                    self.prochaine_reaction = maintenant + ECART_REACTIONS
                    self._jouer(_souleve(), "soulevé")
        elif not en_l_air and self.etait_en_l_air:
            self.etait_en_l_air = False
            self.air_depuis = None
            self.noter_interaction()
            if maintenant >= self.prochaine_reaction:
                self.prochaine_reaction = maintenant + ECART_REACTIONS
                self._jouer(_repose(), "reposé")
        else:
            self.air_depuis = None

    def _regarder_la_main(self, maintenant):
        gauche, droite = self.corps.distances()
        proches = [d for d in (gauche, droite) if d is not None]
        plus_proche = min(proches) if proches else None
        proche = plus_proche is not None and plus_proche < DISTANCE_MAIN
        if gauche is not None and (droite is None or gauche < droite - ECART_LATERAL):
            regard = "LOOK LEFT"
        elif droite is not None and (gauche is None or droite < gauche - ECART_LATERAL):
            regard = "LOOK RIGHT"
        else:
            regard = REGARDS_MAIN[self.humeur.courante()[0]]
        if self.main_presente is None:
            # Première lecture : un objet posé là depuis le début n'est pas une main qui s'approche.
            self.main_presente = proche
            self.regard_main = regard if proche else None
        elif self.main_presente and (plus_proche is None or plus_proche > DISTANCE_MAIN_PARTIE):
            self.main_presente = False
            self.regard_main = None
        elif proche and regard != self.regard_main and maintenant >= self.prochaine_main:
            # Elle vient d'arriver, ou elle est passée de l'autre côté : il la suit des yeux.
            self.main_presente = True
            if self.corps.regard(regard):
                print(f"[capteur] main : {regard}", flush=True)
                self.regard_main = regard
                self.prochaine_main = maintenant + ECART_MAIN
                self.noter_interaction()

    def _vivre_au_repos(self, maintenant):
        coucher, reveil = self.heures_de_sommeil
        nuit = c_est_la_nuit(time.localtime().tm_hour, coucher, reveil)
        if self.corps.dort:
            if self.dort_de_nuit and not nuit:  # le matin, il se réveille tout seul et sans bruit
                self.dort_de_nuit = False
                self.corps.reveiller(silencieux=True)
            return
        if nuit and maintenant - self.derniere_interaction > INACTIVITE_AVANT_SOMMEIL:
            print("[reaction] il s'endort pour la nuit", flush=True)
            self.dort_de_nuit = True
            self.corps.dormir(silencieux=True)
            return
        if maintenant >= self.prochaine_idee:
            self.prochaine_idee = maintenant + random.uniform(IDEE_MIN, IDEE_MAX)
            self.corps.regard(random.choice(REGARDS_AU_REPOS[self.humeur.courante()[0]]))

    def tape(self, cote_gauche):
        """Une tape brève sur un capteur tactile. C'est la conversation qui les repère, car un toucher long sert à parler."""
        maintenant = self.horloge()
        self.noter_interaction()
        if self.corps.dort:
            self.corps.reveiller()
            return
        self.tapes.append(maintenant)
        while self.tapes and maintenant - self.tapes[0] > FENETRE_CARESSES:
            self.tapes.popleft()
        rapides = sum(1 for instant in self.tapes if maintenant - instant < FENETRE_TAPES_RAPIDES)
        if rapides >= TAPES_RAPIDES_AGACE:
            self._quand_on_l_embete(cote_gauche)
        else:
            self._quand_on_le_caresse()

    def appui_long(self, encore_touche):
        """Un doigt gardé posé sans parler : il apprécie, puis il finit par s'agacer. Revient quand le doigt se lève."""
        debut = self.horloge()
        self.noter_interaction()
        etapes = list(APPUI_LONG_FACHE if self.humeur.courante()[0] in (MECHANT, COMBATIF) else APPUI_LONG)
        while encore_touche() and self.horloge() - debut < DUREE_MAX_APPUI:
            ecoule = self.horloge() - debut
            if etapes and ecoule >= etapes[0][0]:
                _, reactions, evenement = etapes.pop(0)
                self.humeur.evenement(evenement)
                self._jouer(random.choice(reactions), f"doigt posé depuis {ecoule:.0f} s de plus")
            time.sleep(0.05)

    def _quand_on_l_embete(self, cote_gauche=None):
        """cote_gauche : None si on ne sait pas d'où viennent les tapes, parce que seule la centrale inertielle les a senties."""
        maintenant = self.horloge()
        self.embetements.append(maintenant)
        while maintenant - self.embetements[0] > FENETRE_ESCALADE:
            self.embetements.popleft()
        rang = len(self.embetements)  # plus on insiste, plus il se fâche
        self.humeur.evenement("embetement")
        humeur, niveau_humeur = self.humeur.courante()
        cote = "" if cote_gauche is None else "_l" if cote_gauche else "_r"
        if humeur == COMBATIF:
            self._jouer(_pique_combative(), "embêté, combatif")
        elif rang >= 4 or (humeur == MECHANT and niveau_humeur >= 3):
            self._jouer(random.choice(GRANDE_COLERE), "embêté, grande colère")
        elif rang == 3 or (humeur == MECHANT and niveau_humeur == 2):
            self._jouer(random.choice(COLERE), "embêté, en colère")
        else:
            self._jouer(f"annoy{rang}{cote}", "embêté")

    def _quand_on_le_caresse(self):
        self.humeur.evenement("caresse")
        humeur, niveau_humeur = self.humeur.courante()
        nombre = len(self.tapes)
        if humeur == MECHANT and niveau_humeur >= 2:
            self._jouer("annoy1", "caresse, encore fâché")
        elif nombre >= 8:
            self._jouer("love_1", "caresses : amour")
        else:
            self._jouer(f"petting{3 if nombre >= 6 else 2 if nombre >= 3 else 1}", f"caresse {nombre}")
