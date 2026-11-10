"""Modelo del problema: ruteo dinámico de vehículos con viajes múltiples y fechas de liberación.

Una flota de K vehículos idénticos, de capacidad Q, sale de un depósito y reparte pedidos en
puntos de entrega de la ciudad durante una jornada [0, H]. Cada pedido p tiene un punto de
entrega, una demanda q_p y una fecha de liberación a_p: el instante en que el pedido se conoce
y su carga está disponible en el depósito. Un vehículo puede hacer varios viajes
(depósito → entregas → depósito) en la jornada, cada uno con a lo sumo Q unidades. Antes de
cada viaje se carga el vehículo en el depósito (tiempo L) y en cada entrega se descarga
(tiempo s). Un viaje empieza a cargarse cuando el vehículo está en el depósito y todos sus
pedidos están liberados, y todos los vehículos vuelven antes de H.

Objetivo (lexicográfico, con una penalización grande): atender la mayor cantidad de pedidos y,
entre esas soluciones, minimizar el tiempo total de viaje de la flota.

Representación de un plan: para cada vehículo, una lista de viajes; cada viaje es una lista de
identificadores de pedido en el orden de visita. Los pedidos sin asignar van en un conjunto
aparte (`pendientes`).
"""

import json
import math
from dataclasses import asdict, dataclass

INFINITO = float("inf")


@dataclass(frozen=True)
class Pedido:
    id: int
    nodo: int          # índice en la matriz de tiempos (0 = depósito)
    demanda: int
    liberacion: float  # s desde el inicio de la jornada


@dataclass
class Instancia:
    tiempos: list      # tiempos[i][j]: s de viaje de i a j por la red vial; nodo 0 = depósito
    pedidos: list      # list[Pedido]
    vehiculos: int
    capacidad: int
    horizonte: float   # s: fin de la jornada
    servicio: float    # s de descarga por pedido
    carga: float       # s de carga en el depósito antes de cada viaje
    nombre: str = ""

    def __post_init__(self):
        self.por_id = {p.id: p for p in self.pedidos}
        # Penalización por pedido no atendido: mayor que cualquier ahorro de viaje posible.
        if math.isfinite(self.horizonte):
            self.penalizacion = 10 * self.horizonte * max(1, self.vehiculos)
        else:
            maximo = max(max(fila) for fila in self.tiempos)
            self.penalizacion = 10 * maximo * max(1, len(self.pedidos))

    def guardar(self, ruta):
        datos = {"nombre": self.nombre, "vehiculos": self.vehiculos, "capacidad": self.capacidad,
                 "horizonte": self.horizonte, "servicio": self.servicio, "carga": self.carga,
                 "pedidos": [asdict(p) for p in self.pedidos], "tiempos": self.tiempos}
        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, ensure_ascii=False)

    @classmethod
    def leer(cls, ruta):
        with open(ruta, encoding="utf-8") as archivo:
            d = json.load(archivo)
        return cls(tiempos=d["tiempos"], pedidos=[Pedido(**p) for p in d["pedidos"]],
                   vehiculos=d["vehiculos"], capacidad=d["capacidad"], horizonte=d["horizonte"],
                   servicio=d["servicio"], carga=d["carga"], nombre=d.get("nombre", ""))


class Evaluador:
    """Calcula duración, carga y liberación de cada viaje (con caché) y el costo de un plan."""

    def __init__(self, inst):
        self.inst = inst
        self._cache = {}

    def viaje(self, viaje):
        """(tiempo de viaje, carga total, liberación máxima) de un viaje."""
        clave = tuple(viaje)
        res = self._cache.get(clave)
        if res is None:
            m, ped = self.inst.tiempos, self.inst.por_id
            nodos = [ped[i].nodo for i in viaje]
            dur = m[0][nodos[0]] + sum(m[a][b] for a, b in zip(nodos, nodos[1:])) + m[nodos[-1]][0]
            res = (dur, sum(ped[i].demanda for i in viaje), max(ped[i].liberacion for i in viaje))
            if len(self._cache) > 200_000:
                self._cache.clear()
            self._cache[clave] = res
        return res

    def vehiculo(self, viajes, disponible):
        """(tiempo de viaje, exceso de capacidad, exceso de horizonte, fin) de un vehículo.

        `disponible`: instante desde el que el vehículo está libre en el depósito.
        """
        inst = self.inst
        t, total, exceso_cap = disponible, 0.0, 0
        for v in viajes:
            dur, carga, lib = self.viaje(v)
            exceso_cap += max(0, carga - inst.capacidad)
            t = max(t, lib) + inst.carga + dur + inst.servicio * len(v)
            total += dur
        return total, exceso_cap, max(0.0, t - inst.horizonte), t

    def plan(self, plan, disponibles, pendientes):
        """Costo de un plan factible o no: dict con sus componentes."""
        viaje = cap = hor = 0.0
        for viajes, disp in zip(plan, disponibles):
            v, c, h, _ = self.vehiculo(viajes, disp)
            viaje, cap, hor = viaje + v, cap + c, hor + h
        return {"viaje": viaje, "exceso_capacidad": cap, "exceso_horizonte": hor,
                "no_atendidos": len(pendientes),
                "objetivo": viaje + self.inst.penalizacion * len(pendientes)}


def verificar(inst, ejecucion, informacion_completa=False):
    """Revisa, sin usar el código del método, que una ejecución cumpla el modelo.

    `ejecucion`: lista de viajes realizados, cada uno un dict con vehiculo, salida (inicio de la
    carga en el depósito), decision (instante en que se fijó el viaje) y pedidos (en orden).
    Devuelve (tiempo total de viaje, pedidos atendidos, llegadas {pedido: instante de entrega}).
    Con `informacion_completa`, los pedidos se conocen desde el inicio (solución de
    referencia) y no se controla que se hayan conocido antes de decidir.
    Lanza AssertionError si algo no cumple.
    """
    m, ped = inst.tiempos, inst.por_id
    atendidos, llegadas, total = set(), {}, 0.0
    por_vehiculo = {}
    for v in ejecucion:
        por_vehiculo.setdefault(v["vehiculo"], []).append(v)
    assert set(por_vehiculo) <= set(range(inst.vehiculos)), "vehículo inexistente"
    for k, viajes in por_vehiculo.items():
        viajes.sort(key=lambda v: v["salida"])
        libre = 0.0
        for v in viajes:
            ids = v["pedidos"]
            assert ids, "viaje vacío"
            assert v["salida"] >= libre - 1e-6, f"vehículo {k}: viajes superpuestos"
            assert sum(ped[i].demanda for i in ids) <= inst.capacidad, f"vehículo {k}: capacidad"
            for i in ids:
                assert i not in atendidos, f"pedido {i} atendido dos veces"
                if not informacion_completa:
                    assert ped[i].liberacion <= v["decision"] + 1e-6, f"pedido {i} usado antes de conocerse"
                assert ped[i].liberacion <= v["salida"] + 1e-6, f"pedido {i} cargado antes de liberarse"
                atendidos.add(i)
            assert v["decision"] <= v["salida"] + 1e-6, "viaje fijado después de salir"
            t, nodo = v["salida"] + inst.carga, 0
            for i in ids:
                t += m[nodo][ped[i].nodo]
                total += m[nodo][ped[i].nodo]
                nodo = ped[i].nodo
                llegadas[i] = t
                t += inst.servicio
            t += m[nodo][0]
            total += m[nodo][0]
            assert t <= inst.horizonte + 1e-6, f"vehículo {k}: vuelve después del horizonte"
            libre = t
    return total, atendidos, llegadas
