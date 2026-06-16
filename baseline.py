# -*- coding: utf-8 -*-
"""
baseline.py — Controlador "ingenuo" de referencia (sin optimización).

Estrategia reactiva típica: en cuanto hay que preparar un repostaje, produce
y comprime A TOPE hasta cumplir los mismos objetivos que el MPC
(MP ≥ req_mp, HP ≥ req_hp, LP repuesto a su nivel inicial), sin mirar el
precio de la electricidad. Sirve para cuantificar el ahorro del MPC en €.
"""
from params import PR


class NaiveController: # es una clase que sirve como molde para crear objetos --> controlador ingenuo o "naive"
    def __init__(self): # self es la referencia al objeto creado
        self.done = False

    def act(self, m_lp, m_mp, m_hp): # act se ejecuta en cada paso de tiempo
        if (m_mp >= PR["req_mp_kg"] and m_hp >= PR["req_hp_kg"] and m_lp >= PR["M_lp0_kg"]):
            self.done = True # verifica que tenemos la cantidad de kg de H2 necesaria.
        if self.done:
            return 0.0, 0.0, 0.0 # si el sistema tiene H2 suficiente devuelve 3 0's.

        # electrolizador a tope mientras quede hueco en el sistema --> manda los kWs
        P = PR["P_ely_max_kW"] if m_lp < PR["M_lp_max"] - 0.1 else 0.0

        # compresor a tope: primero llena MP, luego HP --> manda los kg/h que usar.
        f_mp = f_hp = 0.0
        if m_lp > PR["M_lp_min"] + 0.3:
            if m_mp < PR["req_mp_kg"] + 0.2:
                f_mp = PR["f_comp_max_kgh"]
            elif m_hp < PR["req_hp_kg"] + 0.2:
                f_hp = PR["f_comp_max_kgh"]
        return P, f_mp, f_hp
