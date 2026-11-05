"""Mapas de la metodología para la presentación: la red vial y una muestra de puntos.

Dibuja el rectángulo urbano de Ciudad del Este sobre teselas de OpenStreetMap:
- `mapa_red.svg`: solo el mapa con el rectángulo de estudio.
- `mapa_puntos.svg`: además, los 100 puntos de la muestra de la semilla 2026 (los mismos del
  experimento).
- `mapa_muestra.svg`: los mismos puntos, con un depósito y 15 clientes de una instancia resaltados.

    python3 experimentos/mapa_muestra.py experimentos/resultados/figuras
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
from linea_recta_vs_red import CIUDADES, SEMILLA, puntos_sobre_calles  # noqa: E402
from mapa_ejemplo import a_pixel, tesela  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "demo"))
from consulta import puerto_osrm  # noqa: E402

ZOOM = 13
AZUL, CIAN, MARINO = "#123B70", "#13B6D5", "#0A1733"


def dibujar(puntos, instancia, ruta):
    lat_min, lat_max, lon_min, lon_max = CIUDADES["Ciudad del Este"]
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
    for k, (lat, lon) in enumerate(puntos):
        x, y = a_pixel(lat, lon, ZOOM)
        if instancia and k == instancia[0]:
            continue
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
    dibujar(puntos, [], os.path.join(carpeta, "mapa_puntos.svg"))
    dibujar(puntos, instancia, os.path.join(carpeta, "mapa_muestra.svg"))
    print(f"{carpeta}: mapa_red.svg, mapa_puntos.svg, mapa_muestra.svg")


if __name__ == "__main__":
    main()
