# Fundamento matemático del MPC económico

Este documento explica cómo funciona el algoritmo de control, qué ecuaciones resuelve y por qué ese enfoque tiene sentido para este problema. Está dirigido a alguien con conocimientos de álgebra lineal y optimización básica, aunque no sea programador.

---

## ¿Qué es el MPC (Model Predictive Control)?

El **Control Predictivo basado en Modelo** es una estrategia de control que, en cada instante de tiempo, hace lo siguiente:

1. Mira el **estado actual** del sistema (cuánto H2 hay en cada tanque ahora mismo).
2. Usa un **modelo simplificado** de la planta para predecir cómo evolucionará ese estado durante las próximas horas si se toman distintas acciones.
3. Busca la **secuencia de acciones** (potencia del electrolizador, caudal del compresor) que minimiza el coste eléctrico total, cumpliendo todas las restricciones físicas.
4. **Aplica solo la primera acción** de esa secuencia.
5. En el siguiente paso de tiempo (5 minutos después), **repite todo el proceso** con el estado medido actualizado.

Este "repetir con nuevos datos" es lo que hace el MPC robusto frente a perturbaciones (por ejemplo, una retención de tráfico que retrasa la llegada del camión): en el próximo instante el plan se recalcula automáticamente.

---

## El horizonte de planificación

En cada instante `k`, el MPC resuelve un problema sobre los `N` pasos que quedan hasta el final del día:

```
N = n_total - k
```

Por ejemplo, si la simulación dura 54 pasos de 5 min (270 min) y estamos en el paso 10, el MPC planifica los 44 pasos restantes de una vez.

A medida que avanza el tiempo, el horizonte se va acortando (*receding horizon*). Esto es lo más común en MPC económico porque así se aprovecha toda la información disponible sobre los precios futuros.

---

## Variables de decisión

En cada resolución, el MPC busca los valores óptimos de estas variables, una por cada paso `k` del horizonte:

| Variable | Símbolo | Unidades | Descripción |
|---|---|---|---|
| Potencia del electrolizador | `P_ely(k)` | kW | Cuántos kilovatios consume el electrolizador en el paso k. |
| Caudal de compresión a MP | `f_mp(k)` | kg/h | Cuánto H2 por hora manda el compresor al tanque de 350 bar. |
| Caudal de compresión a HP | `f_hp(k)` | kg/h | Cuánto H2 por hora manda el compresor al tanque de 500 bar. |
| Variable auxiliar de rampa | `r(k)` | kW | Representa matemáticamente `|P_ely(k) − P_ely(k−1)|` (el cambio de potencia entre pasos). No es una variable física, es un truco para linealizar el valor absoluto. |
| Holguras | `s_mp, s_hp, s_lp` | kg | Masa que "falta" para cumplir cada requisito mínimo. Solo toman valores distintos de cero en situaciones extremas (emergencia). |

En total, si el horizonte tiene N pasos: el vector de variables tiene **4·N + 3** componentes.

---

## La función objetivo (lo que el MPC minimiza)

El MPC busca minimizar el coste total en euros:

```
Minimizar:
  Σ_{k=0}^{N-1}  precio(k) · [P_ely(k) + c_mp · f_mp(k) + c_hp · f_hp(k)] · Δt/1000
  + w_ramp · Σ_{k=0}^{N-1} r(k)
  + w_slack · (s_mp + s_hp + s_lp)
```

**Interpretación de cada término:**

- `precio(k) · P_ely(k) · Δt/1000`: coste eléctrico de producir H2 en el paso k. El precio es en €/MWh, la potencia en kW y Δt en horas, de modo que el resultado queda en €.
- `precio(k) · c_mp · f_mp(k) · Δt/1000`: coste eléctrico de comprimir H2 hasta 350 bar. El compresor también consume electricidad, por eso aparece en la función de coste.
- `precio(k) · c_hp · f_hp(k) · Δt/1000`: coste de comprimir hasta 500 bar (más caro que hasta 350 bar).
- `w_ramp · r(k)`: penalización por cambios bruscos de potencia del electrolizador, para proteger el equipo de arranques y paradas frecuentes.
- `w_slack · (s_mp + s_hp + s_lp)`: penalización muy alta (500 €/kg) que garantiza que el problema siempre tenga solución matemáticamente, aunque en una situación de emergencia no se puedan cumplir todos los requisitos. En condiciones normales estas variables son cero.

---

## Las restricciones (lo que el MPC debe respetar)

El problema es una **programación lineal** (LP): tanto la función objetivo como todas las restricciones son lineales en las variables de decisión. Esto permite resolverlo de forma exacta y muy rápida con el algoritmo HiGHS.

### 1. Capacidad del compresor

En cada paso k, la suma de caudales no puede superar el máximo del compresor:

```
f_mp(k) + f_hp(k)  ≤  f_comp_max     para todo k
```

### 2. Balances de masa de los tanques

El modelo predice cómo evoluciona la masa en cada tanque usando sumas acumuladas. Para el tanque LP, tras j pasos:

```
M_LP(j) = m_lp  +  Σ_{i=0}^{j-1} [ P_ely(i)/e_ely · Δt  −  (f_mp(i) + f_hp(i)) · Δt ]
```

donde `1/e_ely` convierte potencia (kW) en caudal de producción (kg/h). El resultado debe estar siempre dentro de los límites:

```
M_lp_min  ≤  M_LP(j)  ≤  M_lp_max     para j = 1, 2, ..., N
```

Para el tanque MP (la demanda de dispensado `D_mp(j)` está planificada con antelación):

```
M_MP(j) = m_mp  +  Σ_{i=0}^{j-1} [ f_mp(i) · Δt ]  −  D_mp(j)
M_mp_min  ≤  M_MP(j)  ≤  M_mp_max
```

Y análogamente para HP.

### 3. Restricción de deadline (llegada del camión)

Si el camión llega al paso `j_arr`, los tanques deben tener masa suficiente en ese momento:

```
M_MP(j_arr)  ≥  req_mp_kg  −  s_mp
M_HP(j_arr)  ≥  req_hp_kg  −  s_hp
```

Las holguras `s_mp` y `s_hp` son cero en condiciones normales. Si la ETA cambia de golpe y es imposible cumplir el requisito, la holgura "absorbe" la infeasibilidad en lugar de que el solver falle.

### 4. Restricción terminal (dejar el LP como al principio)

Al terminar la simulación, el tanque LP debe quedar al menos como estaba al inicio del día:

```
M_LP(N)  ≥  M_LP_0  −  s_lp
```

Esto obliga al MPC a "reponer" lo que ha consumido durante el día, aprovechando las horas baratas del valle solar de la tarde.

### 5. Restricción de rampa

El cambio de potencia del electrolizador entre dos pasos consecutivos está limitado por la variable auxiliar `r(k)`:

```
P_ely(k) − P_ely(k−1)  ≤  r(k)
P_ely(k−1) − P_ely(k)  ≤  r(k)
```

Estas dos desigualdades juntas equivalen a decir `|ΔP_ely(k)| ≤ r(k)`. Como `r(k)` entra en la función objetivo con un coste positivo, el optimizador tenderá a hacer `r(k)` lo más pequeño posible, es decir, a suavizar los cambios de potencia.

### 6. Cotas de las variables

```
0  ≤  P_ely(k)  ≤  P_ely_max     (potencia entre 0 y máximo del electrolizador)
0  ≤  f_mp(k)   ≤  f_comp_max    (caudal positivo y acotado por el compresor)
0  ≤  f_hp(k)   ≤  f_comp_max
r(k)  ≥  0
s_mp, s_hp, s_lp  ≥  0           (las holguras no pueden ser negativas)
```

---

## La demanda prevista de dispensado

Antes de resolver el problema, el MPC calcula cuánto H2 necesita el camión y en qué pasos se va a dispensar. Si la ETA del camión es de `eta_min` minutos, eso equivale al paso:

```
j_arr = redondear(eta_min / dt_min)
```

La cantidad a dispensar se reparte en 3 pasos consecutivos a partir de `j_arr` (15 minutos si dt = 5 min). Este perfil de demanda `d_mp(k)` y `d_hp(k)` entra como dato fijo en las restricciones de balance de masa, no como variable de decisión.

---

## Formulación matricial del problema LP

El solver (HiGHS, incluido en scipy) recibe el problema en la forma estándar:

```
Minimizar:    c^T · x
Sujeto a:     A · x  ≤  b
              x_min  ≤  x  ≤  x_max
```

donde `x` es el vector que contiene todas las variables de decisión concatenadas:

```
x = [P_ely(0), ..., P_ely(N-1),   ← primeras N componentes
     f_mp(0),  ..., f_mp(N-1),    ← siguientes N
     f_hp(0),  ..., f_hp(N-1),    ← siguientes N
     r(0),     ..., r(N-1),       ← siguientes N
     s_mp, s_hp, s_lp]            ← últimas 3
```

El vector `c` contiene los coeficientes de la función de coste. La matriz `A` y el vector `b` codifican todas las restricciones. Para un horizonte de N = 44 pasos, `x` tiene 4·44 + 3 = 179 componentes.

---

## Por qué funciona el bucle cerrado

El MPC usa un modelo **lineal y simplificado** de la planta, pero la planta real tiene no linealidades (consumo del electrolizador dependiente de la carga, compresión dependiente de la presión real, factor de compresibilidad del H2). ¿No es eso un problema?

La respuesta es no, gracias al **bucle cerrado con medición**:

1. El MPC calcula `P_ely(0)` y `f_mp(0)`, `f_hp(0)` óptimos según su modelo lineal.
2. Se aplican esas consignas a la planta real, que responde con sus no linealidades.
3. Se **miden** las masas reales `m_lp`, `m_mp`, `m_hp` resultantes.
4. En el paso siguiente, el MPC parte de esas masas reales medidas (no de las que predijo).

El error de modelo se "reinicia" en cada paso. Siempre que el modelo lineal sea una aproximación razonable, el error acumulado es pequeño y el sistema converge a una solución subóptima pero muy cercana a la óptima real.

---

## Resumen del flujo de cálculo en cada iteración

```
Paso k:
  1. Leer estado actual: m_lp, m_mp, m_hp (medidos de la planta)
  2. Recibir ETA actualizada del camión
  3. Calcular perfil de demanda de dispensado d_mp(k), d_hp(k)
  4. Construir vector c, matriz A y vector b del LP
  5. Resolver LP con HiGHS → x* (solución óptima)
  6. Aplicar a la planta:  P_ely = x*[0],  f_mp = x*[N],  f_hp = x*[2N]
  7. Guardar el plan completo (pasos 0..N-1) para visualizarlo

Paso k+1:
  → Volver al paso 1 con las masas actualizadas por la planta real
```
