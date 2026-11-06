#!/usr/bin/env python3
"""
tester_fonctions.py

Test guidé des fonctions de Doly, à faire à côté de lui. Doly explique chaque étape à voix haute, et le résultat s'écrit
à l'écran. Les parties se lancent une par une, voir GUIDE_DE_TEST.md.

Arrête d'abord l'appli : sudo systemctl stop doly-francais

Usage, sur le robot :
    ~/doly-env/bin/python tester_fonctions.py            # affiche la liste des parties
    ~/doly-env/bin/python tester_fonctions.py sons
"""

import os
import subprocess
import sys
import threading
import time

import doly_helper as helper
import doly_touch as touch

# dire.py est dans le projet voisin.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "doly-parle"))
from dire import service_doly_actif

import jeux
import toucher
from animations import chemin_son
from capacites import SCENES_QUI_ROULENT, Capacites
from converser import SILENCE_AVANT_CALIN, Conversation, Voix, capteur_touche
from corps import Corps
from ecran import disque, fond_uni, pour_ecran
from humeur import MECHANT, Humeur
from photo import prendre_photo
from reactions import Reactions, _pique_combative


class Banc:
    """Le matériel réel, et de quoi annoncer ce qu'il faut faire."""

    def __init__(self):
        self.corps = Corps()
        self.voix = Voix()
        self.corps.animateur.jouer_son = self.voix.jouer_son
        self.humeur = Humeur()
        self.capacites = Capacites(self.corps, self.voix, self.humeur)
        self.conversation = Conversation(self.voix, None, None, self.corps, self.capacites)
        self.reactions = Reactions(self.corps, self.humeur, self.conversation.au_repos, dernier_toucher=toucher.dernier_evenement)
        self.capacites.reactions = self.reactions
        self.conversation.reactions = self.reactions
        self.partie = jeux.Partie(self.corps, self.voix, self.humeur, self.reactions)

    def dire(self, phrase):
        print(f"[doly] {phrase}", flush=True)
        self.voix.dire(phrase)
        self.voix.attendre_fin()

    def attendre_fin_animation(self):
        self.corps.animateur.attendre_fin(40)
        self.voix.attendre_fin()

    def fermer(self):
        self.voix.fermer()
        self.corps.fermer()


def partie_yeux(banc):
    """Le sens de lecture, l'heure, la météo, une scène, et le retour à ses yeux normaux."""
    banc.corps.passer_a("repos")
    banc.dire("Regarde mes yeux. Tu dois lire un à ta gauche, et deux à ta droite.")
    banc.corps.ecran.montrer_texte("1", "2", 5)
    time.sleep(5.3)
    banc.dire("Maintenant, l'heure : les heures à ta gauche, les minutes à ta droite.")
    maintenant = time.localtime()
    banc.corps.ecran.montrer_texte(f"{maintenant.tm_hour:02d}", f"{maintenant.tm_min:02d}", 4)
    time.sleep(4.3)
    for nom, phrase in (("weather/sunny", "Du soleil."), ("weather/rain", "De la pluie."), ("weather/snow_n", "De la neige, la nuit.")):
        banc.dire(phrase)
        banc.corps.ecran.jouer_sequences([nom], 3)
        time.sleep(3.3)
    banc.dire("Un gâteau d'anniversaire.")
    banc.corps.ecran.jouer_sequences(["bcake", "confetti"], 6, fond=(20, 20, 70))
    time.sleep(6.3)
    banc.dire("Une pensée, avec une plage.")
    banc.corps.ecran.jouer_sequences(["i_summer"], 4)
    time.sleep(4.3)
    banc.dire("Je cligne des yeux normalement. Dis-moi si quelque chose reste affiché par erreur.")
    time.sleep(5)


def partie_sons(banc):
    """Le volume de ses petits sons, comparé à sa voix."""
    banc.dire("Voici ma voix. Écoute si mes petits sons sont bien au même niveau.")
    for famille, nom in (("DOLY", "HAPPY (4)"), ("DOLY", "ANGRY (19)"), ("DOLY", "ATTACK (5)"), ("DOLY", "LAUGH (5)"), ("SFX", "CAMERA CLICK"),
                         ("SFX", "SLOT WINNER"), ("SFX", "SLOT LOOSER"), ("ANIMAL", "CAT"), ("ANIMAL", "LION")):
        print(f"[son] {famille} {nom}", flush=True)
        banc.voix.jouer_son(chemin_son(famille, nom)).wait(10)
        time.sleep(0.4)
    banc.dire("Encore ma voix, pour comparer. Et un bout de musique.")
    banc.voix.jouer_son(chemin_son("MUSIC", "SALSA"))
    time.sleep(4)
    banc.voix.interrompre()


def partie_cotes(banc):
    """Vérifie que le capteur tactile et l'œil de chaque côté se correspondent, ce que le défi éclair suppose."""
    decor = fond_uni(0, 0, 0)
    allume = pour_ecran(disque(decor, (255, 220, 0)))
    eteint = pour_ecran(decor)
    banc.corps.ecran.verrouiller()
    try:
        for nom, gauche, droite in (("gauche de Doly", allume, eteint), ("droite de Doly", eteint, allume)):
            banc.corps.ecran.afficher(gauche, droite)
            banc.voix.dire("Touche le capteur juste au-dessus de l'œil allumé.")  # le toucher compte dès cette phrase
            fin = time.monotonic() + 12
            cote = None
            while time.monotonic() < fin and cote is None:
                if touch.is_touched(touch.TouchSide.Left):
                    cote = "gauche"
                elif touch.is_touched(touch.TouchSide.Right):
                    cote = "droite"
                time.sleep(0.01)
            print(f"[résultat] œil allumé : {nom} ; capteur touché : {cote}", flush=True)
            while capteur_touche():
                time.sleep(0.05)
    finally:
        banc.corps.ecran.liberer()


def _reagir_librement(banc, duree):
    """Laisse Doly réagir comme dans la conversation, pendant un moment. Les touchers sont classés comme dans l'appli."""
    banc.corps.passer_a("repos")
    banc.reactions.demarrer()
    fin = time.monotonic() + duree
    while time.monotonic() < fin:
        if capteur_touche():
            joue = banc.reactions.joue()
            banc.corps.arreter()
            banc.voix.interrompre()
            cote = banc.conversation.tape_breve()
            if cote:
                print(f"[toucher] tape, côté {cote}{' (pendant une réaction)' if joue else ''}", flush=True)
                banc.reactions.tape(cote == "gauche")
            else:
                print("[toucher] long : dans l'appli, Doly écoute après le bip", flush=True)
                gauche = toucher.touche_a_gauche()
                banc.voix.jouer_bip()
                depart = time.monotonic()
                while capteur_touche() and time.monotonic() - depart < SILENCE_AVANT_CALIN:
                    time.sleep(0.05)
                if capteur_touche():
                    print("[toucher] doigt gardé posé, sans parler", flush=True)
                    banc.reactions.appui_long(capteur_touche)
                else:
                    banc.reactions.tape(gauche)
        time.sleep(0.02)
    banc.reactions.arreter()
    humeur, niveau = banc.humeur.courante()
    print(f"[humeur] {humeur}, niveau {niveau}", flush=True)
    banc.attendre_fin_animation()


def partie_toucher(banc):
    """Caresses, tapes rapides et toucher long."""
    banc.dire("Tape une fois sur ma tête, puis attends quelques secondes. Recommence plusieurs fois. Je dois être de plus en plus "
              "content. Tu as quarante secondes.")
    _reagir_librement(banc, 40)
    banc.dire("Maintenant, tape très vite, encore et encore, pendant vingt secondes. Je dois m'agacer de plus en plus.")
    _reagir_librement(banc, 20)
    banc.dire("Attends que je me calme.")
    time.sleep(4)
    banc.dire("Pour finir, garde le doigt posé sans parler, pendant quarante secondes. Tu dois entendre un bip, puis je dois "
              "apprécier, et finir par m'agacer.")
    _reagir_librement(banc, 45)


def partie_chocs(banc):
    """Les chocs et les secousses."""
    banc.dire("Donne-moi de petites poussettes, d'abord doucement sur le côté, puis un peu plus fort, devant et derrière. Attends "
              "ma réaction entre deux. Tu as quarante-cinq secondes.")
    _reagir_librement(banc, 45)


def partie_soulever(banc):
    """Quand on le soulève et qu'on le repose."""
    banc.dire("Soulève-moi bien droit, avec les deux mains, puis repose-moi. Recommence une ou deux fois. Tu as trente secondes.")
    _reagir_librement(banc, 30)
    banc.dire("Maintenant, soulève doucement un seul côté, reste comme ça deux secondes, puis repose-moi. Attends dix secondes "
              "entre deux essais. Tu as quarante secondes.")
    _reagir_librement(banc, 40)


def partie_main(banc):
    """Une main qui s'approche : seuls ses yeux réagissent."""
    banc.dire("Approche ta main devant mes yeux, puis retire-la. Essaie à gauche, à droite et au milieu. Seuls mes yeux doivent "
              "réagir, sans son. Tu as trente secondes.")
    _reagir_librement(banc, 30)


def partie_bras(banc):
    """Les réactions qui bougent les bras, et l'arrêt au toucher."""
    banc.dire("Je vais bouger les bras. Garde tes doigts loin d'eux, et dis-moi si c'est trop brusque.")
    for nom in ("annoy2_l", "annoy2_r", "angry3_1", "hand_up", "meditate"):
        print(f"[animation] {nom}", flush=True)
        banc.corps.animateur.jouer(nom, roues=False)
        banc.attendre_fin_animation()
        time.sleep(1)
    print("[animation] pique combative", flush=True)
    banc.corps.animateur.jouer_blocs(_pique_combative(), roues=False, nom="pique")
    banc.attendre_fin_animation()
    banc.dire("Maintenant, je lève les bras. Touche ma tête pendant que je bouge. Je dois m'arrêter, puis les baisser "
              "doucement quatre secondes plus tard.")
    banc.corps.animateur.jouer("policeman", roues=False)
    fin = time.monotonic() + 12
    while time.monotonic() < fin and not capteur_touche():
        time.sleep(0.02)
    touche = capteur_touche()
    banc.corps.arreter()
    banc.voix.interrompre()
    print(f"[résultat] touché : {touche}, bras à baisser : {banc.corps.bras_a_baisser}", flush=True)
    time.sleep(7)
    banc.dire("C'est bon.")


def partie_photo(banc):
    """Une vraie photo, à regarder pour vérifier qu'elle est à l'endroit."""
    banc.dire("Je vais prendre une photo. Elle reste sur moi.")
    banc.corps.animateur.jouer("photo", roues=False)
    debut = time.monotonic()
    chemin, raison = prendre_photo()
    print(f"[résultat] {chemin or raison}, en {time.monotonic() - debut:.1f} s", flush=True)
    banc.attendre_fin_animation()


def partie_minuteur(banc):
    """Une sonnerie, et l'arrêt au toucher."""
    banc.dire("Un minuteur de cinq secondes. Il doit sonner, et s'arrêter si tu me touches.")
    banc.capacites.minuteur.demarrer(5)
    banc.corps.ecran.compte_a_rebours(banc.capacites.minuteur.restant, 4)
    time.sleep(5.3)
    banc.conversation.sonner()
    banc.attendre_fin_animation()


def partie_roue(banc):
    """Le jeu de la roue."""
    print("[résultat]", jeux.jouer_roue(banc.partie), flush=True)


def partie_defi(banc):
    """Le jeu du défi éclair."""
    print("[résultat]", jeux.jouer_defi(banc.partie), flush=True)


def partie_dodo(banc):
    """Le jeu Doly dort."""
    print("[résultat]", jeux.jouer_doly_dort(banc.partie), flush=True)


def partie_tope(banc):
    """Taper dans sa main, faire un check, et son refus quand il est de très mauvaise humeur."""
    banc.capacites.en_jeu = True  # comme dans l'appli : pas de réaction spontanée pendant le geste
    banc.reactions.demarrer()  # pour sentir le choc dans sa main
    banc.dire("Tape dans ma main quand je la lève.")
    print("[résultat]", jeux.taper_dans_la_main(banc.partie), flush=True)
    banc.dire("Et maintenant un check.")
    print("[résultat]", jeux.taper_dans_la_main(banc.partie, check=True), flush=True)
    banc.humeur.demander(MECHANT)
    banc.dire("Je suis fâché. Tope là ? Non.")
    print("[résultat]", jeux.taper_dans_la_main(banc.partie), flush=True)
    banc.humeur.demandee = None
    banc.reactions.arreter()


def partie_scenes(banc):
    """Les scènes qui font rouler Doly, au sol uniquement. Un toucher arrête tout."""
    banc.dire("Attention, je vais rouler un peu. Pose-moi par terre, avec un mètre de libre autour de moi. Un toucher sur ma tête "
              "m'arrête.")
    time.sleep(8)
    if not banc.corps.sol_sous_lui():
        banc.dire("Je ne sens pas le sol sous moi. On arrête là.")
        print("[résultat] pas de sol : test arrêté", flush=True)
        return
    surveiller = {"actif": True}

    def surveiller_toucher():
        etait_touche = False
        while surveiller["actif"]:
            touche = capteur_touche()
            if touche and not etait_touche:
                print("[toucher] arrêt", flush=True)
                banc.corps.arreter()
                banc.voix.interrompre()
            etait_touche = touche
            time.sleep(0.02)

    threading.Thread(target=surveiller_toucher, daemon=True).start()
    try:
        annonces = {"danser": "Je danse.", "s_amuser": "Je m'amuse.", "faire_du_sport": "Je fais du sport."}
        for scene, noms in SCENES_QUI_ROULENT.items():
            for nom in dict.fromkeys(noms):  # la danse réussie figure deux fois dans la liste
                banc.corps.deplacements_restants = 5
                banc.dire(annonces[scene])
                debut = time.monotonic()
                print(f"[scène] {nom} : {banc.corps.animation_avec_roues(nom)}", flush=True)
                banc.attendre_fin_animation()
                print(f"[résultat] {nom} : {time.monotonic() - debut:.1f} s, incident : {banc.corps.animateur.dernier_incident}", flush=True)
                time.sleep(1.5)
    finally:
        surveiller["actif"] = False


PARTIES = {
    "yeux": partie_yeux, "sons": partie_sons, "cotes": partie_cotes, "toucher": partie_toucher, "chocs": partie_chocs,
    "soulever": partie_soulever, "main": partie_main, "bras": partie_bras, "photo": partie_photo, "minuteur": partie_minuteur,
    "roue": partie_roue, "defi": partie_defi, "dodo": partie_dodo, "tope": partie_tope, "scenes": partie_scenes,
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in PARTIES:
        print("Parties :")
        for nom, fonction in PARTIES.items():
            print(f"  {nom:10s} {(fonction.__doc__ or nom).strip().splitlines()[0]}")
        return 2
    if subprocess.run(["systemctl", "is-active", "--quiet", "doly-francais"]).returncode == 0:
        print("L'appli tourne encore. Arrête-la d'abord : sudo systemctl stop doly-francais")
        return 1
    relancer_service = service_doly_actif()
    if helper.stop_doly_service() < 0:
        print("[erreur] Impossible d'arrêter le service Doly.")
        return 1
    os.environ.setdefault("RES_OPTIONS", "single-request timeout:1")
    banc = None
    try:
        if touch.init() < 0:
            print("[erreur] Capteurs tactiles indisponibles.")
            return 1
        toucher.demarrer()
        banc = Banc()
        print(f"[info] Batterie {banc.corps.batterie()} %, sol : {banc.corps.sol_sous_lui()}", flush=True)
        PARTIES[sys.argv[1]](banc)
    finally:
        if banc:
            banc.fermer()
        toucher.arreter()
        touch.dispose()
        if relancer_service:
            subprocess.run(["sudo", "-n", "systemctl", "start", "doly"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
