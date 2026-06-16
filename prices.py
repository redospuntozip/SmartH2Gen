# -*- coding: utf-8 -*-
"""
prices.py — Precio horario de la electricidad [€/MWh].

Curva sintética tipo OMIE para un día con pico matinal y valle solar:
en el futuro, sustituir por la API de ESIOS / OMIE (ver README).
"""

# precio por hora del día [€/MWh]
HOURLY = {
    5: 78.0,
    6: 96.0,
    7: 134.0,   # pico de la mañana
    8: 88.0,
    9: 52.0,    # empieza a entrar la solar
    10: 36.0,
    11: 31.0,   # valle solar
    12: 33.0,
}


def price_eur_mwh(t_min, t0_clock="06:00"):
    """Precio en el minuto t_min desde el inicio de la simulación.
    Interpola linealmente entre horas para una curva suave."""
    h0 = int(t0_clock.split(":")[0])
    m0 = int(t0_clock.split(":")[1])
    tm = h0 * 60 + m0 + t_min            # minuto absoluto del día
    h = int(tm // 60)
    frac = (tm % 60) / 60.0
    p_a = HOURLY.get(h, 60.0)
    p_b = HOURLY.get(h + 1, p_a)
    return p_a + frac * (p_b - p_a)


def clock_label(t_min, t0_clock="06:00"):
    h0, m0 = map(int, t0_clock.split(":"))
    tm = int(h0 * 60 + m0 + round(t_min))
    return f"{(tm // 60) % 24:02d}:{tm % 60:02d}"
