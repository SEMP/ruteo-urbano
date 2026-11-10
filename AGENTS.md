# AGENTS.md — ruteo-urbano

Instrucciones para agentes de IA (Claude Code, Codex, etc.). **Este es el archivo canónico**:
`CLAUDE.md` solo lo importa. Los cambios van acá.

## Contexto

Código del proyecto de investigación **«Ruteo Dinámico de Vehículos en Escenarios Logísticos
Emergentes — Fase II»** (FPUNE, 2026; Daisy Kang y Sergio Morel).

**El contexto del proyecto no está acá**: está en el workspace `proyecto-inv-2026`
(`git@github.com:SEMP/proyecto-inv-2026.git`), que clona este repo en `repos/ruteo-urbano`.
Ahí están el proyecto presentado, el alcance (`docs/pendientes.md`), las herramientas
(`docs/herramientas.md`), la revisión de la literatura y los mensajes entre el equipo. Si este
repo está clonado dentro del workspace, leer `../../AGENTS.md` al empezar.

**Qué resuelve:** el ruteo de vehículos de reparto urbano (depósito → puntos de entrega), con
la ubicación de los puntos como dato, considerando la capacidad de carga de cada vehículo, la
cantidad de vehículos y la posición de cada uno en el momento de decidir (ruteo dinámico). El
caso de aplicación se define en el workspace (`docs/pendientes.md`).

**Este repo es público:** textos, comentarios y nombres son generales (puntos de entrega,
clientes, depósito). El caso de aplicación concreto no se nombra acá; ver la regla
sobre publicaciones del `AGENTS.md` del workspace.

## Reglas

- **Herramientas libres y sin límites de uso.** Red vial de OpenStreetMap con OSRM en local
  (Docker). Nada de APIs pagas o con cuota (Google Maps, servidor público de OSRM).
- **El método de solución es propio**: es la contribución del proyecto. OR-Tools o PyVRP se
  usan solo como comparación en la validación.
- **No se usa el código, el caso ni los datos de la tesis doctoral de Daisy** (trenes de Quito,
  NSGA-II).
- **Reproducibilidad:** cada experimento se puede volver a correr desde el repo: instancia,
  parámetros y semilla registrados; los resultados que van al informe o al artículo salen de
  un script, no de una ejecución a mano.
- **Datos:** el mapa de OSM y los archivos procesados de OSRM se descargan o se generan con un
  script; no se versionan (pesan). Citar «© colaboradores de OpenStreetMap».
- **Git:** `main` siempre funciona. Cada tarea en su rama (`feature/<tema>`, `fix/<tema>`); al
  terminarla, quien la hizo la mergea a `main` y borra la rama. Sin pull requests: si hace
  falta que la otra persona mire algo, mensaje en `mensajes/` del workspace.
- **Todo en español:** documentación, comentarios y mensajes de commit. Los nombres del código
  pueden ir en inglés si el lenguaje o las librerías lo hacen más natural; decidirlo una vez y
  mantenerlo.

## Estado

Python 3, solo biblioteca estándar (corre sin instalar nada). Nombres en español.

- `dvrp/`: modelo (`modelo.py`, con un verificador independiente), métodos (`tabu.py`:
  inserción más barata y búsqueda tabú) y simulación de la jornada (`simulacion.py`).
- `experimentos/`: distancias euclidianas frente a la red vial (`linea_recta_vs_red.py` y
  figuras), validación en CVRPLIB (`cvrplib.py`) y escenarios del DVRP en Asunción y Ciudad del
  Este (`dvrp_escenarios.py`, `dvrp_resumen.py`). Resultados en `experimentos/resultados/`.
- `tests/`: `python3 -m unittest discover tests`. Correrlas antes de mergear a `main`.
