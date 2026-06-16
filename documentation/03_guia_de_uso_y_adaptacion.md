# Guía de uso y adaptación del código

Este documento explica cómo está organizado el código, qué hace cada archivo y qué cambiar para adaptar el simulador a una instalación real o a nuevos objetivos. No es necesario entender el algoritmo MPC para seguir esta guía.

---

## Mapa de archivos

```
h2mpc/
├── params.py               ← PRIMER SITIO DONDE MIRAR: todos los parámetros físicos
├── prices.py               ← Precio horario de la electricidad
├── truck.py                ← Modelo del camión en ruta y estimador de ETA
├── plant.py                ← Planta "real" (sustituto de Simscape)
├── mpc.py                  ← El cerebro: MPC económico (no tocar salvo ajuste fino)
├── baseline.py             ← Controlador ingenuo de referencia (sin optimización)
├── simulate.py             ← Bucle principal: une todo y genera results.json
├── build_dashboard.py      ← Convierte results.json en el dashboard HTML
├── dashboard_template.html ← Plantilla visual (HTML/JS, no tocar)
├── dashboard.html          ← Resultado final (se regenera cada vez)
├── results.json            ← Datos de la última simulación (se regenera)
└── requirements.txt        ← Dependencias de Python
```

---

## `params.py`: el único archivo que hay que tocar para experimentar

Todos los parámetros físicos del sistema están centralizados aquí. El resto de módulos los leen de este diccionario `PR`. Para cambiar cualquier característica de la planta, el camión o el comportamiento del MPC, **solo hay que editar `params.py`**.

### Experimentos rápidos que se pueden hacer cambiando un parámetro

| Pregunta | Parámetro a cambiar | Efecto esperado |
|---|---|---|
| ¿Qué pasa si el electrolizador es más potente? | `P_ely_max_kW` | El MPC puede producir más H2 en menos tiempo; puede esperar más a precios baratos. |
| ¿Qué pasa si los tanques son más grandes? | `M_mp_max`, `M_hp_max` | El MPC tiene más margen para acumular H2 cuando la luz es barata. |
| ¿Qué pasa si el camión llega más cargado? | `truck_m0_kg` (subir) | Se necesita menos H2 para completar el repostaje, los requisitos bajan. |
| ¿Qué pasa si la ruta es más larga? | `route_km` (subir) | El camión tarda más y llega con menos H2; el MPC tiene más tiempo para preparar. |
| ¿El MPC penaliza demasiado los cambios bruscos? | `w_ramp` (bajar) | El electrolizador se enciende y apaga más agresivamente, siguiendo mejor el precio. |
| ¿Quiero una simulación de todo el día? | `t_total_min` (subir a 960 para 16h) | La simulación cubre más horas; ajustar también el diccionario `HOURLY` en `prices.py`. |

---

## `prices.py`: cambiar el perfil de precios eléctricos

El archivo define un diccionario con el precio de la electricidad (€/MWh) por cada hora del día. La función `price_eur_mwh` interpola linealmente entre horas.

```python
HOURLY = {
    5: 78.0,
    6: 96.0,
    7: 134.0,   # pico de la mañana
    8: 88.0,
    9: 52.0,
    10: 36.0,
    11: 31.0,   # valle solar
    12: 33.0,
}
```

**Para usar precios reales de OMIE o ESIOS:** sustituir el diccionario `HOURLY` por una llamada a la API. ESIOS (Red Eléctrica de España) ofrece un token gratuito. El resultado debe seguir siendo un diccionario `{hora: precio_eur_mwh}`.

---

## `truck.py`: cambiar el perfil de la ruta y la retención

El archivo define los tramos de velocidad de la ruta y el evento de retención de tráfico.

```python
SEGMENTS = [
    (0, 15, 60),      # km_inicio, km_fin, velocidad km/h
    (15, 150, 88),
    ...
]

JAM = dict(t_start=70.0, t_end=95.0, v_kmh=15.0)
```

- Para cambiar la ruta, editar `SEGMENTS` con los tramos reales (kilómetro inicio, kilómetro fin, velocidad media).
- Para cambiar la retención de tráfico, editar `JAM` (minuto de inicio, minuto de fin, velocidad durante la retención).
- Para eliminar la retención, establecer `JAM = None` y añadir un `if JAM is not None:` en el bucle de `simulate.py`.

**Para usar ETA real por GPS:** el MPC solo necesita recibir el número `eta_min` (minutos hasta la llegada). El método `truck.eta_min()` puede sustituirse por una llamada a una API de rutas (OSRM, Google Routes) que reciba la posición GPS actual del camión y devuelva el tiempo estimado de llegada.

---

## `plant.py`: conectar la planta real o Simscape

Este archivo es el **sustituto del modelo de Simscape**. Implementa la planta con sus no linealidades (consumo del electrolizador dependiente de carga, compresión isentrópica dependiente de presiones, factor de compresibilidad Z(p)).

La interfaz que el simulador espera es:

```python
resultado = plant.step(P_ely_kW, f_mp_kgh, f_hp_kgh, dispensing=True/False, dt_min=5.0)
```

El resultado es un diccionario con las claves: `P_ely`, `P_comp`, `P_pre`, `P_total`, `prod_kgh`, `f_mp`, `f_hp`, `disp_kgs`, `m_lp`, `m_mp`, `m_hp`, `p_lp`, `p_mp`, `p_hp`, `delivered`.

**Para conectar Simscape**, hay dos vías sin tocar `mpc.py` ni `simulate.py`:

1. **MATLAB Engine API for Python**: importar `matlab.engine`, cargar el modelo `.slx`, fijar las consignas con `set_param`, avanzar `dt_min` minutos con el modo de stepping de Simulink y leer los estados como salidas de bloques "To Workspace".

2. **FMU exportado de Simulink**: exportar el modelo como FMU (Functional Mock-up Unit) con Simulink Compiler y ejecutarlo desde Python con la librería `fmpy` (gratuita, `pip install fmpy`).

En ambos casos, la clase `Plant` queda reducida a un adaptador que llama al modelo externo y formatea la respuesta con las claves esperadas.

---

## `mpc.py`: ajuste fino del controlador

Este es el corazón del sistema. En condiciones normales **no debería modificarse**, pero si se conoce el algoritmo, se puede:

- **Cambiar el modelo lineal del electrolizador:** el parámetro `e_ely_mpc` en `params.py` ajusta el consumo específico que el MPC asume. Si la curva real del electrolizador es muy diferente, se puede usar la media ponderada en el rango de operación habitual.

- **Ampliar el horizonte a días completos:** el horizonte ya es "hasta el final del día" por defecto (N = n_total − k). Si la simulación cubre varios días, hay que definir una ventana de horizonte fija (por ejemplo, 12 horas) en lugar de "hasta el final".

- **Añadir costes de arranque/parada del compresor:** requeriría introducir una variable binaria (0/1 por paso) para indicar si el compresor está encendido, convirtiendo el LP en un MILP (Mixed Integer LP). HiGHS también resuelve MILP; el cambio es extenso pero el solver soporta la formulación.

- **MPC estocástico con incertidumbre de ETA:** en lugar de usar una única ETA estimada, se podrían muestrear N escenarios de ETA y optimizar el valor esperado del coste. Esto multiplica el tamaño del problema por N escenarios.

---

## `baseline.py`: el controlador de referencia

El controlador "ingenuo" no mira el precio de la electricidad: simplemente produce y comprime a tope hasta cumplir los mismos objetivos que el MPC. Su único propósito es cuantificar el ahorro que aporta el MPC en euros.

Si se quiere comparar el MPC con otra estrategia de control propia (por ejemplo, un controlador basado en reglas horarias), se puede reemplazar el contenido del método `act(m_lp, m_mp, m_hp)` con esa lógica. La interfaz es la misma: devuelve `(P_kW, f_mp_kgh, f_hp_kgh)`.

---

## `simulate.py`: el bucle principal

Este es el archivo que "une" todo. Cada 5 minutos:
1. Lee el estado del camión y calcula la ETA.
2. Llama a `solve_mpc(...)` para obtener la acción óptima.
3. Aplica esa acción a la planta real (`plant.step(...)`).
4. Aplica la acción del controlador ingenuo a una copia de la planta (`nplant.step(...)`).
5. Avanza el camión 5 minutos.
6. Guarda todos los datos en una lista `steps`.

Al terminar, escribe `results.json`.

**Cosas que se pueden cambiar aquí:**
- El evento de llegada del camión: la lógica de `docked` y `refuel_done` controla cuándo se activa el dispensado. Si hay varios camiones, se añade una lista de objetos `Truck`.
- La condición de fin de repostaje: actualmente termina cuando `plant.delivered_kg >= target - 0.05`.
- Los eventos que aparecen en el dashboard: el array `events` contiene mensajes con marca de tiempo.

---

## Flujo de datos completo

```
params.py ──────────────────────┐
                                 │ (todos los módulos leen de aquí)
prices.py ──> precios[k] ──────►│
truck.py  ──> eta_min(k) ──────►│
                                 ▼
                           simulate.py
                           (bucle k=0..N)
                                 │
                    ┌────────────┴─────────────┐
                    ▼                          ▼
               mpc.py                    baseline.py
          (acción óptima)            (acción ingenua)
                    │                          │
                    ▼                          ▼
               plant.py                  plant.py (copia)
          (planta con MPC)          (planta con baseline)
                    │                          │
                    └────────────┬─────────────┘
                                 ▼
                           results.json
                                 │
                                 ▼
                        build_dashboard.py
                                 │
                                 ▼
                           dashboard.html
```
