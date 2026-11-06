#!/usr/bin/env python3
"""
converser.py

Conversation en français avec Doly : tu touches, tu parles, Claude réfléchit, Doly répond.

Pose un doigt sur un capteur au-dessus de ses yeux, parle après le bip, puis lève le doigt.
Toucher Doly pendant qu'il parle ou bouge l'arrête. Dire « au revoir » termine la conversation.

Avec --mains-libres, dis aussi « Hé Doly » pour lui parler. Le micro reste alors ouvert en permanence :
le mot d'éveil est détecté sur le robot, et rien ne part sur Internet avant lui. Dis « ne m'écoute plus »
pour fermer le micro jusqu'au prochain toucher, ou « reprends ta personnalité » pour rendre la main.

Usage, sur le robot :
    ~/doly-env/bin/python converser.py
    ~/doly-env/bin/python converser.py --mains-libres
    ~/doly-env/bin/python converser.py --modele claude-opus-5-5
"""

import argparse
import collections
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

from corps import OUTILS, Corps

FICHIER_CLE = os.path.expanduser("~/.config/doly/.env")
MODELE_VOSK = os.path.expanduser("~/doly-modeles/vosk-model-small-fr-0.22")
MODELE_CLAUDE = "claude-haiku-5-5"
EFFORT = "low"  # réponses courtes à l'oral : peu de réflexion, donc plus rapide et moins cher
MAX_TOKENS = 1024
MAX_ECHANGES = 20  # au-delà, Doly repart d'une conversation neuve, pour limiter le coût
MAX_TOURS_OUTILS = 8  # appels à Claude au maximum pour une même phrase

TAUX = 16000
TAILLE_BLOC = TAUX * 2 // 10  # 0,1 s de son
DUREE_MAX = 15  # secondes d'écoute au maximum
FIN_DE_CONTACT = 0.3  # secondes sans contact avant d'arrêter d'écouter
DUREE_MIN = 0.8  # en dessous, le doigt a sans doute été levé trop tôt
ATTENTE_MAX = 300  # secondes sans toucher avant de rendre la main à sa personnalité d'origine
ATTENTE_ORIGINE = 300  # secondes au maximum pour laisser démarrer le logiciel d'origine

# Mode mains libres. « Doly » seul se déclenche à tort, par exemple sur « joli » : on exige les deux mots.
MOT_D_EVEIL = "hé dolly"
MEMOIRE_EVEIL = 80  # blocs de 0,1 s gardés en mémoire vive, pour comprendre « Hé Doly, avance » d'une traite
SILENCE_APRES_EVEIL = 5  # blocs de 0,1 s de silence de plus, après « Hé Doly », avant de conclure qu'il n'y a pas de suite
VOLUME_PAROLE_MIN = 300  # mesuré sur le robot : le silence est vers 100 à 150, et la voix le plus souvent au-dessus de 500
DELAI_APRES_EVEIL = 6  # secondes pour commencer à parler après le bip
DELAI_SUITE = 5  # secondes pendant lesquelles il écoute sans mot d'éveil, juste après une réponse
OUBLI = 600  # secondes sans échange avant de repartir d'une conversation neuve
CONTROLE_BATTERIE = 60  # secondes entre deux lectures de la batterie
# Mesuré sur une décharge, robot à l'écoute : à 30 %, il reste environ 25 minutes, puis la fin est brutale, avec
# 5 minutes entre 16 % et la coupure. Une coupure peut abîmer la carte SD : mieux vaut s'éteindre trop tôt.
BATTERIE_ALERTE = 30  # pour cent
BATTERIE_EXTINCTION = 15  # pour cent : sa personnalité d'origine étant arrêtée, c'est à nous de l'éteindre à temps
LECTURES_AVANT_EXTINCTION = 2  # la lecture varie de quelques pour cent : on attend qu'elle se confirme

NE_PLUS_ECOUTER = re.compile(r"ne m'écoute plus|arrête d'écouter|coupe ton micro")
REPRENDRE_PERSONNALITE = re.compile(r"reprends? ta personnalité")
AU_REVOIR = re.compile(r"\bau revoir\b")

SYSTEME = """Tu es Doly, un petit robot de compagnie curieux, joyeux et un peu taquin. Tu parles avec les \
personnes de la maison, en français, et tu les tutoies. Reste bienveillant et adapté à toute la famille.

Ce que tu écris est lu à voix haute par une synthèse vocale, alors écris comme on parle :
- Réponds en une à trois phrases courtes, et commence par une phrase très courte, pour que ta réponse démarre vite.
- Pas de liste, de titre, de symbole, d'émoji ni de parenthèses.
- Écris les nombres, les heures et les unités en toutes lettres.

Ce que tu reçois vient d'une reconnaissance vocale : il n'y a pas de ponctuation, et il peut y avoir des erreurs. \
Devine le sens si c'est possible, sinon demande gentiment de répéter.

Tu as un corps : tes yeux, tes bras et tes chenilles, grâce à trois outils.
- Utilise se_deplacer uniquement quand on te demande clairement de bouger, jamais de ta propre initiative. Tu ne \
fais que de petits déplacements, cinq au maximum par demande. S'il répond qu'il a refusé ou s'est arrêté, explique \
simplement pourquoi.
- Utilise bouger_les_bras quand on te le demande, ou pour saluer au début et à la fin d'une conversation.
- Utilise exprimer seulement quand une émotion forte s'y prête, pas à chaque phrase.
- Dis d'abord une phrase très courte, puis utilise l'outil. Après un outil, n'ajoute rien, sauf s'il a échoué ou \
s'il reste une question à laquelle répondre.
- Ne décris jamais tes gestes dans le texte.

Pour l'instant, tu ne peux ni voir, ni aller sur Internet, et tu ne connais ni l'heure ni la météo. Si on te le \
demande, dis-le simplement au lieu d'inventer."""

ACCUEIL = "Je t'écoute ! Pose un doigt au-dessus de mes yeux pour me parler."
ACCUEIL_MAINS_LIBRES = "Je t'écoute ! Dis hé Doly pour me parler."
JE_N_ECOUTE_PLUS = "D'accord, je n'écoute plus. Touche-moi pour me réveiller."
JE_REPRENDS = "D'accord, je reprends ma personnalité habituelle. À bientôt !"
BATTERIE_FAIBLE = "Ma batterie est faible. Pose-moi sur ma base, s'il te plaît."
JE_M_ETEINS = "Ma batterie est presque vide. Je m'éteins."
TROP_COURT = "Garde le doigt posé pendant que tu parles."
RIEN_COMPRIS = "Je n'ai rien compris. Tu peux répéter ?"
INACTIVITE = "Je ne sens plus personne. À bientôt !"
ERREUR_RESEAU = "Je n'arrive pas à me connecter à Internet."
ERREUR_CLE = "Ma clé d'accès ne fonctionne pas."
ERREUR_CREDIT = "Je n'ai plus de crédit pour réfléchir."
ERREUR_LIMITE = "Je reçois trop de demandes. Réessaie dans un instant."
ERREUR_AUTRE = "Quelque chose ne va pas de mon côté. Réessaie dans un instant."
REFUS = "Je préfère ne pas répondre à ça."
TROP_D_ACTIONS = "Ça fait beaucoup d'un coup. Redemande-moi la suite."


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


def volume(bloc):
    """Volume d'un bloc de son, sans le décalage continu du micro."""
    return audioop.rms(audioop.bias(bloc, 2, -audioop.avg(bloc, 2)), 2)


class Voix:
    """Piper reste chargé en mémoire. Les phrases sont calculées à l'avance, puis jouées à la suite."""

    def __init__(self):
        # En service, pas de /dev/shm : le système y efface les fichiers de l'utilisateur dès que sa dernière
        # session se ferme, par exemple une connexion SSH. systemd fournit un dossier en mémoire qui n'a pas ce défaut.
        self.dossier = tempfile.mkdtemp(dir=os.environ.get("RUNTIME_DIRECTORY", "/dev/shm"))
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
                    # aplay écrit une erreur quand on lui coupe la parole : ce n'en est pas une.
                    lecteur = self.lecteur = subprocess.Popen(
                        ["aplay", "-D", CARTE_SON, "-q", chemin], stderr=subprocess.DEVNULL
                    )
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
        modele = Model(MODELE_VOSK)
        self.reconnaisseur = KaldiRecognizer(modele, TAUX)
        # Ce second reconnaisseur ne cherche que le mot d'éveil : il ne consomme que 15 % d'un cœur.
        self.guetteur = KaldiRecognizer(modele, TAUX, json.dumps([MOT_D_EVEIL, "[unk]"], ensure_ascii=False))
        self.guetteur.SetWords(True)  # pour savoir à quel moment du son se termine son nom
        self.duree_guettee = 0.0  # secondes de son données au guetteur depuis sa création

    def _ouvrir_micro(self):
        return subprocess.Popen(
            ["arecord", "-D", CARTE_SON, "-q", "-f", "S16_LE", "-r", str(TAUX), "-c", "1", "-t", "raw"],
            stdout=subprocess.PIPE,
        )

    def _fermer_micro(self, arecord):
        """Ferme le tuyau avant d'attendre : s'il est plein, arecord reste bloqué dessus et l'appli se fige pour toujours."""
        arecord.terminate()
        arecord.stdout.close()
        arecord.wait()

    def guetter(self, duree_max, au_reveil):
        """Attend le mot d'éveil ou un toucher. Renvoie ("eveil", phrase qui suit), ("toucher", "") ou ("rien", "")."""
        self.guetteur.Reset()
        memoire = collections.deque(maxlen=MEMOIRE_EVEIL)
        arecord = self._ouvrir_micro()
        debut = time.monotonic()
        try:
            while True:
                if capteur_touche():
                    return "toucher", ""
                bloc = arecord.stdout.read(TAILLE_BLOC)
                if not bloc:
                    print("[erreur] Le micro s'est fermé", flush=True)
                    time.sleep(1)
                    return "rien", ""
                memoire.append(bloc)
                self.duree_guettee += len(bloc) / (2 * TAUX)
                if self.guetteur.AcceptWaveform(bloc):
                    resultat = json.loads(self.guetteur.Result())
                    if MOT_D_EVEIL in resultat["text"]:
                        print(f"[eveil] {resultat['text']}", flush=True)
                        au_reveil()
                        nom = next(mot for mot in resultat["result"] if mot["word"] == MOT_D_EVEIL.split()[-1])
                        return "eveil", self._transcrire_suite(memoire, self.duree_guettee - nom["end"], arecord)
                    memoire.clear()  # ce qui n'était pas pour Doly n'est pas gardé
                elif time.monotonic() - debut > duree_max and not json.loads(self.guetteur.PartialResult())["partial"]:
                    return "rien", ""
        finally:
            self._fermer_micro(arecord)

    def _transcrire_suite(self, memoire, duree_depuis_le_nom, arecord):
        """Transcrit ce qui suit « Hé Doly », même après une courte pause. Renvoie "" s'il n'y a pas de suite."""
        seuil = max(3 * min(map(volume, memoire)), VOLUME_PAROLE_MIN)
        morceaux = []
        # Ce qui a été dit avant son nom n'était pas pour lui : ce n'est même pas transcrit.
        for bloc in list(memoire)[-max(1, round(duree_depuis_le_nom * 10)):]:  # des blocs de 0,1 s
            if self.reconnaisseur.AcceptWaveform(bloc):
                morceaux.append(json.loads(self.reconnaisseur.Result())["text"])
        # Le guetteur s'arrête à la première pause, souvent la virgule après « Hé Doly » : la phrase continue sans doute.
        # Le micro reste donc ouvert, et seul un court silence de plus conclut qu'il n'y a pas de suite. Les premiers mots
        # tardent à apparaître dans le texte provisoire : le volume, lui, dit tout de suite si quelqu'un parle.
        silence = 0
        fin = time.monotonic() + DUREE_MAX
        while not any(morceaux) and silence < SILENCE_APRES_EVEIL and time.monotonic() < fin:
            bloc = arecord.stdout.read(TAILLE_BLOC)
            if not bloc:
                break
            if self.reconnaisseur.AcceptWaveform(bloc):
                morceaux.append(json.loads(self.reconnaisseur.Result())["text"])
            # Juste après une fin de phrase, Vosk répond sans le champ « partial ».
            parle = json.loads(self.reconnaisseur.PartialResult()).get("partial") or volume(bloc) > seuil
            silence = 0 if parle else silence + 1
        morceaux.append(json.loads(self.reconnaisseur.FinalResult())["text"])
        return " ".join(m for m in morceaux if m)

    def ecouter_jusqu_au_silence(self, delai):
        """Écoute une phrase sans toucher. Renvoie ("phrase", texte), ("toucher", "") ou ("rien", "") si personne ne parle."""
        arecord = self._ouvrir_micro()
        debut = time.monotonic()
        parole = False
        try:
            while True:
                if capteur_touche():
                    return "toucher", ""
                bloc = arecord.stdout.read(TAILLE_BLOC)
                if not bloc:
                    return "rien", ""
                if self.reconnaisseur.AcceptWaveform(bloc):
                    texte = json.loads(self.reconnaisseur.Result())["text"]
                    if texte:
                        return "phrase", texte
                    parole = False
                elif json.loads(self.reconnaisseur.PartialResult())["partial"]:
                    parole = True
                ecoule = time.monotonic() - debut
                if (not parole and ecoule > delai) or ecoule > DUREE_MAX:
                    texte = json.loads(self.reconnaisseur.FinalResult())["text"]
                    return ("phrase", texte) if texte else ("rien", "")
        finally:
            self._fermer_micro(arecord)
            self.reconnaisseur.Reset()

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
        arecord = self._ouvrir_micro()

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
    """Envoie la conversation à Claude, transmet chaque phrase dès qu'elle est complète et exécute ses outils."""

    def __init__(self, modele, corps):
        self.client = anthropic.Anthropic(timeout=anthropic.Timeout(30.0, connect=5.0), max_retries=1)
        self.modele = modele
        self.corps = corps
        self.messages = []
        self.premier_mot = None

    def oublier(self):
        self.messages = []

    def repondre(self, texte, dire, actif):
        """Répond à une phrase. actif() devient faux si la réponse a été interrompue par un toucher."""
        if len(self.messages) >= 2 * MAX_ECHANGES:
            self.messages = []
        debut_du_tour = len(self.messages)
        self.messages.append({"role": "user", "content": texte})
        self.premier_mot = None
        depart = time.monotonic()
        try:
            for _ in range(MAX_TOURS_OUTILS):
                final = self._un_appel(dire, depart)
                if final.stop_reason == "refusal":
                    self._echec("réponse refusée par le modèle", REFUS, dire, debut_du_tour)
                    return
                # On renvoie le contenu complet à chaque tour : les blocs de réflexion doivent rester intacts.
                # Après un outil, Claude peut n'avoir rien à ajouter : sa réponse est alors vide.
                if final.content:
                    self.messages.append({"role": "assistant", "content": final.content})
                print(f"[claude] {final.usage.input_tokens} tokens envoyés, {final.usage.output_tokens} reçus, "
                      f"{time.monotonic() - depart:.2f} s, blocs {[bloc.type for bloc in final.content]}", flush=True)
                if final.stop_reason != "tool_use":
                    return
                self.messages.append({"role": "user", "content": self._executer_outils(final.content, actif)})
            # Trop d'appels d'affilée : on répond aux outils sans redemander à Claude, pour garder un historique valide.
            print("[info] Limite d'appels atteinte pour cette phrase", flush=True)
            dire(TROP_D_ACTIONS)
        except anthropic.AuthenticationError:
            self._echec("clé API refusée", ERREUR_CLE, dire, debut_du_tour)
        except anthropic.RateLimitError:
            self._echec("trop de demandes", ERREUR_LIMITE, dire, debut_du_tour)
        except anthropic.APIStatusError as e:
            credit = e.status_code == 402 or "credit" in str(e.message).lower()
            self._echec(f"erreur API {e.status_code}", ERREUR_CREDIT if credit else ERREUR_AUTRE, dire, debut_du_tour)
        except anthropic.APIConnectionError:
            self._echec("pas de connexion", ERREUR_RESEAU, dire, debut_du_tour)

    def _un_appel(self, dire, depart):
        tampon = ""
        with self.client.messages.stream(
            model=self.modele,
            max_tokens=MAX_TOKENS,
            # La date est lue à chaque appel : Doly peut rester allumé plusieurs jours.
            system=SYSTEME + time.strftime(" Nous sommes le %d/%m/%Y."),
            tools=OUTILS,
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
        dire(tampon.strip())
        return final

    def _executer_outils(self, contenu, actif):
        resultats = []
        for bloc in contenu:
            if bloc.type != "tool_use":
                continue
            if actif():
                message, erreur = self.corps.executer(bloc.name, bloc.input)
            else:
                message, erreur = "interrompu par un toucher", False
            print(f"[outil] {bloc.name} {bloc.input} : {message}", flush=True)
            resultats.append({"type": "tool_result", "tool_use_id": bloc.id, "content": message, "is_error": erreur})
        return resultats

    def _echec(self, raison, phrase, dire, debut_du_tour):
        print(f"[erreur] {raison}", flush=True)
        del self.messages[debut_du_tour:]
        dire(phrase)


class Conversation:
    """Enchaîne l'écoute et les réponses. Un toucher coupe toujours Doly pour te donner la parole."""

    def __init__(self, voix, oreille, cerveau, corps, discret=False):
        self.voix = voix
        self.oreille = oreille
        self.cerveau = cerveau
        self.corps = corps
        self.discret = discret  # en service, le journal est gardé sur le disque : tes phrases n'y vont pas
        self.reflexion = None
        self.dernier_controle = time.monotonic()
        self.lectures_critiques = 0
        self.alerte_donnee = False

    def noter(self, etiquette, texte):
        print(f"[{etiquette}] {'(masqué)' if self.discret else texte}", flush=True)

    def ecouter_au_toucher(self):
        """Renvoie (texte compris, instant où le doigt s'est levé). Le texte est vide si rien n'est à envoyer."""
        self.voix.interrompre()
        self.corps.arreter()
        self.corps.passer_a("ecoute")
        self.voix.jouer_bip()
        texte, duree, doigt_leve = self.oreille.ecouter_tant_que_touche()
        self.corps.passer_a("reflexion")
        if duree < DUREE_MIN:
            self.voix.dire(TROP_COURT)
            return "", doigt_leve
        if not texte:
            self.voix.dire(RIEN_COMPRIS)
        return texte, doigt_leve

    def repondre(self, texte, fin_de_parole):
        """Fait répondre Claude. Rend la main à la fin de la réponse, ou dès qu'un toucher l'interrompt."""
        transcrit = time.monotonic()
        texte = re.sub(r"\bdolly\b", "Doly", texte, flags=re.IGNORECASE)
        self.noter("toi", texte)

        # Une réponse interrompue peut encore arriver : on l'attend pour garder l'historique en ordre.
        if self.reflexion:
            self.reflexion.join()
        generation = self.voix.generation
        self.voix.premier_son = None
        self.reflexion = threading.Thread(
            target=self.cerveau.repondre,
            args=(texte, lambda phrase: self.voix.dire(nettoyer(phrase), generation),
                  lambda: self.voix.generation == generation),
            daemon=True,
        )
        self.reflexion.start()

        while (self.reflexion.is_alive() or self.voix.parle()) and not capteur_touche():
            if self.voix.premier_son:
                self.corps.passer_a("parole")
            time.sleep(0.05)

        if self.voix.premier_son:
            print(f"[mesure] fin de ta phrase puis premier son : {self.voix.premier_son - fin_de_parole:.2f} s "
                  f"(transcription {transcrit - fin_de_parole:.2f} s, premier mot de Claude "
                  f"{self.cerveau.premier_mot or 0:.2f} s)", flush=True)

    def au_toucher(self, attente):
        self.voix.dire(ACCUEIL)
        while True:
            debut = time.monotonic()
            while not capteur_touche():
                self.corps.passer_a("parole" if self.voix.parle() else "repos")
                if time.monotonic() - debut > attente and not self.voix.parle():
                    self.voix.dire(INACTIVITE)
                    self.voix.attendre_fin()
                    return
                time.sleep(0.05)

            texte, doigt_leve = self.ecouter_au_toucher()
            if not texte:
                continue
            self.repondre(texte, doigt_leve)
            if AU_REVOIR.search(texte):
                self.reflexion.join()
                self.voix.attendre_fin()
                return

    def surveiller(self):
        """Contrôle régulier en mode mains libres. Renvoie True s'il faut éteindre le robot."""
        if time.monotonic() - self.dernier_controle < CONTROLE_BATTERIE:
            return False
        self.dernier_controle = time.monotonic()
        # Le logiciel d'origine ne doit pas revenir se disputer le matériel avec nous.
        if service_doly_actif():
            print("[info] Le service d'origine est revenu : je l'arrête", flush=True)
            helper.stop_doly_service()
        capacite = self.corps.batterie()
        print(f"[batterie] {capacite} %", flush=True)
        if capacite <= BATTERIE_ALERTE and not self.alerte_donnee:
            self.voix.dire(BATTERIE_FAIBLE)
            self.alerte_donnee = True
        elif capacite > BATTERIE_ALERTE + 5:
            self.alerte_donnee = False
        self.lectures_critiques = self.lectures_critiques + 1 if capacite < BATTERIE_EXTINCTION else 0
        return self.lectures_critiques >= LECTURES_AVANT_EXTINCTION

    def mains_libres(self):
        """Renvoie "personnalite" s'il faut rendre la main, ou "eteindre" si la batterie est presque vide."""
        self.voix.dire(ACCUEIL_MAINS_LIBRES)
        sourd = False  # micro fermé jusqu'au prochain toucher
        suite = False  # juste après une réponse, il écoute sans mot d'éveil
        dernier_echange = time.monotonic()
        while True:
            # Il n'écoute pas pendant qu'il parle : il s'entendrait lui-même.
            while self.voix.parle() and not capteur_touche():
                self.corps.passer_a("parole")
                time.sleep(0.05)

            if self.surveiller():
                self.voix.dire(JE_M_ETEINS)
                self.voix.attendre_fin()
                return "eteindre"
            if time.monotonic() - dernier_echange > OUBLI:
                self.cerveau.oublier()

            fin_de_parole = None
            if capteur_touche():
                evenement, texte = "toucher", ""
            elif sourd:
                self.corps.passer_a("repos")
                time.sleep(0.05)
                continue
            elif suite:
                self.corps.passer_a("ecoute")
                evenement, texte = self.oreille.ecouter_jusqu_au_silence(DELAI_SUITE)
                suite = False
            else:
                self.corps.passer_a("repos")
                # Ses LED passent au vert dès qu'il a entendu son nom, avant même d'avoir compris la suite.
                evenement, texte = self.oreille.guetter(CONTROLE_BATTERIE, lambda: self.corps.passer_a("ecoute"))
                if evenement == "eveil" and not texte:
                    self.voix.jouer_bip()
                    evenement, texte = self.oreille.ecouter_jusqu_au_silence(DELAI_APRES_EVEIL)

            if evenement == "toucher":
                sourd = False
                texte, fin_de_parole = self.ecouter_au_toucher()
            # Un seul mot très court, c'est le plus souvent du bruit transcrit à tort.
            if evenement == "rien" or not texte or (evenement != "toucher" and len(texte) <= 3):
                continue

            fin_de_parole = fin_de_parole or time.monotonic()
            self.corps.passer_a("reflexion")
            if NE_PLUS_ECOUTER.search(texte):
                self.noter("commande", texte)
                sourd = True
                self.voix.dire(JE_N_ECOUTE_PLUS)
                continue
            if REPRENDRE_PERSONNALITE.search(texte):
                self.noter("commande", texte)
                self.voix.dire(JE_REPRENDS)
                self.voix.attendre_fin()
                return "personnalite"

            self.repondre(texte, fin_de_parole)
            dernier_echange = time.monotonic()
            suite = not AU_REVOIR.search(texte)


def main():
    analyse = argparse.ArgumentParser(description="Conversation en français avec Doly.")
    analyse.add_argument("--modele", default=MODELE_CLAUDE, help=f"modèle Claude (par défaut : {MODELE_CLAUDE})")
    analyse.add_argument("--attente", type=int, default=ATTENTE_MAX, help="secondes sans toucher avant de s'arrêter")
    analyse.add_argument("--mains-libres", action="store_true", help="écoute aussi « Hé Doly », micro ouvert en permanence")
    analyse.add_argument("--journal-discret", action="store_true", help="n'écrit pas tes phrases dans le journal")
    analyse.add_argument("--attendre-origine", action="store_true", help="laisse d'abord démarrer le logiciel d'origine")
    options = analyse.parse_args()

    # Par défaut, le système pose ses deux questions DNS (IPv4 et IPv6) en même temps. Sur ce réseau, l'une reste
    # parfois sans réponse : 5 s de silence avant que Doly réponde. On les pose l'une après l'autre, et on réessaie
    # au bout d'une seconde si une réponse se perd quand même. Ce réglage ne vaut que pour cette appli.
    os.environ.setdefault("RES_OPTIONS", "single-request timeout:1")

    if not charger_cle():
        print("[erreur] Clé API introuvable. Lance d'abord : bash enregistrer_cle.sh")
        return 1

    # Une coupure de la connexion SSH ne doit pas laisser le robot sans sa personnalité.
    for signal_recu in (signal.SIGHUP, signal.SIGTERM):
        signal.signal(signal_recu, lambda *_: sys.exit(0))

    if options.attendre_origine:
        # Au démarrage, le logiciel d'origine se lance et installe ses mises à jour : on ne le gêne pas.
        fin = time.monotonic() + ATTENTE_ORIGINE
        while not service_doly_actif() and time.monotonic() < fin:
            time.sleep(2)
        print(f"[info] Logiciel d'origine actif : {service_doly_actif()}", flush=True)

    SetLogLevel(-1)
    relancer_service = service_doly_actif()
    if helper.stop_doly_service() < 0:
        print("[erreur] Impossible d'arrêter le service Doly.")
        return 1

    voix = None
    corps = None
    fin = None
    try:
        rc = touch.init()
        if rc < 0:
            print(f"[erreur] Capteurs tactiles indisponibles (code {rc}).")
            return 1
        print(f"[info] Préparation, modèle {options.modele} ...", flush=True)
        corps = Corps()
        voix = Voix()
        oreille = Oreille()
        essai = voix.calculer("Bonjour, je me prépare à t'écouter.")
        oreille.rechauffer(essai)
        os.remove(essai)
        print("[info] Prêt.", flush=True)
        conversation = Conversation(voix, oreille, Cerveau(options.modele, corps), corps, options.journal_discret)
        if options.mains_libres:
            fin = conversation.mains_libres()
        else:
            conversation.au_toucher(options.attente)
    finally:
        if voix:
            voix.fermer()
        if corps:
            corps.fermer()
        touch.dispose()
        if fin == "eteindre":
            subprocess.run(["sudo", "-n", "systemctl", "poweroff"])
        elif relancer_service or fin == "personnalite":
            subprocess.run(["sudo", "-n", "systemctl", "start", "doly"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
