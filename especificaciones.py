# -*- coding: utf-8 -*-
"""
especificaciones.py — Extrae la ficha de Especificaciones de un aviso de Chileautos
===================================================================================

Qué hace:
  Recibe la URL de un aviso (ej:
  https://www.chileautos.cl/vehiculos/detalles/2022-peugeot-3008.../CP-AD-8511086)
  baja la página del aviso y saca los datos LIMPIOS de la pestaña
  "Especificaciones": versión oficial, cilindrada exacta, power, torque,
  carrocería, tracción, transmisión, etc.

El dato más valioso es 'version_oficial': la versión canónica de Chileautos
(ej: "1.5 NB LTZ R 4X2 SDN CVT AT 4P"). Con eso se agrupan los avisos sin pelear
con el texto sucio que escribe cada vendedor.

IMPORTANTE — esto NO está verificado contra el sitio en vivo todavía:
  Este módulo asume que las especificaciones vienen DENTRO del HTML de la página
  del aviso (caso B del análisis). Intenta dos estrategias:
    1) Buscar un bloque JSON embebido en el HTML con los specs.
    2) Parsear los pares etiqueta/valor del HTML renderizado.
  Si al correr probar_especificaciones.py sobre UN aviso real NO devuelve nada,
  significa que los specs vienen de una API aparte (caso A) y hay que cazar ese
  endpoint con F12 > Network. Ver notas al final del archivo.

Requiere: curl_cffi, beautifulsoup4
"""

import re
import json
import unicodedata
from bs4 import BeautifulSoup

# Reusar exactamente los mismos headers que telefono.py (ya pasan Datadome)
headers_base = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "es,es-ES;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "cache-control": "no-cache",
    "user-agent": "Mozilla/5.0 (Linux; Android 13; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36 Edg/132.0.0.0",
    "referer": "https://www.chileautos.cl/vehiculos/autos-veh%C3%ADculo/",
    "sec-ch-ua": "\"Not A(Brand\";v=\"8\", \"Chromium\";v=\"132\", \"Microsoft Edge\";v=\"132\"",
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": "\"Android\"",
}

# ---------------------------------------------------------------------------
# MAPA DE ETIQUETAS
# ---------------------------------------------------------------------------
# Etiqueta tal como aparece en la página -> nombre de columna limpio.
# Solo mapeo las que sirven para agrupar/diferenciar versiones y precio.
# El resto de los specs igual se guardan en el dict crudo, por si se quieren.
ETIQUETAS_CLAVE = {
    "version": "version_oficial",
    "cilindrada exacta (cc)": "cilindrada_cc",
    "cilindrada": "cilindrada",
    "power": "power_hp",
    "torque": "torque_nm",
    "carroceria": "carroceria",
    "categoria": "categoria",
    "traccion": "traccion_spec",
    "transmision": "transmision_spec",
    "tipo de caja de cambios": "tipo_caja",
    "combustible": "combustible_spec",
    "puertas": "puertas",
    "asientos": "asientos",
    "cilindros": "cilindros",
    "autonomia (km)": "autonomia_km",
    "peso (kg)": "peso_kg",
    "largo (mm)": "largo_mm",
    "ancho (mm)": "ancho_mm",
    "alto (mm)": "alto_mm",
    "distancia entre ejes (mm)": "distancia_ejes_mm",
}


def _norm(s):
    """minúsculas, sin tildes, sin espacios sobrantes — para comparar etiquetas."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s).strip().lower()


# ---------------------------------------------------------------------------
# PARSEO DEL HTML
# ---------------------------------------------------------------------------
def _pares_desde_html(html):
    """
    Extrae TODOS los pares etiqueta->valor de la ficha de especificaciones.
    Prueba, en orden, las estructuras HTML más comunes:
      1) <dl> con <dt>/<dd>
      2) tablas con dos celdas por fila (<th>/<td> o <td>/<td>)
      3) divs/li hermanos donde un elemento es etiqueta y el siguiente, valor

    Devuelve dict { etiqueta_normalizada: valor }.
    """
    soup = BeautifulSoup(html, "html.parser")
    pares = {}

    # --- Estrategia 1: listas de definición <dl><dt><dd> ---
    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            k = _norm(dt.get_text())
            v = dd.get_text(strip=True)
            if k and v:
                pares.setdefault(k, v)

    # --- Estrategia 2: filas de tabla con 2 celdas ---
    for tr in soup.find_all("tr"):
        celdas = tr.find_all(["th", "td"])
        if len(celdas) == 2:
            k = _norm(celdas[0].get_text())
            v = celdas[1].get_text(strip=True)
            if k and v:
                pares.setdefault(k, v)

    # --- Estrategia 3: pares de hermanos (label/value en divs o spans) ---
    # Busca cualquier elemento cuyo texto sea EXACTAMENTE una etiqueta conocida,
    # y toma como valor el texto del siguiente hermano con contenido.
    if not pares:
        etiquetas_conocidas = set(ETIQUETAS_CLAVE.keys())
        for el in soup.find_all(text=True):
            txt = _norm(el)
            if txt in etiquetas_conocidas:
                # subir al elemento contenedor y mirar el siguiente con texto
                cont = el.parent
                sig = cont.find_next(text=lambda t: t and t.strip() and _norm(t) != txt)
                if sig:
                    pares.setdefault(txt, sig.strip())

    return pares


def _pares_desde_json_embebido(html):
    """
    Busca un bloque JSON embebido en el HTML que contenga los specs.
    Muchos sitios (incluida la red Carsales, a la que pertenece Chileautos)
    incrustan el estado de la página como JSON dentro de <script>.
    Si encuentra uno con cilindrada/power/torque, devuelve los pares; si no, {}.

    Nota: esta función es heurística. Hasta no ver el HTML real de Chileautos
    no se sabe si el JSON existe ni con qué nombres de campo viene. Por eso
    el parser de HTML (arriba) es la vía principal y esta es un complemento.
    """
    pares = {}
    # Candidatos típicos de blobs de estado
    patrones = [
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
        r'window\.__DATA__\s*=\s*(\{.*?\});',
    ]
    for pat in patrones:
        for m in re.finditer(pat, html, re.DOTALL):
            try:
                data = json.loads(m.group(1))
            except Exception:
                continue
            # recorrer el JSON buscando claves que parezcan specs
            encontrados = {}

            def walk(o):
                if isinstance(o, dict):
                    for k, v in o.items():
                        kn = _norm(k)
                        if kn in ETIQUETAS_CLAVE and isinstance(v, (str, int, float)):
                            encontrados.setdefault(kn, str(v))
                        walk(v)
                elif isinstance(o, list):
                    for it in o:
                        walk(it)

            walk(data)
            if encontrados:
                pares.update(encontrados)
    return pares


def parsear_especificaciones(html):
    """
    Dado el HTML de la página de un aviso, devuelve dos cosas:
      - specs_limpios: dict con las columnas clave normalizadas
      - specs_crudos:  dict con TODOS los pares etiqueta->valor que se hallaron
                       (útil para depurar y para sumar campos después)
    """
    pares = _pares_desde_html(html)
    # Complementar con JSON embebido si el HTML no trajo lo principal
    if "version" not in pares or "cilindrada exacta (cc)" not in pares:
        pares_json = _pares_desde_json_embebido(html)
        for k, v in pares_json.items():
            pares.setdefault(k, v)

    specs_limpios = {}
    for etiqueta, valor in pares.items():
        if etiqueta in ETIQUETAS_CLAVE:
            specs_limpios[ETIQUETAS_CLAVE[etiqueta]] = valor

    return specs_limpios, pares


# ---------------------------------------------------------------------------
# DESCARGA + PARSEO (la función que usaría main.py)
# ---------------------------------------------------------------------------
async def extract_specs(url, session, max_retries=4):
    """
    Baja la página del aviso y devuelve los specs limpios (dict) o None.
    Pensada para usarse igual que extract_phone_fast de telefono.py:
    misma sesión, mismos reintentos, mismo manejo de 403/429.
    """
    import asyncio, random

    intentos = 0
    while intentos < max_retries:
        try:
            response = await session.get(
                url, headers=headers_base,
                impersonate="chrome99_android", timeout=8
            )
            if response.status_code == 200:
                specs_limpios, _ = parsear_especificaciones(response.text)
                return specs_limpios or None
            elif response.status_code in (403, 429):
                espera = 30 * (intentos + 1)
                print(f"[specs] Bloqueo {response.status_code} en {url}. Esperando {espera}s...")
                await asyncio.sleep(espera)
            else:
                print(f"[specs] Error {response.status_code} en {url}.")
                return None
        except Exception as e:
            print(f"[specs] Excepción en {url}: {e}. Esperando 5s...")
            await asyncio.sleep(5)
        intentos += 1
    return None


# ===========================================================================
# SI ESTE MÓDULO NO DEVUELVE NADA SOBRE UN AVISO REAL:
# ---------------------------------------------------------------------------
# Quiere decir que los specs NO están en el HTML, sino que la página los pide
# a una API aparte después de cargar (caso A). Para cazarla:
#   1) Abrir un aviso en el navegador.
#   2) F12 > pestaña Network > filtrar por "Fetch/XHR".
#   3) Apretar la pestaña "Especificaciones" del aviso.
#   4) Ver qué llamada nueva aparece (alguna URL tipo /_api/... o /mobiapi/...).
#   5) Esa URL es la que hay que pedir acá, igual que telefono.py pide
#      /_api/enquiry-core/[ID]/. El parseo del JSON sería casi igual.
# ===========================================================================
