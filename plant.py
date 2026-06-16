# -*- coding: utf-8 -*-
"""
plant.py — Planta "real" simplificada de la hidrogenera.

ESTE ARCHIVO ES EL SUSTITUTO DE VUESTRO MODELO DE SIMSCAPE.
En el futuro, se reemplaza esta clase por una llamada a MATLAB/Simulink
(MATLAB Engine API for Python o un FMU exportado) manteniendo la misma
interfaz: step(P_ely, f_mp, f_hp, dispensar) -> estados y potencias reales.

Incluye no linealidades que el MPC NO conoce (su modelo es lineal), para que
el prototipo demuestre que el bucle cerrado corrige el error de modelo:
  - consumo específico del electrolizador dependiente de la carga
  - trabajo de compresión dependiente de las presiones reales (isentrópico,
    2 etapas con refrigeración intermedia)
  - presiones de tanque con factor de compresibilidad Z(p)
  - cascada de dispensado MP -> HP
"""
import math
from params import PR


def Z(p_bar):
    """Factor de compresibilidad aproximado del H2 a ~288 K."""
    return 1.0 + 6.4e-4 * p_bar


def pressure_bar(m_kg, V_m3):
    """Presión del tanque a partir de la masa (gas real, iterando Z)."""
    if m_kg <= 0:
        return 0.0
    p = m_kg * PR["R_h2"] * PR["T_K"] / V_m3 / 1e5  # ideal
    for _ in range(4):
        p = (m_kg / V_m3) * Z(p) * PR["R_h2"] * PR["T_K"] / 1e5
    return p


class Plant:
    def __init__(self):
        self.m_lp = PR["M_lp0_kg"]
        self.m_mp = PR["M_mp0_kg"]
        self.m_hp = PR["M_hp0_kg"]
        self.delivered_kg = 0.0

    # ---------- submodelos ----------
    def ely_spec_kwh_kg(self, load):
        """Consumo específico real del electrolizador [kWh/kg] según carga."""
        return 48.0 + 7.0 * (max(load, 0.05) ** 1.4)

    def comp_spec_kwh_kg(self, p_in_bar, p_out_bar):
        """Trabajo específico real del compresor de 2 etapas con
        refrigeración intermedia + factor de auxiliares [kWh/kg]."""
        p_in = max(p_in_bar, 20.0)
        r = max(p_out_bar / p_in, 1.01)
        k = 1.41
        expo = (k - 1.0) / (2.0 * k)          # 2 etapas, ratio repartido
        w = 2.0 * (k / (k - 1.0)) * PR["R_h2"] * PR["T_K"] \
            * (r ** expo - 1.0) / PR["eta_comp"]          # J/kg
        return w / 3.6e6 * PR["aux_comp"]

    # ---------- paso de simulación ----------
    def step(self, P_ely_kW, f_mp_kgh, f_hp_kgh, dispensing, dt_min):
        dt_h = dt_min / 60.0
        out = {}

        # --- electrolizador -> tanque LP (200 bar) ---
        P_ely = min(max(P_ely_kW, 0.0), PR["P_ely_max_kW"])
        load = P_ely / PR["P_ely_max_kW"]
        prod_kgh = P_ely / self.ely_spec_kwh_kg(load) if P_ely > 1.0 else 0.0
        # limitar si el LP está lleno
        space = PR["M_lp_max"] - self.m_lp
        prod_kg = min(prod_kgh * dt_h, max(space, 0.0))
        prod_kgh = prod_kg / dt_h if dt_h > 0 else 0.0
        P_ely = prod_kgh * self.ely_spec_kwh_kg(load) if prod_kgh > 0 else 0.0

        # --- compresor LP -> MP / HP ---
        f_mp = max(f_mp_kgh, 0.0)
        f_hp = max(f_hp_kgh, 0.0)
        tot = f_mp + f_hp
        if tot > PR["f_comp_max_kgh"]:
            f_mp *= PR["f_comp_max_kgh"] / tot
            f_hp *= PR["f_comp_max_kgh"] / tot
        # disponibilidad en LP y hueco en MP/HP
        avail = max(self.m_lp + prod_kg - PR["M_lp_min"], 0.0)
        need = (f_mp + f_hp) * dt_h
        if need > avail and need > 0:
            f_mp *= avail / need
            f_hp *= avail / need
        f_mp = min(f_mp, max(PR["M_mp_max"] - self.m_mp, 0.0) / dt_h)
        f_hp = min(f_hp, max(PR["M_hp_max"] - self.m_hp, 0.0) / dt_h)

        p_lp = pressure_bar(self.m_lp, PR["V_lp_m3"])
        p_mp = pressure_bar(self.m_mp, PR["V_mp_m3"])
        p_hp = pressure_bar(self.m_hp, PR["V_hp_m3"])
        P_comp = f_mp * self.comp_spec_kwh_kg(p_lp, max(p_mp, 350.0)) \
               + f_hp * self.comp_spec_kwh_kg(p_lp, max(p_hp, 500.0))

        # --- dispensado en cascada (MP primero, luego HP) ---
        disp_kg = 0.0
        d_mp = d_hp = 0.0
        if dispensing:
            want = min(PR["f_disp_kgs"] * 60.0 * dt_min,
                       PR["truck_cap_kg"] * 0.985 - PR["truck_m0_kg"]
                       + PR["truck_cons_kg100"] * PR["route_km"] / 100.0
                       - self.delivered_kg)
            want = max(want, 0.0)
            from_mp = min(want, max(self.m_mp - PR["mp_reserve_kg"], 0.0))
            from_hp = min(want - from_mp, max(self.m_hp - PR["M_hp_min"], 0.0))
            d_mp, d_hp = from_mp, from_hp
            disp_kg = from_mp + from_hp
            self.delivered_kg += disp_kg

        # --- balances de masa ---
        self.m_lp += prod_kg - (f_mp + f_hp) * dt_h
        self.m_mp += f_mp * dt_h - d_mp
        self.m_hp += f_hp * dt_h - d_hp
        self.m_lp = min(max(self.m_lp, 0.0), PR["M_lp_max"])
        self.m_mp = min(max(self.m_mp, 0.0), PR["M_mp_max"])
        self.m_hp = min(max(self.m_hp, 0.0), PR["M_hp_max"])

        P_pre = disp_kg / dt_h * PR["e_precool_kwh_kg"] if disp_kg > 0 else 0.0

        out.update(
            P_ely=P_ely, P_comp=P_comp, P_pre=P_pre,
            P_total=P_ely + P_comp + P_pre,
            prod_kgh=prod_kgh, f_mp=f_mp, f_hp=f_hp,
            disp_kgs=disp_kg / (dt_min * 60.0),
            m_lp=self.m_lp, m_mp=self.m_mp, m_hp=self.m_hp,
            p_lp=pressure_bar(self.m_lp, PR["V_lp_m3"]),
            p_mp=pressure_bar(self.m_mp, PR["V_mp_m3"]),
            p_hp=pressure_bar(self.m_hp, PR["V_hp_m3"]),
            delivered=self.delivered_kg,
        )
        return out
