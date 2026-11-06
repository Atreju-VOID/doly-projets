#!/usr/bin/env python3
"""
jeux.py

Les jeux de Doly, avec ses yeux comme écrans. Sa personnalité d'origine propose trois jeux dont les règles ne sont pas
publiées : ceux-ci ont leurs propres règles, et se contentent d'utiliser les images et les sons déjà présents sur le robot.

- La roue : un jeu de hasard, chaque œil est une roue de fruits.
- Le défi éclair : un jeu de réflexes, appuie vite au-dessus de l'œil qui s'allume. Trois vies.
- Doly dort : attends qu'il ronfle, approche ta main sans te faire voir, et appuie sur sa tête sans le réveiller.

Il y a aussi les gestes complices : taper dans la main et faire un check.

Chaque fonction de jeu tourne jusqu'à sa fin et renvoie une phrase qui résume la partie, pour la suite de la conversation.
"""

import json
import os
import random
import time

import doly_arm as arm
import doly_touch as touch

from animations import chemin_son
from ecran import DOSSIER_IMAGES, charger_png, disque, ecrire, poser, pour_ecran

FICHIER_RECORDS = os.path.expanduser("~/.config/doly/records.json")
ATTENTE_MAX_TOUCHER = 15  # secondes sans réponse avant de terminer le jeu
INTERVALLE_SONDAGE = 0.01  # secondes

# La roue
FRUITS = ("apple", "banana", "cherries", "lemon", "strawberry")
MANCHES_ROUE = 5
CHANCE_PAIRE = 0.3  # la probabilité d'avoir les deux mêmes fruits
IMAGES_PAR_SECONDE_ROUE = 12
ARRET_ROUE_1 = 1.6  # secondes de rotation de la première roue, à gauche pour la personne en face
ARRET_ROUE_2 = 2.6
INTERVALLE_TIC = 0.3  # secondes entre deux bruits de roue

# Le défi éclair
TEMPS_DEPART = 3.0  # secondes pour répondre au début
TEMPS_MIN = 1.0
TEMPS_EN_MOINS_PAR_NIVEAU = 0.4
PAUSE_AVANT_DEFI = 2.5  # secondes entre le toucher qui lance la partie et la première cible
# Mesuré sur le robot : le capteur voit un appui franc 7 fois sur 8, et une tape très courte après un repos 1 fois sur 8.
# Une tape qu'il n'a pas vue ne doit donc pas terminer la partie.
VIES_DEFI = 3
POINTS_PAR_NIVEAU = 5
NIVEAU_DES_DEUX_COTES = 2  # à partir de ce niveau, il faut parfois toucher les deux côtés à la fois
PAUSE_MIN, PAUSE_MAX = 0.3, 0.9  # secondes entre deux cibles

# Doly dort
DUREE_MAX_DODO = 90  # secondes
ENDORMISSEMENT_MIN, ENDORMISSEMENT_MAX = 3.0, 6.0  # secondes avant qu'il ronfle : appuyer plus tôt ne marche pas
RONFLEMENT = "SLEEP (1)"
ENTRE_DEUX_REGARDS_MIN, ENTRE_DEUX_REGARDS_MAX = 2.0, 5.0  # secondes
BOUGE_TROP = 20  # mm : la main ne doit pas bouger plus que ça pendant qu'il a un œil ouvert
PORTEE_SURE = 150  # mm : au-delà, le capteur est à sa limite et ses mesures vont et viennent

# Taper dans la main
ATTENTE_MAIN = 6  # secondes pour taper dans sa main
DISTANCE_MAIN = 70  # mm


class Partie:
    """Ce dont un jeu a besoin : le corps de Doly, sa voix, son humeur et ses réactions."""

    def __init__(self, corps, voix, humeur, reactions=None):
        self.corps = corps
        self.voix = voix
        self.humeur = humeur
        self.reactions = reactions
        self.ecran = corps.ecran

    def dire(self, phrase):
        """Dit une phrase et attend qu'elle soit finie."""
        self.voix.dire(phrase)
        self.voix.attendre_fin()

    def son(self, famille, nom):
        return self.voix.jouer_son(chemin_son(famille, nom))

    def touche(self):
        """Renvoie (gauche touché, droite touché)."""
        return touch.is_touched(touch.TouchSide.Left), touch.is_touched(touch.TouchSide.Right)

    def attendre_relachement(self, delai=2.0):
        fin = time.monotonic() + delai
        while any(self.touche()) and time.monotonic() < fin:
            time.sleep(INTERVALLE_SONDAGE)

    def attendre_toucher(self, delai=ATTENTE_MAX_TOUCHER):
        """Attend un toucher. Renvoie False si personne n'a touché à temps."""
        self.attendre_relachement()
        fin = time.monotonic() + delai
        while time.monotonic() < fin:
            if any(self.touche()):
                return True
            time.sleep(INTERVALLE_SONDAGE)
        return False

    def distance_main(self):
        """Distance en mm de ce qui est devant lui, ou None si rien n'est à portée (une lecture dure 100 ms)."""
        return self.corps.obstacle_devant()

    def animation(self, nom):
        """Joue une animation sans roues et attend qu'elle soit finie."""
        self.corps.animateur.jouer(nom, roues=False)
        self.corps.animateur.attendre_fin(10)


def lire_records():
    try:
        with open(FICHIER_RECORDS) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def ecrire_record(nom, valeur):
    """Retient le meilleur score. Renvoie True si c'est un nouveau record."""
    records = lire_records()
    if valeur <= records.get(nom, 0):
        return False
    records[nom] = valeur
    try:
        os.makedirs(os.path.dirname(FICHIER_RECORDS), exist_ok=True)
        with open(FICHIER_RECORDS, "w") as f:
            json.dump(records, f)
    except OSError as erreur:
        print(f"[jeu] enregistrement impossible : {erreur}", flush=True)
    return True


def tirer_fruits():
    """Tire le résultat des deux roues."""
    gauche = random.choice(FRUITS)
    if random.random() < CHANCE_PAIRE:
        return gauche, gauche
    return gauche, random.choice([f for f in FRUITS if f != gauche])


def jouer_roue(partie):
    casino = DOSSIER_IMAGES + "/casino/"
    decor = charger_png(casino + "retro_1.png")
    images = {fruit: pour_ecran(poser(decor, charger_png(casino + fruit + ".png"))) for fruit in FRUITS}
    pret = pour_ecran(poser(decor, charger_png(casino + "ready.png")))
    gagne = pour_ecran(poser(decor, charger_png(casino + "winner.png")))
    gros_lot = pour_ecran(poser(decor, charger_png(casino + "jackpot.png")))

    partie.ecran.verrouiller()
    gagnees = 0
    jouees = 0
    try:
        partie.ecran.afficher(pret)
        partie.dire("La roue ! Touche ma tête pour lancer. Deux fruits pareils, et tu gagnes.")
        for _ in range(MANCHES_ROUE):
            partie.ecran.afficher(pret)
            if not partie.attendre_toucher():
                break
            jouees += 1
            partie.son("SFX", "SLOT LEVER")
            fruit_1, fruit_2 = tirer_fruits()
            debut = time.monotonic()
            prochain_tic = debut
            rang = random.randrange(len(FRUITS))
            while True:
                ecoule = time.monotonic() - debut
                if ecoule >= ARRET_ROUE_2:
                    break
                rang += 1
                en_cours_1 = fruit_1 if ecoule >= ARRET_ROUE_1 else FRUITS[rang % len(FRUITS)]
                partie.ecran.afficher_a_lire(images[en_cours_1], images[FRUITS[(rang + 2) % len(FRUITS)]])
                if time.monotonic() >= prochain_tic:
                    prochain_tic += INTERVALLE_TIC
                    partie.son("SFX", "SLOT TURN")
                time.sleep(1 / IMAGES_PAR_SECONDE_ROUE)
            partie.ecran.afficher_a_lire(images[fruit_1], images[fruit_2])
            if fruit_1 == fruit_2:
                gagnees += 1
                gros = fruit_1 == "cherries"
                time.sleep(0.5)
                partie.ecran.afficher(gros_lot if gros else gagne)
                partie.son("SFX", "SLOT JACKPOT" if gros else "SLOT WINNER").wait(8)
            else:
                partie.son("SFX", "SLOT LOOSER").wait(3)
                time.sleep(0.5)
    finally:
        partie.ecran.liberer()
    partie.humeur.evenement("jeu")
    if not jouees:
        return "La roue : personne n'a joué."
    partie.animation("happy_1" if gagnees else "doly_lost_1")
    resume = f"La roue : tu as gagné {gagnees} fois sur {jouees}."
    partie.dire(f"Tu as gagné {gagnees} fois sur {jouees} !" if gagnees else "Pas de chance, rien cette fois.")
    return resume


def cible_du_defi(niveau):
    """Choisit les côtés à toucher : (gauche, droite)."""
    if niveau >= NIVEAU_DES_DEUX_COTES and random.random() < 0.2:
        return True, True
    return random.choice(((True, False), (False, True)))


def temps_du_niveau(niveau):
    return max(TEMPS_MIN, TEMPS_DEPART - TEMPS_EN_MOINS_PAR_NIVEAU * (niveau - 1))


def attendre_reponse(partie, gauche_attendu, droite_attendu, delai):
    """Attend que le bon côté soit touché. Renvoie "bon", "faux" ou "trop_tard".

    Un doigt resté posé depuis la cible précédente ne compte pas : il faut un nouveau contact."""
    deja_gauche, deja_droite = partie.touche()
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        gauche, droite = partie.touche()
        deja_gauche = deja_gauche and gauche
        deja_droite = deja_droite and droite
        gauche = gauche and not deja_gauche
        droite = droite and not deja_droite
        if (gauche and not gauche_attendu) or (droite and not droite_attendu):
            return "faux"
        if (gauche or not gauche_attendu) and (droite or not droite_attendu):
            return "bon"
        time.sleep(INTERVALLE_SONDAGE)
    return "trop_tard"


def score_sur_panneau(panneau, points):
    """Écrit le score dans le cadre blanc de l'image match_score, mesuré sur le robot : de y = 107 à y = 174, sur 198 points de large."""
    return ecrire(panneau, str(points), (20, 40, 160), centre_y=140, largeur_max=150, hauteur_max=45)


def jouer_defi(partie):
    match = DOSSIER_IMAGES + "/match/"
    decor = charger_png(match + "retro_3.png")
    vide = pour_ecran(decor)
    allume = pour_ecran(disque(decor, (255, 220, 0)))
    niveau_superieur = pour_ecran(poser(decor, charger_png(match + "level_up.png")))
    fin_de_partie = pour_ecran(charger_png(match + "match_over.png"))
    panneau = charger_png(match + "match_score.png")

    partie.ecran.verrouiller()
    points = 0
    niveau = 1
    vies = VIES_DEFI
    try:
        partie.ecran.afficher(vide)
        partie.dire("Défi éclair ! Appuie vite au-dessus de l'œil qui s'allume, franchement, comme sur un bouton. Si les deux "
                    f"s'allument, appuie des deux côtés. Tu as {VIES_DEFI} vies. Touche ma tête pour commencer.")
        if not partie.attendre_toucher():
            return "Le défi éclair : personne n'a joué."
        partie.attendre_relachement()
        partie.ecran.afficher(vide)
        time.sleep(PAUSE_AVANT_DEFI)
        while True:
            gauche_attendu, droite_attendu = cible_du_defi(niveau)
            partie.ecran.afficher(allume if gauche_attendu else vide, allume if droite_attendu else vide)
            depart = time.monotonic()
            reponse = attendre_reponse(partie, gauche_attendu, droite_attendu, temps_du_niveau(niveau))
            print(f"[défi] niveau {niveau}, gauche {gauche_attendu}, droite {droite_attendu} : {reponse} en "
                  f"{time.monotonic() - depart:.2f} s", flush=True)
            partie.ecran.afficher(vide)
            if reponse == "bon":
                points += 1
                partie.son("SFX", "COLLECT")
                partie.attendre_relachement(1.0)
                if points % POINTS_PAR_NIVEAU == 0:
                    niveau += 1
                    partie.ecran.afficher(niveau_superieur)
                    partie.son("SFX", "LEVEL UP").wait(3)
                    partie.ecran.afficher(vide)
            else:
                vies -= 1
                if not vies:
                    break
                partie.dire("Raté ! Dernière vie." if vies == 1 else f"Raté ! Plus que {vies} vies.")
            time.sleep(random.uniform(PAUSE_MIN, PAUSE_MAX))
        partie.son("SFX", "LOST (1)")
        partie.ecran.afficher(fin_de_partie)
        time.sleep(1.5)
        partie.ecran.afficher(pour_ecran(score_sur_panneau(panneau, points)))
        record = ecrire_record("defi_eclair", points)
        message = f"Tu as fait {points} points" + (", c'est un nouveau record !" if record and points else " !")
        partie.dire(message)
        time.sleep(1.0)
    finally:
        partie.ecran.liberer()
    partie.humeur.evenement("victoire" if points < 10 else "defaite")  # Doly gagne quand tu perds tôt
    return f"Le défi éclair : {points} points, niveau {niveau}."


def jouer_doly_dort(partie):
    partie.dire("Je vais dormir. Attends que je ronfle, puis approche ta main tout doucement et appuie sur ma tête. "
                "Si j'ouvre un œil, ne bouge plus !")
    corps = partie.corps
    corps.dormir(silencieux=True, tamiser=False)  # il faut bien voir quand il ouvre un œil
    gagne = None
    trop_tot = False
    try:
        # Sans cette attente, appuyer tout de suite suffit pour gagner : c'est ce qu'on fait naturellement.
        fin_endormissement = time.monotonic() + random.uniform(ENDORMISSEMENT_MIN, ENDORMISSEMENT_MAX)
        while time.monotonic() < fin_endormissement and not trop_tot:
            trop_tot = any(partie.touche())
            time.sleep(0.02)
        if trop_tot:
            gagne = False
        else:
            ronflement = partie.son("DOLY", RONFLEMENT)
            debut = time.monotonic()
            # Le premier regard peut venir très vite : appuyer dès le premier ronflement reste risqué.
            prochain_regard = debut + random.uniform(ENTRE_DEUX_REGARDS_MIN / 4, ENTRE_DEUX_REGARDS_MAX)
        while gagne is None:
            maintenant = time.monotonic()
            if maintenant - debut > DUREE_MAX_DODO:
                break
            if any(partie.touche()):
                gagne = True
            elif maintenant >= prochain_regard:
                partie.voix.interrompre()  # il arrête de ronfler quand il ouvre un œil : un signal de plus pour s'arrêter
                if regard_en_coin(partie):
                    gagne = False
                prochain_regard = time.monotonic() + random.uniform(ENTRE_DEUX_REGARDS_MIN, ENTRE_DEUX_REGARDS_MAX)
                ronflement = partie.son("DOLY", RONFLEMENT)
            else:
                if ronflement.is_set():
                    ronflement = partie.son("DOLY", RONFLEMENT)
                time.sleep(0.02)
    finally:
        partie.voix.interrompre()
        corps.reveiller(silencieux=True)
    if gagne is None:
        partie.dire("Finalement, je me suis vraiment endormi. Tu as mis trop de temps !")
        partie.humeur.evenement("defaite")
        return "Doly dort : personne n'a touché sa tête à temps."
    if gagne:
        partie.animation("happy_2")
        partie.dire("Bravo, tu m'as eu ! Je n'ai rien vu venir.")
        partie.humeur.evenement("defaite")
        return "Doly dort : tu as touché sa tête sans le réveiller, tu as gagné."
    partie.animation(random.choice(("angry1_1", "angry1_3")))
    partie.dire("Trop tôt ! Je ne dormais pas encore." if trop_tot else "Je t'ai vu ! Ta main a bougé.")
    partie.humeur.evenement("victoire")
    return "Doly dort : touché trop tôt, Doly a gagné." if trop_tot else "Doly dort : Doly t'a vu bouger, il a gagné."


def regard_en_coin(partie):
    """Il ouvre un œil pendant moins de 2 s. Renvoie True s'il a vu la main bouger ou toucher sa tête."""
    partie.corps.ouvrir_un_oeil(random.choice(("AWAKE L", "AWAKE R")))
    time.sleep(0.45)  # le temps que l'œil s'ouvre : c'est le signal pour s'arrêter
    reference = partie.distance_main()
    fin = time.monotonic() + 1.0
    vu = False
    while time.monotonic() < fin and not vu:
        if any(partie.touche()):
            vu = True
            break
        distance = partie.distance_main()
        if reference is None:
            vu = distance is not None and distance < PORTEE_SURE  # une main vient d'apparaître
        elif distance is None:
            vu = reference < PORTEE_SURE  # une main proche ne peut pas disparaître sans bouger
        else:
            vu = abs(distance - reference) > BOUGE_TROP
    return vu


def taper_dans_la_main(partie, check=False):
    """Lève un bras et attend qu'on tape dedans. S'il est de très mauvaise humeur, il refuse."""
    corps = partie.corps
    humeur, niveau = partie.humeur.courante()
    refus = "fist_bump_angry" if check else "five_angry"
    if humeur == "mechant" and niveau >= 2:
        partie.animation("fist_ready_angry" if check else "five_ready_angry")
        partie.animation(refus)
        return "Tu as tendu la main, mais Doly a boudé."
    corps.tendre_un_bras(arm.ArmSide.Right, 90, 40)
    partie.animation("fist_ready" if check else "high_five_ready")
    arrivee = time.monotonic() + 3
    while arm.get_state(arm.ArmSide.Right) == arm.ArmState.Running and time.monotonic() < arrivee:
        time.sleep(0.02)
    time.sleep(0.3)  # le temps que le bras se calme : son mouvement secoue aussi la centrale inertielle
    depart = time.monotonic()
    tape = False
    while time.monotonic() < depart + ATTENTE_MAIN and not tape:
        dernier = partie.reactions.dernier_geste if partie.reactions else None
        distance = partie.distance_main()
        tape = (any(partie.touche())
                or (dernier is not None and dernier[0] > depart)
                or (distance is not None and distance < DISTANCE_MAIN))
    corps.relacher_le_bras()
    if not tape:
        partie.animation(refus)
        return "Personne n'a tapé dans la main de Doly."
    partie.animation("fist_bump" if check else "high_five")
    partie.humeur.evenement("caresse")
    return "Tu as tapé dans la main de Doly."


JEUX = {
    "roue": jouer_roue,
    "defi_eclair": jouer_defi,
    "doly_dort": jouer_doly_dort,
    "tope_la": lambda partie: taper_dans_la_main(partie),
    "check": lambda partie: taper_dans_la_main(partie, check=True),
}
