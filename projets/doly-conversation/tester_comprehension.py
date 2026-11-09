#!/usr/bin/env python3
"""
tester_comprehension.py

Test guidé de la compréhension. Doly te fait répéter une dizaine de phrases dans quatre situations : à 1 m, à 3 m, télé
allumée, puis avec une autre voix. Il donne ensuite, en français, la part des mots compris dans chaque situation, et
combien de fois il a reconnu « Hé Doly ».

La transcription suit le même chemin que dans l'appli : le guetteur cherche « Hé Doly », puis seule la suite est
transcrite, avec le même modèle Vosk.

Chaque essai est enregistré sur le robot, dans ~/doly-comprehension/<date et heure>/, et ce programme n'efface jamais
rien : les mêmes sons pourront servir plus tard à comparer un autre moteur de reconnaissance (--relire). Ces
enregistrements ne quittent pas le robot. Pour les effacer, supprime le dossier.

Arrête d'abord l'appli : sudo systemctl stop doly-francais

Usage, sur le robot :
    ~/doly-env/bin/python tester_comprehension.py                   # les 4 situations
    ~/doly-env/bin/python tester_comprehension.py 3m tele           # seulement celles-ci : 1m, 3m, tele, autre
    ~/doly-env/bin/python tester_comprehension.py --relire ~/doly-comprehension/2026-11-09_10-30-00
"""

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
import unicodedata
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "doly-parle"))

from micro import TAILLE_BLOC, TAUX, Micro, SuiviDeVoix, commande_arecord, volume

DOSSIER = os.path.expanduser("~/doly-comprehension")
FICHIER_ESSAIS = "essais.json"

# Des phrases typiques, comme on lui en dit vraiment. Les nombres sont écrits en lettres, comme Vosk les rend.
PHRASES = [
    "Hé Doly, quelle heure est-il ?",
    "Hé Doly, quel temps fera-t-il demain à Lyon ?",
    "Hé Doly, mets un minuteur de cinq minutes.",
    "Hé Doly, change la couleur de tes yeux en vert.",
    "Hé Doly, prends une photo.",
    "Hé Doly, on joue à la roue.",
    "Hé Doly, lève les bras.",
    "Hé Doly, je suis un peu triste aujourd'hui.",
    "Hé Doly, imagine que tu es à la plage.",
    "Hé Doly, est-ce que tu es sur ta base ?",
]

# code : (titre, consigne dite par Doly, secondes laissées pour se mettre en place)
SITUATIONS = {
    "1m": ("à un mètre", "Mets-toi à un mètre de moi, face à moi, dans une pièce calme.", 0),
    "3m": ("à trois mètres", "Mets-toi à trois mètres de moi, face à moi, dans une pièce calme.", 10),
    "tele": ("télé allumée", "Allume la télé à un volume normal, puis mets-toi à un mètre de moi.", 0),
    "autre": ("une autre voix", "Demande à une autre personne de répéter les phrases, à un mètre de moi.", 0),
}

DUREE_MAX = 8  # secondes d'enregistrement au plus par phrase
SILENCE_FINAL = 1.2  # secondes de calme après la voix qui terminent l'enregistrement
BLOCS_DE_VOIX_MIN = 3


# --- Comparer ce qui est compris à ce qui est attendu --------------------------------------------------------------

def mots(texte):
    """Les mots d'une phrase, écrits comme Vosk les rend : minuscules, sans ponctuation, « l'heure » en « l' heure »."""
    texte = unicodedata.normalize("NFC", texte.lower()).replace("’", "'")
    texte = re.sub(r"[-–]", " ", texte)
    texte = re.sub(r"(\w)'", r"\1' ", texte)
    texte = re.sub(r"[^\w' ]", " ", texte)
    return ["dolly" if mot == "doly" else mot for mot in texte.split()]


def sans_eveil(texte):
    """La phrase attendue sans « Hé Doly » : l'appli ne transcrit que ce qui suit son nom."""
    return re.sub(r"^\s*hé\s+doly\s*,?\s*", "", texte, flags=re.IGNORECASE)


def mots_retrouves(attendu, entendu):
    """Combien de mots attendus se retrouvent dans ce qui a été compris, dans le bon ordre (plus longue sous-suite commune)."""
    a, b = mots(attendu), mots(entendu)
    precedente = [0] * (len(b) + 1)
    for mot_a in a:
        ligne = [0]
        for j, mot_b in enumerate(b):
            ligne.append(precedente[j] + 1 if mot_a == mot_b else max(precedente[j + 1], ligne[j]))
        precedente = ligne
    return precedente[-1]


def noter(essai):
    """Ajoute à un essai le nombre de mots attendus et de mots retrouvés, et le renvoie."""
    attendu = sans_eveil(essai["phrase"])
    essai["mots"] = len(mots(attendu))
    essai["compris"] = mots_retrouves(attendu, essai["entendu"])
    return essai


def bilan(essais):
    """Le résultat, une ligne par situation puis une pour tout, en français simple."""
    lignes = []
    groupes = {}
    for essai in essais:
        groupes.setdefault(essai["situation"], []).append(essai)
    for code, liste in list(groupes.items()) + ([("tout", essais)] if len(groupes) > 1 else []):
        titre = "En tout" if code == "tout" else SITUATIONS.get(code, (code,))[0].capitalize()
        attendus = sum(e["mots"] for e in liste)
        compris = sum(e["compris"] for e in liste)
        parfaites = sum(e["compris"] == e["mots"] for e in liste)
        eveils = sum(bool(e["eveil"]) for e in liste)
        taux = round(100 * compris / attendus) if attendus else 0
        lignes.append(f"{titre} : {taux} % des mots compris ({compris} sur {attendus}), {parfaites} phrase(s) entièrement "
                      f"comprise(s) sur {len(liste)}, « Hé Doly » reconnu {eveils} fois sur {len(liste)}.")
    # La vitesse de Vosk sur de vraies voix : au-delà de 1, il prend du retard sur le micro.
    if essais and all("calcul" in e and e.get("duree_son") for e in essais):
        calcul, son = sum(e["calcul"] for e in essais), sum(e["duree_son"] for e in essais)
        lignes.append(f"Calcul de Vosk : {calcul:.1f} s pour {son:.1f} s de son, soit {calcul / son:.2f} fois la durée du son.")
    return "\n".join(lignes) if lignes else "Aucun essai."


def taux_de_mots(essais, situation):
    liste = [e for e in essais if e["situation"] == situation]
    attendus = sum(e["mots"] for e in liste)
    return round(100 * sum(e["compris"] for e in liste) / attendus) if attendus else 0


# --- Enregistrer et transcrire -------------------------------------------------------------------------------------

def enregistrer(lire, seuil, duree_max=DUREE_MAX, silence_final=SILENCE_FINAL, horloge=time.monotonic):
    """Lit le micro jusqu'à un court silence après la voix, ou duree_max secondes de son.

    lire() renvoie (bloc, instant) comme Micro.lire. Renvoie (blocs, vrai si une voix a été entendue)."""
    blocs = []
    suivi = SuiviDeVoix(seuil, silence_final, BLOCS_DE_VOIX_MIN)
    limite = horloge() + duree_max + 2  # au cas où le micro se tairait
    while len(blocs) < duree_max * 10 and horloge() < limite:
        bloc, instant = lire()
        if bloc == b"":
            break
        if bloc is None:
            continue
        blocs.append(bloc)
        suivi.ajouter(bloc, instant)
        if suivi.phrase_finie():
            break
    return blocs, suivi.blocs_de_voix >= BLOCS_DE_VOIX_MIN


def niveau_ambiant(blocs):
    """Le volume habituel de la pièce : la médiane, pour qu'un bruit bref ne compte pas."""
    return statistics.median(volume(bloc) for bloc in blocs) if blocs else 0


def _fin_du_nom(resultat, mot_d_eveil):
    if mot_d_eveil not in resultat.get("text", ""):
        return None
    dernier = mot_d_eveil.split()[-1]
    return next((mot["end"] for mot in resultat.get("result", []) if mot["word"] == dernier), None)


def transcrire(blocs, creer_reconnaisseur, mot_d_eveil):
    """Comme dans l'appli : le guetteur cherche le mot d'éveil, puis seule la suite est transcrite.

    creer_reconnaisseur(grammaire) renvoie un reconnaisseur Vosk neuf (grammaire None : tous les mots).
    Renvoie (mot d'éveil reconnu, texte de la suite). Sans mot d'éveil reconnu, tout le son est transcrit."""
    guetteur = creer_reconnaisseur([mot_d_eveil, "[unk]"])
    fin_du_nom = None
    for bloc in blocs:
        if guetteur.AcceptWaveform(bloc):
            fin_du_nom = _fin_du_nom(json.loads(guetteur.Result()), mot_d_eveil)
            if fin_du_nom is not None:
                break
    if fin_du_nom is None:
        fin_du_nom = _fin_du_nom(json.loads(guetteur.FinalResult()), mot_d_eveil)
    reconnaisseur = creer_reconnaisseur(None)
    morceaux = []
    for bloc in blocs if fin_du_nom is None else blocs[round(fin_du_nom * 10):]:  # des blocs de 0,1 s
        if reconnaisseur.AcceptWaveform(bloc):
            morceaux.append(json.loads(reconnaisseur.Result())["text"])
    morceaux.append(json.loads(reconnaisseur.FinalResult())["text"])
    return fin_du_nom is not None, " ".join(m for m in morceaux if m)


def ecrire_wav(chemin, blocs):
    with wave.open(chemin, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAUX)
        w.writeframes(b"".join(blocs))


def lire_wav(chemin):
    with wave.open(chemin) as w:
        donnees = w.readframes(w.getnframes())
    return [donnees[debut:debut + TAILLE_BLOC] for debut in range(0, len(donnees), TAILLE_BLOC)]


def enregistrer_essais(dossier, essais, nom=FICHIER_ESSAIS):
    """Réécrit la liste des essais à chaque fois : rien n'est perdu si le test s'arrête en route."""
    provisoire = os.path.join(dossier, nom + ".tmp")
    with open(provisoire, "w", encoding="utf-8") as f:
        json.dump(essais, f, ensure_ascii=False, indent=1)
    os.replace(provisoire, os.path.join(dossier, nom))


def createur_vosk(modele):
    """Comme dans l'appli, le grand reconnaisseur sert d'une phrase à l'autre : Vosk garde ce qu'il a déjà calculé, et
    va bien plus vite ensuite. Le guetteur est neuf à chaque phrase, car ses instants comptent depuis sa création."""
    from vosk import KaldiRecognizer
    grand = []

    def creer(grammaire):
        if grammaire is None:
            if not grand:
                grand.append(KaldiRecognizer(modele, TAUX))
            grand[0].Reset()
            return grand[0]
        reconnaisseur = KaldiRecognizer(modele, TAUX, json.dumps(grammaire, ensure_ascii=False))
        reconnaisseur.SetWords(True)
        return reconnaisseur
    return creer


# --- Le test guidé, sur le robot -----------------------------------------------------------------------------------

class Banc:
    """La voix de Doly, le micro et la reconnaissance, et la liste des essais."""

    def __init__(self, voix, creer_reconnaisseur, ouvrir_micro, dossier, mot_d_eveil, volume_parole_min):
        self.voix = voix
        self.creer_reconnaisseur = creer_reconnaisseur
        self.ouvrir_micro = ouvrir_micro
        self.dossier = dossier
        self.mot_d_eveil = mot_d_eveil
        self.volume_parole_min = volume_parole_min
        self.essais = []

    def dire(self, phrase):
        print(f"[doly] {phrase}", flush=True)
        self.voix.dire(phrase)
        self.voix.attendre_fin()

    def ecouter(self, seuil):
        self.voix.attendre_fin()  # il ne doit pas s'enregistrer lui-même
        self.voix.jouer_bip()
        with self.ouvrir_micro() as micro:
            return enregistrer(micro.lire, seuil)

    def mesurer_le_bruit(self):
        with self.ouvrir_micro() as micro:
            blocs = []
            limite = time.monotonic() + 3
            while len(blocs) < 10 and time.monotonic() < limite:
                bloc, _ = micro.lire()
                if bloc == b"":
                    break
                if bloc:
                    blocs.append(bloc)
        return niveau_ambiant(blocs)

    def situation(self, code, phrases):
        """Une situation complète. Renvoie False si tu as demandé d'arrêter."""
        titre, consigne, delai = SITUATIONS[code]
        print(f"\n=== Situation : {titre}", flush=True)
        self.dire(f"Situation suivante : {titre}. {consigne}")
        reponse = input("Entrée pour commencer, p puis Entrée pour passer cette situation, q pour arrêter : ").strip().lower()
        if reponse.startswith("q"):
            return False
        if reponse.startswith("p"):
            return True
        if delai:
            self.dire(f"Je commence dans {delai} secondes.")
            time.sleep(delai)
        self.dire("Ne dis rien pendant une seconde : j'écoute le bruit de la pièce.")
        ambiant = self.mesurer_le_bruit()
        seuil = max(self.volume_parole_min, 2 * ambiant)
        print(f"Bruit de la pièce : {ambiant:.0f}, voix au-dessus de {seuil:.0f}", flush=True)
        for numero, phrase in enumerate(phrases, 1):
            print(f"\nPhrase {numero} : {phrase}", flush=True)
            self.dire(f"Phrase {numero}. Après le bip, répète : {phrase}")
            for tentative in (1, 2):
                blocs, voix_entendue = self.ecouter(seuil)
                debut = time.monotonic()
                eveil, entendu = transcrire(blocs, self.creer_reconnaisseur, self.mot_d_eveil)
                calcul = time.monotonic() - debut
                if voix_entendue or entendu or tentative == 2:
                    break
                self.dire("Je n'ai rien entendu. On recommence.")
            fichier = f"{code}_{numero:02d}.wav"
            ecrire_wav(os.path.join(self.dossier, fichier), blocs)
            essai = noter({"situation": code, "numero": numero, "phrase": phrase, "fichier": fichier, "eveil": eveil,
                           "entendu": entendu, "voix": voix_entendue, "bruit": round(ambiant),
                           "calcul": round(calcul, 2), "duree_son": len(blocs) / 10})
            self.essais.append(essai)
            enregistrer_essais(self.dossier, self.essais)
            print(f"Compris : « {entendu} » : {essai['compris']} mot(s) sur {essai['mots']}, « Hé Doly » "
                  f"{'reconnu' if eveil else 'non reconnu'}, transcrit en {calcul:.1f} s pour {len(blocs) / 10:.1f} s "
                  f"de son", flush=True)
        print(bilan([e for e in self.essais if e["situation"] == code]), flush=True)
        self.dire(f"{titre.capitalize()}, j'ai compris {taux_de_mots(self.essais, code)} pour cent des mots.")
        return True


def service_actif(nom):
    return subprocess.run(["systemctl", "is-active", "--quiet", nom]).returncode == 0


def tester(situations, nombre):
    import doly_helper as helper
    from vosk import Model, SetLogLevel

    from converser import MODELE_VOSK, MOT_D_EVEIL, TAMPON_MICRO, VOLUME_PAROLE_MIN, Voix
    from dire import CARTE_SON, service_doly_actif

    if service_actif("doly-francais"):
        print("L'appli tourne encore et occupe le micro. Arrête-la d'abord : sudo systemctl stop doly-francais")
        return 1
    relancer = service_doly_actif()
    if helper.stop_doly_service() < 0:
        print("[erreur] Impossible d'arrêter le service Doly.")
        return 1
    voix = None
    try:
        SetLogLevel(-1)
        print("Préparation de la reconnaissance vocale et de la voix...", flush=True)
        creer = createur_vosk(Model(MODELE_VOSK))
        voix = Voix()
        dossier = os.path.join(DOSSIER, time.strftime("%Y-%m-%d_%H-%M-%S"))
        os.makedirs(dossier)
        print(f"Les enregistrements vont dans {dossier}", flush=True)
        banc = Banc(voix, creer, lambda: Micro(commande_arecord(CARTE_SON, TAMPON_MICRO)), dossier, MOT_D_EVEIL,
                    VOLUME_PAROLE_MIN)
        banc.dire("Bonjour ! On vérifie si je te comprends bien. Je dis une phrase, puis tu la répètes après le bip, "
                  "normalement, comme si tu me parlais.")
        for code in situations:
            if not banc.situation(code, PHRASES[:nombre]):
                break
        print("\n=== Résultat\n" + bilan(banc.essais), flush=True)
        with open(os.path.join(dossier, "bilan.txt"), "w", encoding="utf-8") as f:
            f.write(bilan(banc.essais) + "\n")
        banc.dire("C'est fini. Merci ! Le résultat est écrit à l'écran.")
        return 0
    finally:
        if voix:
            voix.fermer()
        if relancer:
            subprocess.run(["sudo", "-n", "systemctl", "start", "doly"])


def relire(dossier):
    """Refait la transcription des sons enregistrés, avec le modèle actuel, sans rien effacer ni remplacer."""
    from vosk import Model, SetLogLevel

    from converser import MODELE_VOSK, MOT_D_EVEIL

    with open(os.path.join(dossier, FICHIER_ESSAIS), encoding="utf-8") as f:
        anciens = json.load(f)
    SetLogLevel(-1)
    creer = createur_vosk(Model(MODELE_VOSK))
    essais = []
    for ancien in anciens:
        blocs = lire_wav(os.path.join(dossier, ancien["fichier"]))
        debut = time.monotonic()
        eveil, entendu = transcrire(blocs, creer, MOT_D_EVEIL)
        essais.append(noter(dict(ancien, eveil=eveil, entendu=entendu, calcul=round(time.monotonic() - debut, 2),
                                 duree_son=len(blocs) / 10)))
    nom = f"relecture_{time.strftime('%Y-%m-%d_%H-%M-%S')}.json"
    enregistrer_essais(dossier, essais, nom)
    print(f"Avant :\n{bilan(anciens)}\n\nMaintenant ({nom}) :\n{bilan(essais)}")
    return 0


def main():
    analyse = argparse.ArgumentParser(description="Test guidé de la compréhension de Doly.")
    analyse.add_argument("situations", nargs="*", help=f"parmi {', '.join(SITUATIONS)} (par défaut, toutes)")
    analyse.add_argument("--phrases", type=int, default=len(PHRASES), help="nombre de phrases par situation")
    analyse.add_argument("--relire", metavar="DOSSIER", help="refait la transcription d'un test déjà enregistré")
    options = analyse.parse_args()
    if options.relire:
        return relire(os.path.expanduser(options.relire))
    inconnues = [code for code in options.situations if code not in SITUATIONS]
    if inconnues:
        print(f"Situation inconnue : {', '.join(inconnues)}. Choisis parmi {', '.join(SITUATIONS)}.")
        return 2
    return tester(options.situations or list(SITUATIONS), max(1, min(options.phrases, len(PHRASES))))


if __name__ == "__main__":
    raise SystemExit(main())
