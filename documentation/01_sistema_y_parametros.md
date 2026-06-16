# El sistema físico y sus parámetros

Este documento describe la instalación física que el modelo simula y todos los parámetros que la caracterizan. No es necesario saber programar para entenderlo: basta con conocer los conceptos básicos de hidrógeno y termodinámica.

---

## Arquitectura de la hidrogenera portátil

La estación sigue esta cadena de transformación:

```
Electricidad
     |
     v
Electrolizador PEM
(produce H2 a ~200 bar)
     |
     v
 Tanque LP (baja presión, 200 bar)
     |
     v
Compresor de 2 etapas
     |          |
     v          v
Tanque MP    Tanque HP
(350 bar)    (500 bar)
     |          |
     +----+-----+
          |
          v
    Válvula + Precooler
          |
          v
      Manguera --> Camión (depósito 820 L, 350 bar)
```

El electrolizador produce hidrógeno a baja presión (LP). El compresor coge ese hidrógeno del tanque LP y lo empuja hasta los tanques de media presión (MP) o alta presión (HP), según lo que necesite el MPC. Cuando llega el camión, se dispensa en cascada: primero desde MP, y si no hay suficiente, desde HP.

---

## Parámetros del sistema

Todos estos valores están en el archivo `params.py` y se pueden cambiar para adaptar el modelo a una instalación real.

### Tiempo de simulación

| Parámetro | Clave | Valor por defecto | Unidades | Descripción |
|---|---|---|---|---|
| Paso de tiempo | `dt_min` | 5 | min | Intervalo entre dos decisiones del MPC. Cada 5 minutos el controlador vuelve a calcular el plan óptimo. |
| Duración total | `t_total_min` | 270 | min | Cuánto tiempo dura la simulación (4 h 30 min, de 06:00 a 10:30). |
| Hora de inicio | `t0_clock` | "06:00" | hh:mm | Hora real a la que empieza la simulación (afecta a los precios de electricidad). |

---

### Electrolizador PEM

| Parámetro | Clave | Valor | Unidades | Descripción |
|---|---|---|---|---|
| Potencia máxima | `P_ely_max_kW` | 400 | kW | Potencia eléctrica máxima que puede absorber el electrolizador. La variable de control del MPC nunca supera este valor. |
| Consumo específico (modelo MPC) | `e_ely_mpc` | 52 | kWh/kg | Cuánta energía eléctrica consume el electrolizador para producir 1 kg de H2, según el **modelo lineal** del MPC. |

> **Nota sobre la no linealidad:** El electrolizador real consume más cuando trabaja a cargas muy altas o muy bajas. La planta simula eso con la fórmula `e(carga) = 48 + 7·carga^1.4` kWh/kg. El MPC usa un valor fijo (52 kWh/kg) porque su modelo es lineal; el bucle cerrado corrige el error en cada iteración.

---

### Tanques de almacenamiento

Hay tres tanques que trabajan a distintas presiones:

#### Tanque LP (baja presión, ~200 bar) — buffer entre el electrolizador y el compresor

| Parámetro | Clave | Valor | Unidades | Descripción |
|---|---|---|---|---|
| Volumen | `V_lp_m3` | 0.80 | m³ | Volumen geométrico interior del tanque. |
| Masa inicial | `M_lp0_kg` | 4.0 | kg | Hidrógeno almacenado al inicio de la simulación. |
| Masa mínima | `M_lp_min` | 0.5 | kg | Límite inferior de seguridad (nunca se vacía del todo). |
| Masa máxima | `M_lp_max` | 12.0 | kg | Capacidad máxima del tanque. |

#### Tanque MP (media presión, ~350 bar) — presión de repostaje del camión

| Parámetro | Clave | Valor | Unidades | Descripción |
|---|---|---|---|---|
| Volumen | `V_mp_m3` | 0.85 | m³ | Volumen geométrico interior. |
| Masa inicial | `M_mp0_kg` | 5.5 | kg | Hidrógeno al inicio de la simulación. |
| Masa mínima | `M_mp_min` | 0.15 | kg | Límite inferior de seguridad. |
| Masa máxima | `M_mp_max` | 20.0 | kg | Capacidad máxima. |

#### Tanque HP (alta presión, ~500 bar) — reserva para completar el repostaje

| Parámetro | Clave | Valor | Unidades | Descripción |
|---|---|---|---|---|
| Volumen | `V_hp_m3` | 0.50 | m³ | Volumen geométrico interior. |
| Masa inicial | `M_hp0_kg` | 2.5 | kg | Hidrógeno al inicio de la simulación. |
| Masa mínima | `M_hp_min` | 0.15 | kg | Límite inferior de seguridad. |
| Masa máxima | `M_hp_max` | 15.0 | kg | Capacidad máxima. |

---

### Compresor de dos etapas

El compresor aspira hidrógeno del tanque LP y lo impulsa hacia MP o HP en dos pasos consecutivos con refrigeración intermedia.

| Parámetro | Clave | Valor | Unidades | Descripción |
|---|---|---|---|---|
| Caudal máximo total | `f_comp_max_kgh` | 30 | kg/h | La suma del caudal hacia MP y hacia HP no puede superar este límite. |
| Energía específica LP→MP (MPC) | `c_comp_mp_mpc` | 0.95 | kWh/kg | Energía que el modelo del MPC asigna a comprimir 1 kg de 200 a 350 bar. |
| Energía específica LP→HP (MPC) | `c_comp_hp_mpc` | 1.55 | kWh/kg | Energía que el modelo del MPC asigna a comprimir 1 kg de 200 a 500 bar. |
| Rendimiento isentrópico | `eta_comp` | 0.62 | adimensional | Eficiencia real de cada etapa de compresión (usado en la planta, no en el MPC). |
| Factor de auxiliares | `aux_comp` | 3.0 | adimensional | Multiplicador que engloba motor eléctrico, ventiladores de refrigeración y otros consumos auxiliares (usado en la planta). |

---

### Dispensado al camión

| Parámetro | Clave | Valor | Unidades | Descripción |
|---|---|---|---|---|
| Caudal de la manguera | `f_disp_kgs` | 0.03 | kg/s | Velocidad máxima a la que la válvula reductora puede transferir H2 al depósito del camión. |
| Consumo del precooler | `e_precool_kwh_kg` | 0.35 | kWh/kg | Energía del enfriador que baja la temperatura del H2 antes de entrar al depósito del camión (necesario para evitar sobrepresión térmica). |
| Reserva de cascada en MP | `mp_reserve_kg` | 1.2 | kg | Masa mínima que debe quedar en MP después del dispensado; si queda menos, el resto se toma de HP. |

---

### Camión de hidrógeno

| Parámetro | Clave | Valor | Unidades | Descripción |
|---|---|---|---|---|
| Volumen del depósito | `truck_tank_L` | 820 | L | Volumen geométrico del depósito del camión. |
| Presión de repostaje | `truck_p_bar` | 350 | bar | El camión repostea a 350 bar (presión MP). |
| Masa objetivo | `truck_cap_kg` | 19.0 | kg | Masa de H2 que corresponde al depósito lleno a 350 bar. |
| Masa al salir del origen | `truck_m0_kg` | 16.6 | kg | H2 que lleva el camión cuando sale del centro logístico (ya lleva algo de combustible propio). |
| Consumo en ruta | `truck_cons_kg100` | 7.0 | kg/100 km | Cuánto H2 quema el camión por cada 100 km recorridos. |
| Distancia de la ruta | `route_km` | 210 | km | Kilómetros entre el centro logístico y la hidrogenera. |

---

### Requisitos del MPC en la llegada del camión

Estos son los "objetivos mínimos" que el MPC debe garantizar para cuando llegue el camión, es decir, la restricción de *deadline*:

| Parámetro | Clave | Valor | Unidades | Descripción |
|---|---|---|---|---|
| Masa mínima en MP al llegar | `req_mp_kg` | 11.8 | kg | El tanque MP debe tener al menos esta masa cuando llegue el camión. |
| Masa mínima en HP al llegar | `req_hp_kg` | 7.5 | kg | El tanque HP debe tener al menos esta masa cuando llegue el camión. |

> Estos valores se calcularon a partir de la masa que el camión necesita repostar (≈ 16,8 kg tras descontar lo que ya trae), repartida entre la cascada MP→HP.

---

### Pesos del optimizador

Estos parámetros no representan propiedades físicas del sistema, sino cuánto le "importa" al MPC cada tipo de penalización. Son botones de ajuste del comportamiento del controlador:

| Parámetro | Clave | Valor | Unidades | Descripción |
|---|---|---|---|---|
| Penalización por rampa | `w_ramp` | 0.005 | €/kW | Cuánto cuesta en la función objetivo cada kW de cambio brusco de potencia del electrolizador entre dos pasos. Evita subidas y bajadas rápidas que desgastan el equipo. |
| Penalización por holgura | `w_slack` | 500 | €/kg | Coste ficticio altísimo por incumplir las restricciones de masa mínima en los tanques. Al ser tan alto, el MPC solo recurre a esto como último recurso de emergencia (garantiza que el problema siempre tiene solución). |

---

### Constantes del gas (hidrógeno)

| Parámetro | Clave | Valor | Unidades | Descripción |
|---|---|---|---|---|
| Constante específica del H2 | `R_h2` | 4124 | J/(kg·K) | Constante de gas ideal del hidrógeno molecular (R universal / masa molar). |
| Temperatura de los tanques | `T_K` | 288 | K | Temperatura media asumida en el interior de los tanques (~15 °C). Se usa para calcular la presión a partir de la masa con la ecuación de gas real. |

---

## Resumen visual del flujo de energía y masa

```
Electricidad (precio variable €/MWh)
        |
        | P_ely [kW]
        v
  Electrolizador --> H2 [kg/h = P_ely / 52 kWh/kg]
        |
        v
    Tanque LP (200 bar, 0-12 kg)
        |
        | f_mp [kg/h]         | f_hp [kg/h]
        v                     v
  Tanque MP (350 bar)    Tanque HP (500 bar)
   0.15 - 20 kg           0.15 - 15 kg
        |                     |
        +----------+----------+
                   |
            Precooler (0.35 kWh/kg)
                   |
             0.03 kg/s
                   |
                   v
            Depósito del camión (820 L, 350 bar)
```
