"""Escenarios de prueba del DVRP en Asunción y Ciudad del Este, con tiempos de la red vial.

Para cada ciudad y semilla se ubican un depósito y 30 puntos de entrega al azar sobre las calles
del mismo rectángulo urbano del experimento de distancias (linea_recta_vs_red.py), y se piden a
OSRM los tiempos de viaje entre todos (matriz asimétrica). Sobre esa red se generan 60 pedidos
de una jornada de 8 h, con demanda de 1 a 5 unidades y un punto de entrega al azar. Una
fracción δ de los pedidos (grado de dinamismo; Larsen, 2000) se libera
durante la jornada, en un instante uniforme entre 0 y 0,75 H; el resto se conoce al inicio.
Flota: 3 vehículos de 20 unidades; 10 min de carga por viaje y 5 min de descarga por pedido.

Se comparan cuatro políticas (ver dvrp/simulacion.py): inserción, búsqueda tabú, búsqueda tabú
con espera (un viaje sale con al menos el 80 % de la capacidad, o después del último pedido
posible) y la referencia con información completa. Cada ejecución se verifica con dvrp.modelo.verificar.

    python3 experimentos/dvrp_escenarios.py --salida experimentos/resultados/dvrp

Las instancias quedan en <salida>/instancias/ (puntos y matriz incluidos): si ya existen, se
reutilizan y no hace falta OSRM.
"""

import argparse
import csv
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dvrp.modelo import Instancia, Pedido  # noqa: E402
from dvrp.simulacion import simular  # noqa: E402

CIUDADES = {  # mismos rectángulos que linea_recta_vs_red.py
    "Asunción": (-25.340, -25.260, -57.640, -57.540),
    "Ciudad del Este": (-25.560, -25.470, -54.690, -54.605),
}
PARAMETROS = {"puntos": 30, "pedidos": 60, "vehiculos": 3, "capacidad": 20,
              "horizonte_h": 8, "carga_min": 10, "servicio_min": 5, "liberacion_max": 0.75}
DINAMISMOS = [0.25, 0.5, 0.75]
POLITICAS = ["insercion", "tabu", "tabu_espera", "informacion_completa"]


def red(ciudad, semilla, carpeta):
    """Depósito y puntos sobre las calles, y su matriz de tiempos (s) de OSRM, con caché."""
    ruta = os.path.join(carpeta, f"red_{ciudad.replace(' ', '_')}_{semilla}.json")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    from linea_recta_vs_red import matriz_osrm, puntos_sobre_calles
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "demo"))
    from consulta import puerto_osrm
    servidor = f"http://localhost:{puerto_osrm()}"
    rng = random.Random(f"red-{ciudad}-{semilla}")
    puntos = puntos_sobre_calles(servidor, CIUDADES[ciudad], PARAMETROS["puntos"] + 1, rng)
    tiempos, distancias, _ = matriz_osrm(servidor, puntos)
    datos = {"ciudad": ciudad, "semilla": semilla, "puntos": puntos, "tiempos": tiempos,
             "distancias": distancias}
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f)
    return datos


def instancia(datos_red, dinamismo, semilla):
    P = PARAMETROS
    H = P["horizonte_h"] * 3600
    rng = random.Random(f"pedidos-{datos_red['ciudad']}-{semilla}-{dinamismo}")
    n = P["pedidos"]
    dinamicos = set(rng.sample(range(n), round(dinamismo * n)))
    pedidos = [Pedido(i, rng.randint(1, P["puntos"]), rng.randint(1, 5),
                      round(rng.uniform(0, P["liberacion_max"] * H), 1) if i in dinamicos else 0.0)
               for i in range(n)]
    return Instancia(datos_red["tiempos"], pedidos, P["vehiculos"], P["capacidad"], H,
                     P["servicio_min"] * 60, P["carga_min"] * 60,
                     f"{datos_red['ciudad']} s{semilla} δ={dinamismo}")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--salida", default="experimentos/resultados/dvrp")
    p.add_argument("--semillas", type=int, default=5)
    p.add_argument("--iteraciones", type=int, default=300, help="por reoptimización")
    p.add_argument("--iteraciones-completa", type=int, default=6000)
    p.add_argument("--intervalo-min", type=float, default=10)
    p.add_argument("--umbral", type=float, default=0.8, help="carga mínima para salir (tabu_espera)")
    a = p.parse_args()
    carpeta = os.path.join(a.salida, "instancias")
    os.makedirs(carpeta, exist_ok=True)
    filas, ejecuciones = [], {}
    for ciudad in CIUDADES:
        for s in range(1, a.semillas + 1):
            datos_red = red(ciudad, s, carpeta)
            for d in DINAMISMOS:
                inst = instancia(datos_red, d, s)
                inst.guardar(os.path.join(carpeta, f"{ciudad.replace(' ', '_')}_{s}_d{int(d * 100)}.json"))
                for pol in POLITICAS:
                    inicio = time.perf_counter()
                    r = simular(inst, pol, intervalo=a.intervalo_min * 60, semilla=s,
                                iteraciones=a.iteraciones, iteraciones_completa=a.iteraciones_completa,
                                umbral=a.umbral, corte=PARAMETROS["liberacion_max"] * inst.horizonte)
                    ejecuciones[f"{inst.nombre} {pol}"] = r.pop("ejecucion")
                    r.update({"ciudad": ciudad, "semilla": s, "dinamismo": d,
                              "tiempo_total_s": time.perf_counter() - inicio})
                    filas.append(r)
                    print(f"{inst.nombre:28} {pol:21} viaje {r['tiempo_viaje_h']:6.2f} h  "
                          f"no atendidos {r['no_atendidos']:2}  viajes {r['viajes']:2}  "
                          f"decisión {r['tiempo_decision_medio_s']:5.2f} s", flush=True)
    with open(os.path.join(a.salida, "escenarios.json"), "w", encoding="utf-8") as f:
        json.dump({"parametros": {**PARAMETROS, **vars(a), "dinamismos": DINAMISMOS},
                   "resultados": filas, "ejecuciones": ejecuciones}, f, ensure_ascii=False)
    with open(os.path.join(a.salida, "escenarios.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


if __name__ == "__main__":
    main()
