"""¿Alcanza la línea recta, o hace falta la red vial? Experimento preliminar con OSRM.

Compara, en Ciudad del Este y Asunción, la distancia en línea recta (haversine) con la
distancia y el tiempo por calles que da OSRM (perfil car), y mide:

1. Circuidad: distancia por calles / distancia en línea recta, para todos los pares.
2. Vecino más cercano: en cuántos puntos el más cercano en línea recta no es el más cercano
   en tiempo por calles.
3. Recorridos: un depósito y 15 clientes; se arma el recorrido (vecino más cercano + 2-opt)
   con la matriz en línea recta y con la de tiempos por calles, y se evalúan los dos con los
   tiempos por calles. La diferencia es lo que se pierde al planificar con la línea recta.
4. Tiempo de cálculo de la matriz de OSRM (`table`) según la cantidad de puntos.

Los puntos son aleatorios (semilla fija) dentro de un rectángulo urbano de cada ciudad, y se
descartan los que quedan a más de 150 m de una calle. NO son clientes reales.

Requiere OSRM levantado (`docker compose up -d osrm`). Solo biblioteca estándar.

    python3 experimentos/linea_recta_vs_red.py --salida experimentos/resultados
"""

import argparse
import json
import math
import os
import random
import statistics
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "demo"))
from consulta import puerto_osrm  # noqa: E402

# Rectángulos urbanos (lat_min, lat_max, lon_min, lon_max). Aproximados, a ojo sobre el mapa.
CIUDADES = {
    "Ciudad del Este": (-25.560, -25.470, -54.690, -54.605),
    "Asunción": (-25.340, -25.260, -57.640, -57.540),
}
MAX_SNAP_M = 150
SEMILLA = 2026
# Tramos de distancia en línea recta (m) para ver cómo cambia la circuidad con la distancia.
TRAMOS_M = [(200, 1000), (1000, 3000), (3000, 6000), (6000, float("inf"))]


def haversine_m(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def pedir(servidor, ruta):
    with urllib.request.urlopen(f"{servidor}{ruta}", timeout=120) as respuesta:
        datos = json.load(respuesta)
    if datos.get("code") != "Ok":
        raise RuntimeError(datos)
    return datos


def puntos_sobre_calles(servidor, caja, n, rng):
    """n puntos aleatorios en la caja, ya ubicados sobre la calle más cercana."""
    puntos = []
    while len(puntos) < n:
        lat, lon = rng.uniform(caja[0], caja[1]), rng.uniform(caja[2], caja[3])
        cercano = pedir(servidor, f"/nearest/v1/driving/{lon},{lat}")["waypoints"][0]
        if cercano["distance"] <= MAX_SNAP_M:
            lon_c, lat_c = cercano["location"]
            puntos.append((lat_c, lon_c))
    return puntos


def matriz_osrm(servidor, puntos):
    coordenadas = ";".join(f"{lon},{lat}" for lat, lon in puntos)
    inicio = time.perf_counter()
    datos = pedir(servidor, f"/table/v1/driving/{coordenadas}?annotations=duration,distance")
    return datos["durations"], datos["distances"], time.perf_counter() - inicio


def costo(recorrido, m):
    return sum(m[a][b] for a, b in zip(recorrido, recorrido[1:]))


def vecino_mas_cercano_2opt(m):
    """Recorrido cerrado desde el nodo 0 (depósito). Heurística simple, solo de referencia."""
    pendientes, recorrido = set(range(1, len(m))), [0]
    while pendientes:
        siguiente = min(pendientes, key=lambda j: m[recorrido[-1]][j])
        recorrido.append(siguiente)
        pendientes.remove(siguiente)
    recorrido.append(0)
    mejora = True
    while mejora:
        mejora = False
        for i in range(1, len(recorrido) - 2):
            for k in range(i + 1, len(recorrido) - 1):
                nuevo = recorrido[:i] + recorrido[i:k + 1][::-1] + recorrido[k + 1:]
                if costo(nuevo, m) < costo(recorrido, m) - 1e-9:
                    recorrido, mejora = nuevo, True
    return recorrido


def percentil(valores, p):
    valores = sorted(valores)
    return valores[min(len(valores) - 1, int(round(p / 100 * (len(valores) - 1))))]


def analizar_ciudad(servidor, nombre, caja, rng, n_pares, n_instancias, tam_instancia):
    puntos = puntos_sobre_calles(servidor, caja, n_pares, rng)
    durac, dist, _ = matriz_osrm(servidor, puntos)
    recta = [[haversine_m(a, b) for b in puntos] for a in puntos]

    pares = [(recta[i][j], dist[i][j], durac[i][j]) for i in range(n_pares) for j in range(n_pares)
             if i != j and recta[i][j] > 200]
    circuidad = [d / r for r, d, _ in pares]
    por_tramo = []
    for desde, hasta in TRAMOS_M:
        valores = [d / r for r, d, _ in pares if desde <= r < hasta]
        if valores:
            por_tramo.append({"desde_m": desde, "hasta_m": None if hasta == float("inf") else hasta,
                              "pares": len(valores), "circuidad_mediana": statistics.median(valores)})
    distinto = sum(
        min((j for j in range(n_pares) if j != i), key=lambda j: recta[i][j])
        != min((j for j in range(n_pares) if j != i), key=lambda j: durac[i][j])
        for i in range(n_pares))

    excesos = []
    for _ in range(n_instancias):
        idx = rng.sample(range(n_pares), tam_instancia + 1)
        m_recta = [[recta[a][b] for b in idx] for a in idx]
        m_tiempo = [[durac[a][b] for b in idx] for a in idx]
        con_recta = costo(vecino_mas_cercano_2opt(m_recta), m_tiempo)
        con_red = costo(vecino_mas_cercano_2opt(m_tiempo), m_tiempo)
        excesos.append(100 * (con_recta - con_red) / con_red)

    resumen = {
        "ciudad": nombre,
        "puntos": n_pares,
        "pares": len(circuidad),
        "circuidad_mediana": statistics.median(circuidad),
        "circuidad_p10": percentil(circuidad, 10),
        "circuidad_p90": percentil(circuidad, 90),
        "vecino_distinto_pct": 100 * distinto / n_pares,
        "asimetria_tiempo_pct": 100 * statistics.median(
            abs(durac[i][j] - durac[j][i]) / max(durac[i][j], durac[j][i])
            for i in range(n_pares) for j in range(i + 1, n_pares) if durac[i][j] > 0),
        "instancias": n_instancias,
        "clientes_por_instancia": tam_instancia,
        "exceso_recta_mediana_pct": statistics.median(excesos),
        "exceso_recta_max_pct": max(excesos),
        "instancias_con_exceso_pct": 100 * sum(e > 0.01 for e in excesos) / n_instancias,
        "exceso_recta_media_pct": statistics.mean(excesos),
        "circuidad_por_tramo": por_tramo,
    }
    # Datos por par e instancia, para las figuras del artículo.
    detalle = {"ciudad": nombre, "pares_recta_dist_tiempo": [[round(r), round(d), round(t, 1)] for r, d, t in pares],
               "excesos_pct": [round(e, 3) for e in excesos]}
    return resumen, detalle


def tiempos_matriz(servidor, caja, rng, tamanos, repeticiones=3):
    puntos = puntos_sobre_calles(servidor, caja, max(tamanos), rng)
    filas = []
    for n in tamanos:
        segundos = [matriz_osrm(servidor, puntos[:n])[2] for _ in range(repeticiones)]
        filas.append({"puntos": n, "segundos_mediana": statistics.median(segundos)})
    return filas


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--servidor", default=None)
    parser.add_argument("--puntos", type=int, default=100, help="puntos por ciudad para pares")
    parser.add_argument("--instancias", type=int, default=50)
    parser.add_argument("--clientes", type=int, default=15)
    parser.add_argument("--salida", default=None, help="carpeta donde guardar resultados.json")
    parser.add_argument("--semilla", type=int, default=SEMILLA)
    parser.add_argument("--sin-matriz", action="store_true", help="no medir el tiempo de cálculo de la matriz")
    args = parser.parse_args()
    servidor = args.servidor or f"http://localhost:{puerto_osrm()}"
    rng = random.Random(args.semilla)

    resultados = {"semilla": args.semilla, "max_snap_m": MAX_SNAP_M, "ciudades": [], "matriz": None}
    detalles = []
    for nombre, caja in CIUDADES.items():
        fila, detalle = analizar_ciudad(servidor, nombre, caja, rng, args.puntos, args.instancias, args.clientes)
        resultados["ciudades"].append(fila)
        detalles.append(detalle)
        print(json.dumps(fila, ensure_ascii=False, indent=2))
    if not args.sin_matriz:
        resultados["matriz"] = tiempos_matriz(servidor, CIUDADES["Asunción"], rng, [10, 100, 500, 1000])
        print(json.dumps(resultados["matriz"], indent=2))

    if args.salida:
        os.makedirs(args.salida, exist_ok=True)
        sufijo = "" if args.semilla == SEMILLA else f"_s{args.semilla}"
        with open(os.path.join(args.salida, f"linea_recta_vs_red{sufijo}.json"), "w", encoding="utf-8") as archivo:
            json.dump(resultados, archivo, ensure_ascii=False, indent=2)
        with open(os.path.join(args.salida, f"linea_recta_vs_red{sufijo}_detalle.json"), "w", encoding="utf-8") as archivo:
            json.dump(detalles, archivo, ensure_ascii=False)


if __name__ == "__main__":
    main()
