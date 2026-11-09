#!/usr/bin/env python3
"""
micro.py

Le micro de Doly, lu sans perte : arecord est lu par un fil à part, qui range chaque bloc de son dans une file bornée,
avec l'instant où il est arrivé. Vosk prend les blocs dans cette file de son côté : s'il prend du retard, le son attend
dans la file au lieu de bloquer arecord, qui perdrait alors du son (« overrun »).

Un second fil lit les messages d'arecord. Chaque coupure est notée dans le journal avec l'état de la file : une coupure
alors que la file est vide montre que Vosk suivait, et que la cause est ailleurs (processeur, mémoire). Rien de ce qui est
dit n'y figure, seulement des nombres.

SuiviDeVoix suit le volume bloc par bloc : il sait quand la voix s'est arrêtée, et peut conclure une phrase après un
court silence.
"""

import collections
import subprocess
import threading
import time
import warnings

warnings.filterwarnings("ignore", message="'audioop' is deprecated")  # toujours présent en Python 3.11, sur le robot
import audioop

import sante

TAUX = 16000  # échantillons par seconde
TAILLE_BLOC = TAUX * 2 // 10  # 0,1 s de son, en octets
DUREE_BLOC = 0.1  # secondes
FILE_MAX = 100  # blocs de 0,1 s : 10 s de son, 320 Ko au plus. Au-delà, le plus ancien est perdu, et c'est noté.
ATTENTE_BLOC = 0.5  # secondes au plus à attendre un bloc : la boucle peut regarder le toucher même si le micro se tait
ARRET_MAX = 1.0  # secondes laissées à arecord pour s'arrêter avant de le tuer
FILE_A_NOTER = 5  # blocs en attente à partir desquels la file est notée dans le journal, à la fermeture


def volume(bloc):
    """Volume d'un bloc de son, sans le décalage continu du micro."""
    return audioop.rms(audioop.bias(bloc, 2, -audioop.avg(bloc, 2)), 2)


def commande_arecord(carte_son, tampon=None):
    """arecord en 16 kHz, mono, 16 bits, sans en-tête. tampon : secondes de son gardées par la carte son (--buffer-time),
    ou None pour son réglage habituel."""
    commande = ["arecord", "-D", carte_son, "-q", "-f", "S16_LE", "-r", str(TAUX), "-c", "1", "-t", "raw"]
    if tampon:
        commande.append(f"--buffer-time={round(tampon * 1_000_000)}")
    return commande


def _etat_du_robot():
    """Charge du processeur et mémoire, pour comprendre une coupure : que des nombres."""
    dispo, echange = sante.memoire_du_systeme()
    charge = sante._premier_nombre("/proc/loadavg")
    return (f"charge={'?' if charge is None else format(charge, '.2f')} "
            f"dispo={'?' if dispo is None else dispo}Mo echange={'?' if echange is None else echange}Mo")


class Micro:
    """arecord, lu par un fil à part. lire() donne les blocs dans l'ordre, avec l'instant de leur arrivée."""

    def __init__(self, commande, taille_bloc=TAILLE_BLOC, file_max=FILE_MAX):
        self.taille_bloc = taille_bloc
        self.file_max = file_max
        self.file = collections.deque()  # (bloc, instant d'arrivée)
        self.condition = threading.Condition()
        self.fini = False  # arecord s'est arrêté : plus aucun bloc n'arrivera
        self.ferme = False
        self.perdus = 0  # blocs retirés de la file pleine
        self.plus_longue_file = 0
        self.coupures = 0
        self.ouvert_a = time.monotonic()
        self.processus = subprocess.Popen(commande, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.lecteur = threading.Thread(target=self._lire_le_son, daemon=True)
        self.lecteur_messages = threading.Thread(target=self._lire_les_messages, daemon=True)
        self.lecteur.start()
        self.lecteur_messages.start()

    def _lire_le_son(self):
        """Lit le tuyau jusqu'au bout, sans jamais attendre Vosk : arecord n'est donc jamais bloqué par un tuyau plein."""
        sortie = self.processus.stdout
        try:
            while True:
                bloc = sortie.read(self.taille_bloc)
                instant = time.monotonic()
                if not bloc:
                    break
                with self.condition:
                    if len(self.file) >= self.file_max:
                        self.file.popleft()  # Vosk a pris trop de retard : on garde le son le plus récent
                        self.perdus += 1
                    self.file.append((bloc, instant))
                    self.plus_longue_file = max(self.plus_longue_file, len(self.file))
                    self.condition.notify_all()
        except (OSError, ValueError):
            pass  # tuyau fermé
        finally:
            with self.condition:
                self.fini = True
                self.condition.notify_all()

    def _lire_les_messages(self):
        """Recopie les messages d'arecord dans le journal. Une coupure y est complétée par l'état de la file et du robot.

        Le texte d'arecord est gardé tel quel (« overrun!!! (at least ... ms long) ») : resumer_journal.py le compte."""
        try:
            for ligne in self.processus.stderr:
                texte = ligne.decode("utf-8", "replace").strip()
                if not texte:
                    continue
                if "overrun" in texte:
                    self.coupures += 1
                    with self.condition:
                        en_attente = len(self.file)
                    print(f"[micro] {texte} file={en_attente} file_max={self.plus_longue_file} perdus={self.perdus} "
                          f"ouvert={time.monotonic() - self.ouvert_a:.1f}s {_etat_du_robot()}", flush=True)
                else:
                    print(f"[micro] {texte}", flush=True)
        except (OSError, ValueError):
            pass

    def lire(self, attente=ATTENTE_BLOC):
        """Renvoie (bloc, instant d'arrivée) pour le bloc suivant.

        Si rien n'arrive pendant attente secondes, renvoie (None, None) : la boucle peut regarder le reste et revenir.
        Quand arecord s'est arrêté et que la file est vide, renvoie (b"", None)."""
        with self.condition:
            if not self.file and not self.fini:
                self.condition.wait(attente)
            if self.file:
                return self.file.popleft()
            return (b"", None) if self.fini else (None, None)

    def en_attente(self):
        with self.condition:
            return len(self.file)

    def fermer(self):
        """Arrête arecord sans jamais rester bloqué, même s'il est figé. Les blocs déjà lus restent dans la file.

        Le fil de lecture lit le tuyau jusqu'au bout : arecord ne peut donc pas rester coincé sur un tuyau plein."""
        if self.ferme:
            return
        self.ferme = True
        if self.processus.poll() is None:
            self.processus.terminate()
        try:
            self.processus.wait(timeout=ARRET_MAX)
        except subprocess.TimeoutExpired:
            self.processus.kill()  # figé, par exemple par kill -STOP : seul SIGKILL l'arrête
            try:
                self.processus.wait(timeout=ARRET_MAX)
            except subprocess.TimeoutExpired:
                print("[erreur] arecord ne s'arrête pas", flush=True)
        self.lecteur.join(ARRET_MAX)
        self.lecteur_messages.join(ARRET_MAX)
        with self.condition:
            self.fini = True  # même si le fil de lecture est resté coincé : plus aucun bloc n'est attendu
            self.condition.notify_all()
        for tuyau, fil in ((self.processus.stdout, self.lecteur), (self.processus.stderr, self.lecteur_messages)):
            if not fil.is_alive():
                tuyau.close()
        if self.plus_longue_file >= FILE_A_NOTER or self.perdus:
            print(f"[micro] file_max={self.plus_longue_file} perdus={self.perdus} "
                  f"ouvert={time.monotonic() - self.ouvert_a:.0f}s", flush=True)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.fermer()
        return False


class SuiviDeVoix:
    """Suit le volume bloc par bloc : où ta voix s'est arrêtée, et si un court silence vient de finir ta phrase."""

    def __init__(self, seuil, silence_de_fin=None, blocs_de_voix_min=3):
        """seuil : volume au-dessus duquel un bloc est de la voix. silence_de_fin : secondes de calme qui concluent une
        phrase, ou None pour ne jamais conclure au volume. blocs_de_voix_min : il faut avoir vraiment parlé avant."""
        self.seuil = seuil
        self.blocs_de_fin = None if not silence_de_fin else max(1, round(silence_de_fin / DUREE_BLOC))
        self.blocs_de_voix_min = blocs_de_voix_min
        self.blocs_de_voix = 0
        self.silence = 0  # blocs calmes depuis le dernier bloc de voix
        self.fin_de_voix = None  # instant d'arrivée du dernier bloc de voix

    def ajouter(self, bloc, instant):
        """Renvoie True si ce bloc est assez fort pour être de la voix."""
        if volume(bloc) > self.seuil:
            self.blocs_de_voix += 1
            self.silence = 0
            self.fin_de_voix = instant
            return True
        self.silence += 1
        return False

    def phrase_finie(self):
        """Vrai si la fin au volume est activée, si quelqu'un a vraiment parlé, et si un court silence vient de suivre."""
        return (self.blocs_de_fin is not None and self.blocs_de_voix >= self.blocs_de_voix_min
                and self.silence >= self.blocs_de_fin)
