#!/usr/bin/env python3
"""
converser.py

Conversation en français avec Doly : tu touches, tu parles, Claude réfléchit, Doly répond.

Pose un doigt sur un capteur au-dessus de ses yeux, parle après le bip, puis lève le doigt.
Toucher Doly pendant qu'il parle lui coupe la parole. Dire « au revoir » termine la conversation.

Usage, sur le robot :
    ~/doly-env/bin/python converser.py
    ~/doly-env/bin/python converser.py --modele claude-opus-5-5
"""

import argparse
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import warnings
import wave

warnings.filterwarnings("ignore", message="'audioop' is deprecated")  # toujours présent en Python 3.11, sur le robot
import audioop

import anthropic
import doly_helper as helper
import doly_touch as touch
from vosk import KaldiRecognizer, Model, SetLogLevel

# dire.py est dans le projet voisin.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "doly-parle"))
from dire import CARTE_SON, DOSSIER_PIPER, VOIX, creer_bip, service_doly_actif

FICHIER_CLE = os.path.expanduser("~/.config/doly/.env")
MODELE_VOSK = os.path.expanduser("~/doly-modeles/vosk-model-small-fr-0.22")
MODELE_CLAUDE = "claude-haiku-5-5"
EFFORT = "low"  # réponses courtes à l'oral : peu de réflexion, donc plus rapide et moins cher
MAX_TOKENS = 1024
MAX_ECHANGES = 20  # au-delà, Doly repart d'une conversation neuve, pour limiter le coût

TAUX = 16000
TAILLE_BLOC = TAUX * 2 // 10  # 0,1 s de son
DUREE_MAX = 15  # secondes d'écoute au maximum
FIN_DE_CONTACT = 0.3  # secondes sans contact avant d'arrêter d'écouter
DUREE_MIN = 0.8  # en dessous, le doigt a sans doute été levé trop tôt
ATTENTE_MAX = 300  # secondes sans toucher avant de rendre la main à sa personnalité d'origine

SYSTEME = f"""Tu es Doly, un petit robot de compagnie curieux, joyeux et un peu taquin. Tu parles avec les \
personnes de la maison, en français, et tu les tutoies. Reste bienveillant et adapté à toute la famille.

Ce que tu écris est lu à voix haute par une synthèse vocale, alors écris comme on parle :
- Réponds en une à trois phrases courtes, et commence par une phrase très courte, pour que ta réponse démarre vite.
- Pas de liste, de titre, de symbole, d'émoji ni de parenthèses.
- Écris les nombres, les heures et les unités en toutes lettres.

Ce que tu reçois vient d'une reconnaissance vocale : il n'y a pas de ponctuation, et il peut y avoir des erreurs. \
Devine le sens si c'est possible, sinon demande gentiment de répéter.

Pour l'instant, tu peux seulement écouter et parler. Tu ne peux ni bouger, ni voir, ni aller sur Internet, et tu ne \
connais ni l'heure ni la météo. Si on te le demande, dis-le simplement au lieu d'inventer. Nous sommes le \
{time.strftime("%d/%m/%Y")}."""

ACCUEIL = "Je t'écoute ! Pose un doigt au-dessus de mes yeux pour me parler."
TROP_COURT = "Garde le doigt posé pendant que tu parles."
RIEN_COMPRIS = "Je n'ai rien compris. Tu peux répéter ?"
INACTIVITE = "Je ne sens plus personne. À bientôt !"
ERREUR_RESEAU = "Je n'arrive pas à me connecter à Internet."
ERREUR_CLE = "Ma clé d'accès ne fonctionne pas."
ERREUR_CREDIT = "Je n'ai plus de crédit pour réfléchir."
ERREUR_LIMITE = "Je reçois trop de demandes. Réessaie dans un instant."
ERREUR_AUTRE = "Quelque chose ne va pas de mon côté. Réessaie dans un instant."
REFUS = "Je préfère ne pas répondre à ça."


def charger_cle():
    if not os.path.isfile(FICHIER_CLE):
        return False
    with open(FICHIER_CLE) as f:
        for ligne in f:
            nom, _, valeur = ligne.strip().partition("=")
            if nom == "ANTHROPIC_API_KEY" and valeur:
                os.environ[nom] = valeur
                return True
    return False


def capteur_touche():
    return touch.is_touched(touch.TouchSide.Left) or touch.is_touched(touch.TouchSide.Right)


def extraire_phrases(tampon):
    """Sépare les phrases complètes du début du texte reçu. Renvoie (phrases, reste)."""
    phrases = []
    debut = 0
    for fin in re.finditer(r"[.!?…]+[\"»)]*\s+", tampon):
        phrases.append(tampon[debut:fin.end()].strip())
        debut = fin.end()
    return phrases, tampon[debut:]


def nettoyer(phrase):
    """Retire ce que la synthèse vocale lirait à tort : symboles de mise en forme et émojis."""
    return re.sub(r"[*_#`\U00010000-\U0010FFFF]", "", phrase).strip()


class Voix:
    """Piper reste chargé en mémoire. Les phrases sont calculées à l'avance, puis jouées à la suite."""

    def __init__(self):
        self.dossier = tempfile.mkdtemp(dir="/dev/shm")
        self.piper = subprocess.Popen(
            [DOSSIER_PIPER + "/piper", "--model", VOIX, "--espeak_data", DOSSIER_PIPER + "/espeak-ng-data",
             "--output_dir", self.dossier, "--quiet"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=dict(os.environ, LD_LIBRARY_PATH=DOSSIER_PIPER), text=True, encoding="utf-8", bufsize=1,
        )
        self.bip = os.path.join(self.dossier, "bip.wav")
        creer_bip(self.bip)
        self.a_calculer = queue.Queue()
        self.a_jouer = queue.Queue()
        self.verrou = threading.Lock()
        self.restant = 0
        self.generation = 0  # une interruption change de génération : les anciennes phrases sont ignorées
        self.lecteur = None
        self.premier_son = None
        threading.Thread(target=self._boucle_calcul, daemon=True).start()
        threading.Thread(target=self._boucle_lecture, daemon=True).start()

    def calculer(self, phrase):
        """Transforme une phrase en fichier WAV et renvoie son chemin."""
        self.piper.stdin.write(" ".join(phrase.split()) + "\n")
        self.piper.stdin.flush()
        return self.piper.stdout.readline().strip()

    def _boucle_calcul(self):
        while True:
            generation, phrase = self.a_calculer.get()
            chemin = self.calculer(phrase) if generation == self.generation else None
            self.a_jouer.put((generation, chemin))

    def _boucle_lecture(self):
        while True:
            generation, chemin = self.a_jouer.get()
            lecteur = None
            with self.verrou:
                if chemin and generation == self.generation:
                    if self.premier_son is None:
                        self.premier_son = time.monotonic()
                    lecteur = self.lecteur = subprocess.Popen(["aplay", "-D", CARTE_SON, "-q", chemin])
            if lecteur:
                lecteur.wait()
                self.lecteur = None
            if chemin:
                os.remove(chemin)
            with self.verrou:
                self.restant -= 1

    def dire(self, phrase, generation=None):
        generation = self.generation if generation is None else generation
        if generation != self.generation or not phrase:
            return
        with self.verrou:
            self.restant += 1
        self.a_calculer.put((generation, phrase))

    def parle(self):
        return self.restant > 0

    def attendre_fin(self):
        while self.parle():
            time.sleep(0.05)

    def interrompre(self):
        """Coupe la parole en cours et oublie les phrases en attente."""
        with self.verrou:
            self.generation += 1
            lecteur = self.lecteur
        if lecteur:
            lecteur.terminate()
        while self.lecteur:
            time.sleep(0.01)

    def jouer_bip(self):
        subprocess.run(["aplay", "-D", CARTE_SON, "-q", self.bip])

    def fermer(self):
        self.piper.stdin.close()
        self.piper.terminate()
        shutil.rmtree(self.dossier, ignore_errors=True)


class Oreille:
    """Transcrit la parole avec Vosk pendant qu'elle est enregistrée."""

    def __init__(self):
        self.reconnaisseur = KaldiRecognizer(Model(MODELE_VOSK), TAUX)

    def rechauffer(self, fichier_wav):
        """La première phrase est bien plus lente : on la fait passer sur une phrase de synthèse."""
        with wave.open(fichier_wav) as w:
            brut = w.readframes(w.getnframes())
            taux = w.getframerate()
        donnees, _ = audioop.ratecv(brut, 2, 1, taux, TAUX, None)
        for debut in range(0, len(donnees), TAILLE_BLOC):
            self.reconnaisseur.AcceptWaveform(donnees[debut:debut + TAILLE_BLOC])
        self.reconnaisseur.FinalResult()

    def ecouter_tant_que_touche(self):
        """Renvoie (texte compris, durée écoutée, instant où le doigt s'est levé)."""
        morceaux = []
        octets = 0
        arecord = subprocess.Popen(
            ["arecord", "-D", CARTE_SON, "-q", "-f", "S16_LE", "-r", str(TAUX), "-c", "1", "-t", "raw"],
            stdout=subprocess.PIPE,
        )

        def transcrire_en_direct():
            nonlocal octets
            while True:
                bloc = arecord.stdout.read(TAILLE_BLOC)
                if not bloc:
                    return
                octets += len(bloc)
                if self.reconnaisseur.AcceptWaveform(bloc):
                    morceaux.append(json.loads(self.reconnaisseur.Result())["text"])

        transcription = threading.Thread(target=transcrire_en_direct, daemon=True)
        transcription.start()

        debut = dernier_contact = time.monotonic()
        while True:
            maintenant = time.monotonic()
            if capteur_touche():
                dernier_contact = maintenant
            if maintenant - dernier_contact > FIN_DE_CONTACT or maintenant - debut > DUREE_MAX:
                break
            time.sleep(0.05)

        arecord.terminate()
        transcription.join()
        arecord.wait()
        morceaux.append(json.loads(self.reconnaisseur.FinalResult())["text"])
        return " ".join(m for m in morceaux if m), octets / (TAUX * 2), dernier_contact


class Cerveau:
    """Envoie la conversation à Claude et transmet chaque phrase dès qu'elle est complète."""

    def __init__(self, modele):
        self.client = anthropic.Anthropic(timeout=anthropic.Timeout(30.0, connect=5.0), max_retries=1)
        self.modele = modele
        self.messages = []
        self.premier_mot = None

    def repondre(self, texte, dire):
        if len(self.messages) >= 2 * MAX_ECHANGES:
            self.messages = []
        self.messages.append({"role": "user", "content": texte})
        self.premier_mot = None
        depart = time.monotonic()
        tampon = ""
        try:
            with self.client.messages.stream(
                model=self.modele,
                max_tokens=MAX_TOKENS,
                system=SYSTEME,
                messages=self.messages,
                output_config={"effort": EFFORT},
            ) as flux:
                for morceau in flux.text_stream:
                    if self.premier_mot is None:
                        self.premier_mot = time.monotonic() - depart
                    tampon += morceau
                    phrases, tampon = extraire_phrases(tampon)
                    for phrase in phrases:
                        dire(phrase)
                final = flux.get_final_message()
        except anthropic.AuthenticationError:
            self._echec("clé API refusée", ERREUR_CLE, dire)
            return
        except anthropic.RateLimitError:
            self._echec("trop de demandes", ERREUR_LIMITE, dire)
            return
        except anthropic.APIStatusError as e:
            credit = e.status_code == 402 or "credit" in str(e.message).lower()
            self._echec(f"erreur API {e.status_code}", ERREUR_CREDIT if credit else ERREUR_AUTRE, dire)
            return
        except anthropic.APIConnectionError:
            self._echec("pas de connexion", ERREUR_RESEAU, dire)
            return

        if final.stop_reason == "refusal":
            self._echec("réponse refusée par le modèle", REFUS, dire)
            return
        dire(tampon.strip())
        # On renvoie le contenu complet à chaque tour : les blocs de réflexion doivent rester intacts.
        self.messages.append({"role": "assistant", "content": final.content})
        print(f"[claude] {final.usage.input_tokens} tokens envoyés, {final.usage.output_tokens} reçus", flush=True)

    def _echec(self, raison, phrase, dire):
        print(f"[erreur] {raison}", flush=True)
        self.messages.pop()
        dire(phrase)


def converser(voix, oreille, cerveau, attente):
    voix.dire(ACCUEIL)
    reflexion = None
    while True:
        debut = time.monotonic()
        while not capteur_touche():
            if time.monotonic() - debut > attente and not voix.parle():
                voix.dire(INACTIVITE)
                voix.attendre_fin()
                return
            time.sleep(0.05)

        voix.interrompre()
        voix.jouer_bip()
        texte, duree, doigt_leve = oreille.ecouter_tant_que_touche()
        transcrit = time.monotonic()
        if duree < DUREE_MIN:
            voix.dire(TROP_COURT)
            continue
        texte = re.sub(r"\bdolly\b", "Doly", texte, flags=re.IGNORECASE)
        print(f"[toi] {duree:.1f} s : {texte}", flush=True)
        if not texte:
            voix.dire(RIEN_COMPRIS)
            continue

        # Une réponse interrompue peut encore arriver : on l'attend pour garder l'historique en ordre.
        if reflexion:
            reflexion.join()
        generation = voix.generation
        voix.premier_son = None
        reflexion = threading.Thread(
            target=cerveau.repondre, args=(texte, lambda phrase: voix.dire(nettoyer(phrase), generation)), daemon=True
        )
        reflexion.start()

        while (reflexion.is_alive() or voix.parle()) and not capteur_touche():
            time.sleep(0.05)

        if voix.premier_son:
            print(f"[mesure] doigt levé puis premier son : {voix.premier_son - doigt_leve:.2f} s "
                  f"(transcription {transcrit - doigt_leve:.2f} s, premier mot de Claude "
                  f"{cerveau.premier_mot or 0:.2f} s)", flush=True)

        if re.search(r"\bau revoir\b", texte, flags=re.IGNORECASE):
            reflexion.join()
            voix.attendre_fin()
            return


def main():
    analyse = argparse.ArgumentParser(description="Conversation en français avec Doly.")
    analyse.add_argument("--modele", default=MODELE_CLAUDE, help=f"modèle Claude (par défaut : {MODELE_CLAUDE})")
    analyse.add_argument("--attente", type=int, default=ATTENTE_MAX, help="secondes sans toucher avant de s'arrêter")
    options = analyse.parse_args()

    if not charger_cle():
        print("[erreur] Clé API introuvable. Lance d'abord : bash enregistrer_cle.sh")
        return 1

    # Une coupure de la connexion SSH ne doit pas laisser le robot sans sa personnalité.
    for signal_recu in (signal.SIGHUP, signal.SIGTERM):
        signal.signal(signal_recu, lambda *_: sys.exit(1))

    SetLogLevel(-1)
    relancer_service = service_doly_actif()
    if helper.stop_doly_service() < 0:
        print("[erreur] Impossible d'arrêter le service Doly.")
        return 1

    voix = None
    try:
        rc = touch.init()
        if rc < 0:
            print(f"[erreur] Capteurs tactiles indisponibles (code {rc}).")
            return 1
        print(f"[info] Préparation, modèle {options.modele} ...", flush=True)
        voix = Voix()
        oreille = Oreille()
        essai = voix.calculer("Bonjour, je me prépare à t'écouter.")
        oreille.rechauffer(essai)
        os.remove(essai)
        print("[info] Prêt.", flush=True)
        converser(voix, oreille, Cerveau(options.modele), options.attente)
    finally:
        if voix:
            voix.fermer()
        touch.dispose()
        if relancer_service:
            subprocess.run(["sudo", "-n", "systemctl", "start", "doly"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
