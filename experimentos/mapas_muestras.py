"""Mapas de las 12 muestras del experimento (6 por ciudad), para el anexo de la presentación.

Reproduce la secuencia aleatoria de linea_recta_vs_red.py con cada semilla (2026 y 1–5), en el
mismo orden: puntos de Ciudad del Este, sorteo de sus 50 instancias, y después los puntos de
Asunción. Así los puntos son exactamente los del experimento.

    python3 experimentos/mapas_muestras.py experimentos/resultados/figuras/muestras
"""

import functools
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
import mapa_muestra  # noqa: E402
from linea_recta_vs_red import CIUDADES, puntos_sobre_calles  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "demo"))
from consulta import puerto_osrm  # noqa: E402

SEMILLAS = [2026, 1, 2, 3, 4, 5]  # el orden de «Muestra 1» a «Muestra 6» en la presentación
INSTANCIAS, CASILLEROS = 50, 15

# Las teselas se repiten entre mapas de la misma ciudad: se bajan una sola vez.
mapa_muestra.tesela = functools.lru_cache(maxsize=None)(mapa_muestra.tesela)


def main():
    carpeta = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(carpeta, exist_ok=True)
    servidor = f"http://localhost:{puerto_osrm()}"
    for k, semilla in enumerate(SEMILLAS, 1):
        rng = random.Random(semilla)
        cde = puntos_sobre_calles(servidor, CIUDADES["Ciudad del Este"], 100, rng)
        for _ in range(INSTANCIAS):
            rng.sample(range(100), CASILLEROS + 1)
        asu = puntos_sobre_calles(servidor, CIUDADES["Asunción"], 100, rng)
        mapa_muestra.dibujar(cde, [], os.path.join(carpeta, f"cde_{k}.svg"), ciudad="Ciudad del Este")
        mapa_muestra.dibujar(asu, [], os.path.join(carpeta, f"asu_{k}.svg"), ciudad="Asunción")
        print(f"muestra {k} (semilla {semilla}) lista")


if __name__ == "__main__":
    main()
