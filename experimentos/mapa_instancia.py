"""Instancia de ejemplo para el anexo: las dos rutas que compara el experimento 3.

Toma la instancia ilustrativa de mapa_muestra.py (Ciudad del Este, semilla 2026), arma la ruta
con la misma heurística (vecino más cercano y 2-opt) dos veces, con la distancia euclidiana y
con los tiempos por carretera, y evalúa las dos con los tiempos por carretera, como en el
experimento. Dibuja cada ruta por calles sobre el mapa y guarda los tiempos.

    python3 experimentos/mapa_instancia.py experimentos/resultados/figuras
"""

import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
import mapa_muestra  # noqa: E402
from linea_recta_vs_red import (CIUDADES, SEMILLA, costo, haversine_m, pedir, puntos_sobre_calles,  # noqa: E402
                                vecino_mas_cercano_2opt)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "demo"))
from consulta import puerto_osrm  # noqa: E402


def main():
    carpeta = sys.argv[1] if len(sys.argv) > 1 else "."
    servidor = f"http://localhost:{puerto_osrm()}"
    puntos = puntos_sobre_calles(servidor, CIUDADES["Ciudad del Este"], 100, random.Random(SEMILLA))
    instancia = random.Random(1).sample(range(len(puntos)), 16)  # la misma de mapa_muestra.py
    sel = [puntos[k] for k in instancia]
    coords = ";".join(f"{lon},{lat}" for lat, lon in sel)
    tiempos = pedir(servidor, f"/table/v1/driving/{coords}")["durations"]
    recta = [[haversine_m(a, b) for b in sel] for a in sel]
    resultado = {}
    for nombre, matriz in (("euclidiana", recta), ("carretera", tiempos)):
        orden = vecino_mas_cercano_2opt(matriz)
        via = ";".join(f"{sel[k][1]},{sel[k][0]}" for k in orden)
        ruta = pedir(servidor, f"/route/v1/driving/{via}?overview=full&geometries=geojson")["routes"][0]
        recorrido = [(lat, lon) for lon, lat in ruta["geometry"]["coordinates"]]
        mapa_muestra.dibujar(puntos, instancia, os.path.join(carpeta, f"instancia_{nombre}.svg"),
                             recorrido=recorrido)
        resultado[nombre] = {"minutos": costo(orden, tiempos) / 60, "km": ruta["distance"] / 1000, "orden": orden}
    e, c = resultado["euclidiana"]["minutos"], resultado["carretera"]["minutos"]
    resultado["exceso_pct"] = 100 * (e - c) / c
    with open(os.path.join(carpeta, "instancia_ejemplo.json"), "w", encoding="utf-8") as archivo:
        json.dump(resultado, archivo, indent=2)
    print(f"euclidiana {e:.1f} min, carretera {c:.1f} min, exceso {resultado['exceso_pct']:.1f} %")


if __name__ == "__main__":
    main()
