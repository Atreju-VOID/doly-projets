#!/usr/bin/env python3
"""
meteo.py

Récupère la météo sur Open-Meteo (https://open-meteo.com), gratuit pour un usage personnel non commercial, jusqu'à 10 000
appels par jour, sans compte. Données sous licence CC BY 4.0.

Sans ville précisée, on prend la ville retenue à la voix, sinon la position enregistrée par l'appli officielle dans les
réglages du robot. Cette position reste sur le robot : seule une position arrondie à environ 10 km part sur Internet,
et seulement quand on demande la météo. Elle ne doit jamais aller dans le dépôt.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ADRESSE_PREVISIONS = "https://api.open-meteo.com/v1/forecast"
ADRESSE_VILLES = "https://geocoding-api.open-meteo.com/v1/search"
REGLAGES_DU_ROBOT = "/.doly/config/settings.xml"
FICHIER_VILLE = os.path.expanduser("~/.config/doly/ville.json")
DELAI_RESEAU = 5  # secondes

QUAND = ("maintenant", "aujourd_hui", "demain", "apres_demain")

# Codes météo de l'Organisation météorologique mondiale : (description, séquence d'images de Doly).
CODES = {
    0: ("ciel dégagé", "sunny"), 1: ("ciel plutôt dégagé", "partlycloudy"), 2: ("quelques nuages", "scatteredcloudy"),
    3: ("ciel couvert", "cloudy"), 45: ("brouillard", "mist"), 48: ("brouillard givrant", "mist"),
    51: ("bruine légère", "drizzle"), 53: ("bruine", "drizzle"), 55: ("bruine dense", "drizzle"),
    56: ("bruine verglaçante", "drizzle"), 57: ("bruine verglaçante", "drizzle"),
    61: ("pluie faible", "rain"), 63: ("pluie", "rain"), 65: ("forte pluie", "rain"),
    66: ("pluie verglaçante", "rain"), 67: ("pluie verglaçante", "rain"),
    71: ("neige faible", "snow"), 73: ("neige", "snow"), 75: ("forte neige", "snow"), 77: ("grains de neige", "snow"),
    80: ("quelques averses", "rain"), 81: ("averses", "rain"), 82: ("fortes averses", "rain"),
    85: ("averses de neige", "snow"), 86: ("fortes averses de neige", "snow"),
    95: ("orage", "storm"), 96: ("orage avec grêle", "storm"), 97: ("orage violent", "storm"),
    99: ("orage avec forte grêle", "storm"),
}


class ErreurMeteo(Exception):
    """Une erreur à expliquer à l'utilisateur."""


def _lire(adresse, parametres):
    url = adresse + "?" + urllib.parse.urlencode(parametres)
    try:
        with urllib.request.urlopen(url, timeout=DELAI_RESEAU) as reponse:
            return json.load(reponse)
    except (urllib.error.URLError, OSError, ValueError) as erreur:
        print(f"[meteo] {type(erreur).__name__}", flush=True)
        raise ErreurMeteo("Je n'arrive pas à joindre le service météo.") from erreur


def position_des_reglages(chemin=REGLAGES_DU_ROBOT):
    """Lit la position enregistrée par l'appli officielle. Renvoie (latitude, longitude), ou None si elle est absente."""
    try:
        position = ET.parse(chemin).getroot().find("Location")
        latitude, longitude = float(position.get("Latitude")), float(position.get("Longitude"))
    except (OSError, ET.ParseError, AttributeError, TypeError, ValueError):
        return None
    return None if latitude == 0 and longitude == 0 else (latitude, longitude)


def ville_retenue(chemin=FICHIER_VILLE):
    """Renvoie la ville retenue à la voix : {"nom", "latitude", "longitude"}, ou None."""
    try:
        with open(chemin) as f:
            ville = json.load(f)
        return {"nom": ville["nom"], "latitude": float(ville["latitude"]), "longitude": float(ville["longitude"])}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def retenir_ville(ville, chemin=FICHIER_VILLE):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    provisoire = chemin + ".tmp"
    with open(provisoire, "w") as f:
        json.dump(ville, f)
    os.chmod(provisoire, 0o600)
    os.replace(provisoire, chemin)


def chercher_ville(nom):
    resultats = _lire(ADRESSE_VILLES, {"name": nom, "count": 1, "language": "fr", "format": "json"}).get("results")
    if not resultats:
        raise ErreurMeteo(f"Je ne trouve pas la ville {nom}.")
    return {"nom": resultats[0]["name"], "latitude": resultats[0]["latitude"], "longitude": resultats[0]["longitude"]}


def lieu_a_utiliser(ville=""):
    """Choisit le lieu. Renvoie (nom à dire, latitude, longitude). Le nom est vide pour la maison."""
    if ville.strip():
        trouvee = chercher_ville(ville.strip())
        return trouvee["nom"], trouvee["latitude"], trouvee["longitude"]
    retenue = ville_retenue()
    if retenue:
        return retenue["nom"], retenue["latitude"], retenue["longitude"]
    position = position_des_reglages()
    if position:
        # 0,1 degré, c'est environ 10 km : assez précis pour la météo, sans donner l'adresse de la maison.
        return "", round(position[0], 1), round(position[1], 1)
    raise ErreurMeteo("Je ne connais pas la ville de la maison : demande-la, puis rappelle l'outil avec cette ville.")


def previsions(latitude, longitude):
    return _lire(ADRESSE_PREVISIONS, {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": 3,
    })


def sequence_pour(code, de_jour=True):
    """Nom de la séquence d'images de Doly pour un code météo."""
    nom = CODES.get(code, ("", "cloudy"))[1]
    if de_jour:
        return "weather/" + nom
    return "weather/night" if nom == "sunny" else f"weather/{nom}_n"


def resumer(donnees, quand, lieu=""):
    """Transforme la réponse d'Open-Meteo en une phrase pour Claude. Renvoie (texte, séquence d'images)."""
    ou = f"à {lieu}" if lieu else "à la maison"
    jour = {"aujourd_hui": 0, "demain": 1, "apres_demain": 2}.get(quand)
    if jour is None:
        actuel = donnees["current"]
        code = actuel["weather_code"]
        description = CODES.get(code, ("temps indéterminé",))[0]
        texte = (f"Maintenant {ou} : {description}, {round(actuel['temperature_2m'])} degrés, "
                 f"ressenti {round(actuel['apparent_temperature'])}, vent {round(actuel['wind_speed_10m'])} kilomètres heure.")
        return texte, sequence_pour(code, bool(actuel.get("is_day", 1)))
    quotidien = donnees["daily"]
    code = quotidien["weather_code"][jour]
    description = CODES.get(code, ("temps indéterminé",))[0]
    nom_du_jour = {0: "Aujourd'hui", 1: "Demain", 2: "Après-demain"}[jour]
    texte = (f"{nom_du_jour} {ou} : {description}, de {round(quotidien['temperature_2m_min'][jour])} à "
             f"{round(quotidien['temperature_2m_max'][jour])} degrés")
    pluie = quotidien["precipitation_probability_max"][jour]
    if pluie is not None:
        texte += f", {round(pluie)} pour cent de risque de pluie"
    return texte + ".", sequence_pour(code)


def meteo(ville="", quand="maintenant", retenir=False):
    """Renvoie (texte pour Claude, séquence d'images). Lève ErreurMeteo si le service ne répond pas ou si le lieu est inconnu."""
    lieu, latitude, longitude = lieu_a_utiliser(ville)
    if retenir and ville.strip():
        retenir_ville({"nom": lieu, "latitude": latitude, "longitude": longitude})
    texte, sequence = resumer(previsions(latitude, longitude), quand, lieu)
    return texte, sequence
