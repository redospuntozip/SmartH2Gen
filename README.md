# H2·MPC — Prototipo de control predictivo económico para una hidrogenera portátil

Prototipo funcional y 100 % gratuito (Python + scipy) de la herramienta que
decide **cuándo producir hidrógeno y cuándo comprimirlo** en función de la
**ETA del camión** y del **precio horario de la electricidad**, con un panel
web autocontenido para visualizarlo todo.

Arquitectura del proceso (igual que vuestro modelo de Simscape):

```
Electrolizador (H2 a 200 bar) ──> Tanque LP 200 bar ──> Compresor 2 etapas ──┬──> Tanque MP 350 bar ──┐
                                                                             └──> Tanque HP 500 bar ──┤
                                                                  válvula 0,03 kg/s + precooler <─────┘
                                                                            └──> manguera ──> camión (820 L)
```

---

## 1. Cómo ejecutarlo (2 minutos)

Necesitas Python 3.9+ (gratuito). En una terminal:

```bash
pip install -r requirements.txt   # numpy + scipy
python simulate.py                # corre el bucle cerrado MPC + planta + camión
python build_dashboard.py         # genera dashboard.html
```

Abre **`dashboard.html`** con doble clic en cualquier navegador (no hace
falta servidor: los resultados van embebidos). Dale a ▶ Reproducir.

> Si solo quieres ver el resultado, en este paquete ya va incluido un
> `dashboard.html` generado.

## 2. Qué hace cada archivo

| Archivo | Papel |
|---|---|
| `params.py` | Todos los parámetros (tanques, compresor, camión, requisitos, pesos). **Toca aquí para experimentar.** |
| `prices.py` | Precio eléctrico horario (curva sintética tipo OMIE). |
| `truck.py` | Camión en ruta + estimador de ETA (con una retención de tráfico para ver la replanificación). |
| `plant.py` | **Sustituto de vuestro Simscape**: planta "real" con no linealidades que el MPC no conoce (consumo del electrolizador según carga, compresión isentrópica dependiente de presiones, Z(p), cascada MP→HP). |
| `mpc.py` | El cerebro: MPC económico formulado como **programación lineal** (HiGHS, incluido en scipy). Minimiza € sujeto a balances de masa, límites de tanques y al **deadline** "MP ≥ 11,8 kg y HP ≥ 7,5 kg cuando llegue el camión". |
| `baseline.py` | Estrategia ingenua de referencia (producir/comprimir a tope sin mirar el precio) para cuantificar el ahorro. |
| `simulate.py` | Bucle cerrado: cada 5 min mide estados, re-resuelve el MPC con la ETA actualizada y aplica la acción a la planta. Escribe `results.json`. |
| `build_dashboard.py` + `dashboard_template.html` | Generan el panel de visualización. |

## 3. El escenario de demostración

- 06:00 — el camión sale a 210 km; precio alto por la mañana (pico de 134 €/MWh a las 07:00) que cae con la solar (52 a las 09:00, 31 a las 11:00).
- Minuto 70 — retención de tráfico: la ETA sube y el MPC **replanifica en vivo**.
- ~08:54 — llegada, repostaje de ~16,8 kg a 0,03 kg/s en cascada MP→HP.
- Después, el MPC repone el tanque LP a su nivel inicial aprovechando el valle solar.

Resultado típico: **≈38 € con MPC frente a ≈93 € sin optimizar (−58 %)**,
es decir 2,3 €/kg frente a 5,5 €/kg de coste eléctrico. El MPC retrasa la
producción hacia las horas baratas y comprime en el último momento
compatible con el deadline; el baseline lo hace todo en el pico matinal.

## 4. Qué tendrías que hacer tú en el futuro (integración real)

El prototipo está diseñado para que cada pieza "falsa" se sustituya por la
real **sin tocar el MPC**:

1. **Tu modelo de Simscape en lugar de `plant.py`.** Mantén la misma
   interfaz `step(P_ely, f_mp, f_hp, dispensar, dt) → estados`. Dos vías:
   - *MATLAB Engine API for Python* (viene con tu licencia de MATLAB):
     `import matlab.engine`, cargar el modelo, fijar las consignas con
     `set_param`, avanzar `dt` con `sim`/stepping y leer los estados.
   - Exportar el modelo como **FMU** (Simulink Compiler) y ejecutarlo desde
     Python con la librería gratuita `fmpy`.
   También puedes invertir el sentido: dejar Simulink como maestro y llamar
   a `solve_mpc()` desde un bloque *MATLAB Function / Python* cada 5 min.
2. **Precios reales en `prices.py`.** API pública de ESIOS (Red Eléctrica,
   token gratuito) u OMIE para el precio horario del día D y D+1. Son
   ~15 líneas con `requests`.
3. **ETA real en `truck.py`.** Posición GPS del camión (telemetría) + una
   API de rutas para la ETA: OSRM (gratuita, autoalojable) o Google
   Routes. El MPC solo necesita el número `eta_min`.
4. **Calibración de `params.py`** con vuestros datos: volúmenes y límites
   reales de tanques, curva kWh/kg del electrolizador, kWh/kg del compresor
   (el modelo lineal del MPC no necesita ser exacto: el bucle cerrado
   corrige el error, como ya se ve en el prototipo).
5. Cuando funcione, ampliaciones naturales: incertidumbre de ETA (MPC
   robusto/estocástico), varios camiones, degradación del electrolizador,
   o dimensionado óptimo de tanques usando este mismo simulador.

## 5. Limitaciones del prototipo

- El MPC usa un modelo lineal (consumos específicos constantes); es lo
  habitual en la capa económica y el realimentado compensa el error.
- Arranques/paradas del compresor sin coste fijo (sería un MILP; HiGHS
  también lo resuelve si lo necesitáis).
- Un solo camión y precios deterministas.
