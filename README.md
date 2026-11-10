# ruteo-urbano

Prototipo del proyecto de investigación **«Ruteo Dinámico de Vehículos en Escenarios
Logísticos Emergentes — Fase II»** (FPUNE, 2026): ruteo dinámico de vehículos de reparto urbano,
considerando capacidad de carga, tamaño de la flota y posición de los vehículos.

- Red vial: OpenStreetMap + OSRM (local).
- Documentación del proyecto, alcance y revisión de la literatura: workspace
  [`proyecto-inv-2026`](https://github.com/SEMP/proyecto-inv-2026).

## Ruteo dinámico (`dvrp/`)

Modelo: flota de K vehículos de capacidad Q que hacen varios viajes desde un depósito durante una
jornada; los pedidos (punto de entrega, demanda) se conocen y quedan listos en el depósito en su
fecha de liberación, a lo largo del día. Objetivo: atender todos los pedidos posibles con el
menor tiempo de viaje. Detalle en `dvrp/modelo.py`.

- **Métodos** (`dvrp/tabu.py`): inserción más barata y búsqueda tabú (reubicación,
  intercambio, 2-opt y 2-opt*, con penalizaciones adaptativas).
- **Simulación** (`dvrp/simulacion.py`): reoptimiza cada 10 min con los pedidos conocidos; cada
  ejecución se controla con un verificador que no usa el código del método.
- **Validación:**

```
python3 -m unittest discover tests
python3 experimentos/cvrplib.py --salida experimentos/resultados/dvrp          # instancias estándar
python3 experimentos/dvrp_escenarios.py --salida experimentos/resultados/dvrp  # requiere OSRM la 1.ª vez
python3 experimentos/dvrp_resumen.py experimentos/resultados/dvrp
```

`experimentos/cvrplib/` tiene las instancias A de CVRPLIB (Augerat et al., 1995), descargadas
de <https://galgos.inf.puc-rio.br/cvrplib/>. Las matrices de los escenarios quedan en
`experimentos/resultados/dvrp/instancias/`, así que repetirlos no necesita OSRM.

## Demo: red vial con OSRM

Requisitos: Docker (con Compose) y Python 3 (solo para el demo; no instala nada).

```
docker compose run --rm preparar   # una vez: baja el mapa de Paraguay (~150 MB) y lo procesa
docker compose up -d               # OSRM en http://localhost:5000 y el visor en http://localhost:8080
python3 demo/consulta.py           # (opcional) lo mismo por consola: ruta y matriz de tiempos
docker compose down                # apagar
```

**Visor** (<http://localhost:8080>): mapa con los puntos de `demo/puntos.json`. Clic en el
mapa agrega un punto de entrega, arrastrar lo mueve, clic derecho lo quita. Botones:

- *Ruta en este orden*: depósito → puntos de entrega en el orden de la lista → depósito, dibujada por
  las calles, con km y minutos de cada tramo.
- *Mejor orden (OSRM)*: el servicio `trip` de OSRM, una heurística para un solo vehículo y sin
  capacidad. Es una referencia, no el método del proyecto.
- *Matriz de tiempos*: la entrada del ruteo.

- `preparar` tarda ~1,5 min y deja ~600 MB en el volumen de Docker `osrm-datos` (fuera del
  repo). Para actualizar el mapa: `docker compose --profile preparar down -v` y otra vez
  `preparar`. Ojo: `down -v` borra el volumen; para solo apagar, `docker compose down`.
- **Puerto ocupado:** crear un `.env` con `OSRM_PUERTO=5080` y/o `VISOR_PUERTO=8088` (los que
  estén libres); `consulta.py` lee el de OSRM de ahí.
- El visor usa Leaflet y los mosaicos de `tile.openstreetmap.org` (libres, para uso liviano).
  El ruteo no sale de la máquina: nginx pasa `/osrm/` al OSRM local (`demo/nginx.conf`).
- Imagen: `ghcr.io/project-osrm/osrm-backend:v6.0.0`. Las imágenes de Docker Hub
  (`osrm/osrm-backend`) dejaron de actualizarse en 2021.
- Servicios de OSRM que usamos: `route` (ruta entre puntos) y `table` (matriz de tiempos y
  distancias, entrada del ruteo; hasta 1000 × 1000 puntos con la configuración actual).
  Documentación: <https://project-osrm.org/docs/v5.24.0/api/>.

Los puntos del demo son de prueba en Ciudad del Este, no puntos de entrega reales.

Autores: Daisy Kang, Sergio Morel.

Datos de mapas © colaboradores de OpenStreetMap, bajo licencia ODbL.
