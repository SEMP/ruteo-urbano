"""Métodos de solución: inserción más barata y búsqueda tabú sobre la parte libre del plan.

Ambos trabajan sobre la parte del plan que todavía se puede cambiar: los viajes que ningún
vehículo empezó a cargar. Cada vehículo k queda libre en el depósito a partir de
`disponibles[k]` (después de su viaje en curso, si lo tiene).

Búsqueda tabú (Glover, 1986), con las ideas habituales para el VRP (Gendreau, Hertz y Laporte,
1994; Cordeau, Laporte y Mercier, 2001):
- vecindario de cuatro movimientos: reubicar un pedido en la mejor posición de otro viaje (o de
  un viaje nuevo, o fuera del plan), intercambiar dos pedidos, intercambiar las colas de dos
  viajes (2-opt*) e invertir un tramo de un viaje (2-opt);
- en cada iteración se evalúa una muestra aleatoria del vecindario y se aplica el mejor
  movimiento no tabú, aunque empeore;
- atributo tabú (pedido, predecesor): durante `tenencia` iteraciones un pedido movido no puede
  volver detrás del pedido que tenía antes (o al inicio de un viaje, si estaba ahí), salvo que
  el movimiento mejore la mejor solución factible (criterio de aspiración);
- se admiten soluciones que exceden la capacidad o el horizonte, con penalizaciones que se
  ajustan solas: suben mientras la solución actual es infactible y bajan cuando es factible;
- si pasan `estancamiento` iteraciones sin mejorar, la búsqueda vuelve a la mejor solución.
"""

import math


def insercion(ev, plan, disponibles, pendientes, orden=None):
    """Inserta cada pedido pendiente donde menos aumenta el costo sin perder factibilidad.

    Modifica `plan` y devuelve el conjunto de pedidos que no se pudieron insertar.
    """
    inst = ev.inst
    pend = sorted(pendientes, key=orden or (lambda i: (inst.por_id[i].liberacion, i)))
    restantes = set()
    for r in pend:
        mejor = None  # (aumento, k, j, p)
        for k, viajes in enumerate(plan):
            base, _, _, _ = ev.vehiculo(viajes, disponibles[k])
            for j in range(len(viajes) + 1):
                if j == len(viajes):
                    candidatos = [viajes + [[r]]]
                    posiciones = [0]
                else:
                    candidatos, posiciones = [], []
                    if ev.viaje(viajes[j])[1] + inst.por_id[r].demanda > inst.capacidad:
                        continue
                    for p in range(len(viajes[j]) + 1):
                        nuevo = viajes[j][:p] + [r] + viajes[j][p:]
                        candidatos.append(viajes[:j] + [nuevo] + viajes[j + 1:])
                        posiciones.append(p)
                for cand, p in zip(candidatos, posiciones):
                    v, c, h, _ = ev.vehiculo(cand, disponibles[k])
                    if c == 0 and h == 0 and (mejor is None or v - base < mejor[0]):
                        mejor = (v - base, k, j, p)
        if mejor is None:
            restantes.add(r)
            continue
        _, k, j, p = mejor
        if j == len(plan[k]):
            plan[k].append([r])
        else:
            plan[k][j].insert(p, r)
    return restantes


class BusquedaTabu:
    def __init__(self, ev, rng, muestras=120, tenencia=(7, 20), estancamiento=500):
        self.ev, self.rng = ev, rng
        self.muestras, self.tenencia, self.estancamiento = muestras, tenencia, estancamiento
        t = ev.inst.tiempos
        n = len(t)
        media = sum(map(sum, t)) / max(1, n * (n - 1))
        demanda = sum(p.demanda for p in ev.inst.pedidos) / max(1, len(ev.inst.pedidos))
        self.alfa0 = media / max(1.0, demanda)  # costo por unidad de exceso de capacidad
        self.gama0 = 1.0                         # costo por segundo de exceso de horizonte

    def _penalizado(self, comp, n_pend):
        v, c, h = comp
        return v + self.alfa * c + self.gama * h + self.ev.inst.penalizacion * n_pend

    def _objetivo_factible(self, comps, n_pend):
        v, c, h = map(sum, zip(*comps))
        if c > 0 or h > 1e-9:
            return math.inf
        return v + self.ev.inst.penalizacion * n_pend

    def optimizar(self, plan, disponibles, pendientes, iteraciones):
        """Mejora `plan` (lista de vehículos con sus viajes) y devuelve (plan, pendientes).

        Parte de la solución recibida, que se supone factible, y devuelve la mejor solución
        factible encontrada. Si pasan `estancamiento` iteraciones sin mejorar, vuelve a la mejor.
        """
        rng, ev = self.rng, self.ev
        plan = [[list(v) for v in viajes] for viajes in plan]
        pend = set(pendientes)
        K = len(plan)
        if not any(plan) and not pend:
            return plan, pend
        self.alfa, self.gama = self.alfa0, self.gama0
        comp = [ev.vehiculo(plan[k], disponibles[k])[:3] for k in range(K)]
        mejor_plan = [[list(v) for v in viajes] for viajes in plan]
        mejor_pend, mejor_comp = set(pend), list(comp)
        mejor_obj = self._objetivo_factible(comp, len(pend))
        tabu = {}  # (pedido, predecesor) -> iteración hasta la que es tabú
        sin_mejora = 0

        for it in range(iteraciones):
            ubic = [(k, j, p) for k in range(K) for j, v in enumerate(plan[k]) for p in range(len(v))]
            mejor_mov = None
            for _ in range(self.muestras):
                mov = self._muestrear(plan, pend, ubic, disponibles)
                if mov is None:
                    continue
                cambios, nuevo_pend, quitados = mov
                comps = list(comp)
                for k, viajes in cambios.items():
                    comps[k] = ev.vehiculo(viajes, disponibles[k])[:3]
                n_pend = len(nuevo_pend)
                costo = self._penalizado(tuple(map(sum, zip(*comps))), n_pend)
                if self._es_tabu(tabu, it, cambios, quitados) and \
                        self._objetivo_factible(comps, n_pend) >= mejor_obj - 1e-9:
                    continue
                if mejor_mov is None or costo < mejor_mov[0]:
                    mejor_mov = (costo, cambios, nuevo_pend, comps, quitados)
            if mejor_mov is None:
                continue
            _, cambios, nuevo_pend, comps, quitados = mejor_mov
            # Atributo tabú: el pedido movido no vuelve detrás de su predecesor anterior.
            for r in quitados:
                tabu[(r, self._predecesor(plan, r))] = it + rng.randint(*self.tenencia)
            for k, viajes in cambios.items():
                plan[k] = viajes
            pend, comp = nuevo_pend, comps
            obj = self._objetivo_factible(comp, len(pend))
            if obj < mejor_obj - 1e-9:
                mejor_obj, mejor_comp, sin_mejora = obj, list(comp), 0
                mejor_plan = [[list(v) for v in viajes] for viajes in plan]
                mejor_pend = set(pend)
            else:
                sin_mejora += 1
                if sin_mejora >= self.estancamiento:
                    plan = [[list(v) for v in viajes] for viajes in mejor_plan]
                    pend, comp, sin_mejora = set(mejor_pend), list(mejor_comp), 0
            # Ajuste de las penalizaciones.
            _, c, h = map(sum, zip(*comp))
            self.alfa = min(self.alfa0 * 100, self.alfa * 1.2) if c > 0 else max(self.alfa0 / 100, self.alfa / 1.2)
            self.gama = min(self.gama0 * 100, self.gama * 1.2) if h > 0 else max(self.gama0 / 100, self.gama / 1.2)
        return mejor_plan, mejor_pend

    @staticmethod
    def _predecesor(plan, r):
        """Pedido anterior a r en su viaje (None si es el primero); 'fuera' si no está en el plan."""
        for viajes in plan:
            for v in viajes:
                if r in v:
                    p = v.index(r)
                    return v[p - 1] if p > 0 else None
        return "fuera"

    def _es_tabu(self, tabu, it, cambios, quitados):
        for r in quitados:
            for viajes in cambios.values():
                for v in viajes:
                    if r in v:
                        p = v.index(r)
                        if tabu.get((r, v[p - 1] if p > 0 else None), -1) >= it:
                            return True
        return False

    def _mejor_lugar(self, viajes, r, j):
        """Copia de `viajes` con r en la mejor posición del viaje j (j == len: viaje nuevo)."""
        viajes = [list(v) for v in viajes]
        if j >= len(viajes):
            viajes.insert(self.rng.randrange(len(viajes) + 1), [r])
            return viajes
        v = viajes[j]
        mejor = min(range(len(v) + 1), key=lambda p: self.ev.viaje(v[:p] + [r] + v[p:])[0])
        v.insert(mejor, r)
        return viajes

    def _muestrear(self, plan, pend, ubic, disponibles):
        """Un movimiento al azar: (cambios {k: viajes nuevos}, pendientes, pedidos movidos)."""
        rng, K = self.rng, len(plan)
        tipo = rng.random()
        if pend and (not ubic or tipo < 0.15):
            # Insertar un pedido pendiente en la mejor posición de un viaje al azar.
            r = rng.choice(sorted(pend))
            k = rng.randrange(K)
            return {k: self._mejor_lugar(plan[k], r, rng.randrange(len(plan[k]) + 1))}, pend - {r}, [r]
        if not ubic:
            return None
        if tipo < 0.6:
            # Reubicar un pedido en la mejor posición de otro viaje (o del mismo).
            k, j, p = rng.choice(ubic)
            r = plan[k][j][p]
            origen = [list(v) for v in plan[k]]
            del origen[j][p]
            if rng.random() < 0.02:
                return {k: [v for v in origen if v]}, pend | {r}, [r]
            k2 = rng.randrange(K)
            destino = origen if k2 == k else plan[k2]
            j2 = rng.randrange(len(destino) + 1)
            nuevo = self._mejor_lugar(destino, r, j2)
            if k2 == k:
                return {k: [v for v in nuevo if v]}, pend, [r]
            return {k: [v for v in origen if v], k2: nuevo}, pend, [r]
        if tipo < 0.8 and len(ubic) >= 2:
            # Intercambiar dos pedidos.
            (k1, j1, p1), (k2, j2, p2) = rng.sample(ubic, 2)
            r1, r2 = plan[k1][j1][p1], plan[k2][j2][p2]
            cambios = {k1: [list(v) for v in plan[k1]]}
            if k2 != k1:
                cambios[k2] = [list(v) for v in plan[k2]]
            cambios[k1][j1][p1] = r2
            cambios[k2][j2][p2] = r1
            return cambios, pend, [r1, r2]
        if tipo < 0.9:
            # 2-opt*: intercambiar las colas de dos viajes.
            (k1, j1, p1), (k2, j2, p2) = rng.sample(ubic, 2) if len(ubic) >= 2 else (ubic[0], ubic[0])
            if (k1, j1) == (k2, j2):
                return None
            a, b = plan[k1][j1], plan[k2][j2]
            na, nb = a[:p1 + 1] + b[p2 + 1:], b[:p2 + 1] + a[p1 + 1:]
            cambios = {k1: [list(v) for v in plan[k1]]}
            if k2 != k1:
                cambios[k2] = [list(v) for v in plan[k2]]
            cambios[k1][j1] = na
            cambios[k2][j2] = nb
            for k in cambios:
                cambios[k] = [v for v in cambios[k] if v]
            return cambios, pend, []
        # 2-opt dentro de un viaje.
        k, j, _ = rng.choice(ubic)
        v = plan[k][j]
        if len(v) < 2:
            return None
        a, b = sorted(rng.sample(range(len(v)), 2))
        viajes = [list(x) for x in plan[k]]
        viajes[j] = v[:a] + v[a:b + 1][::-1] + v[b + 1:]
        return {k: viajes}, pend, []
