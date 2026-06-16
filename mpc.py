# -*- coding: utf-8 -*-
"""
mpc.py — MPC económico de la hidrogenera (programación lineal, HiGHS).

En cada paso resuelve, sobre el horizonte restante hasta el final del día:

  min  Σ precio(k)·[P_ely(k) + c_mp·f_mp(k) + c_hp·f_hp(k)]·Δt + w_ramp·Σ|ΔP_ely| + w_slack·(holguras)

  s.a. balances de masa LP / MP / HP (modelo lineal)
       límites de masa de cada tanque
       límites de potencia y caudal del compresor
       M_MP(t_llegada) ≥ req_mp ,  M_HP(t_llegada) ≥ req_hp   (deadline!)
       M_LP(final) ≥ M_LP(inicial)   (deja la estación como estaba)

Variables por paso: P_ely [kW], f_mp [kg/h], f_hp [kg/h] (+ aux de rampa).
Las holguras garantizan factibilidad si la ETA se adelanta de golpe.
"""
import numpy as np
from scipy.optimize import linprog
from params import PR


def solve_mpc(m_lp, m_mp, m_hp, k_now, n_total, eta_min, delivered_kg, prices, P_prev=0.0):
    """Devuelve la acción a aplicar ahora y el plan completo (para pintarlo).

    prices: vector de precios €/MWh para TODOS los pasos de la simulación.
    eta_min: ETA estimada del camión (None si ya repostó y se fue).
    """
    dt_h = PR["dt_min"] / 60.0 # intervalo de tiempo entre iteraciones
    N = n_total - k_now                       # 1. calculamos los pasos restantes del horizonte
    if N <= 0:
        return dict(P_ely=0.0, f_mp=0.0, f_hp=0.0, plan=None)

    y = 1.0 / PR["e_ely_mpc"]                 # 2. kg/kWh del electrolizador --> e_ely_mpc estaba en kWh/kg
    pr = np.asarray(prices[k_now:k_now + N])  # €/MWh por paso desde el momento hasta el final

    # ---- perfil de dispensado previsto d_mp(k), d_hp(k) [kg/h] ----
    to_deliver = max(PR["truck_cap_kg"] * 0.985 - (PR["truck_m0_kg"] - PR["truck_cons_kg100"] * PR["route_km"] / 100.0) - delivered_kg, 0.0)
    d_mp = np.zeros(N)
    d_hp = np.zeros(N)
    j_arr = None
    if eta_min is not None and to_deliver > 0.05:
        j_arr = int(round(eta_min / PR["dt_min"]))
        j_arr = min(max(j_arr, 0), N - 1) # ejemplo: ETA=18 min, dt=5 → j_arr=4 (llegará en el paso 4)
        # reparto previsto de la cascada MP -> HP:
        #  - si el camión ya está conectado, usar las masas reales actuales
        #  - si aún no ha llegado, usar la masa requerida en MP a su llegada
        avail_mp = (max(m_mp - PR["mp_reserve_kg"], 0.0) if j_arr == 0
                    else max(PR["req_mp_kg"] - PR["mp_reserve_kg"], 0.0))  # puedo dar como máximo esta masa de MP, el resto lo saco de HP
        from_mp = min(to_deliver, avail_mp)
        from_hp = to_deliver - from_mp
        n_disp = 3                            # OJO !!! simplificación importante: repartir el repostaje en 3 pasos ... si dt = 5mins será en 15 mins
        for j in range(j_arr, min(j_arr + n_disp, N)): # irá desde j_arr hasta j_arr + 2
            d_mp[j] = from_mp / (n_disp * dt_h) # caudal calculado --> habría que poner algo de ver si es mayor que 0.03 kg/s
            d_hp[j] = from_hp / (n_disp * dt_h) # caudal calculado

    # ---- variables: x = [P(0..N-1) | f_mp | f_hp | r(0..N-1) | s_mp s_hp s_lp] --> potencia elect, caudal de compresion MP, "" HP, rampa de suavizado (cambio de P entre pasos), holgura (slack) cuantos kg les falta
    nP, nF = N, N
    iP, iMP, iHP, iR = 0, N, 2 * N, 3 * N # (0, 10, 20, 30)
    iS = 4 * N # (40)
    nx = 4 * N + 3 # (43)

    # ---- la función objetivo ----
    c = np.zeros(nx) # vector de precio por variable en €
    c[iP:iP + N] = pr * dt_h / 1000.0 # € por kWh ely 
    c[iMP:iMP + N] = pr * dt_h / 1000.0 * PR["c_comp_mp_mpc"] # penalizaciones o costes por comprimir
    c[iHP:iHP + N] = pr * dt_h / 1000.0 * PR["c_comp_hp_mpc"]
    c[iR:iR + N] = PR["w_ramp"] # penalización por cambios bruscos
    c[iS:] = PR["w_slack"] # penalización por incumplimiento

    A, b = [], []
    # Se va a resolver A * x < b 
    # Donde x es un vecor de decisiones (potencias y caudales)
    # A es la matriz de coeficientes (cuanto consume cada variable)
    # b es la cpacidad máxima permitida

    def row():
        return np.zeros(nx)

    # ---- capacidad del compresor ----
    # para que la suma del flujo a mp y a hp en cualquier instante k no supere el limite del compresor
    for k in range(N):
        r = row(); r[iMP + k] = 1; r[iHP + k] = 1
        A.append(r); b.append(PR["f_comp_max_kgh"]) # b pone como limite el caudal maximo del compresor --> la suma de ambos flujos no puede superar el del compresor

    # ---- balances acumulados de tanques ----
    Dmp = np.cumsum(d_mp) * dt_h              # dispensado acumulado [kg]
    Dhp = np.cumsum(d_hp) * dt_h
    for j in range(1, N + 1):
        # M_LP(j) = m_lp + Σ (P·y − f_mp − f_hp)·dt_h
        rU = row(); rU[iP:iP + j] = y * dt_h
        rU[iMP:iMP + j] = -dt_h; rU[iHP:iHP + j] = -dt_h
        A.append(rU);  b.append(PR["M_lp_max"] - m_lp)          # ≤ max
        A.append(-rU); b.append(m_lp - PR["M_lp_min"])          # ≥ min

        # M_MP(j) = m_mp + Σ f_mp·dt_h − Dmp(j)
        rM = row(); rM[iMP:iMP + j] = dt_h
        A.append(rM);  b.append(PR["M_mp_max"] - m_mp + Dmp[j - 1])
        A.append(-rM); b.append(m_mp - Dmp[j - 1] - PR["M_mp_min"])

        rH = row(); rH[iHP:iHP + j] = dt_h
        A.append(rH);  b.append(PR["M_hp_max"] - m_hp + Dhp[j - 1])
        A.append(-rH); b.append(m_hp - Dhp[j - 1] - PR["M_hp_min"])

    # ---- requisito en la llegada del camión (deadline) ----
    if j_arr is not None and j_arr >= 1:
        rM = row(); rM[iMP:iMP + j_arr] = -dt_h; rM[iS] = -1
        A.append(rM); b.append(m_mp - PR["req_mp_kg"])
        rH = row(); rH[iHP:iHP + j_arr] = -dt_h; rH[iS + 1] = -1
        A.append(rH); b.append(m_hp - PR["req_hp_kg"])

    # ---- terminal: el LP acaba al menos como empezó el día ----
    rT = row(); rT[iP:iP + N] = -y * dt_h
    rT[iMP:iMP + N] = dt_h; rT[iHP:iHP + N] = dt_h; rT[iS + 2] = -1
    A.append(rT); b.append(m_lp - PR["M_lp0_kg"])

    # ---- rampa |P(k) − P(k−1)| ≤ r(k) ----
    for k in range(N):
        r1 = row(); r1[iP + k] = 1; r1[iR + k] = -1
        r2 = row(); r2[iP + k] = -1; r2[iR + k] = -1
        if k == 0:
            A.append(r1); b.append(P_prev)
            A.append(r2); b.append(-P_prev)
        else:
            r1[iP + k - 1] = -1; A.append(r1); b.append(0.0)
            r2[iP + k - 1] = 1;  A.append(r2); b.append(0.0)

    bounds = ([(0, PR["P_ely_max_kW"])] * N
              + [(0, PR["f_comp_max_kgh"])] * (2 * N)
              + [(0, None)] * N
              + [(0, None)] * 3)

    res = linprog(c, A_ub=np.array(A), b_ub=np.array(b),
                  bounds=bounds, method="highs")
    if not res.success:
        # plan de emergencia: producir y comprimir a tope
        return dict(P_ely=PR["P_ely_max_kW"], f_mp=PR["f_comp_max_kgh"],
                    f_hp=0.0, plan=None, infeasible=True)

    x = res.x
    plan = dict(
        k0=k_now,
        P=[round(v, 1) for v in x[iP:iP + N]],
        Pc=[round(PR["c_comp_mp_mpc"] * a + PR["c_comp_hp_mpc"] * h, 2)
            for a, h in zip(x[iMP:iMP + N], x[iHP:iHP + N])],
    )
    return dict(P_ely=float(x[iP]), f_mp=float(x[iMP]), f_hp=float(x[iHP]),
                plan=plan, cost_plan=float(res.fun), infeasible=False)
