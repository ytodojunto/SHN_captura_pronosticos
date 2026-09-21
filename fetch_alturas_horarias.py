#!/usr/bin/env python3
"""
Scraper de Alturas Horarias de Mareógrafos - Servicio de Hidrografía Naval (SHN)
Fuente: https://www.hidro.gov.ar/oceanografia/alturashorarias.asp

Extrae la columna más reciente (última hora publicada) de cada mareógrafo
y la agrega como una línea nueva a data/alturas_historico.jsonl.

Pensado para correr junto al scraper de pronósticos (fetch_pronosticos.py)
en el mismo repo SHN_captura_pronosticos, vía GitHub Actions (cron horario).
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://www.hidro.gov.ar/oceanografia/alturashorarias.asp"
OUT_PATH = Path("data/alturas_historico.jsonl")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MULTIPAR-scraper/1.0; +https://github.com/ytodojunto)"
}

# Regex para timestamps tipo "19/09/2026 11:45" dentro del texto del header
TS_RE = re.compile(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})")


def parse_ts(dd_mm_yyyy: str, hh_mm: str) -> str:
    """Convierte 'dd/mm/yyyy' + 'hh:mm' a ISO 8601 (hora local Arg, UTC-3)."""
    dt = datetime.strptime(f"{dd_mm_yyyy} {hh_mm}", "%d/%m/%Y %H:%M")
    return dt.strftime("%Y-%m-%dT%H:%M:%S-03:00")


def fetch_tabla():
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Buscar la tabla que contiene "Mareógrafo" en su encabezado
    tabla = None
    for t in soup.find_all("table"):
        if "Mareógrafo" in t.get_text():
            tabla = t
            break
    if tabla is None:
        raise RuntimeError("No se encontró la tabla de alturas horarias en la página.")

    filas = tabla.find_all("tr")
    if not filas:
        raise RuntimeError("Tabla de alturas horarias vacía.")

    # Header: primera fila con las columnas de fecha/hora
    header_cells = filas[0].find_all(["th", "td"])
    timestamps = []
    for cell in header_cells:
        m = TS_RE.search(cell.get_text(separator=" ", strip=True))
        if m:
            timestamps.append(parse_ts(m.group(1), m.group(2)))

    if not timestamps:
        raise RuntimeError("No se pudieron extraer los timestamps del encabezado de la tabla.")

    ultima_hora = timestamps[0]  # la columna más reciente es la primera

    alturas = {}
    for fila in filas[1:]:
        celdas = fila.find_all(["th", "td"])
        if len(celdas) < 3:
            continue
        # La celda del nombre suele tener un link con el nombre del mareógrafo
        nombre_raw = celdas[1].get_text(separator=" ", strip=True)
        nombre = re.sub(r"\(\*+\)", "", nombre_raw).strip()
        if not nombre or nombre.lower().startswith("mare"):
            continue

        valor_raw = celdas[2].get_text(strip=True).replace(",", ".")
        try:
            valor = float(valor_raw)
        except ValueError:
            continue  # S/D, F/S, etc.

        alturas[nombre] = valor

    return ultima_hora, alturas


def main():
    try:
        timestamp, alturas = fetch_tabla()
    except Exception as e:
        print(f"ERROR al scrapear alturas horarias: {e}", file=sys.stderr)
        sys.exit(1)

    if not alturas:
        print("ERROR: no se extrajo ninguna altura.", file=sys.stderr)
        sys.exit(1)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Evitar duplicar si ya guardamos este mismo timestamp (la página se
    # actualiza cada 1 hora aprox., pero el cron puede correr más seguido)
    if OUT_PATH.exists():
        with OUT_PATH.open("r", encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    if json.loads(linea).get("timestamp") == timestamp:
                        print(f"Sin novedades: {timestamp} ya estaba guardado.")
                        return
                except json.JSONDecodeError:
                    continue

    registro = {
        "capturado_en": datetime.now(timezone.utc).isoformat(),
        "timestamp": timestamp,
        "alturas": alturas,
    }

    with OUT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    print(f"OK: guardado snapshot de {timestamp} con {len(alturas)} mareógrafos.")


if __name__ == "__main__":
    main()
