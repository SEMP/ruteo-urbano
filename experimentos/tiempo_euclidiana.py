"""Tiempo de cálculo de la matriz de distancias euclidianas (haversine), para comparar con OSRM.

Mismos tamaños que la medición de OSRM en linea_recta_vs_red.py (10, 100, 500 y 1000 puntos de
Asunción) y mediana de tres repeticiones. Python puro, en la misma computadora. No necesita OSRM.

    python3 experimentos/tiempo_euclidiana.py experimentos/resultados
"""

import json
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from linea_recta_vs_red import CIUDADES, SEMILLA, haversine_m  # noqa: E402


def main():
    carpeta = sys.argv[1] if len(sys.argv) > 1 else "."
    lat0, lat1, lon0, lon1 = CIUDADES["Asunción"]
    rng = random.Random(SEMILLA)
    filas = []
    for n in (10, 100, 500, 1000):
        puntos = [(rng.uniform(lat0, lat1), rng.uniform(lon0, lon1)) for _ in range(n)]
        segundos = []
        for _ in range(3):
            inicio = time.perf_counter()
            [[haversine_m(p, q) for q in puntos] for p in puntos]
            segundos.append(time.perf_counter() - inicio)
        filas.append({"puntos": n, "segundos_mediana": statistics.median(segundos)})
    with open(os.path.join(carpeta, "tiempo_euclidiana.json"), "w", encoding="utf-8") as archivo:
        json.dump({"semilla": SEMILLA, "matriz": filas}, archivo, indent=2)
    print(json.dumps(filas, indent=2))


if __name__ == "__main__":
    main()
