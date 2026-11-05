"""Mapas de la metodología para la presentación: la red vial y una muestra de puntos.

Dibuja el rectángulo urbano de cada ciudad sobre teselas de OpenStreetMap:
- `mapa_red.svg` y `mapa_red_asuncion.svg`: solo el mapa con el rectángulo de estudio
  (Ciudad del Este y Asunción).
- `mapa_puntos.svg`: además, los 100 puntos de la muestra de la semilla 2026 (los mismos del
  experimento).
- `mapa_muestra.svg`: los mismos puntos, con un depósito y 15 clientes de una instancia resaltados.
- `mapa_ruta.svg`: esa instancia y la ruta por carretera que arma la heurística (vecino más
  cercano y 2-opt sobre los tiempos de OSRM).

    python3 experimentos/mapa_muestra.py experimentos/resultados/figuras
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
from linea_recta_vs_red import CIUDADES, SEMILLA, pedir, puntos_sobre_calles, vecino_mas_cercano_2opt  # noqa: E402
from mapa_ejemplo import a_pixel, tesela  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "demo"))
from consulta import puerto_osrm  # noqa: E402

ZOOM = 13
AZUL, CIAN, MARINO = "#123B70", "#13B6D5", "#0A1733"


def dibujar(puntos, instancia, ruta, ciudad="Ciudad del Este", recorrido=None):
    lat_min, lat_max, lon_min, lon_max = CIUDADES[ciudad]
    (x1, y1), (x2, y2) = a_pixel(lat_max, lon_min, ZOOM), a_pixel(lat_min, lon_max, ZOOM)
    margen = 40
    x0, y0 = x1 - margen, y1 - margen
    ancho, alto = int(x2 - x1 + 2 * margen), int(y2 - y1 + 2 * margen)
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
              f'viewBox="0 0 {ancho} {alto}" font-family="Helvetica, Arial, sans-serif">']
    for tx in range(int(x0 // 256), int((x0 + ancho) // 256) + 1):
        for ty in range(int(y0 // 256), int((y0 + alto) // 256) + 1):
            partes.append(f'<image x="{tx * 256 - x0:.1f}" y="{ty * 256 - y0:.1f}" width="256" height="256" '
                          f'xlink:href="data:image/png;base64,{tesela(tx, ty, ZOOM)}"/>')
    partes.append(f'<rect width="{ancho}" height="{alto}" fill="#ffffff" fill-opacity="0.2"/>')
    partes.append(f'<rect x="{margen}" y="{margen}" width="{x2 - x1:.1f}" height="{y2 - y1:.1f}" fill="none" '
                  f'stroke="{AZUL}" stroke-width="3" stroke-dasharray="10 6"/>')
    if recorrido:
        camino = " ".join(f"{a_pixel(la, lo, ZOOM)[0] - x0:.1f},{a_pixel(la, lo, ZOOM)[1] - y0:.1f}"
                          for la, lo in recorrido)
        partes.append(f'<polyline points="{camino}" fill="none" stroke="{CIAN}" stroke-width="4" '
                      f'stroke-linejoin="round" stroke-opacity="0.9"/>')
    for k, (lat, lon) in enumerate(puntos):
        x, y = a_pixel(lat, lon, ZOOM)
        if instancia and k == instancia[0]:
            continue
        if recorrido and k not in instancia:
            continue  # en el mapa de la ruta solo van los puntos de la instancia
        resaltado = k in instancia
        partes.append(f'<circle cx="{x - x0:.1f}" cy="{y - y0:.1f}" r="{6 if resaltado else 4.5}" '
                      f'fill="{CIAN if resaltado else AZUL}" stroke="#fff" stroke-width="1.5"/>')
    if instancia:
        x, y = a_pixel(*puntos[instancia[0]], ZOOM)
        partes.append(f'<rect x="{x - x0 - 8:.1f}" y="{y - y0 - 8:.1f}" width="16" height="16" fill="{MARINO}" '
                      f'stroke="#fff" stroke-width="2"/>')
    partes.append(f'<rect x="{ancho - 215}" y="{alto - 22}" width="215" height="22" fill="#fff" fill-opacity="0.85"/>')
    partes.append(f'<text x="{ancho - 6}" y="{alto - 7}" text-anchor="end" font-size="12" fill="#333">'
                  f'© colaboradores de OpenStreetMap</text>')
    partes.append("</svg>")
    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write("\n".join(partes))


def main():
    carpeta = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(carpeta, exist_ok=True)
    servidor = f"http://localhost:{puerto_osrm()}"
    rng = random.Random(SEMILLA)  # Ciudad del Este primero: mismos puntos que el experimento
    puntos = puntos_sobre_calles(servidor, CIUDADES["Ciudad del Este"], 100, rng)
    instancia = random.Random(1).sample(range(len(puntos)), 16)  # solo ilustrativa
    dibujar([], [], os.path.join(carpeta, "mapa_red.svg"))
    dibujar([], [], os.path.join(carpeta, "mapa_red_asuncion.svg"), ciudad="Asunción")
    dibujar(puntos, [], os.path.join(carpeta, "mapa_puntos.svg"))
    dibujar(puntos, instancia, os.path.join(carpeta, "mapa_muestra.svg"))
    # Ruta de la instancia: orden con la heurística sobre los tiempos por carretera, y trazado
    # por calles de OSRM visitando los puntos en ese orden (vuelve al depósito).
    sel = [puntos[k] for k in instancia]
    coords = ";".join(f"{lon},{lat}" for lat, lon in sel)
    tiempos = pedir(servidor, f"/table/v1/driving/{coords}")["durations"]
    orden = vecino_mas_cercano_2opt(tiempos)
    via = ";".join(f"{sel[k][1]},{sel[k][0]}" for k in orden)
    geometria = pedir(servidor, f"/route/v1/driving/{via}?overview=full&geometries=geojson")["routes"][0]
    recorrido = [(lat, lon) for lon, lat in geometria["geometry"]["coordinates"]]
    dibujar(puntos, instancia, os.path.join(carpeta, "mapa_ruta.svg"), recorrido=recorrido)
    print(f"{carpeta}: mapa_red.svg, mapa_red_asuncion.svg, mapa_puntos.svg, mapa_muestra.svg, mapa_ruta.svg; "
          f"ruta de {geometria['duration'] / 60:.0f} min y {geometria['distance'] / 1000:.1f} km")


if __name__ == "__main__":
    main()
