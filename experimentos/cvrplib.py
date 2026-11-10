"""Validación del método en instancias estándar: conjunto A de CVRPLIB (Augerat et al., 1995).

Sin dinamismo, sin horizonte y sin tiempos de carga y descarga, el modelo es el CVRP clásico
(un vehículo con viajes ilimitados equivale a una flota sin límite). Se compara el costo que
obtiene la búsqueda tabú con el óptimo publicado en CVRPLIB (Uchoa et al., 2017). Las distancias
son euclidianas, redondeadas al entero más cercano (convención TSPLIB).

    python3 experimentos/cvrplib.py --salida experimentos/resultados/dvrp

Descarga los .vrp a experimentos/cvrplib/ si no están (los identificadores de descarga son del
sitio de CVRPLIB y pueden cambiar).
"""

import argparse
import json
import math
import os
import random
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dvrp.modelo import Evaluador, Instancia, Pedido  # noqa: E402
from dvrp.tabu import BusquedaTabu, insercion  # noqa: E402

BASE = "https://galgos.inf.puc-rio.br/cvrplib/index.php/en/download/instance/"
# nombre: (id de descarga en CVRPLIB, óptimo publicado)
INSTANCIAS = {
    "A-n32-k5": (4, 784), "A-n33-k5": (5, 661), "A-n37-k5": (10, 669), "A-n45-k6": (16, 944),
    "A-n53-k7": (20, 1010), "A-n60-k9": (23, 1354), "A-n69-k9": (30, 1159), "A-n80-k10": (31, 1763),
}
CARPETA = os.path.join(os.path.dirname(__file__), "cvrplib")


def descargar(nombre):
    ruta = os.path.join(CARPETA, f"{nombre}.vrp")
    if not os.path.exists(ruta):
        os.makedirs(CARPETA, exist_ok=True)
        pedido = urllib.request.Request(BASE + str(INSTANCIAS[nombre][0]),
                                        headers={"User-Agent": "ruteo-urbano/1.0"})
        with urllib.request.urlopen(pedido, timeout=60) as r:
            texto = r.read().decode("utf-8")
        if f"NAME : {nombre}" not in texto.replace("\t", " ") and nombre not in texto.splitlines()[0]:
            raise RuntimeError(f"{nombre}: la descarga no es la instancia esperada")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(texto)
    return ruta


def leer_vrp(ruta):
    """Lee un .vrp de TSPLIB (EUC_2D) y lo devuelve como Instancia del modelo."""
    with open(ruta, encoding="utf-8") as f:
        lineas = [l.strip() for l in f]
    capacidad, coords, demandas, deposito, seccion = None, {}, {}, None, None
    for l in lineas:
        if not l or l == "EOF":
            continue
        if ":" in l and l.split(":")[0].strip().isupper():
            clave, valor = (x.strip() for x in l.split(":", 1))
            if clave == "CAPACITY":
                capacidad = int(valor)
            if clave == "EDGE_WEIGHT_TYPE" and valor != "EUC_2D":
                raise ValueError(valor)
            continue
        if l.endswith("_SECTION"):
            seccion = l
            continue
        partes = l.split()
        if seccion == "NODE_COORD_SECTION":
            coords[int(partes[0])] = (float(partes[1]), float(partes[2]))
        elif seccion == "DEMAND_SECTION":
            demandas[int(partes[0])] = int(partes[1])
        elif seccion == "DEPOT_SECTION" and int(partes[0]) > 0:
            deposito = int(partes[0])
    orden = [deposito] + sorted(n for n in coords if n != deposito)
    t = [[float(round(math.dist(coords[a], coords[b]))) for b in orden] for a in orden]
    pedidos = [Pedido(i - 1, i, demandas[n], 0.0) for i, n in enumerate(orden) if i > 0]
    return Instancia(t, pedidos, 1, capacidad, math.inf, 0.0, 0.0, os.path.basename(ruta)[:-4])


def resolver(inst, semilla, iteraciones, muestras):
    ev = Evaluador(inst)
    inicio = time.perf_counter()
    plan = [[]]
    pend = insercion(ev, plan, [0.0], set(inst.por_id))
    costo_insercion = ev.plan(plan, [0.0], pend)["viaje"]
    plan, pend = BusquedaTabu(ev, random.Random(semilla), muestras=muestras).optimizar(
        plan, [0.0], pend, iteraciones)
    c = ev.plan(plan, [0.0], pend)
    assert not pend and c["exceso_capacidad"] == 0
    return costo_insercion, c["viaje"], len(plan[0]), time.perf_counter() - inicio


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--salida", default="experimentos/resultados/dvrp")
    p.add_argument("--semillas", type=int, default=5)
    p.add_argument("--iteraciones", type=int, default=5000)
    p.add_argument("--muestras", type=int, default=120)
    a = p.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    filas = []
    for nombre, (_, optimo) in INSTANCIAS.items():
        inst = leer_vrp(descargar(nombre))
        corridas = [resolver(inst, s, a.iteraciones, a.muestras) for s in range(1, a.semillas + 1)]
        costos = [c[1] for c in corridas]
        fila = {"instancia": nombre, "clientes": len(inst.pedidos), "optimo": optimo,
                "insercion": corridas[0][0], "tabu_mejor": min(costos),
                "tabu_medio": sum(costos) / len(costos),
                "brecha_mejor_pct": 100 * (min(costos) - optimo) / optimo,
                "brecha_media_pct": 100 * (sum(costos) / len(costos) - optimo) / optimo,
                "brecha_insercion_pct": 100 * (corridas[0][0] - optimo) / optimo,
                "rutas": [c[2] for c in corridas], "tiempo_medio_s": sum(c[3] for c in corridas) / len(corridas),
                "costos": costos}
        filas.append(fila)
        print(f"{nombre}: óptimo {optimo}, inserción {fila['insercion']:.0f}, tabú mejor "
              f"{fila['tabu_mejor']:.0f} ({fila['brecha_mejor_pct']:.1f} %), medio "
              f"{fila['tabu_medio']:.0f} ({fila['brecha_media_pct']:.1f} %), {fila['tiempo_medio_s']:.0f} s")
    datos = {"parametros": vars(a), "instancias": filas}
    with open(os.path.join(a.salida, "cvrplib.json"), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
