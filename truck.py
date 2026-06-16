# -*- coding: utf-8 -*-
"""
truck.py — Modelo del camión en ruta y estimador de ETA.

La "verdad" (posición real, retención de tráfico) y el "estimador" que ve la
hidrogenera están separados a propósito: el MPC solo conoce la ETA estimada,
que cambia cuando aparece la retención -> se ve la replanificación.

En el futuro: sustituir por telemetría GPS real + una API de rutas
(OSRM / Google Routes) para la ETA.
"""
from params import PR

# perfil de velocidad por tramo de la ruta (km_inicio, km_fin, km/h)
SEGMENTS = [
    (0, 15, 60),     # salida del centro logístico
    (15, 150, 88),   # autovía
    (150, 185, 95),  # autopista
    (185, 205, 75),  # nacional
    (205, 210, 40),  # acceso a la hidrogenera
]

# retención de tráfico: entre los minutos 70 y 95 la velocidad cae a 15 km/h
JAM = dict(t_start=70.0, t_end=95.0, v_kmh=15.0)


class Truck:
    def __init__(self):
        self.km = 0.0
        self.t_min = 0.0
        self.m_kg = PR["truck_m0_kg"]
        self.arrived = False
        self.arrival_t = None
        self.in_jam = False

    def _segment_speed(self):
        for a, b, v in SEGMENTS:
            if a <= self.km < b:
                return v
        return SEGMENTS[-1][2]

    def speed_now(self):
        if self.arrived:
            return 0.0
        if JAM["t_start"] <= self.t_min < JAM["t_end"]:
            self.in_jam = True
            return JAM["v_kmh"]
        self.in_jam = False
        return self._segment_speed()

    def step(self, dt_min):
        """Avanza el camión dt_min minutos (integración en sub-pasos de 1 min)."""
        if self.arrived:
            self.t_min += dt_min
            return
        sub = 1.0
        t_left = dt_min
        while t_left > 1e-9 and not self.arrived:
            d = min(sub, t_left)
            v = self.speed_now()
            dk = v * d / 60.0
            self.km += dk
            self.m_kg -= PR["truck_cons_kg100"] * dk / 100.0
            self.t_min += d
            t_left -= d
            if self.km >= PR["route_km"]:
                self.km = PR["route_km"]
                self.arrived = True
                self.arrival_t = self.t_min

    # ---------- lo que "ve" la hidrogenera ----------
    def eta_min(self):
        """ETA estimada [min]. El estimador no conoce el futuro: usa una
        velocidad media nominal y, si detecta que el camión va lento,
        añade una penalización heurística."""
        if self.arrived:
            return 0.0
        remaining = PR["route_km"] - self.km
        eta = remaining / 82.0 * 60.0
        if self.speed_now() < 30.0:
            eta += 18.0  # penalización por retención detectada
        return eta
