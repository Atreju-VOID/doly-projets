#!/usr/bin/env python3
"""
essais_sur_pc.py

Lance sur un PC les essais sans matériel qui n'ont pas besoin du robot : rien n'y est installé, ni Vosk, ni anthropic,
ni numpy, et audioop a disparu de Python 3.13. Ce programme les remplace par des imitations minimales, juste ce qu'il
faut pour charger le code, puis lance les essais demandés. Aucun appel réseau, aucun son.

Les autres essais lisent les animations d'origine, ou /proc : ils échouent sur un PC, c'est normal. Sur le robot, utilise
essais_sans_materiel.py.

Usage, sur le PC (Windows : py à la place de python3) :
    python3 essais_sur_pc.py                        # micro, ecoute, rapidite, comprehension
    python3 essais_sur_pc.py cerveau conversation
"""

import array
import math
import os
import shutil
import sys
import traceback
import types

ESSAIS_SUR_PC = ["micro", "ecoute", "rapidite", "comprehension"]


def _module(nom, **attributs):
    """N'installe une imitation que si le vrai module manque."""
    try:
        __import__(nom)
        return
    except ImportError:
        pass
    module = types.ModuleType(nom)
    module.__dict__.update(attributs)
    sys.modules[nom] = module


def _echantillons(bloc):
    return array.array("h", bloc)


def installer_imitations():
    _module("audioop",
            avg=lambda bloc, largeur: int(sum(_echantillons(bloc)) / len(_echantillons(bloc))) if bloc else 0,
            bias=lambda bloc, largeur, decalage: array.array(
                "h", (max(-32768, min(32767, x + decalage)) for x in _echantillons(bloc))).tobytes(),
            rms=lambda bloc, largeur: int(math.sqrt(sum(x * x for x in _echantillons(bloc)) / len(_echantillons(bloc))))
            if bloc else 0,
            ratecv=lambda *arguments: (b"", None))
    _module("numpy")
    _module("fcntl", ioctl=lambda *arguments: 0)
    _module("doly_vcontent", VContent=type("VContent", (), {"get_image": staticmethod(lambda *arguments: None)}))
    _module("vosk", Model=lambda *arguments: None, KaldiRecognizer=lambda *arguments: None, SetLogLevel=lambda niveau: None)

    class AnthropicError(Exception):
        pass

    class APIError(AnthropicError):
        pass

    class APIStatusError(APIError):
        pass

    erreurs = {"AnthropicError": AnthropicError, "APIError": APIError, "APIStatusError": APIStatusError,
               "APIConnectionError": type("APIConnectionError", (APIError,), {})}
    for nom in ("AuthenticationError", "RateLimitError", "BadRequestError"):
        erreurs[nom] = type(nom, (APIStatusError,), {})
    _module("anthropic", Anthropic=type("Anthropic", (), {"__init__": lambda self, **options: None}),
            Timeout=lambda *arguments, **options: None, **erreurs)


def main():
    noms = sys.argv[1:] or ESSAIS_SUR_PC
    sys.argv = sys.argv[:1]
    installer_imitations()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import essais_sans_materiel as essais
    for nom in noms:
        try:
            getattr(essais, "essai_" + nom)()
        except Exception:
            essais.rates.append(f"{nom} : plantage")
            traceback.print_exc()
    shutil.rmtree(essais.DOSSIER_ESSAI, ignore_errors=True)
    print(f"\n{essais.reussis} vérifications réussies, {len(essais.rates)} échecs", flush=True)
    for raison in essais.rates:
        print("  -", raison)
    os._exit(1 if essais.rates else 0)  # des fils d'essai peuvent encore dormir : on ne les attend pas


if __name__ == "__main__":
    main()
