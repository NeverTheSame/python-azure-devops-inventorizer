"""
This module contains functions for printing colored text in the terminal using ANSI escape codes.

Functions:
- prRed(skk): Print text in red color.
- prGreen(skk): Print text in green color.
- prYellow(skk): Print text in yellow color.
- prLightPurple(skk): Print text in light purple color.
- prPurple(skk): Print text in purple color.
- prCyan(skk): Print text in cyan color.
- prLightGray(skk): Print text in light gray color.
- prBlack(skk): Print text in black color.
"""

def prRed(skk): print("\033[91m {}\033[00m" .format(skk))


def prGreen(skk): print("\033[92m {}\033[00m" .format(skk))


def prYellow(skk): print("\033[93m {}\033[00m" .format(skk))


def prLightPurple(skk): print("\033[94m {}\033[00m" .format(skk))


def prPurple(skk): print("\033[95m {}\033[00m" .format(skk))


def prCyan(skk): print("\033[96m {}\033[00m" .format(skk))


def prLightGray(skk): print("\033[97m {}\033[00m" .format(skk))


def prBlack(skk): print("\033[98m {}\033[00m" .format(skk))
