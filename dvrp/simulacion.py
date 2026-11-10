"""Simulación de la jornada: los pedidos llegan con el tiempo y el plan se reoptimiza.

La jornada se divide en intervalos de `intervalo` segundos (como en Montemanni et al., 2005). Al comienzo de cada intervalo, en el instante τ:

1. Se fijan los viajes que empezaron a cargarse antes de τ, según el plan vigente: ya no
   cambian (la carga está en el vehículo). Cada vehículo queda libre en el depósito cuando
   vuelve del último viaje fijado, o en τ si está esperando.
2. Se agregan a los pendientes los pedidos liberados hasta τ.
3. La política reoptimiza la parte libre del plan con los pedidos conocidos.

Después del último pedido se ejecuta el resto del plan sin más cambios. Un vehículo sale en
cuanto tiene un viaje planificado (no espera para juntar más pedidos), salvo en `tabu_espera`.

Políticas:
- `insercion`: agrega los pedidos nuevos con inserción más barata; no mejora lo ya planificado.
- `tabu`: agrega los pedidos nuevos con inserción y mejora todo el plan libre con búsqueda tabú
  (el plan inicial, en τ = 0, con `iteraciones_completa` iteraciones; cada reoptimización, con
  `iteraciones`).
- `tabu_espera`: como `tabu`, pero un vehículo espera en el depósito hasta que su próximo viaje
  lleve al menos `umbral` · Q, o hasta el `corte` (estrategia de espera, en la línea de
  Mitrović-Minić y Laporte, 2004).
- `informacion_completa`: referencia que conoce todos los pedidos desde el inicio (fecha y
  lugar), con la misma búsqueda tabú y más iteraciones; mide lo que cuesta no conocer el
  futuro. Cada pedido igual se carga después de su liberación.
"""

import random
import time

from .modelo import Evaluador, verificar
from .tabu import BusquedaTabu, insercion


def _fijar_hasta(inst, ev, plan, disponibles, tau, ejecucion, decision, umbral=None,
                 corte=float("inf"), intervalo=0.0):
    """Fija los viajes de cada vehículo que empiezan a cargarse antes de `tau`.

    Con `umbral` (estrategia de espera), un viaje sale solo si lleva al menos umbral · Q, si ya
    pasó el `corte` (no llegan más pedidos) o si esperar un intervalo más haría que el vehículo
    no vuelva antes del horizonte. Si no sale, el vehículo espera en el depósito y el viaje
    sigue abierto a cambios.
    """
    for k in range(len(plan)):
        while plan[k]:
            v = plan[k][0]
            dur, carga, lib = ev.viaje(v)
            salida = max(disponibles[k], lib)
            if salida >= tau:
                break
            if umbral is not None and carga < umbral * inst.capacidad and tau <= corte \
                    and ev.vehiculo(plan[k], tau + intervalo)[2] == 0:
                break
            ejecucion.append({"vehiculo": k, "salida": salida, "decision": decision[k],
                              "pedidos": list(v)})
            disponibles[k] = salida + inst.carga + dur + inst.servicio * len(v)
            plan[k].pop(0)


def simular(inst, politica, intervalo=600.0, semilla=0, iteraciones=300, muestras=120,
            iteraciones_completa=6000, umbral=0.8, corte=float("inf")):
    """Simula la jornada con una política y devuelve un dict de resultados (ya verificados).

    `umbral` y `corte` solo se usan en la política `tabu_espera`; `corte` es el instante a
    partir del cual no llegan más pedidos (lo conoce el despachador).
    """
    ev = Evaluador(inst)
    rng = random.Random(semilla)
    tabu = BusquedaTabu(ev, rng, muestras=muestras)
    K = inst.vehiculos
    ejecucion, tiempos_decision = [], []

    if politica == "informacion_completa":
        inicio = time.perf_counter()
        plan = [[] for _ in range(K)]
        disponibles = [0.0] * K
        pend = insercion(ev, plan, disponibles, {p.id for p in inst.pedidos})
        plan, pend = tabu.optimizar(plan, disponibles, pend, iteraciones_completa)
        tiempos_decision.append(time.perf_counter() - inicio)
        _fijar_hasta(inst, ev, plan, disponibles, float("inf"), ejecucion, [0.0] * K)
    else:
        pedidos = sorted(inst.pedidos, key=lambda p: (p.liberacion, p.id))
        ultimo = pedidos[-1].liberacion if pedidos else 0.0
        plan = [[] for _ in range(K)]
        disponibles = [0.0] * K
        decision = [0.0] * K   # instante en que se decidió el plan vigente de cada vehículo
        pend, siguiente, tau = set(), 0, 0.0
        while True:
            if politica == "tabu_espera":
                _fijar_hasta(inst, ev, plan, disponibles, tau, ejecucion, decision, umbral, corte,
                             intervalo)
            else:
                _fijar_hasta(inst, ev, plan, disponibles, tau, ejecucion, decision)
            disponibles = [max(d, tau) for d in disponibles]
            nuevos = 0
            while siguiente < len(pedidos) and pedidos[siguiente].liberacion <= tau:
                pend.add(pedidos[siguiente].id)
                siguiente += 1
                nuevos += 1
            if nuevos or pend:
                inicio = time.perf_counter()
                pend = insercion(ev, plan, disponibles, pend)
                if politica in ("tabu", "tabu_espera"):
                    # El plan inicial se arma antes de la jornada, con el mismo presupuesto que
                    # la referencia; las reoptimizaciones durante la jornada, con `iteraciones`.
                    n_it = iteraciones_completa if tau == 0 else iteraciones
                    plan, pend = tabu.optimizar(plan, disponibles, pend, n_it)
                elif politica != "insercion":
                    raise ValueError(politica)
                tiempos_decision.append(time.perf_counter() - inicio)
                decision = [tau] * K
            if tau >= ultimo:
                break
            tau += intervalo
        _fijar_hasta(inst, ev, plan, disponibles, float("inf"), ejecucion, decision)

    total, atendidos, llegadas = verificar(inst, ejecucion, politica == "informacion_completa")
    no_atendidos = sorted(set(inst.por_id) - atendidos)
    esperas = [llegadas[i] - inst.por_id[i].liberacion for i in atendidos]
    return {
        "politica": politica,
        "tiempo_viaje_h": total / 3600,
        "atendidos": len(atendidos),
        "no_atendidos": len(no_atendidos),
        "viajes": len(ejecucion),
        "espera_media_min": (sum(esperas) / len(esperas) / 60) if esperas else None,
        "espera_max_min": (max(esperas) / 60) if esperas else None,
        "decisiones": len(tiempos_decision),
        "tiempo_decision_medio_s": sum(tiempos_decision) / max(1, len(tiempos_decision)),
        "tiempo_decision_max_s": max(tiempos_decision, default=0.0),
        "ejecucion": ejecucion,
    }
