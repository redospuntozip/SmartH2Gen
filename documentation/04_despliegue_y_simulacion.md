# Guía de despliegue y lanzamiento del dashboard

Esta guía lleva paso a paso desde cero hasta tener el simulador corriendo y el dashboard abierto en el navegador. No se necesita ningún servidor web ni conocimientos avanzados de informática.

---

## Requisitos previos

- **Python 3.9 o superior** (gratuito). Si no está instalado, descargarlo desde [python.org](https://www.python.org/downloads/) y marcar la opción "Add Python to PATH" durante la instalación.
- **Un terminal** (en Windows: PowerShell o el símbolo del sistema `cmd`).
- **Un navegador web moderno** (Chrome, Firefox, Edge...).

Para comprobar que Python está disponible, abrir un terminal y ejecutar:

```bash
python --version
```

Debe mostrar algo como `Python 3.11.x`. Si aparece un error, revisar la instalación.

---

## Paso 1: Situarse en la carpeta del proyecto

Abrir un terminal y navegar hasta la carpeta `h2mpc`:

```bash
cd "ruta\completa\hasta\h2mpc"
```

Por ejemplo, en Windows:

```bash
cd "C:\Users\TuUsuario\Desktop\h2mpc_prototipo\h2mpc"
```

---

## Paso 2: Instalar las dependencias

El proyecto solo requiere dos librerías externas (`numpy` y `scipy`). Instalarlas con:

```bash
pip install -r requirements.txt
```

Este comando lee el archivo `requirements.txt` e instala automáticamente las versiones correctas. Solo hace falta hacerlo una vez. La salida esperada termina con algo como:

```
Successfully installed numpy-x.x.x scipy-x.x.x
```

> Si `pip` no se reconoce como comando, probar con `python -m pip install -r requirements.txt`.

---

## Paso 3: Ejecutar la simulación

```bash
python simulate.py
```

Este comando arranca el bucle cerrado (MPC + planta + camión) durante los 270 minutos simulados (de 06:00 a 10:30). En la terminal aparecerá un resumen como este:

```
results.json escrito.
{
  "cost_mpc": 38.47,
  "cost_naive": 93.21,
  "saving_eur": 54.74,
  "saving_pct": 58.7,
  "delivered_kg": 16.83,
  "eur_kg_mpc": 2.29,
  "eur_kg_naive": 5.54,
  "arrival_clock": "08:54"
}
```

Al terminar, se habrá generado el archivo `results.json` con todos los datos de la simulación (estados de los tanques, potencias, precios, posición del camión...) en cada uno de los 54 pasos de tiempo.

---

## Paso 4: Generar el dashboard HTML

```bash
python build_dashboard.py
```

Este comando toma `results.json` y lo "inyecta" dentro de la plantilla `dashboard_template.html`, generando el archivo `dashboard.html`. La terminal mostrará:

```
dashboard.html generado (ábrelo en el navegador).
```

El archivo `dashboard.html` es completamente autocontenido: lleva los datos embebidos dentro del HTML, por lo que **no necesita ningún servidor web** para funcionar.

---

## Paso 5: Abrir el dashboard en el navegador

Hacer **doble clic** en el archivo `dashboard.html` desde el explorador de archivos, o bien arrastrarlo a la ventana del navegador.

Se abrirá una página interactiva con:

- Un botón **▶ Reproducir** que anima la simulación paso a paso.
- Gráficas de la potencia del electrolizador, masas de los tanques y precio de la electricidad.
- Un marcador de la posición del camión en ruta.
- Un resumen final comparando el coste del MPC con el controlador ingenuo.

---

## Resumen: los tres comandos

```bash
pip install -r requirements.txt   # solo la primera vez
python simulate.py                # genera results.json
python build_dashboard.py         # genera dashboard.html
```

Luego abrir `dashboard.html` con doble clic.

---

## Flujo completo explicado

```
simulate.py
    │  Lee params.py, prices.py, truck.py, plant.py, mpc.py
    │  Ejecuta 54 pasos de 5 minutos
    │
    └──> results.json   (datos de la simulación)
              │
              ▼
    build_dashboard.py
         │  Lee results.json y dashboard_template.html
         │  Inyecta los datos en la plantilla
         │
         └──> dashboard.html   (abrir en el navegador)
```

---

## Modificar parámetros y volver a simular

Si se cambia algún parámetro en `params.py` (por ejemplo, la potencia del electrolizador o el tamaño de los tanques), hay que repetir los pasos 3 y 4 para regenerar los resultados:

```bash
python simulate.py
python build_dashboard.py
```

No hace falta reinstalar nada ni reiniciar ningún servidor.

---

## Posibles errores y soluciones

### `ModuleNotFoundError: No module named 'numpy'`

Las dependencias no están instaladas. Ejecutar:

```bash
pip install -r requirements.txt
```

### `FileNotFoundError: results.json`

Se intentó ejecutar `build_dashboard.py` sin haber ejecutado antes `simulate.py`. Ejecutar primero:

```bash
python simulate.py
```

### El dashboard no muestra nada o aparece en blanco

- Comprobar que se ha ejecutado `build_dashboard.py` después de la última simulación.
- Probar a abrir `dashboard.html` en otro navegador.
- En algunos navegadores con políticas de seguridad muy estrictas (raro), puede ser necesario iniciar un servidor local mínimo. Desde la carpeta del proyecto:

```bash
python -m http.server 8080
```

Y luego abrir en el navegador: `http://localhost:8080/dashboard.html`

### `Infeasible` aparece en el dashboard

El MPC no ha podido encontrar una solución factible en algún paso (normalmente porque la ETA del camión se adelantó demasiado y los tanques no tenían suficiente H2). En ese caso, el controlador entra en modo de emergencia (electrolizador y compresor a tope). Revisar los requisitos `req_mp_kg` y `req_hp_kg` en `params.py` o aumentar los niveles iniciales de los tanques.

---

## Entorno de desarrollo recomendado

Para editar el código, cualquier editor de texto sirve, pero se recomienda **Visual Studio Code** con la extensión de Python. El proyecto ya incluye una configuración de VSCode en `.vscode/settings.json`.

Para ejecutar los scripts directamente desde VSCode: abrir el archivo `simulate.py` y pulsar el botón de "Run" (triángulo verde), o usar el terminal integrado con los comandos indicados arriba.
