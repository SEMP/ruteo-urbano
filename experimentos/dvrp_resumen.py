"""Resumen de los escenarios del DVRP: tablas agregadas y figura para el informe técnico.

    python3 experimentos/dvrp_resumen.py experimentos/resultados/dvrp

Lee escenarios.json y cvrplib.json de esa carpeta y escribe resumen.json y
figuras/dvrp_tiempo_viaje.svg.
"""

import json
import os
import statistics
import sys

ETIQUETAS = {"insercion": "Inserción", "tabu": "Búsqueda tabú", "tabu_espera": "Tabú con espera",
             "informacion_completa": "Información completa"}
COLORES = {"insercion": "#9aa5b1", "tabu": "#1a4d7a", "tabu_espera": "#5b8fc7",
           "informacion_completa": "#13B6D5"}


def coma(x, decimales=1):
    """Número con coma decimal, solo para los rótulos (nunca para coordenadas)."""
    return f"{x:.{decimales}f}".replace(".", ",")


def resumir(res):
    grupos = {}
    for r in res:
        grupos.setdefault((r["ciudad"], r["dinamismo"]), {}).setdefault(r["politica"], []).append(r)
    filas = []
    for (ciudad, d), pols in sorted(grupos.items()):
        fila = {"ciudad": ciudad, "dinamismo": d}
        for pol, rs in pols.items():
            fila[pol] = {
                "tiempo_viaje_h": statistics.mean(r["tiempo_viaje_h"] for r in rs),
                "no_atendidos": sum(r["no_atendidos"] for r in rs),
                "viajes": statistics.mean(r["viajes"] for r in rs),
                "espera_media_min": statistics.mean(r["espera_media_min"] for r in rs),
                "tiempo_decision_medio_s": statistics.mean(r["tiempo_decision_medio_s"] for r in rs),
                "tiempo_decision_max_s": max(r["tiempo_decision_max_s"] for r in rs),
            }
        # Comparaciones por semilla (misma instancia), luego promedio.
        por_semilla = {}
        for pol, rs in pols.items():
            for r in rs:
                por_semilla.setdefault(r["semilla"], {})[pol] = r["tiempo_viaje_h"]
        mejora = [100 * (v["insercion"] - v["tabu"]) / v["insercion"] for v in por_semilla.values()]
        brecha = [100 * (v["tabu"] - v["informacion_completa"]) / v["informacion_completa"]
                  for v in por_semilla.values()]
        fila["mejora_tabu_vs_insercion_pct"] = {"media": statistics.mean(mejora),
                                                "min": min(mejora), "max": max(mejora)}
        fila["brecha_tabu_vs_completa_pct"] = {"media": statistics.mean(brecha),
                                               "min": min(brecha), "max": max(brecha)}
        if all("tabu_espera" in v for v in por_semilla.values()):
            esp = [100 * (v["tabu_espera"] - v["informacion_completa"]) / v["informacion_completa"]
                   for v in por_semilla.values()]
            mej = [100 * (v["tabu"] - v["tabu_espera"]) / v["tabu"] for v in por_semilla.values()]
            fila["brecha_espera_vs_completa_pct"] = {"media": statistics.mean(esp),
                                                     "min": min(esp), "max": max(esp)}
            fila["mejora_espera_vs_tabu_pct"] = {"media": statistics.mean(mej),
                                                 "min": min(mej), "max": max(mej)}
        filas.append(fila)
    return filas


def figura(filas, ruta):
    """Barras agrupadas: tiempo de viaje medio por ciudad, grado de dinamismo y política."""
    ancho, alto, izq, abajo, arriba = 760, 360, 60, 70, 40
    grupos = [(f["ciudad"], f["dinamismo"], f) for f in filas]
    maximo = max(f[p]["tiempo_viaje_h"] for _, _, f in grupos for p in ETIQUETAS)
    tope = 2 * int(maximo / 2 + 1)
    escala = (alto - abajo - arriba) / tope
    ancho_g = (ancho - izq - 20) / len(grupos)
    barra = ancho_g / 5.2
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" '
         f'font-family="Helvetica, Arial, sans-serif" font-size="12">',
         f'<rect width="{ancho}" height="{alto}" fill="#fff"/>']
    for v in range(0, tope + 1, 2):
        y = alto - abajo - v * escala
        p.append(f'<line x1="{izq}" x2="{ancho - 20}" y1="{y:.1f}" y2="{y:.1f}" stroke="#e3e6ea"/>')
        p.append(f'<text x="{izq - 8}" y="{y + 4:.1f}" text-anchor="end" fill="#444">{v}</text>')
    p.append(f'<text x="16" y="{(alto - abajo + arriba) / 2:.0f}" transform="rotate(-90 16 '
             f'{(alto - abajo + arriba) / 2:.0f})" text-anchor="middle" fill="#222">'
             f'Tiempo de viaje de la flota (h)</text>')
    for g, (ciudad, d, f) in enumerate(grupos):
        x0 = izq + g * ancho_g + (ancho_g - 4 * barra) / 2
        for b, pol in enumerate(ETIQUETAS):
            v = f[pol]["tiempo_viaje_h"]
            h = v * escala
            x = x0 + b * barra
            p.append(f'<rect x="{x:.1f}" y="{alto - abajo - h:.1f}" width="{barra - 2:.1f}" '
                     f'height="{h:.1f}" fill="{COLORES[pol]}"/>')
            p.append(f'<text x="{x + barra / 2 - 1:.1f}" y="{alto - abajo - h - 4:.1f}" '
                     f'text-anchor="middle" font-size="10" fill="#222">{coma(v)}</text>')
        xc = izq + g * ancho_g + ancho_g / 2
        p.append(f'<text x="{xc:.1f}" y="{alto - abajo + 16}" text-anchor="middle" fill="#222">'
                 f'δ = {coma(d, 2)}</text>')
    for c, ciudad in enumerate(dict.fromkeys(f["ciudad"] for f in filas)):
        n = sum(1 for f in filas if f["ciudad"] == ciudad)
        xc = izq + (c * n + n / 2) * ancho_g
        p.append(f'<text x="{xc:.1f}" y="{alto - abajo + 34}" text-anchor="middle" '
                 f'font-weight="bold" fill="#222">{ciudad}</text>')
    x = izq
    for pol, etiqueta in ETIQUETAS.items():
        p.append(f'<rect x="{x}" y="{alto - 22}" width="12" height="12" fill="{COLORES[pol]}"/>')
        p.append(f'<text x="{x + 17}" y="{alto - 12}" fill="#222">{etiqueta}</text>')
        x += 30 + 7 * len(etiqueta)
    p.append("</svg>")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(p))


def main():
    carpeta = sys.argv[1] if len(sys.argv) > 1 else "experimentos/resultados/dvrp"
    with open(os.path.join(carpeta, "escenarios.json"), encoding="utf-8") as f:
        esc = json.load(f)
    filas = resumir(esc["resultados"])
    salida = {"parametros": esc["parametros"], "escenarios": filas}
    ruta_cvrp = os.path.join(carpeta, "cvrplib.json")
    if os.path.exists(ruta_cvrp):
        with open(ruta_cvrp, encoding="utf-8") as f:
            cv = json.load(f)["instancias"]
        salida["cvrplib"] = {
            "brecha_mejor_media_pct": statistics.mean(i["brecha_mejor_pct"] for i in cv),
            "brecha_media_media_pct": statistics.mean(i["brecha_media_pct"] for i in cv),
            "brecha_insercion_media_pct": statistics.mean(i["brecha_insercion_pct"] for i in cv),
            "optimos_alcanzados": sum(1 for i in cv if i["tabu_mejor"] <= i["optimo"]),
            "instancias": len(cv)}
    os.makedirs(os.path.join(carpeta, "figuras"), exist_ok=True)
    figura(filas, os.path.join(carpeta, "figuras", "dvrp_tiempo_viaje.svg"))
    with open(os.path.join(carpeta, "resumen.json"), "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    for fila in filas:
        print(f"{fila['ciudad']:16} δ={fila['dinamismo']:.2f}  " + "  ".join(
            f"{p[:5]} {fila[p]['tiempo_viaje_h']:5.2f} h ({fila[p]['no_atendidos']} n/a)" for p in ETIQUETAS)
            + f"  tabú vs ins. −{fila['mejora_tabu_vs_insercion_pct']['media']:.1f} %"
            f"  tabú vs compl. +{fila['brecha_tabu_vs_completa_pct']['media']:.1f} %"
            + (f"  espera vs compl. +{fila['brecha_espera_vs_completa_pct']['media']:.1f} %"
               if "brecha_espera_vs_completa_pct" in fila else ""))
    if "cvrplib" in salida:
        print(salida["cvrplib"])


if __name__ == "__main__":
    main()
