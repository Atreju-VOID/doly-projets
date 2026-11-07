#!/usr/bin/env python3
"""
garde.py

Le chien de garde de l'appli : si elle se fige, systemd la tue et la relance.

Un programme figé reste « actif » pour systemd. On lui demande donc une preuve de vie (WatchdogSec, dans le fichier
doly-francais.service) : sans message WATCHDOG=1 pendant 30 s, il tue l'appli. Ces messages partent d'un petit fil à
part, mais ce fil ne les envoie que si la boucle principale a donné signe de vie : un micro bloqué fige la boucle
principale, pas ce fil. Il garde ainsi la main pour écrire dans le journal où le programme est bloqué.

Deux façons de donner signe de vie, depuis le fil principal uniquement :
- vivant() : à chaque tour d'une boucle qui avance vraiment, par exemple après chaque bloc de son reçu ;
- with activite("jeu", 900) : pour une chose longue et normale, avec sa durée maximale. Passé ce délai, c'est un gel.

Hors du service, il n'y a pas de socket vers systemd : rien n'est envoyé, et tout le reste marche pareil.
"""

import contextlib
import faulthandler
import os
import socket
import threading
import time

PATIENCE = 20  # secondes sans signe de vie avant de ne plus répondre à systemd : le plus long silence normal est de 15 s
PERIODE = 5  # secondes entre deux messages à systemd, bien moins que les 30 s de WatchdogSec


def envoyer_a_systemd(message):
    """Envoie un message à systemd, sans dépendance : c'est un simple datagramme. Renvoie False hors du service."""
    adresse = os.environ.get("NOTIFY_SOCKET")
    if not adresse:
        return False
    if adresse.startswith("@"):  # socket abstrait
        adresse = "\0" + adresse[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.sendto(message.encode(), adresse)
        return True
    except OSError as erreur:
        print(f"[garde] message à systemd impossible : {erreur}", flush=True)
        return False


def _ecrire_ou_on_en_est():
    # Écrit seulement les fichiers, les lignes et les noms de fonctions : rien de ce qui a été dit.
    faulthandler.dump_traceback(all_threads=True)


class Garde:
    def __init__(self, envoyer=envoyer_a_systemd, horloge=time.monotonic, patience=PATIENCE, ecrire_pile=_ecrire_ou_on_en_est):
        self.envoyer = envoyer
        self.horloge = horloge
        self.patience = patience
        self.ecrire_pile = ecrire_pile
        self.fil_surveille = threading.main_thread()
        self.dernier_signe = horloge()
        self.en_cours = None  # (nom de l'activité, instant où elle aurait dû finir)
        self.en_alerte = False

    def _depuis_le_fil_surveille(self):
        # Un autre fil qui donnerait signe de vie cacherait un gel de la boucle principale.
        return threading.current_thread() is self.fil_surveille

    def vivant(self):
        if self._depuis_le_fil_surveille():
            self.dernier_signe = self.horloge()

    @contextlib.contextmanager
    def activite(self, nom, duree_max):
        """Une chose longue et normale du fil principal. Quand elle se termine, c'est aussi un signe de vie."""
        if not self._depuis_le_fil_surveille():
            yield
            return
        precedente = self.en_cours
        self.en_cours = (nom, self.horloge() + duree_max)
        try:
            yield
        finally:
            self.en_cours = precedente
            self.vivant()

    def doit_repondre(self):
        """Vrai si la boucle principale a donné signe de vie récemment, ou si elle fait une chose longue dans les temps."""
        maintenant = self.horloge()
        if maintenant - self.dernier_signe < self.patience:
            return True
        return self.en_cours is not None and maintenant < self.en_cours[1]

    def un_tour(self):
        """Répond à systemd, ou écrit une seule fois dans le journal pourquoi on ne répond plus."""
        if self.doit_repondre():
            if self.en_alerte:
                print("[garde] La boucle principale a repris", flush=True)
                self.en_alerte = False
            self.envoyer("WATCHDOG=1")
        elif not self.en_alerte:
            self.en_alerte = True
            depuis = self.horloge() - self.dernier_signe
            activite = f", activité dépassée : {self.en_cours[0]}" if self.en_cours else ""
            print(f"[garde] Plus de signe de vie depuis {depuis:.0f} s{activite}. systemd va me relancer.", flush=True)
            self.ecrire_pile()

    def _boucle(self):
        while True:
            self.un_tour()
            time.sleep(PERIODE)

    def demarrer(self):
        """À appeler tout au début, avant d'attendre le logiciel d'origine.

        Pour systemd, le service reste « en démarrage » jusqu'à READY=1, et multi-user.target l'attend. Or le logiciel
        d'origine démarre après multi-user.target : attendre avant de dire READY=1 bloquerait tout le démarrage."""
        faulthandler.enable()  # écrit aussi où on en est quand systemd envoie SIGABRT, ou en cas de plantage du SDK
        self.dernier_signe = self.horloge()
        if self.envoyer("READY=1") and "WATCHDOG_USEC" in os.environ:
            threading.Thread(target=self._boucle, daemon=True).start()


_garde = Garde()
demarrer = _garde.demarrer
vivant = _garde.vivant
activite = _garde.activite
