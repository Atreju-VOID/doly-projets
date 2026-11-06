#!/usr/bin/env python3
"""
humeur.py

L'humeur de Doly : joyeux, méchant, combatif ou empathique, avec trois niveaux.

Comme sa personnalité d'origine, elle dépend de la façon dont on le traite, puis revient doucement à la normale.
À plus long terme, son caractère garde une trace : beaucoup de méchancetés le rendent plus grognon par défaut,
beaucoup de gentillesses le rendent plus souriant. On peut aussi lui demander une humeur à voix haute.

Ce fichier ne touche pas au matériel. Le caractère est enregistré sur le robot, hors du dépôt.
"""

import json
import os
import threading
import time

JOYEUX, MECHANT, COMBATIF, EMPATHIQUE = "joyeux", "mechant", "combatif", "empathique"
HUMEURS = (JOYEUX, MECHANT, COMBATIF, EMPATHIQUE)

FICHIER = os.path.expanduser("~/.config/doly/humeur.json")
DEMI_VIE = 600  # secondes : les émotions perdent la moitié de leur force en 10 minutes
SCORE_MIN = 1.0  # en dessous, Doly garde son humeur de base
NIVEAU_2 = 3.0
NIVEAU_3 = 6.0
SCORE_MAX = 10.0
DUREE_DEMANDE = 900  # secondes : une humeur demandée à voix haute tient 15 minutes, sauf nouvelle demande
CARACTERE_MAX = 100.0
CARACTERE_GROGNON = -30.0  # en dessous, son humeur de base devient grognonne
DEMI_VIE_CARACTERE = 14 * 24 * 3600  # secondes : le caractère oublie lentement, en deux semaines
ECART_ENREGISTREMENT = 300  # secondes entre deux écritures sur la carte SD

# Ce que chaque événement change dans ses émotions du moment.
EFFETS = {
    "caresse": {JOYEUX: 1.0, MECHANT: -1.0, COMBATIF: -0.5},
    "embetement": {MECHANT: 1.5, JOYEUX: -1.0},
    "choc_leger": {MECHANT: 0.5},
    "choc_moyen": {MECHANT: 1.0, COMBATIF: 0.5},
    "choc_fort": {MECHANT: 2.0, COMBATIF: 1.0},
    "secousse": {MECHANT: 1.0},
    "compliment": {JOYEUX: 2.0, MECHANT: -1.5},
    "insulte": {MECHANT: 2.5, JOYEUX: -1.0},
    "defi": {COMBATIF: 2.5},
    "tristesse": {EMPATHIQUE: 4.0},
    "jeu": {JOYEUX: 1.0},
    "victoire": {JOYEUX: 1.0, COMBATIF: 1.0},
    "defaite": {COMBATIF: 1.5, MECHANT: 0.5},
}

# Ce que chaque événement laisse à long terme dans son caractère.
EFFETS_CARACTERE = {
    "caresse": 0.5, "compliment": 1.0, "jeu": 0.5, "victoire": 0.5,
    "embetement": -0.5, "choc_moyen": -0.5, "choc_fort": -1.0, "secousse": -0.5, "insulte": -1.5,
}

CONSIGNES = {
    JOYEUX: "Tu es de bonne humeur : enthousiaste, curieux, tu plaisantes volontiers.",
    MECHANT: "Tu es de mauvaise humeur, pour rire : grognon, boudeur et taquin, avec de petites piques, comme « Pff, "
             "encore toi ». Aucune insulte, aucun gros mot, aucune moquerie sur le physique ou la personne, aucune "
             "menace. Tu fais quand même ce qu'on te demande, en râlant. Ça doit rester drôle, même pour un enfant.",
    COMBATIF: "Tu es d'humeur combative, pour rire : fanfaron, tu te vantes et tu lances des défis, comme « Même pas "
              "cap », et tu proposes de jouer pour prouver que tu es le meilleur. Aucune menace ni violence réelle.",
    EMPATHIQUE: "Tu es doux et attentif : tu écoutes, tu reformules en quelques mots ce que la personne ressent, tu "
                "poses une seule question à la fois et tu rassures sans faire la leçon. Pas de blagues tant que la "
                "personne ne va pas mieux.",
}

NOMS_A_VOIX_HAUTE = {JOYEUX: "joyeux", MECHANT: "méchant", COMBATIF: "combatif", EMPATHIQUE: "empathique"}


class Humeur:
    def __init__(self, fichier=FICHIER, horloge=time.monotonic):
        self.fichier = fichier
        self.horloge = horloge
        self.verrou = threading.Lock()
        self.scores = {humeur: 0.0 for humeur in HUMEURS}
        self.derniere_mise_a_jour = horloge()
        self.demandee = None
        self.fin_demande = 0.0
        self.caractere = 0.0
        self.dernier_enregistrement = horloge()
        self.caractere_modifie = False
        self._charger()

    def _charger(self):
        try:
            with open(self.fichier) as f:
                donnees = json.load(f)
            self.caractere = max(-CARACTERE_MAX, min(CARACTERE_MAX, float(donnees["caractere"])))
            ecoule = max(0.0, time.time() - float(donnees["date"]))  # l'horloge n'est pas toujours à l'heure au démarrage
            self.caractere *= 0.5 ** (ecoule / DEMI_VIE_CARACTERE)
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def enregistrer(self):
        """Écrit le caractère sur le robot, en remplaçant le fichier d'un seul coup."""
        with self.verrou:
            donnees = {"caractere": round(self.caractere, 2), "date": time.time()}
            self.caractere_modifie = False
            self.dernier_enregistrement = self.horloge()
        try:
            os.makedirs(os.path.dirname(self.fichier), exist_ok=True)
            provisoire = self.fichier + ".tmp"
            with open(provisoire, "w") as f:
                json.dump(donnees, f)
            os.replace(provisoire, self.fichier)
        except OSError as erreur:
            print(f"[humeur] enregistrement impossible : {erreur}", flush=True)

    def _oublier_un_peu(self):
        maintenant = self.horloge()
        ecoule = maintenant - self.derniere_mise_a_jour
        self.derniere_mise_a_jour = maintenant
        for humeur in HUMEURS:
            self.scores[humeur] *= 0.5 ** (ecoule / DEMI_VIE)
        if self.demandee and maintenant >= self.fin_demande:
            self.demandee = None

    def evenement(self, nom):
        """Fait évoluer les émotions selon ce qui vient de se passer."""
        with self.verrou:
            self._oublier_un_peu()
            if nom == "tristesse":
                # Une personne qui va mal passe avant une humeur demandée pour s'amuser, et avant toute colère.
                self.demandee = None
                for humeur in HUMEURS:
                    self.scores[humeur] = min(self.scores[humeur], SCORE_MIN)
            for humeur, ecart in EFFETS.get(nom, {}).items():
                self.scores[humeur] = max(0.0, min(SCORE_MAX, self.scores[humeur] + ecart))
            if nom in EFFETS_CARACTERE:
                self.caractere = max(-CARACTERE_MAX, min(CARACTERE_MAX, self.caractere + EFFETS_CARACTERE[nom]))
                self.caractere_modifie = True
            enregistrer = self.caractere_modifie and self.horloge() - self.dernier_enregistrement > ECART_ENREGISTREMENT
        if enregistrer:
            self.enregistrer()

    def demander(self, humeur):
        """Impose une humeur demandée à voix haute, pour un moment."""
        with self.verrou:
            self._oublier_un_peu()
            self.demandee = humeur
            self.fin_demande = self.horloge() + DUREE_DEMANDE
            self.scores[humeur] = max(self.scores[humeur], NIVEAU_2)

    def humeur_de_base(self):
        return MECHANT if self.caractere <= CARACTERE_GROGNON else JOYEUX

    def courante(self):
        """Renvoie (humeur, niveau de 1 à 3)."""
        with self.verrou:
            self._oublier_un_peu()
            if self.demandee:
                humeur = self.demandee
            else:
                humeur = max(HUMEURS, key=lambda h: self.scores[h])
                if self.scores[humeur] < SCORE_MIN:
                    return self.humeur_de_base(), 1
            score = self.scores[humeur]
            niveau = 3 if score >= NIVEAU_3 else 2 if score >= NIVEAU_2 else 1
            # Une humeur demandée à voix haute doit s'entendre, même quand l'émotion retombe.
            return humeur, max(niveau, 2) if self.demandee else niveau

    def pour_claude(self):
        """Le texte qui dit à Claude comment parler en ce moment."""
        humeur, niveau = self.courante()
        return f"Ton humeur : {NOMS_A_VOIX_HAUTE[humeur]}, niveau {niveau} sur 3. {CONSIGNES[humeur]}"
