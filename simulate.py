# -*- coding: utf-8 -*-
"""
simulate.py — Bucle cerrado: MPC + planta + camión, y baseline en paralelo.

Ejecutar:  python simulate.py
Genera:    results.json  (lo consume build_dashboard.py)
"""
import json
import numpy as np
from params import PR
from prices import price_eur_mwh, clock_label
from truck import Truck, JAM
from plant import Plant
from mpc import solve_mpc
from baseline import NaiveController


def run():
    dt = PR["dt_min"]
    n_total = int(PR["t_total_min"] / dt)
    prices = [price_eur_mwh(k * dt, PR["t0_clock"]) for k in range(n_total)]

    truck = Truck()
    plant = Plant()
    nplant = Plant()
    naive = NaiveController()

    cost_mpc = 0.0
    cost_naive = 0.0
    P_prev = 0.0
    docked = False
    refuel_done = False
    steps = []
    events = [dict(t=0, txt="El camión sale del centro logístico (210 km). "
                            "Arranca el MPC económico.")]
    jam_logged = False
    arr_logged = False

    for k in range(n_total):
        t_min = k * dt
        price = prices[k]

        # --- estado del camión visto por la estación ---
        if truck.arrived and not refuel_done:
            docked = True
        eta = None if refuel_done else (truck.eta_min() if not truck.arrived else 0.0)

        # --- MPC ---
        sol = solve_mpc(plant.m_lp, plant.m_mp, plant.m_hp, k, n_total,
                        eta, plant.delivered_kg, prices, P_prev)

        # --- aplicar a la planta "real" ---
        o = plant.step(sol["P_ely"], sol["f_mp"], sol["f_hp"],
                       dispensing=docked and not refuel_done, dt_min=dt)
        P_prev = o["P_ely"]
        cost_mpc += price / 1000.0 * o["P_total"] * dt / 60.0

        target = (PR["truck_cap_kg"] * 0.985
                  - (PR["truck_m0_kg"] - PR["truck_cons_kg100"] * PR["route_km"] / 100.0))
        if docked and plant.delivered_kg >= target - 0.05 and not refuel_done:
            refuel_done = True
            events.append(dict(t=t_min + dt,
                               txt=f"Repostaje completado: {plant.delivered_kg:.1f} kg "
                                   f"a 0,03 kg/s. El camión se va."))

        # --- baseline en paralelo (misma física, misma demanda) ---
        Pn, fmn, fhn = naive.act(nplant.m_lp, nplant.m_mp, nplant.m_hp)
        on = nplant.step(Pn, fmn, fhn,
                         dispensing=docked and not refuel_done, dt_min=dt)
        cost_naive += price / 1000.0 * on["P_total"] * dt / 60.0

        # --- mover el camión durante este intervalo ---
        was_arrived = truck.arrived
        truck.step(dt)
        if truck.in_jam and not jam_logged:
            jam_logged = True
            events.append(dict(t=t_min, txt="Retención de tráfico en ruta: la ETA "
                                            "aumenta y el MPC replanifica."))
        if truck.arrived and not was_arrived and not arr_logged:
            arr_logged = True
            events.append(dict(t=truck.arrival_t,
                               txt=f"El camión llega a la hidrogenera "
                                   f"({clock_label(truck.arrival_t)}). Conectando manguera."))

        steps.append(dict(
            t=t_min, clock=clock_label(t_min), price=round(price, 1),
            truck=dict(km=round(truck.km, 1), frac=round(truck.km / PR["route_km"], 4),
                       v=round(truck.speed_now(), 0), eta=None if eta is None else round(eta, 0),
                       fuel=round(truck.m_kg, 2), arrived=truck.arrived,
                       jam=truck.in_jam, refueled=refuel_done),
            mpc=dict(P=round(o["P_ely"], 1), Pc=round(o["P_comp"], 2),
                     Ppre=round(o["P_pre"], 2),
                     prod=round(o["prod_kgh"], 2), fmp=round(o["f_mp"], 2),
                     fhp=round(o["f_hp"], 2), disp=round(o["disp_kgs"], 4),
                     mlp=round(o["m_lp"], 2), mmp=round(o["m_mp"], 2),
                     mhp=round(o["m_hp"], 2),
                     plp=round(o["p_lp"], 0), pmp=round(o["p_mp"], 0),
                     php=round(o["p_hp"], 0),
                     deliv=round(o["delivered"], 2), cost=round(cost_mpc, 2),
                     infeas=bool(sol.get("infeasible", False))),
            naive=dict(P=round(on["P_ely"], 1), Pc=round(on["P_comp"], 2),
                       cost=round(cost_naive, 2)),
            plan=sol.get("plan"),
        ))

    summary = dict(
        cost_mpc=round(cost_mpc, 2), cost_naive=round(cost_naive, 2),
        saving_eur=round(cost_naive - cost_mpc, 2),
        saving_pct=round(100 * (cost_naive - cost_mpc) / max(cost_naive, 1e-9), 1),
        delivered_kg=round(plant.delivered_kg, 2),
        eur_kg_mpc=round(cost_mpc / max(plant.delivered_kg, 1e-9), 2),
        eur_kg_naive=round(cost_naive / max(plant.delivered_kg, 1e-9), 2),
        arrival_clock=clock_label(truck.arrival_t) if truck.arrival_t else "-",
    )

    data = dict(
        meta=dict(dt_min=dt, t0=PR["t0_clock"], n=n_total,
                  route_km=PR["route_km"], jam=JAM,
                  P_ely_max=PR["P_ely_max_kW"], f_comp_max=PR["f_comp_max_kgh"],
                  caps=dict(lp=PR["M_lp_max"], mp=PR["M_mp_max"], hp=PR["M_hp_max"]),
                  req=dict(mp=PR["req_mp_kg"], hp=PR["req_hp_kg"])),
        prices=[round(p, 1) for p in prices],
        steps=steps, events=events, summary=summary,
    )
    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print("results.json escrito.")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()
