#!/usr/bin/env python3
"""
tester_phrases.py

Teste la reconnaissance vocale de Doly avec Vosk, sur quelques phrases en français.

Doly lit chaque phrase. Pose un doigt sur un capteur au-dessus de ses yeux, répète la phrase
après le bip, puis lève le doigt. Doly dit alors ce qu'il a compris.

Usage, sur le robot :
    ~/doly-env/bin/python tester_phrases.py

Les enregistrements et les résultats restent sur le robot, dans ~/doly-ecoute.
"""

import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import wave

import doly_helper as helper
import doly_touch as touch
from vosk import KaldiRecognizer, Model, SetLogLevel

# dire.py est dans le projet voisin.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "doly-parle"))
from dire import CARTE_SON, creer_bip, jouer, service_doly_actif, synthetiser

DOSSIER = os.path.expanduser("~/doly-ecoute")
MODELE = os.path.expanduser("~/doly-modeles/vosk-model-small-fr-0.22")
TAUX = 16000
OCTETS_PAR_SECONDE = TAUX * 2
ATTENTE_TOUCHER = 40  # secondes avant de passer à la phrase suivante
DUREE_MAX = 10  # secondes d'enregistrement au maximum
FIN_DE_CONTACT = 0.3  # secondes sans contact avant d'arrêter l'enregistrement
DUREE_MIN = 0.8  # en dessous, le doigt a sans doute été levé trop tôt

PHRASES = [
    "Bonjour Doly, comment ça va aujourd'hui ?",
    "Avance un peu, puis tourne à gauche.",
    "Quelle est la capitale de l'Australie ?",
    "Raconte-moi une blague sur les robots.",
    "Est-ce que tu peux lever les bras et faire un grand sourire ?",
    "Quel temps fera-t-il demain à Paris ?",
]
INTRO = (
    "On va tester mes oreilles ! Je vais te dire six phrases. Après chacune, pose un doigt "
    "au-dessus de mes yeux, et garde-le posé. Répète la phrase après le bip, puis lève le doigt."
)
TROP_COURT = "Garde le doigt posé pendant que tu parles. On recommence."
RIEN_COMPRIS = "Je n'ai rien compris."
ABANDON = "Je ne sens plus ton doigt. On arrête là."
FIN = "C'est terminé. Merci beaucoup !"


def son(texte):
    """Renvoie le fichier WAV de ce texte, en le calculant s'il n'existe pas encore."""
    nom = hashlib.md5(texte.encode("utf-8")).hexdigest() + ".wav"
    chemin = os.path.join(DOSSIER, "sons", nom)
    if not os.path.exists(chemin) and not synthetiser(texte, chemin):
        raise RuntimeError("synthèse vocale impossible")
    return chemin


def capteur_touche():
    return touch.is_touched(touch.TouchSide.Left) or touch.is_touched(touch.TouchSide.Right)


def attendre_toucher():
    debut = time.monotonic()
    while time.monotonic() - debut < ATTENTE_TOUCHER:
        if capteur_touche():
            return True
        time.sleep(0.05)
    return False


def enregistrer_tant_que_touche():
    """Enregistre en mono 16 kHz tant que le capteur est touché et renvoie les données brutes."""
    brut = os.path.join(DOSSIER, "en_cours.raw")
    arecord = subprocess.Popen(
        ["arecord", "-D", CARTE_SON, "-q", "-f", "S16_LE", "-r", str(TAUX), "-c", "1", "-t", "raw", brut]
    )
    debut = dernier_contact = time.monotonic()
    while True:
        maintenant = time.monotonic()
        if capteur_touche():
            dernier_contact = maintenant
        if maintenant - dernier_contact > FIN_DE_CONTACT or maintenant - debut > DUREE_MAX:
            break
        time.sleep(0.05)
    arecord.terminate()
    arecord.wait()
    with open(brut, "rb") as f:
        donnees = f.read()
    os.remove(brut)
    return donnees


def sauver_wav(chemin, donnees):
    with wave.open(chemin, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAUX)
        w.writeframes(donnees)


def transcrire(reconnaisseur, donnees):
    morceaux = []
    for debut in range(0, len(donnees), OCTETS_PAR_SECONDE // 10):
        if reconnaisseur.AcceptWaveform(donnees[debut:debut + OCTETS_PAR_SECONDE // 10]):
            morceaux.append(json.loads(reconnaisseur.Result())["text"])
    morceaux.append(json.loads(reconnaisseur.FinalResult())["text"])
    return " ".join(m for m in morceaux if m)


def mots(texte):
    return re.sub(r"[^\w]+", " ", texte.lower()).split()


def erreurs_de_mots(reference, compris):
    """Nombre de mots à ajouter, retirer ou remplacer pour passer de l'un à l'autre."""
    precedent = list(range(len(compris) + 1))
    for i, mot_reference in enumerate(reference, 1):
        courant = [i]
        for j, mot_compris in enumerate(compris, 1):
            courant.append(min(precedent[j] + 1, courant[j - 1] + 1, precedent[j - 1] + (mot_reference != mot_compris)))
        precedent = courant
    return precedent[-1]


def ecouter_une_phrase(bip):
    """Attend le toucher et enregistre. Renvoie les données, ou None si personne n'a touché."""
    for _ in range(2):
        if not attendre_toucher():
            return None
        jouer(bip)
        donnees = enregistrer_tant_que_touche()
        if len(donnees) >= DUREE_MIN * OCTETS_PAR_SECONDE:
            return donnees
        jouer(son(TROP_COURT))
    return None


def derouler_test():
    print("[info] Préparation des phrases ...", flush=True)
    bip = os.path.join(DOSSIER, "sons", "bip.wav")
    creer_bip(bip)
    consignes = [son(f"Phrase {numero}. {phrase}") for numero, phrase in enumerate(PHRASES, 1)]
    for texte in (INTRO, TROP_COURT, RIEN_COMPRIS, ABANDON, FIN):
        son(texte)

    debut = time.monotonic()
    # Un seul reconnaisseur pour toutes les phrases : son cache se réchauffe et le calcul va deux fois plus vite.
    reconnaisseur = KaldiRecognizer(Model(MODELE), TAUX)
    print(f"[info] Modèle chargé en {time.monotonic() - debut:.1f} s", flush=True)

    jouer(son(INTRO))
    resultats = []
    absences = 0
    for numero, (phrase, consigne) in enumerate(zip(PHRASES, consignes), 1):
        jouer(consigne)
        donnees = ecouter_une_phrase(bip)
        if donnees is None:
            print(f"[info] Phrase {numero} : pas de toucher", flush=True)
            absences += 1
            if absences == 2:
                jouer(son(ABANDON))
                break
            continue
        absences = 0
        jouer(bip)

        debut = time.monotonic()
        compris = transcrire(reconnaisseur, donnees)
        calcul = time.monotonic() - debut
        duree = len(donnees) / OCTETS_PAR_SECONDE
        sauver_wav(os.path.join(DOSSIER, f"phrase_{numero}.wav"), donnees)

        reference = mots(phrase)
        erreurs = erreurs_de_mots(reference, mots(compris))
        resultats.append({"numero": numero, "phrase": phrase, "compris": compris, "mots": len(reference),
                          "erreurs": erreurs, "duree": round(duree, 1), "calcul": round(calcul, 2)})
        print(f"[resultat] {numero} : {erreurs}/{len(reference)} erreurs, {duree:.1f} s de parole, "
              f"{calcul:.2f} s de calcul, compris : {compris}", flush=True)

        if compris:
            fichier = os.path.join(DOSSIER, "compris.wav")
            if synthetiser(f"J'ai compris : {compris}", fichier):
                jouer(fichier)
        else:
            jouer(son(RIEN_COMPRIS))
    else:
        jouer(son(FIN))

    with open(os.path.join(DOSSIER, "resultats_vosk.json"), "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)
    return resultats


def main():
    # Une coupure de la connexion SSH ne doit pas laisser le robot sans sa personnalité.
    for signal_recu in (signal.SIGHUP, signal.SIGTERM):
        signal.signal(signal_recu, lambda *_: sys.exit(1))

    os.makedirs(os.path.join(DOSSIER, "sons"), exist_ok=True)
    SetLogLevel(-1)

    relancer_service = service_doly_actif()
    if helper.stop_doly_service() < 0:
        print("[erreur] Impossible d'arrêter le service Doly.")
        return 1

    try:
        rc = touch.init()
        if rc < 0:
            print(f"[erreur] Capteurs tactiles indisponibles (code {rc}).")
            return 1
        resultats = derouler_test()
    finally:
        touch.dispose()
        if relancer_service:
            subprocess.run(["sudo", "-n", "systemctl", "start", "doly"])

    total_mots = sum(r["mots"] for r in resultats)
    if total_mots:
        total_erreurs = sum(r["erreurs"] for r in resultats)
        print(f"[bilan] {total_erreurs} erreurs sur {total_mots} mots, soit {100 * total_erreurs / total_mots:.0f} %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
