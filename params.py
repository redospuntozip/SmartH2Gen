# -*- coding: utf-8 -*-
"""
params.py — Parámetros centrales de la hidrogenera portátil.
Todos los módulos (planta, MPC, baseline, simulación) leen de aquí.
"""

PR = dict(
    # ----- Tiempo -----
    dt_min=5.0,                # paso de simulación / control [min]
    t_total_min=270.0,         # duración total simulada [min] (06:00 -> 10:30)
    t0_clock="06:00",          # hora de inicio (para precios y etiquetas)

    # ----- Electrolizador (PEM) -----
    P_ely_max_kW=400.0,        # potencia máxima
    e_ely_mpc=52.0,            # consumo específico usado por el MPC [kWh/kg] (modelo lineal)
    # la planta "real" usa e(carga) = 48 + 7*carga^1.4  (mejor a carga parcial)

    # ----- Tanques (masa útil) -----
    # LP = buffer a 200 bar (salida del electrolizador)
    V_lp_m3=0.80,  M_lp0_kg=4.0,  M_lp_min=0.5,  M_lp_max=12.0,
    # MP = 350 bar
    V_mp_m3=0.85,  M_mp0_kg=5.5,  M_mp_min=0.15, M_mp_max=20.0,
    # HP = 500 bar
    V_hp_m3=0.50,  M_hp0_kg=2.5,  M_hp_min=0.15, M_hp_max=15.0,

    # ----- Compresor de 2 etapas (aspira del LP) -----
    f_comp_max_kgh=30.0,       # caudal másico máximo total [kg/h]
    c_comp_mp_mpc=0.95,        # energía específica 200->350 bar usada por el MPC [kWh/kg]
    c_comp_hp_mpc=1.55,        # energía específica 200->500 bar usada por el MPC [kWh/kg]
    eta_comp=0.62,             # rendimiento isentrópico por etapa (planta)
    aux_comp=3.0,              # factor motor + refrigeración + auxiliares (planta)

    # ----- Dispensado -----
    f_disp_kgs=0.03,           # caudal de la válvula reductora / manguera [kg/s]
    e_precool_kwh_kg=0.35,     # precooler [kWh/kg dispensado]
    mp_reserve_kg=1.2,         # cascada: el MP deja de aportar por debajo de esta masa

    # ----- Camión -----
    truck_tank_L=820.0,        # volumen del depósito del camión
    truck_p_bar=350.0,         # presión de repostaje del camión
    truck_cap_kg=19.0,         # masa objetivo a 350 bar (~820 L)
    truck_m0_kg=16.6,          # masa al salir del origen
    truck_cons_kg100=7.0,      # consumo [kg H2 / 100 km]
    route_km=210.0,

    # ----- Requisitos del MPC en el instante de llegada -----
    req_mp_kg=11.8,            # masa mínima en MP al llegar el camión
    req_hp_kg=7.5,             # masa mínima en HP al llegar el camión

    # ----- Pesos del optimizador -----
    w_ramp=0.005,               # €/kW por suavizado de rampa del electrolizador
    w_slack=500.0,             # €/kg de penalización por incumplir requisitos (factibilidad)

    # ----- Gas -----
    R_h2=4124.0,               # J/(kg·K)
    T_K=288.0,                 # temperatura media de tanques
)
