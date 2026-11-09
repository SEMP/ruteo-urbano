"""Demo de OSRM: ruta entre dos puntos y matriz de tiempos entre varios.

Requiere el servidor levantado (`docker compose up -d osrm`). Solo usa la biblioteca
estándar de Python, para que corra sin instalar nada.

    python3 demo/consulta.py
    python3 demo/consulta.py --servidor http://localhost:5080

Sin --servidor, usa el puerto de OSRM_PUERTO (variable de entorno o .env), o 5000.

Los puntos son de prueba, en Ciudad del Este: no son puntos de entrega ni depósitos reales.
OSRM ubica cada punto en la calle más cercana.
"""

import argparse
import json
import os
import urllib.request

# Los mismos puntos que el visor (demo/puntos.json): (nombre, latitud, longitud).
# OSRM recibe longitud,latitud: ojo con el orden.
with open(os.path.join(os.path.dirname(__file__), "puntos.json"), encoding="utf-8") as archivo:
    PUNTOS = [(p["nombre"], p["lat"], p["lon"]) for p in json.load(archivo)["puntos"]]


def puerto_osrm():
    """El mismo puerto que usa docker compose: OSRM_PUERTO del entorno o de .env."""
    if "OSRM_PUERTO" in os.environ:
        return os.environ["OSRM_PUERTO"]
    env = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env):
        for linea in open(env, encoding="utf-8"):
            clave, _, valor = linea.strip().partition("=")
            if clave == "OSRM_PUERTO" and valor:
                return valor
    return "5000"


def pedir(servidor, servicio, puntos, parametros):
    coordenadas = ";".join(f"{lon},{lat}" for _, lat, lon in puntos)
    url = f"{servidor}/{servicio}/v1/driving/{coordenadas}?{parametros}"
    with urllib.request.urlopen(url, timeout=30) as respuesta:
        datos = json.load(respuesta)
    if datos.get("code") != "Ok":
        raise RuntimeError(f"OSRM respondió {datos.get('code')}: {datos.get('message')}")
    return datos


def main():
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--servidor", default=f"http://localhost:{puerto_osrm()}")
    servidor = argumentos.parse_args().servidor

    # 1. Ruta entre dos puntos (lo que haría Google Maps).
    origen, destino = PUNTOS[0], PUNTOS[1]
    ruta = pedir(servidor, "route", [origen, destino], "overview=false")["routes"][0]
    print(f"Ruta {origen[0]} → {destino[0]}: "
          f"{ruta['distance'] / 1000:.1f} km, {ruta['duration'] / 60:.1f} min")

    # 2. Matriz de tiempos y distancias entre todos los puntos: la entrada del ruteo.
    tabla = pedir(servidor, "table", PUNTOS, "annotations=duration,distance")
    nombres = [nombre for nombre, _, _ in PUNTOS]
    ancho = max(len(n) for n in nombres)

    print("\nTiempo de viaje en minutos (fila = origen, columna = destino):")
    print(" " * ancho + "".join(f"{n[:12]:>14}" for n in nombres))
    for nombre, fila in zip(nombres, tabla["durations"]):
        print(f"{nombre:<{ancho}}" + "".join(f"{s / 60:>14.1f}" for s in fila))

    print("\nDistancia en km:")
    print(" " * ancho + "".join(f"{n[:12]:>14}" for n in nombres))
    for nombre, fila in zip(nombres, tabla["distances"]):
        print(f"{nombre:<{ancho}}" + "".join(f"{m / 1000:>14.1f}" for m in fila))

    # La matriz no es simétrica: las calles de un solo sentido cambian ida y vuelta.


if __name__ == "__main__":
    main()
