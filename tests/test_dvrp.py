"""Pruebas del modelo, los métodos y la simulación.  python3 -m unittest discover tests"""

import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dvrp.modelo import Evaluador, Instancia, Pedido, verificar  # noqa: E402
from dvrp.simulacion import simular  # noqa: E402
from dvrp.tabu import BusquedaTabu, insercion  # noqa: E402


def instancia_aleatoria(semilla, n_puntos=15, n_pedidos=30, dinamicos=0.5, vehiculos=2,
                        capacidad=15, horizonte=6 * 3600):
    rng = random.Random(semilla)
    pts = [(0.5, 0.5)] + [(rng.random(), rng.random()) for _ in range(n_puntos)]
    # Matriz asimétrica, como la de la red vial.
    t = [[math.dist(a, b) * 2400 * (1 + 0.1 * rng.random()) for b in pts] for a in pts]
    for i in range(len(pts)):
        t[i][i] = 0.0
    pedidos = [Pedido(i, rng.randint(1, n_puntos), rng.randint(1, 4),
                      0.0 if rng.random() >= dinamicos else rng.uniform(0, 0.7 * horizonte))
               for i in range(n_pedidos)]
    return Instancia(t, pedidos, vehiculos, capacidad, horizonte, 300, 600, f"prueba-{semilla}")


class PruebasModelo(unittest.TestCase):
    def test_viaje_y_vehiculo(self):
        t = [[0, 10, 20], [10, 0, 5], [20, 7, 0]]
        inst = Instancia(t, [Pedido(0, 1, 3, 0.0), Pedido(1, 2, 4, 100.0)], 1, 5, 1000, 2, 3)
        ev = Evaluador(inst)
        self.assertEqual(ev.viaje([0, 1]), (10 + 5 + 20, 7, 100.0))
        # Excede la capacidad (7 > 5); sale en 100 por la liberación: 100 + 3 + 35 + 2·2 = 142.
        self.assertEqual(ev.vehiculo([[0, 1]], 0.0), (35, 2, 0.0, 142.0))
        # En dos viajes: 0+3+20+2 = 25; max(25,100)+3+40+2 = 145.
        self.assertEqual(ev.vehiculo([[0], [1]], 0.0), (60, 0, 0.0, 145.0))

    def test_verificar_detecta_errores(self):
        t = [[0, 10, 20], [10, 0, 5], [20, 7, 0]]
        inst = Instancia(t, [Pedido(0, 1, 3, 0.0), Pedido(1, 2, 4, 100.0)], 1, 5, 1000, 2, 3)
        bien = [{"vehiculo": 0, "salida": 0.0, "decision": 0.0, "pedidos": [0]},
                {"vehiculo": 0, "salida": 100.0, "decision": 100.0, "pedidos": [1]}]
        self.assertEqual(verificar(inst, bien)[0], 60)
        casos = [
            [{"vehiculo": 0, "salida": 100.0, "decision": 100.0, "pedidos": [0, 1]}],   # capacidad
            [{"vehiculo": 0, "salida": 0.0, "decision": 0.0, "pedidos": [1]}],          # liberación
            [{"vehiculo": 0, "salida": 0.0, "decision": 0.0, "pedidos": [0]},
             {"vehiculo": 0, "salida": 10.0, "decision": 0.0, "pedidos": [1]}],         # superpuestos
            [{"vehiculo": 0, "salida": 0.0, "decision": 0.0, "pedidos": [0]},
             {"vehiculo": 0, "salida": 200.0, "decision": 200.0, "pedidos": [0]}],      # dos veces
            [{"vehiculo": 0, "salida": 990.0, "decision": 990.0, "pedidos": [1]}],      # horizonte
        ]
        for caso in casos:
            with self.assertRaises(AssertionError):
                verificar(inst, caso)


class PruebasMetodos(unittest.TestCase):
    def test_insercion_factible(self):
        inst = instancia_aleatoria(1, dinamicos=0.0)
        ev = Evaluador(inst)
        plan = [[] for _ in range(inst.vehiculos)]
        pend = insercion(ev, plan, [0.0] * inst.vehiculos, set(inst.por_id))
        c = ev.plan(plan, [0.0] * inst.vehiculos, pend)
        self.assertEqual((c["exceso_capacidad"], c["exceso_horizonte"]), (0, 0))

    def test_tabu_no_empeora_la_insercion(self):
        for semilla in range(3):
            inst = instancia_aleatoria(semilla, dinamicos=0.0)
            ev = Evaluador(inst)
            disp = [0.0] * inst.vehiculos
            plan = [[] for _ in range(inst.vehiculos)]
            pend = insercion(ev, plan, disp, set(inst.por_id))
            antes = ev.plan(plan, disp, pend)["objetivo"]
            plan2, pend2 = BusquedaTabu(ev, random.Random(semilla)).optimizar(plan, disp, pend, 300)
            despues = ev.plan(plan2, disp, pend2)
            self.assertLessEqual(despues["objetivo"], antes + 1e-6)
            self.assertEqual((despues["exceso_capacidad"], despues["exceso_horizonte"]), (0, 0))
            asignados = sorted(i for viajes in plan2 for v in viajes for i in v)
            self.assertEqual(sorted(asignados + sorted(pend2)), sorted(inst.por_id))


class PruebasSimulacion(unittest.TestCase):
    def test_politicas_verificadas(self):
        # simular() llama a verificar(): si una ejecución no cumple el modelo, falla.
        for semilla in range(3):
            inst = instancia_aleatoria(semilla)
            for politica in ("insercion", "tabu", "tabu_espera", "informacion_completa"):
                r = simular(inst, politica, semilla=semilla, iteraciones=50, iteraciones_completa=300,
                            corte=0.7 * inst.horizonte)
                self.assertEqual(r["atendidos"] + r["no_atendidos"], len(inst.pedidos))

    def test_reproducible(self):
        inst = instancia_aleatoria(7)
        a = simular(inst, "tabu", semilla=3, iteraciones=50)
        b = simular(inst, "tabu", semilla=3, iteraciones=50)
        self.assertEqual(a["ejecucion"], b["ejecucion"])

    def test_estatico_igual_a_completa_sin_dinamismo(self):
        # Sin pedidos dinámicos, la simulación decide una vez en τ = 0 con todo conocido.
        inst = instancia_aleatoria(4, dinamicos=0.0)
        r = simular(inst, "tabu", semilla=1, iteraciones=200)
        self.assertEqual(r["decisiones"], 1)


if __name__ == "__main__":
    unittest.main()
