#!/usr/bin/env python3
"""
capacites.py

Tout ce que Claude peut demander à Doly en plus de son corps : météo, photo, heure, minuteur, jeux, humeur, scènes,
imitations d'animaux et couleurs. Les valeurs possibles sont fixées ici, et chaque outil a ses propres limites.
"""

import random
import time

import meteo as service_meteo
from animations import attente, chemin_son, couleur, son, yeux
from corps import OUTILS as OUTILS_DU_CORPS, air_de_defi
from humeur import COMBATIF, EMPATHIQUE, JOYEUX, MECHANT
from jeux import JEUX, Partie
from photo import prendre_photo

DUREE_METEO = 8  # secondes d'animation sur les yeux
DUREE_HEURE = 7  # secondes d'affichage sur les yeux
DUREE_COMPTE_A_REBOURS = 10  # secondes
MINUTEUR_MAX = 12 * 3600  # secondes

JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
        "décembre")
MOIS_COURTS = ("JAN", "FEV", "MAR", "AVR", "MAI", "JUN", "JUL", "AOU", "SEP", "OCT", "NOV", "DEC")

COULEURS = {
    "rouge": "Red", "orange": "Orange", "jaune": "Yellow", "vert": "Green", "bleu": "Blue", "bleu_ciel": "SkyBlue",
    "bleu_marine": "DarkBlue", "violet": "Purple", "rose": "Pink", "marron": "Brown", "noir": "Black", "blanc": "White",
    "gris": "Gray", "cyan": "Cyan", "magenta": "Magenta", "dore": "Gold", "citron_vert": "Lime",
}
FORMES_DES_YEUX = {
    "classique": "Classic", "moderne": "Modern", "espace": "Space", "orbite": "Orbit", "lumineux": "Glow",
    "numerique": "Digi",
}
ANIMAUX = {
    "abeille": "BEE", "ane": "DONKEY", "baleine": "WHALE", "canard": "DUCK", "chat": "CAT", "cheval": "HORSE",
    "chien": "DOG", "chimpanze": "CHIMPANZEE", "cochon": "PIG", "coq": "ROOSTER", "corbeau": "CROW", "coyote": "COYOTE",
    "dauphin": "DOLPHIN", "elephant": "ELEPHANT", "gibbon": "GIBBON", "grenouille": "FROG", "hibou": "OWL",
    "kookaburra": "KOOKABURRA", "leopard": "LEOPARD", "lion": "LION", "loup": "WOLF", "mouton": "SHEEP", "oie": "GOOSE",
    "oiseau": "BIRD", "ours": "BEAR", "poule": "CHICKEN", "serpent": "SNAKE", "tigre": "TIGER", "vache": "COW",
    "zebre": "ZEBRA",
}

# Les scènes qui peuvent faire rouler Doly un peu, seulement parce qu'on les lui a demandées.
SCENES_QUI_ROULENT = {
    "danser": ("salsa", "salsa", "salsa_fail"),  # une chance sur trois de rater, comme sa personnalité d'origine
    "s_amuser": ("roll_around", "twist", "rock"),
    "faire_du_sport": ("workout",),
}
# Les scènes jouées sur place.
SCENES_SUR_PLACE = {"policier": "policeman", "pompier": "fireman", "mediter": "meditate", "eternuer": "sneeze"}
# Les pensées affichées sur les deux yeux : (séquence, durée en secondes, son).
PENSEES = {
    "imaginer_la_plage": ("i_summer", 7, ("SFX", "BEACH")),
    "imaginer_le_sport": ("i_exercise", 5, None),
    "imaginer_un_livre": ("i_book", 4, None),
    "imaginer_la_realite_virtuelle": ("i_vr", 5, None),
}
AUTRES_SCENES = ("anniversaire", "dormir", "se_reveiller")
SCENES = sorted((*SCENES_QUI_ROULENT, *SCENES_SUR_PLACE, *PENSEES, *AUTRES_SCENES))

EVENEMENTS = {
    "compliment": "compliment", "insulte": "insulte", "defi": "defi", "tristesse": "tristesse",
    "demande_joyeux": JOYEUX, "demande_mechant": MECHANT, "demande_combatif": COMBATIF, "demande_empathique": EMPATHIQUE,
}


def _ecoute_douce():
    return [yeux("LOW"), couleur("#6600cc"), attente(1500), couleur("#000000", immediat=False)]


def _outil(nom, description, proprietes):
    return {
        "name": nom,
        "description": description,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": proprietes,
            "required": sorted(proprietes),
            "additionalProperties": False,
        },
    }


OUTILS = OUTILS_DU_CORPS + [
    _outil("ressentir", "Fait évoluer ton humeur. Pour un compliment, une insulte ou une moquerie, un défi lancé, une "
                        "personne triste, ou quand on te demande d'adopter une humeur, même celle que tu as déjà. Pas pour "
                        "une simple question sur ton humeur. Répond comment parler désormais.",
           {"evenement": {"type": "string", "enum": sorted(EVENEMENTS)}}),
    _outil("meteo", "Donne la météo réelle. ville : vide pour la maison. retenir_ville : vrai si on te dit que c'est "
                    "désormais la ville de la maison. Montre aussi la météo sur tes yeux.",
           {"ville": {"type": "string"},
            "quand": {"type": "string", "enum": list(service_meteo.QUAND)},
            "retenir_ville": {"type": "boolean"}}),
    _outil("prendre_photo", "Prend une photo avec ta caméra, seulement si on te le demande. Elle reste sur le robot, et "
                            "ni toi ni personne d'autre ne la voit à ce moment-là.", {}),
    _outil("montrer_sur_les_yeux", "Affiche quelques secondes sur tes yeux l'heure, la date ou le temps restant du minuteur, "
                                   "seulement si on te demande de le montrer. Pour une simple question, réponds sans cet outil.",
           {"quoi": {"type": "string", "enum": ["heure", "date", "minuteur"]}}),
    _outil("minuteur", "Démarre ou annule le minuteur, ou donne le temps restant. secondes : la durée, 0 pour annuler ou "
                       "consulter. Doly sonne tout seul à la fin.",
           {"action": {"type": "string", "enum": ["demarrer", "annuler", "consulter"]},
            "secondes": {"type": "integer"}}),
    _outil("jouer", "Lance un jeu juste après ta phrase. Il explique lui-même ses règles, et dure une à deux minutes. "
                    "roue : hasard avec des fruits. defi_eclair : réflexes. doly_dort : approcher sa main sans te "
                    "réveiller. tope_la : taper dans ta main. check : faire un check.",
           {"jeu": {"type": "string", "enum": sorted(JEUX)}}),
    _outil("jouer_scene", "Joue une petite scène, seulement si on te la demande ou si on t'annonce un anniversaire. danser, "
                          "s_amuser et faire_du_sport peuvent te faire rouler un peu. Répond si tu l'as faite sur place.",
           {"scene": {"type": "string", "enum": SCENES}}),
    _outil("imiter_animal", "Imite le cri d'un animal.", {"animal": {"type": "string", "enum": sorted(ANIMAUX)}}),
    _outil("changer_couleur", "Change la couleur de tes yeux, du fond de tes yeux ou de tes LED au repos. Doly s'en souvient.",
           {"partie": {"type": "string", "enum": ["yeux", "fond", "led"]},
            "couleur": {"type": "string", "enum": sorted(COULEURS)}}),
    _outil("changer_forme_des_yeux", "Change la forme de tes yeux. Doly s'en souvient.",
           {"forme": {"type": "string", "enum": sorted(FORMES_DES_YEUX)}}),
]


class Minuteur:
    """Un seul minuteur à la fois. La conversation regarde s'il est fini, et se charge de sonner."""

    def __init__(self, horloge=time.monotonic):
        self.horloge = horloge
        self.fin = None
        self.duree = 0

    def demarrer(self, secondes):
        self.fin = self.horloge() + secondes
        self.duree = secondes

    def annuler(self):
        self.fin = None

    def actif(self):
        return self.fin is not None

    def restant(self):
        return max(0.0, self.fin - self.horloge()) if self.fin is not None else 0.0

    def echu(self):
        return self.fin is not None and self.horloge() >= self.fin


def dire_duree(secondes):
    """Écrit une durée pour la voix : « 1 heure 5 minutes », « 30 secondes »."""
    heures, reste = divmod(int(round(secondes)), 3600)
    minutes, secondes = divmod(reste, 60)
    morceaux = []
    if heures:
        morceaux.append(f"{heures} heure" + ("s" if heures > 1 else ""))
    if minutes:
        morceaux.append(f"{minutes} minute" + ("s" if minutes > 1 else ""))
    if secondes or not morceaux:
        morceaux.append(f"{secondes} seconde" + ("s" if secondes > 1 else ""))
    return " ".join(morceaux)


class BaseInconnue:
    """Quand on ne sait pas où il est : par exemple sans capteur de courant. C'est le cas le plus prudent."""

    def sur_base(self):
        return None

    def en_charge(self):
        return False

    def pour_claude(self):
        return None

    def pour_le_journal(self):
        return "base inconnue"


class Capacites:
    def __init__(self, corps, voix, humeur, reactions=None, base=None):
        self.corps = corps
        self.voix = voix
        self.humeur = humeur
        self.reactions = reactions
        self.base = base or BaseInconnue()
        self.minuteur = Minuteur()
        self.jeu_demande = None  # le jeu démarre quand Doly a fini sa phrase
        self.en_jeu = False
        self.resultats = []  # à transmettre à Claude à la phrase suivante

    def etat_pour_claude(self):
        """Ce que Claude doit savoir à chaque phrase. Lu à chaque fois : Doly peut rester allumé plusieurs jours."""
        maintenant = time.localtime()
        # Essayé sur Haiku 5.5 : sans cette première phrase, il prend ce message pour une de ses réponses et dit qu'il
        # ne connaît pas l'heure.
        lignes = ["Informations du robot, exactes à cet instant, à utiliser pour répondre.",
                  f"Date : {JOURS[maintenant.tm_wday]} {maintenant.tm_mday} {MOIS[maintenant.tm_mon - 1]} {maintenant.tm_year}.",
                  f"Heure : {maintenant.tm_hour} h {maintenant.tm_min:02d}.",
                  f"Batterie : {self.corps.batterie()} pour cent.",
                  self.humeur.pour_claude()]
        ou_il_est = self.base.pour_claude()
        if ou_il_est:
            lignes.insert(4, ou_il_est)
        if self.minuteur.actif():
            lignes.append(f"Il reste {dire_duree(self.minuteur.restant())} au minuteur.")
        lignes.extend(self.resultats)
        self.resultats = []
        return " ".join(lignes)

    def executer(self, outil, entree):
        """Exécute un outil demandé par Claude. Renvoie (message pour Claude, est-ce une erreur)."""
        fonction = getattr(self, "_outil_" + outil, None)
        try:
            if fonction is None:
                return self.corps.executer(outil, entree)
            return fonction(**entree), False
        except Exception as erreur:  # un outil raté ne doit pas laisser Claude sans résultat, ni couper la réponse
            print(f"[outil] {outil} : {type(erreur).__name__} {erreur}", flush=True)
            return f"L'outil a échoué ({type(erreur).__name__}).", True

    def _outil_ressentir(self, evenement):
        cible = EVENEMENTS[evenement]
        if evenement.startswith("demande_"):
            self.humeur.demander(cible)
            animation = {JOYEUX: "happy_1", MECHANT: "angry1_2", COMBATIF: air_de_defi, EMPATHIQUE: _ecoute_douce}[cible]
        else:
            self.humeur.evenement(cible)
            humeur, niveau = self.humeur.courante()
            if cible == "compliment":
                animation = f"compliment_{random.randint(1, 5)}"
            elif cible == "insulte":
                animation = "bad_robot_1" if humeur == MECHANT and niveau >= 2 else f"rudeness_{random.randint(1, 7)}"
            elif cible == "defi":
                animation = air_de_defi
            else:
                animation = _ecoute_douce
        if callable(animation):
            self.corps.animateur.jouer_blocs(animation(), roues=False, nom=evenement)
        else:
            self.corps.animateur.jouer(animation, roues=False)
        return self.humeur.pour_claude()

    def _outil_meteo(self, ville, quand, retenir_ville):
        try:
            texte, sequence = service_meteo.meteo(ville, quand, retenir_ville)
        except service_meteo.ErreurMeteo as erreur:
            return str(erreur)
        self.corps.ecran.jouer_sequences([sequence], DUREE_METEO)
        return texte

    def _outil_prendre_photo(self):
        self.corps.animateur.jouer("photo", roues=False)
        chemin, raison = prendre_photo()
        return "Photo prise et gardée sur le robot." if chemin else f"Photo ratée : {raison}."

    def _outil_montrer_sur_les_yeux(self, quoi):
        maintenant = time.localtime()
        if quoi == "heure":
            self.corps.ecran.montrer_texte(f"{maintenant.tm_hour:02d}", f"{maintenant.tm_min:02d}", DUREE_HEURE)
        elif quoi == "date":
            self.corps.ecran.montrer_texte(f"{maintenant.tm_mday:02d}", MOIS_COURTS[maintenant.tm_mon - 1], DUREE_HEURE)
        elif not self.minuteur.actif():
            return "Il n'y a pas de minuteur en cours."
        else:
            self.corps.ecran.compte_a_rebours(self.minuteur.restant, DUREE_COMPTE_A_REBOURS)
        return "C'est affiché. Dis-le aussi à voix haute."

    def _outil_minuteur(self, action, secondes):
        if action == "annuler":
            actif = self.minuteur.actif()
            self.minuteur.annuler()
            return "Minuteur annulé." if actif else "Il n'y avait pas de minuteur."
        if action == "consulter":
            if not self.minuteur.actif():
                return "Il n'y a pas de minuteur en cours."
            return f"Il reste {dire_duree(self.minuteur.restant())}."
        if not 1 <= secondes <= MINUTEUR_MAX:
            return "Refusé : le minuteur va de une seconde à douze heures."
        self.minuteur.demarrer(secondes)
        return f"Minuteur de {dire_duree(secondes)} démarré."

    def _outil_jouer(self, jeu):
        if jeu not in JEUX:
            raise ValueError(jeu)
        self.jeu_demande = jeu
        return "Le jeu démarre dès que tu as fini ta phrase. Ne donne pas les règles."

    def _outil_jouer_scene(self, scene):
        animateur = self.corps.animateur
        if scene in SCENES_QUI_ROULENT:
            return self.corps.animation_avec_roues(random.choice(SCENES_QUI_ROULENT[scene]))
        if scene in SCENES_SUR_PLACE:
            animateur.jouer(SCENES_SUR_PLACE[scene], roues=False)
        elif scene in PENSEES:
            sequence, duree, bruit = PENSEES[scene]
            self.corps.ecran.jouer_sequences([sequence], duree)
            if bruit:
                self.voix.jouer_son(chemin_son(*bruit))
        elif scene == "anniversaire":
            self.corps.ecran.jouer_sequences(["bcake", "confetti"], 12, fond=(20, 20, 70))
            self.voix.jouer_son(chemin_son("MUSIC", "BIRTHDAY"))
        elif scene == "dormir":
            self.corps.dormir()
        elif scene == "se_reveiller":
            self.corps.reveiller()
        else:
            raise ValueError(scene)
        return "C'est parti."

    def _outil_imiter_animal(self, animal):
        self.corps.animateur.jouer_blocs([yeux("EXCITED"), son("ANIMAL", ANIMAUX[animal])], roues=False, nom=animal)
        return "C'est fait, n'ajoute rien."

    def _outil_changer_couleur(self, partie, couleur):
        self.corps.changer_style(partie, COULEURS[couleur])
        self.corps.animateur.jouer("eye_color" if partie != "led" else "led_color", roues=False)
        return "C'est fait."

    def _outil_changer_forme_des_yeux(self, forme):
        self.corps.changer_style("forme", FORMES_DES_YEUX[forme])
        self.corps.animateur.jouer("eye_color", roues=False)
        return "C'est fait."

    def oublier_jeu(self):
        self.jeu_demande = None

    def lancer_jeu_demande(self):
        """Lance le jeu demandé par Claude, s'il y en a un, et attend sa fin."""
        nom, self.jeu_demande = self.jeu_demande, None
        if nom is None:
            return False
        self.en_jeu = True
        try:
            resume = JEUX[nom](Partie(self.corps, self.voix, self.humeur, self.reactions))
            print(f"[jeu] {resume}", flush=True)
            self.resultats.append(f"Dernière partie : {resume}")
        except Exception as erreur:  # un jeu raté ne doit jamais faire tomber la conversation
            print(f"[jeu] {nom} : {type(erreur).__name__} {erreur}", flush=True)
            self.resultats.append("Le jeu vient de planter : excuse-toi avec humour.")
            self.corps.ecran.arreter()
        finally:
            self.en_jeu = False
        return True
