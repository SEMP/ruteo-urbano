"""Mapa de ejemplo para la presentación: distancia euclidiana frente a ruta por carretera.

Toma la muestra de Ciudad del Este de la semilla 2026 (los mismos puntos del experimento),
elige, entre los pares a 1,5–3 km en línea recta, el de circuidad más cercana a 2, pide a OSRM
la ruta y la dibuja sobre teselas de OpenStreetMap, junto con el segmento recto. Sale un SVG
con las teselas incrustadas, sin dependencias externas.

Las teselas se bajan de tile.openstreetmap.org (uso liviano: una docena por corrida).
Atribución obligatoria: «© colaboradores de OpenStreetMap».

    python3 experimentos/mapa_ejemplo.py experimentos/resultados/figuras/mapa_ejemplo.svg
"""

import base64
import math
import os
import random
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from linea_recta_vs_red import CIUDADES, SEMILLA, haversine_m, pedir, puntos_sobre_calles  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "demo"))
from consulta import puerto_osrm  # noqa: E402

AGENTE = "proyecto-inv-2026 FPUNE (investigacion academica)"
ZOOM = 15
ANCHO, ALTO = 960, 600


def a_pixel(lat, lon, z=ZOOM):
    """Coordenadas a píxeles globales de Web Mercator (teselas de 256 px)."""
    n = 256 * 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def tesela(x, y, z=ZOOM):
    peticion = urllib.request.Request(f"https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                                      headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(peticion, timeout=30) as respuesta:
        return base64.b64encode(respuesta.read()).decode()


def main():
    salida = sys.argv[1] if len(sys.argv) > 1 else "mapa_ejemplo.svg"
    servidor = f"http://localhost:{puerto_osrm()}"
    rng = random.Random(SEMILLA)  # Ciudad del Este es la primera ciudad: mismos puntos que el experimento
    puntos = puntos_sobre_calles(servidor, CIUDADES["Ciudad del Este"], 100, rng)
    coords = ";".join(f"{lon},{lat}" for lat, lon in puntos)
    dist = pedir(servidor, f"/table/v1/driving/{coords}?annotations=distance")["distances"]

    candidatos = [(dist[i][j] / haversine_m(puntos[i], puntos[j]), i, j)
                  for i in range(len(puntos)) for j in range(len(puntos))
                  if i != j and 1500 <= haversine_m(puntos[i], puntos[j]) <= 3000]
    # El par más cercano a circuidad 2 (cola alta típica); el máximo suele ser un punto sobre un
    # tramo de red casi aislado, que no representa la ciudad.
    circuidad, i, j = min(candidatos, key=lambda c: abs(c[0] - 2.0))
    a, b = puntos[i], puntos[j]
    ruta = pedir(servidor, f"/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}"
                           "?overview=full&geometries=geojson")["routes"][0]
    linea = [(lat, lon) for lon, lat in ruta["geometry"]["coordinates"]]
    recta_km = haversine_m(a, b) / 1000

    # Encuadre: la ruta completa con margen, centrada.
    px = [a_pixel(lat, lon) for lat, lon in linea]
    cx = (min(p[0] for p in px) + max(p[0] for p in px)) / 2
    cy = (min(p[1] for p in px) + max(p[1] for p in px)) / 2
    x0, y0 = cx - ANCHO / 2, cy - ALTO / 2

    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
              f'viewBox="0 0 {ANCHO} {ALTO}" font-family="Helvetica, Arial, sans-serif">']
    for tx in range(int(x0 // 256), int((x0 + ANCHO) // 256) + 1):
        for ty in range(int(y0 // 256), int((y0 + ALTO) // 256) + 1):
            partes.append(f'<image x="{tx * 256 - x0:.1f}" y="{ty * 256 - y0:.1f}" width="256" height="256" '
                          f'xlink:href="data:image/png;base64,{tesela(tx, ty)}"/>')
    partes.append(f'<rect width="{ANCHO}" height="{ALTO}" fill="#ffffff" fill-opacity="0.25"/>')
    camino = " ".join(f"{x - x0:.1f},{y - y0:.1f}" for x, y in px)
    partes.append(f'<polyline points="{camino}" fill="none" stroke="#c0612b" stroke-width="6" '
                  f'stroke-linejoin="round" stroke-linecap="round"/>')
    (ax, ay), (bx, by) = a_pixel(*a), a_pixel(*b)
    partes.append(f'<line x1="{ax - x0:.1f}" y1="{ay - y0:.1f}" x2="{bx - x0:.1f}" y2="{by - y0:.1f}" '
                  f'stroke="#1b6f8a" stroke-width="5" stroke-dasharray="14 9"/>')
    for (x, y), rotulo in (((ax, ay), "A"), ((bx, by), "B")):
        partes.append(f'<circle cx="{x - x0:.1f}" cy="{y - y0:.1f}" r="14" fill="#111" stroke="#fff" stroke-width="3"/>')
        partes.append(f'<text x="{x - x0:.1f}" y="{y - y0 + 6:.1f}" text-anchor="middle" font-size="17" '
                      f'font-weight="bold" fill="#fff">{rotulo}</text>')
    leyenda = [("#1b6f8a", "14 9", f"Distancia euclidiana: {recta_km:.2f} km".replace(".", ",")),
               ("#c0612b", "none", f"Distancia por carretera: {ruta['distance'] / 1000:.2f} km "
                                   f"({ruta['duration'] / 60:.0f} min)".replace(".", ","))]
    partes.append(f'<rect x="16" y="16" width="420" height="96" rx="6" fill="#fff" fill-opacity="0.92"/>')
    for k, (color, guiones, texto) in enumerate(leyenda):
        y = 44 + k * 30
        partes.append(f'<line x1="32" y1="{y}" x2="78" y2="{y}" stroke="{color}" stroke-width="5" stroke-dasharray="{guiones}"/>')
        partes.append(f'<text x="90" y="{y + 6}" font-size="18" fill="#111">{texto}</text>')
    indice = f"{circuidad:.2f}".replace(".", ",")
    partes.append(f'<text x="32" y="{44 + 2 * 30 + 2}" font-size="16" fill="#333">'
                  f'Índice de circuidad: {indice}</text>')
    partes.append(f'<rect x="{ANCHO - 250}" y="{ALTO - 24}" width="250" height="24" fill="#fff" fill-opacity="0.85"/>')
    partes.append(f'<text x="{ANCHO - 8}" y="{ALTO - 7}" text-anchor="end" font-size="13" fill="#333">'
                  f'© colaboradores de OpenStreetMap</text>')
    partes.append("</svg>")
    os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)
    with open(salida, "w", encoding="utf-8") as archivo:
        archivo.write("\n".join(partes))
    print(f"par {i}-{j}: euclidiana {recta_km:.2f} km, carretera {ruta['distance'] / 1000:.2f} km, "
          f"circuidad {circuidad:.2f}, A={a}, B={b}")


if __name__ == "__main__":
    main()
