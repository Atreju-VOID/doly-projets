#!/usr/bin/env python3
"""
sons_prets.py

Des sons prêts à jouer, pour que Doly réponde plus vite :
- PhrasesPretes garde sur le disque le son de ses phrases fixes (« Je t'écoute ! », les messages d'erreur...), calculé une
  seule fois par Piper, la première fois qu'il les dit. Un texte ou une voix qui change donne un autre nom de fichier :
  le son est alors recalculé, et l'ancien retiré. Ce n'est que sa propre voix : rien de ce que tu dis n'est écrit sur le
  disque. Elles ne sont pas préparées d'avance : Piper aurait pris le processeur à Vosk pendant qu'il écoute.
- creer_son_d_attente() fabrique le petit son joué quand Claude tarde à répondre.
"""

import array
import hashlib
import math
import os
import wave

DOSSIER = os.path.expanduser("~/.cache/doly/phrases")
VERSION = 1  # à augmenter si la façon de fabriquer les sons change : tout sera recalculé


def empreinte_de_la_voix(fichiers):
    """Ce qui identifie la voix : la taille et la date des fichiers du modèle et de Piper. Si l'un change, tout est refait."""
    morceaux = [f"version {VERSION}"]
    for chemin in fichiers:
        try:
            infos = os.stat(chemin)
            morceaux.append(f"{chemin}:{infos.st_size}:{infos.st_mtime_ns}")
        except OSError:
            morceaux.append(f"{chemin}:absent")
    return "|".join(morceaux)


def son_valable(chemin):
    """Vrai si le fichier est un WAV lisible, non vide, sur 16 bits : une coupure de courant peut laisser un fichier abîmé."""
    try:
        with wave.open(chemin) as w:
            return w.getnframes() > 0 and w.getsampwidth() == 2
    except (OSError, EOFError, wave.Error):
        return False


class PhrasesPretes:
    """Le son des phrases fixes, gardé sur le disque."""

    def __init__(self, phrases, empreinte, dossier=DOSSIER):
        self.dossier = dossier
        self.noms = {phrase: self._nom(empreinte, phrase) for phrase in phrases}
        self.pretes = set()  # phrases dont le son est sur le disque, et lisible
        self.en_panne = False  # disque plein ou illisible : Doly continue en calculant chaque phrase
        try:
            os.makedirs(dossier, exist_ok=True)
            self._ranger()
        except OSError as erreur:
            self._signaler(erreur)
        manquantes = len(self.manquantes())
        print(f"[voix] phrases fixes : {len(self.pretes)} prêtes sur le disque"
              + (f", {manquantes} gardées la première fois qu'il les dira" if manquantes else ""), flush=True)

    @staticmethod
    def _nom(empreinte, phrase):
        return hashlib.sha256(f"{empreinte}\n{phrase}".encode("utf-8")).hexdigest()[:24] + ".wav"

    def _signaler(self, erreur):
        if not self.en_panne:
            print(f"[voix] phrases fixes indisponibles sur le disque : {type(erreur).__name__}", flush=True)
        self.en_panne = True

    def _ranger(self):
        """Retient les sons valables des phrases actuelles, et retire les autres : ancien texte, ancienne voix, fichier abîmé.

        Seuls les fichiers .wav et .tmp de ce dossier, qui ne sert qu'à cela, sont retirés."""
        phrase_du_nom = {nom: phrase for phrase, nom in self.noms.items()}
        for nom in os.listdir(self.dossier):
            chemin = os.path.join(self.dossier, nom)
            if nom in phrase_du_nom and son_valable(chemin):
                self.pretes.add(phrase_du_nom[nom])
            elif nom.endswith((".wav", ".tmp")) and os.path.isfile(chemin):
                os.remove(chemin)

    def manquantes(self):
        return [phrase for phrase in self.noms if phrase not in self.pretes]

    def chemin(self, phrase):
        """Le fichier du son tout prêt de cette phrase, ou None s'il faut la calculer."""
        if phrase in self.pretes:
            chemin = os.path.join(self.dossier, self.noms[phrase])
            if os.path.isfile(chemin):
                return chemin
            self.pretes.discard(phrase)  # effacé entre-temps : on le recalculera
        return None

    def contient(self, chemin):
        """Vrai pour un fichier de ce dossier : il ne faut jamais l'effacer après l'avoir joué."""
        return os.path.dirname(chemin) == self.dossier

    def garder(self, phrase, chemin_calcule):
        """Recopie sur le disque le son tout juste calculé d'une phrase fixe. Ne fait rien pour les autres phrases.

        La copie est écrite à côté, vidée sur le disque, puis renommée : une coupure de courant ne laisse jamais un son
        à moitié écrit sous le bon nom."""
        if phrase not in self.noms or phrase in self.pretes or self.en_panne or not chemin_calcule:
            return False
        final = os.path.join(self.dossier, self.noms[phrase])
        provisoire = f"{final}.{os.getpid()}.tmp"
        try:
            with open(chemin_calcule, "rb") as source, open(provisoire, "wb") as copie:
                copie.write(source.read())
                copie.flush()
                os.fsync(copie.fileno())
            if not son_valable(provisoire):
                os.remove(provisoire)
                return False
            os.replace(provisoire, final)
        except OSError as erreur:
            self._signaler(erreur)
            return False
        self.pretes.add(phrase)
        return True


def creer_son_d_attente(chemin, taux=22050):
    """Deux notes brèves (sol puis do, aiguës), 0,28 s en tout : « je réfléchis », sans couvrir la réponse qui suit.

    Moins fort que le bip d'écoute (6 000 contre 8 000), et chaque note monte et redescend pour ne pas claquer. Une
    première version, plus grave et à 2 500, n'était pas entendue sur son petit haut-parleur."""
    echantillons = array.array("h")
    for frequence in (783.99, 1046.5):
        nombre = int(taux * 0.12)
        for i in range(nombre):
            enveloppe = math.sin(math.pi * i / nombre)
            echantillons.append(int(6000 * enveloppe * math.sin(2 * math.pi * frequence * i / taux)))
        echantillons.extend([0] * int(taux * 0.02))
    with wave.open(chemin, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taux)
        w.writeframes(echantillons.tobytes())
