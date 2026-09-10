"""
Captura el Pronóstico Mareológico del SHN (hidro.gov.ar) y lo guarda
como un snapshot fechado en data/. Pensado para correr cada 12hs vía
GitHub Actions, sin depender de una PC local.

Cada snapshot guarda:
  - cuándo se capturó (capturado_en)
  - para qué ventana vale el pronóstico (valido_desde / valido_hasta)
  - el texto de corrección (ej "1.20 m sobre tabla, luego bajando a 0.60")
  - la tabla de pleamares/bajamares corregidas por puerto

Con muchos snapshots acumulados en el tiempo, más adelante se cruza
cada uno con lo que realmente se observó (alturashorarias.asp) para
medir el acierto del pronóstico.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://www.hidro.gov.ar/oceanografia/pronostico.asp"
DATA_DIR = Path(__file__).parent / "data"


def parsear_pronostico(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    texto = soup.get_text("\n", strip=True)

    fecha_match = re.search(r"FECHA:\s*(.+)", texto)
    validez_match = re.search(
        r"VALIDO DESDE LAS\s*([\d:]+)\s*Hs DE\s*([\d/]+)\s*HASTA LAS\s*([\d:]+)\s*Hs DE\s*([\d/]+)",
        texto,
    )

    secciones = {}
    for bloque, clave in [
        ("RIO DE LA PLATA INTERIOR", "interior"),
        ("RIO DE LA PLATA EXTERIOR", "exterior"),
    ]:
        patron = rf"{bloque}:.*?\n(.+?)\n\*Valores corregidos\*"
        m = re.search(patron, texto, re.DOTALL)
        secciones[clave] = m.group(1).strip() if m else None

    # Tablas: cada <table> del pronóstico tiene filas LUGAR/ESTADO/HORA/ALTURA/FECHA.
    # OJO (bug encontrado 2026-09-10): NO se puede confiar en la cantidad de
    # celdas para saber si una fila repite el LUGAR o no — el SHN a veces
    # manda la fila de continuación con 3 celdas (ESTADO,HORA,ALTURA) y a
    # veces con 4 (ESTADO,HORA,ALTURA,FECHA), y con la cuenta de celdas sola
    # esa segunda variante se confundía con una fila completa, corriendo
    # todos los campos una posición (quedaba "estado"="17:00", etc). En vez
    # de contar celdas, se detecta la continuación por contenido: si la
    # primera celda es literalmente BAJAMAR o PLEAMAR, es continuación (no
    # trae LUGAR); si no, la primera celda es el LUGAR.
    ESTADOS = {"BAJAMAR", "PLEAMAR"}
    puertos = []
    lugar_actual = None
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            celdas = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            celdas = [c for c in celdas if c]
            if not celdas or celdas[0].upper() in ("LUGAR", "ESTADO"):
                continue

            if celdas[0].upper() in ESTADOS:
                # fila de continuación: no repite el LUGAR
                if lugar_actual is None:
                    continue  # fila de continuación sin lugar previo, no debería pasar
                resto = celdas
            else:
                # fila completa: la primera celda es el LUGAR
                lugar_actual = celdas[0]
                resto = celdas[1:]

            if len(resto) < 2:
                continue  # no alcanza ni para estado+hora, descarto
            estado = resto[0]
            hora = resto[1]
            altura = resto[2] if len(resto) > 2 else None
            fecha = resto[3] if len(resto) > 3 else None

            puertos.append(
                {
                    "lugar": lugar_actual,
                    "estado": estado,
                    "hora": hora,
                    "altura_m": altura,
                    "fecha": fecha,
                }
            )

    return {
        "capturado_en": datetime.now(timezone.utc).isoformat(),
        "fecha_pronostico": fecha_match.group(1).strip() if fecha_match else None,
        "valido_desde": f"{validez_match.group(2)} {validez_match.group(1)}" if validez_match else None,
        "valido_hasta": f"{validez_match.group(4)} {validez_match.group(3)}" if validez_match else None,
        "correccion_interior": secciones.get("interior"),
        "correccion_exterior": secciones.get("exterior"),
        "puertos": puertos,
    }


def main():
    DATA_DIR.mkdir(exist_ok=True)
    resp = requests.get(URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    dato = parsear_pronostico(resp.text)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    salida = DATA_DIR / f"pronostico_{ts}.json"
    salida.write_text(json.dumps(dato, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Guardado: {salida}")

    # Mantener también un acumulado (todas las capturas en un solo archivo,
    # útil para leer histórico fácil sin recorrer archivos sueltos)
    historico_path = DATA_DIR / "historico.jsonl"
    with historico_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dato, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
