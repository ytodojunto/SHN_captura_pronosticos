# Captura automática del pronóstico SHN

Guarda cada 12hs, sin que dependas de tu PC, el pronóstico mareológico
del Río de la Plata (`hidro.gov.ar/oceanografia/pronostico.asp`). Corre
en los servidores de GitHub, no en tu computadora.

## Cómo ponerlo en marcha (desde el celular, sin PC)

1. Entrá a github.com desde el navegador del teléfono, con la misma
   cuenta donde tenés `CALADO-DE-DESPACHO-V2`.
2. Creá un repo nuevo, por ejemplo `shn-captura`.
3. Subí estos 3 archivos manteniendo la carpeta:
   - `capturar_pronostico.py`
   - `.github/workflows/capturar.yml`
   - este `README.md`
   (Se puede hacer con el botón "Add file → Upload files" del propio
   GitHub, sin instalar nada.)
4. Andá a la pestaña **Actions** del repo y confirmá que el workflow
   "Capturar pronóstico SHN" esté habilitado.
5. Listo. A partir de ahí corre solo dos veces por día y va guardando
   los archivos en `data/`.

Podés forzar una corrida manual en cualquier momento desde
**Actions → Capturar pronóstico SHN → Run workflow**, útil para probar
que funciona sin esperar al próximo horario.

## Qué vas a tener acumulado en unas semanas

- Un archivo `data/pronostico_<fecha>.json` por cada captura.
- Un archivo `data/historico.jsonl` con todas las capturas juntas,
  una por línea — el más cómodo para analizar después con pandas.

## Próximo paso (cuando tengas la PC)

Con unas semanas de `historico.jsonl` acumulado ya se puede cruzar
cada pronóstico contra lo que realmente pasó (usando los datos
horarios observados que también publica el SHN en Datos Abiertos) y
medir cuántos cm de error tuvo cada corrección, por puerto y por
intensidad de sudestada.
