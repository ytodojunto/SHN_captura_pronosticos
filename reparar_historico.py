"""
Reparación única (no corre en cron) del bug de parseo encontrado
2026-09-10 en capturar_pronostico.py: las filas de "continuación"
(mismo puerto, sin repetir el nombre) con 4 celdas se confundían con
filas completas, corriendo todos los campos una posición. Resultado:
en el histórico ya guardado, el 59% de las filas de puertos quedaron
con "lugar" = "BAJAMAR" o "PLEAMAR" en vez del nombre real del puerto,
y el resto de los campos también corridos.

Como el corrimiento es siempre el mismo (determinístico), se puede
reconstruir el valor correcto sin volver a bajar nada:

  guardado (corrupto)          real
  ----------------------------  ----------------------------
  lugar    = "PLEAMAR"          estado = "PLEAMAR"
  estado   = "17:00"            hora   = "17:00"
  hora     = "0.80"             altura_m = "0.80"
  altura_m = "10/09/2026"       fecha  = "10/09/2026"
  fecha    = null               (el "lugar" real es el del puerto
                                  anterior en la misma tabla)

Este script lee data/historico.jsonl, reconstruye cada fila corrupta
usando el "lugar" del último puerto válido visto en esa misma tabla
(mismo snapshot, orden de aparición), y reescribe el archivo entero
con los datos corregidos. Las filas que ya estaban bien no se tocan.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
HISTORICO = DATA_DIR / "historico.jsonl"

ESTADOS = {"BAJAMAR", "PLEAMAR"}


def reparar_snapshot(dato: dict) -> tuple[dict, int]:
    puertos_reparados = []
    lugar_actual = None
    n_reparadas = 0

    for p in dato.get("puertos", []):
        lugar = p.get("lugar")
        if (lugar or "").upper() in ESTADOS:
            # fila corrupta: reconstruyo corriendo los campos
            n_reparadas += 1
            nuevo = {
                "lugar": lugar_actual,  # el del ultimo puerto valido visto
                "estado": p.get("lugar"),
                "hora": p.get("estado"),
                "altura_m": p.get("hora"),
                "fecha": p.get("altura_m"),
            }
        else:
            # fila que ya estaba bien
            lugar_actual = lugar
            nuevo = p

        puertos_reparados.append(nuevo)

    dato = dict(dato)
    dato["puertos"] = puertos_reparados
    return dato, n_reparadas


def main():
    if not HISTORICO.exists():
        print(f"No existe {HISTORICO}, nada para reparar.")
        return

    lineas = HISTORICO.read_text(encoding="utf-8").splitlines()
    salida = []
    total_reparadas = 0
    snapshots_afectados = 0

    for linea in lineas:
        if not linea.strip():
            continue
        dato = json.loads(linea)
        dato_reparado, n = reparar_snapshot(dato)
        if n > 0:
            snapshots_afectados += 1
            total_reparadas += n
        salida.append(json.dumps(dato_reparado, ensure_ascii=False))

    HISTORICO.write_text("\n".join(salida) + "\n", encoding="utf-8")
    print(
        f"Listo. {len(salida)} snapshots revisados, {snapshots_afectados} tenian "
        f"filas corruptas, {total_reparadas} filas de puerto reparadas en total."
    )


if __name__ == "__main__":
    main()
