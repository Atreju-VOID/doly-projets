#!/usr/bin/env python3
"""
resumer_journal.py

Résume le journal de l'appli en français simple : durée d'écoute la plus longue, mémoire, coupures du micro, erreurs,
redémarrages et délais de réponse. Il ne fait que lire le journal, sans toucher au matériel, et n'affiche aucune phrase dite.

Les durées viennent de l'horloge interne de chaque démarrage (__MONOTONIC_TIMESTAMP), car l'heure du robot est fausse
pendant les premières secondes après l'allumage.

Usage, sur le robot :
    python3 resumer_journal.py                         # tout ce que le journal a gardé
    python3 resumer_journal.py --depuis "2 hours ago"
    python3 resumer_journal.py --ce-demarrage
    python3 resumer_journal.py --unite doly-essai
"""

import argparse
import json
import math
import re
import statistics
import subprocess
import sys

COUPURE_LONGUE = 200  # ms
CHAUFFE = 1800  # secondes
FILE_PRESQUE_VIDE = 2  # blocs : à une coupure, une file aussi courte montre que Vosk suivait

MOTIF_COUPURE = re.compile(r"overrun.*?at least ([\d.]+) ms")
MOTIF_FILE_A_LA_COUPURE = re.compile(r"\bfile=(\d+)")
MOTIF_FILE = re.compile(r"\[micro\] file_max=(\d+) perdus=(\d+)")
MOTIF_MESURE = re.compile(r"\[mesure\] fin de ta phrase puis premier son : ([\d.]+) s \((.*)\)")
MOTIF_PREMIER_MOT = re.compile(r"premier mot de Claude ([\d.]+) s")
MOTIF_ORIGINE = re.compile(r"depuis (la fin de ta voix|le doigt levé|le texte compris)")
MOTIF_OUTIL = re.compile(r"premier outil ([\d.]+) s, (\d+) appels")
MOTIF_ETAT_A_LA_COUPURE = re.compile(r"charge=([\d.]+) dispo=(\d+)Mo echange=(\d+)Mo")
MOTIF_PRECHAUFFAGE = re.compile(r"\[cache\] préchauffage : (\d+) lus et (\d+) écrits")
MOTIF_SANTE = re.compile(r"\[sante\] (.*)")
MOTIF_CHAMP = re.compile(r"(\w+)=(\?|[\d.]+)")
MOTIF_ERREUR = re.compile(r"\[erreur\] (.*)")
MOTIF_RELANCE = re.compile(r"restart counter is at")
MOTIF_BATTERIE = re.compile(r"\[batterie\] (\d+) %(?:, (sur sa base|hors de sa base))?")


def _message(entree):
    """Le journal écrit un message qui n'est pas de l'UTF-8 sous forme de liste d'octets."""
    message = entree.get("MESSAGE", "")
    if isinstance(message, list):
        return bytes(octet for octet in message if isinstance(octet, int)).decode("utf-8", "replace")
    return message if isinstance(message, str) else ""


def nouveau_resume():
    return {
        "seances": [],  # une par lancement de l'appli : {"debut", "fin", "sante": [...]}
        "coupures": 0,
        "coupures_longues": 0,
        "coupure_max": 0.0,
        "erreurs": {},
        "plantages": 0,
        "gels": 0,
        "alertes_garde": 0,
        "relances": 0,
        "abandons": 0,
        "phrases": 0,
        "minutes_sur_base": 0,
        "minutes_hors_base": 0,
        "batterie_min": None,
        # Écoute et rapidité.
        "delais": {},  # d'où part la mesure -> délais entre la fin de ta phrase et le premier son, en s
        "delais_avec_outil": [],  # s, mesurés depuis l'étape 2, quand Claude a lancé un geste ou un outil
        "delais_sans_outil": [],
        "premiers_outils": [],  # s après l'envoi à Claude
        "appels_max": 0,  # appels à Claude pour une même phrase
        "etats_a_la_coupure": [],  # (charge, mémoire disponible en Mo, échange en Mo) au moment d'une coupure
        "premiers_mots": [],  # s
        "sons_d_attente": 0,
        "coupures_file_connue": 0,  # coupures notées avec l'état de la file
        "coupures_file_vide": 0,
        "file_max": None,  # blocs
        "blocs_perdus": 0,
        "prechauffages": 0,
        "prechauffages_rates": 0,
        "prechauffages_inutiles": 0,
    }


def lire_entrees(lignes):
    """Transforme le JSON de journalctl en (identifiant de démarrage, pid, secondes depuis l'allumage, message)."""
    for ligne in lignes:
        try:
            entree = json.loads(ligne)
            yield entree.get("_BOOT_ID"), entree.get("_PID"), int(entree["__MONOTONIC_TIMESTAMP"]) / 1e6, _message(entree)
        except (ValueError, KeyError, TypeError):
            continue


def resumer(entrees):
    """entrees : (démarrage, pid, secondes, message), dans l'ordre du journal. Renvoie le résumé."""
    r = nouveau_resume()
    seance = None
    for demarrage, pid, instant, message in entrees:
        cle = (demarrage, pid)
        if "[info] Prêt." in message:
            seance = {"cle": cle, "debut": instant, "fin": instant, "sante": []}
            r["seances"].append(seance)
        elif seance is not None and seance["cle"] == cle:
            seance["fin"] = instant  # la dernière chose écrite par ce programme : au-delà, rien ne dit qu'il écoutait
        coupure = MOTIF_COUPURE.search(message)
        sante = MOTIF_SANTE.search(message)
        erreur = MOTIF_ERREUR.search(message)
        batterie = MOTIF_BATTERIE.search(message)
        if batterie:
            niveau = int(batterie.group(1))
            r["batterie_min"] = niveau if r["batterie_min"] is None else min(r["batterie_min"], niveau)
            if batterie.group(2) == "sur sa base":
                r["minutes_sur_base"] += 1
            elif batterie.group(2) == "hors de sa base":
                r["minutes_hors_base"] += 1
        elif coupure:
            duree = float(coupure.group(1))
            r["coupures"] += 1
            r["coupures_longues"] += duree > COUPURE_LONGUE
            r["coupure_max"] = max(r["coupure_max"], duree)
            file = MOTIF_FILE_A_LA_COUPURE.search(message)
            if file:
                r["coupures_file_connue"] += 1
                r["coupures_file_vide"] += int(file.group(1)) <= FILE_PRESQUE_VIDE
            etat = MOTIF_ETAT_A_LA_COUPURE.search(message)
            if etat:
                r["etats_a_la_coupure"].append((float(etat.group(1)), int(etat.group(2)), int(etat.group(3))))
        elif MOTIF_FILE.search(message):
            file_max, perdus = map(int, MOTIF_FILE.search(message).groups())
            r["file_max"] = file_max if r["file_max"] is None else max(r["file_max"], file_max)
            r["blocs_perdus"] += perdus
        elif message.startswith("[cache] "):
            r["prechauffages"] += bool(MOTIF_PRECHAUFFAGE.search(message))
            r["prechauffages_rates"] += message.startswith(("[cache] préchauffage raté", "[cache] préchauffage refusé",
                                                            "[cache] préchauffage arrêté"))
            r["prechauffages_inutiles"] += message.startswith("[cache] encore chaud")
        elif sante:
            valeurs = {nom: float(valeur) for nom, valeur in MOTIF_CHAMP.findall(sante.group(1)) if valeur != "?"}
            if seance is not None and seance["cle"] == cle:
                seance["sante"].append(valeurs)
        elif erreur:
            r["erreurs"][erreur.group(1)] = r["erreurs"].get(erreur.group(1), 0) + 1
        elif "Traceback (most recent call last)" in message:
            r["plantages"] += 1
        elif "Watchdog timeout" in message:
            r["gels"] += 1
        elif message.startswith("[garde] Plus de signe de vie"):
            r["alertes_garde"] += 1
        elif MOTIF_RELANCE.search(message):
            r["relances"] += 1
        elif "Start request repeated too quickly" in message:
            r["abandons"] += 1
        elif message.startswith("[mesure] fin de ta phrase"):
            r["phrases"] += 1
            mesure = MOTIF_MESURE.search(message)
            if mesure:
                details = mesure.group(2)
                premier_mot = MOTIF_PREMIER_MOT.search(details)
                if premier_mot:
                    r["premiers_mots"].append(float(premier_mot.group(1)))
                # Les mesures d'avant l'étape 2 ne disent pas d'où elles partent : elles ne comptent pas dans les délais,
                # car en mains libres elles oubliaient environ 1 s.
                origine = MOTIF_ORIGINE.search(details)
                if origine:
                    r["delais"].setdefault(origine.group(1), []).append(float(mesure.group(1)))
                    outil = MOTIF_OUTIL.search(details)
                    r["delais_avec_outil" if outil else "delais_sans_outil"].append(float(mesure.group(1)))
                    if outil:
                        r["premiers_outils"].append(float(outil.group(1)))
                        r["appels_max"] = max(r["appels_max"], int(outil.group(2)))
                r["sons_d_attente"] += "son d'attente" in details
    return r


def _duree(secondes):
    minutes = round(secondes / 60)
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d}"


def _evolution(valeurs):
    return f"de {valeurs[0]:.0f} à {valeurs[-1]:.0f} Mo" + (f", au plus {max(valeurs):.0f}" if max(valeurs) > valeurs[-1] else "")


def _repartition(valeurs):
    """Médiane, 9 sur 10 en dessous (à partir de 5 valeurs) et maximum, en secondes."""
    texte = f"médiane {statistics.median(valeurs):.2f} s"
    if len(valeurs) >= 5:
        texte += f", 90 % sous {sorted(valeurs)[math.ceil(0.9 * len(valeurs)) - 1]:.2f} s"
    return texte + f", au plus {max(valeurs):.2f} s ({len(valeurs)} phrase{'s' if len(valeurs) > 1 else ''})"


def en_francais(r):
    """Le résumé, en quelques lignes."""
    lignes = []
    seances = r["seances"]
    if not seances:
        lignes.append("Écoute : aucun lancement de l'appli dans cette période.")
    else:
        la_plus_longue = max(seances, key=lambda s: s["fin"] - s["debut"])
        total = sum(s["fin"] - s["debut"] for s in seances)
        lignes.append(f"Écoute : {len(seances)} lancement(s), {_duree(total)} en tout, "
                      f"{_duree(la_plus_longue['fin'] - la_plus_longue['debut'])} d'affilée au plus.")
        sante = la_plus_longue["sante"]
        appli = [s["appli"] for s in sante if "appli" in s]
        dispo = [s["dispo"] for s in sante if "dispo" in s]
        temperatures = [s["temp"] for s in sante if "temp" in s]
        charges = [s["charge"] for s in sante if "charge" in s]
        if appli and dispo:
            lignes.append(f"Mémoire, sur ce lancement le plus long ({len(sante)} relevés) : l'appli {_evolution(appli)}, "
                          f"la mémoire disponible {_evolution(dispo)}.")
            # L'appli gonfle au début et pendant les conversations : seule la dernière heure dit si elle monte encore.
            # Une moyenne depuis le début s'y tromperait : +26 Mo par heure mesurés, pour 2 h sans bouger d'un Mo.
            relevés = [s for s in sante if "appli" in s and "appli_depuis" in s]
            if relevés:
                depuis = max(CHAUFFE, relevés[-1]["appli_depuis"] - 3600)
                heure = [s for s in relevés if s["appli_depuis"] >= depuis]
                # Juste après un lancement, aucun relevé n'a encore passé la chauffe.
                if len(heure) >= 2 and heure[-1]["appli_depuis"] - heure[0]["appli_depuis"] >= 3000:
                    lignes.append(f"Sur la dernière heure : {heure[-1]['appli'] - heure[0]['appli']:+.0f} Mo pour l'appli.")
        else:
            lignes.append("Mémoire : pas de relevé de santé sur ce lancement.")
        if temperatures and charges:
            lignes.append(f"Température : {max(temperatures):.0f} °C au plus. Charge du processeur : {max(charges):.1f} au plus, "
                          f"pour 4 cœurs.")
    if r["coupures"]:
        lignes.append(f"Coupures du micro : {r['coupures']}, dont {r['coupures_longues']} de plus de {COUPURE_LONGUE / 1000:.1f} s, "
                      f"jusqu'à {r['coupure_max'] / 1000:.2f} s.")
        if r["coupures_file_connue"]:
            lignes.append(f"Au moment de ces coupures, la file du micro était presque vide {r['coupures_file_vide']} fois "
                          f"sur {r['coupures_file_connue']} : Vosk suivait alors, la cause est ailleurs.")
        if r["etats_a_la_coupure"]:
            charges, dispos, echanges = zip(*r["etats_a_la_coupure"])
            releves = [s["echange"] for seance in r["seances"] for s in seance["sante"] if "echange" in s]
            lignes.append(f"Au moment des coupures : échange de {min(echanges)} à {max(echanges)} Mo"
                          + (f" (de {min(releves):.0f} à {max(releves):.0f} Mo sur les relevés de santé)" if releves else "")
                          + f", mémoire disponible {min(dispos)} Mo au plus bas, charge {max(charges):.2f} au plus.")
    else:
        lignes.append("Coupures du micro : aucune.")
    if r["file_max"] is not None:
        lignes.append(f"File du micro : jusqu'à {r['file_max']} blocs en attente ({r['file_max'] / 10:.1f} s de son), "
                      f"{r['blocs_perdus']} bloc(s) perdu(s).")
    if r["erreurs"]:
        lignes.append("Erreurs : " + ", ".join(f"{nom} ({nombre} fois)" for nom, nombre in sorted(r["erreurs"].items())) + ".")
    else:
        lignes.append("Erreurs : aucune.")
    if r["plantages"]:
        lignes.append(f"Plantages avec message d'erreur Python : {r['plantages']}.")
    gels = max(r["gels"], r["alertes_garde"])
    lignes.append(f"Gels détectés par le chien de garde : {gels}." if gels else "Gels détectés par le chien de garde : aucun.")
    lignes.append(f"Redémarrages automatiques : {r['relances']}." if r["relances"] else "Redémarrages automatiques : aucun.")
    if r["abandons"]:
        lignes.append(f"Trop d'échecs d'affilée, retour à sa personnalité d'origine : {r['abandons']} fois.")
    lignes.append(f"Phrases auxquelles il a répondu : {r['phrases']}.")
    for origine in ("la fin de ta voix", "le doigt levé", "le texte compris"):
        if r["delais"].get(origine):
            lignes.append(f"Délai de réponse, depuis {origine} : {_repartition(r['delais'][origine])}.")
    if r["delais_avec_outil"]:
        lignes.append(f"Délai de réponse quand Claude lance un geste ou un outil : {_repartition(r['delais_avec_outil'])}, "
                      f"premier outil lancé en médiane {statistics.median(r['premiers_outils']):.2f} s après l'envoi, "
                      f"jusqu'à {r['appels_max']} appels à Claude pour une phrase.")
        if r["delais_sans_outil"]:
            lignes.append(f"Délai de réponse sans geste ni outil : {_repartition(r['delais_sans_outil'])}.")
    if r["premiers_mots"]:
        lignes.append(f"Premier mot de Claude : {_repartition(r['premiers_mots'])}.")
    if r["sons_d_attente"]:
        lignes.append(f"Petit son d'attente : {r['sons_d_attente']} fois.")
    if r["prechauffages"] or r["prechauffages_rates"] or r["prechauffages_inutiles"]:
        lignes.append(f"Préchauffage du cache : {r['prechauffages']} fois, {r['prechauffages_rates']} raté(s), "
                      f"{r['prechauffages_inutiles']} fois inutile car le cache était encore chaud.")
    if r["minutes_sur_base"] or r["minutes_hors_base"]:
        lignes.append(f"Sa place : {_duree(r['minutes_sur_base'] * 60)} sur sa base, {_duree(r['minutes_hors_base'] * 60)} hors de sa base.")
    if r["batterie_min"] is not None:
        lignes.append(f"Batterie : {r['batterie_min']} % au plus bas.")
    return "\n".join(lignes)


def main():
    analyse = argparse.ArgumentParser(description="Résume le journal de l'appli en français simple.")
    analyse.add_argument("--depuis", help="par exemple \"2 hours ago\" ou \"2026-11-07 12:00\"")
    analyse.add_argument("--ce-demarrage", action="store_true", help="seulement depuis le dernier allumage")
    analyse.add_argument("--unite", default="doly-francais", help="le service à regarder")
    options = analyse.parse_args()
    commande = ["journalctl", "-u", options.unite, "-o", "json", "--no-pager"]
    if options.depuis:
        commande += ["--since", options.depuis]
    if options.ce_demarrage:
        commande.append("-b")
    with subprocess.Popen(commande, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="replace") as journal:
        r = resumer(lire_entrees(journal.stdout))
    if journal.returncode:
        print("Je n'arrive pas à lire le journal.", file=sys.stderr)
        return 1
    print(en_francais(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
