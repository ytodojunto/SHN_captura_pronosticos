"""
Captura las Alturas Horarias observadas por los mareógrafos del SHN
(hidro.gov.ar) y las guarda como snapshot fechado en data/alturas/.
Complementa a capturar_pronostico.py: ese guarda lo que el SHN
PRONOSTICA, este guarda lo que REALMENTE se midió. Con ambos
acumulados se puede cruzar pronóstico vs. observado y medir el
acierto real de cada corrección meteorológica.

La página solo expone una ventana móvil de 10 días (después se
pierde), así que conviene correr esto seguido para no perder datos.

Guarda dos cosas por corrida:
  - el archivo crudo tal cual lo devolvió el sitio (por si el
    parseo de abajo está mal armado — así no se pierde nada y se
    puede reprocesar más adelante)
  - una versión ya parseada y aplanada (una fila por mareógrafo +
    fecha/hora + altura) agregada a data/historico_alturas.jsonl
"""
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL_CSV = "https://www.hidro.gov.ar/oceanografia/AlturasHorarias.asp?export=csv"
URL_HTML = "https://www.hidro.gov.ar/oceanografia/alturashorarias.asp"
DATA_DIR = Path(__file__).parent / "data"
RAW_DIR = DATA_DIR / "alturas_raw"


def parsear_como_csv(texto: str) -> list[dict]:
    """Formato real confirmado 2026-09-10: separado por ';' (no ','),
    y AL REVES de lo que se habia asumido en la primera version — cada
    FILA es un timestamp ("Fecha y hora") y las columnas siguientes
    son los mareografos (Martín García, San Fernando, Buenos Aires,
    Pilote Norden, La Plata, Atalaya, Oyarvide, San Clemente, Mar del
    Plata, Puerto Belgrano, Ushuaia). Celdas sin dato vienen como
    "S/D" (sin datos), no vacias."""
    lector = csv.reader(io.StringIO(texto), delimiter=";")
    filas = [f for f in lector if any(c.strip() for c in f)]
    if len(filas) < 2:
        return []
    encabezado = filas[0]
    estaciones = [e.strip() for e in encabezado[1:]]
    registros = []
    for fila in filas[1:]:
        if not fila or not fila[0].strip():
            continue
        fecha_hora = fila[0].strip()
        for estacion, valor in zip(estaciones, fila[1:]):
            valor = (valor or "").strip()
            if not valor or valor.upper() == "S/D":
                continue
            registros.append({"estacion": estacion, "fecha_hora": fecha_hora, "altura_m": valor})
    return registros


def parsear_como_html(html: str) -> list[dict]:
    """Fallback si export=csv en realidad devuelve HTML (algunas
    páginas ASP lo hacen). Misma orientación que el CSV: cada fila de
    la tabla es un timestamp, las columnas son los mareografos."""
    soup = BeautifulSoup(html, "html.parser")
    registros = []
    for table in soup.find_all("table"):
        filas = table.find_all("tr")
        if not filas:
            continue
        encabezado = [c.get_text(strip=True) for c in filas[0].find_all(["td", "th"])]
        if len(encabezado) < 2:
            continue
        estaciones = encabezado[1:]
        for fila in filas[1:]:
            celdas = [c.get_text(strip=True) for c in fila.find_all(["td", "th"])]
            if not celdas or not celdas[0]:
                continue
            fecha_hora = celdas[0]
            for estacion, valor in zip(estaciones, celdas[1:]):
                if not valor or valor.upper() == "S/D":
                    continue
                registros.append({"estacion": estacion, "fecha_hora": fecha_hora, "altura_m": valor})
    return registros


def main():
    DATA_DIR.mkdir(exist_ok=True)
    RAW_DIR.mkdir(exist_ok=True)

    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(URL_CSV, timeout=30, headers=headers)
    resp.raise_for_status()
    contenido = resp.text

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    es_html = contenido.strip().lower().startswith(("<!doctype", "<html"))
    ext = "html" if es_html else "csv"
    (RAW_DIR / f"alturas_{ts}.{ext}").write_text(contenido, encoding="utf-8", errors="replace")

    registros = parsear_como_html(contenido) if es_html else parsear_como_csv(contenido)

    # Si el export=csv no vino bien pero tampoco parseó nada, probamos
    # la página HTML normal como último recurso.
    if not registros:
        resp2 = requests.get(URL_HTML, timeout=30, headers=headers)
        resp2.raise_for_status()
        (RAW_DIR / f"alturas_{ts}_fallback.html").write_text(
            resp2.text, encoding="utf-8", errors="replace"
        )
        registros = parsear_como_html(resp2.text)

    snapshot = {
        "capturado_en": datetime.now(timezone.utc).isoformat(),
        "fuente": "html" if es_html else "csv",
        "cantidad_registros": len(registros),
        "mediciones": registros,
    }

    salida = DATA_DIR / f"alturas_{ts}.json"
    salida.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Guardado: {salida} ({len(registros)} mediciones)")

    historico_path = DATA_DIR / "historico_alturas.jsonl"
    with historico_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
