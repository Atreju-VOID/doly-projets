#!/usr/bin/env python3
"""
sante.py

Le relevé de santé : toutes les 10 minutes, une ligne dans le journal, avec uniquement des nombres sur l'état de l'appli
et du robot. Rien de ce qui est dit n'y figure. resumer_journal.py les relit.
"""

import os
import threading
import time

PERIODE = 600  # secondes entre deux relevés
FICHIER_TEMPERATURE = "/sys/class/thermal/thermal_zone0/temp"


def memoire_du_programme(pid="self"):
    """La mémoire d'un programme en Mo, y compris ce qui est parti dans le fichier d'échange, ou None s'il n'existe plus."""
    try:
        with open(f"/proc/{pid}/status") as f:
            champs = dict(ligne.split(":", 1) for ligne in f if ":" in ligne)
        return (int(champs["VmRSS"].split()[0]) + int(champs.get("VmSwap", "0 kB").split()[0])) // 1024
    except (OSError, KeyError, ValueError, IndexError):
        return None


def memoire_du_systeme(chemin="/proc/meminfo"):
    """Renvoie (mémoire disponible, fichier d'échange utilisé), en Mo, ou (None, None)."""
    try:
        with open(chemin) as f:
            champs = {ligne.split(":")[0]: int(ligne.split()[1]) for ligne in f}
        return champs["MemAvailable"] // 1024, (champs["SwapTotal"] - champs["SwapFree"]) // 1024
    except (OSError, KeyError, ValueError, IndexError):
        return None, None


def _premier_nombre(chemin):
    try:
        with open(chemin) as f:
            return float(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def mesurer(debut_appli, pid_piper=None, horloge=time.monotonic):
    """Lit l'état de l'appli et du robot. Une valeur illisible vaut None."""
    dispo, echange = memoire_du_systeme()
    temperature = _premier_nombre(FICHIER_TEMPERATURE)
    return {
        "appli": memoire_du_programme(),
        "piper": memoire_du_programme(pid_piper) if pid_piper else None,
        "dispo": dispo,
        "echange": echange,
        "temp": None if temperature is None else temperature / 1000,
        "charge": _premier_nombre("/proc/loadavg"),  # processus en moyenne sur 1 minute, pour 4 cœurs
        "appli_depuis": horloge() - debut_appli,
        "robot_depuis": _premier_nombre("/proc/uptime"),
    }


def _ou_inconnu(valeur, modele):
    return "?" if valeur is None else format(valeur, modele)


def ligne_de_sante(m):
    """La ligne écrite dans le journal. Que des nombres : aucun texte venu d'ailleurs n'y entre."""
    return (f"[sante] appli={_ou_inconnu(m['appli'], 'd')}Mo piper={_ou_inconnu(m['piper'], 'd')}Mo "
            f"dispo={_ou_inconnu(m['dispo'], 'd')}Mo echange={_ou_inconnu(m['echange'], 'd')}Mo "
            f"temp={_ou_inconnu(m['temp'], '.1f')}C charge={_ou_inconnu(m['charge'], '.2f')} "
            f"appli_depuis={_ou_inconnu(m['appli_depuis'], '.0f')}s robot_depuis={_ou_inconnu(m['robot_depuis'], '.0f')}s")


def _boucle(debut_appli, pid_piper):
    while True:
        print(ligne_de_sante(mesurer(debut_appli, pid_piper)), flush=True)
        time.sleep(PERIODE)


def demarrer(pid_piper=None):
    """Lance le relevé dans un fil à part : il continue d'écrire même si la boucle principale se fige."""
    threading.Thread(target=_boucle, args=(time.monotonic(), pid_piper), daemon=True).start()
