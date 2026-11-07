#!/usr/bin/env python3
"""
ina219.py

Lit le courant de la batterie sur le INA219, à l'adresse 0x41 de /dev/i2c-3 (voir SDK/docs/AI_Integration_Developer_FAQ.md).

Ce bus sert aussi au SDK : ce module ne fait que lire. Il n'écrit dans aucun registre de réglage du composant. Le seul octet
envoyé est le numéro du registre à lire, dans une même opération avec la lecture, pour que personne ne puisse s'intercaler.
"""

import ctypes
import fcntl
import os

BUS = "/dev/i2c-3"
ADRESSE = 0x41
I2C_RDWR = 0x0707  # opération groupée du noyau : plusieurs messages sans que personne s'intercale
I2C_M_RD = 0x0001

REGISTRE_CONFIGURATION = 0x00
REGISTRE_SHUNT = 0x01  # tension aux bornes du shunt, signée, par pas de 10 µV : ne dépend pas du calibrage
REGISTRE_BUS = 0x02  # tension de la batterie, sur les 13 bits du haut, par pas de 4 mV
REGISTRE_CALIBRAGE = 0x05


class _Message(ctypes.Structure):
    _fields_ = [("addr", ctypes.c_uint16), ("flags", ctypes.c_uint16), ("len", ctypes.c_uint16),
                ("buf", ctypes.POINTER(ctypes.c_uint8))]


class _Lot(ctypes.Structure):
    _fields_ = [("msgs", ctypes.POINTER(_Message)), ("nmsgs", ctypes.c_uint32)]


class Ina219:
    def __init__(self, bus=BUS):
        self.fd = os.open(bus, os.O_RDWR)

    def _lire(self, registre):
        numero = (ctypes.c_uint8 * 1)(registre)
        donnees = (ctypes.c_uint8 * 2)()
        messages = (_Message * 2)(_Message(ADRESSE, 0, 1, numero), _Message(ADRESSE, I2C_M_RD, 2, donnees))
        fcntl.ioctl(self.fd, I2C_RDWR, _Lot(messages, 2))
        return (donnees[0] << 8) | donnees[1]

    def courant_mv(self):
        """Tension du shunt en mV : positive quand la batterie charge, d'après la FAQ du SDK."""
        brut = self._lire(REGISTRE_SHUNT)
        return (brut - 65536 if brut >= 32768 else brut) * 0.01

    def tension_v(self):
        return (self._lire(REGISTRE_BUS) >> 3) * 0.004

    def configuration(self):
        return self._lire(REGISTRE_CONFIGURATION)

    def calibrage(self):
        return self._lire(REGISTRE_CALIBRAGE)

    def fermer(self):
        os.close(self.fd)
