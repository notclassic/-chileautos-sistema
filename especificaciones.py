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

# ---------------------------------------------------------------------------
# COOKIE DATADOME
# ---------------------------------------------------------------------------
# Valor sacado del navegador (F12 > Application > Cookies > datadome).
# DESACTIVADO: mandar solo la cookie datadome (sin el resto de la huella)
# empeoró los bloqueos (403 desde el aviso 1, contra ~180 sin cookie).
# Vacío = pedido sin cookie, que era el comportamiento que avanzaba por tandas.
DATADOME_COOKIE = ""

# Sin cookie, se usa el user-agent Android que acompañaba las tandas que
# sí avanzaban (~180 avisos antes del bloqueo).
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
# Lista ordenada de columnas de specs limpios (para guardar en CSV).
# La usan bajar_especificaciones.py y actualizar_incremental.py.
COLUMNAS_SPECS = [
    "version_oficial", "cilindrada_cc", "cilindrada", "power_hp", "torque_nm",
    "carroceria", "categoria", "traccion_spec", "transmision_spec",
    "tipo_caja", "combustible_spec", "puertas", "asientos",
    "cilindros", "autonomia_km", "peso_kg",
]

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

    Devuelve (pares_norm, pares_orig):
      - pares_norm: { etiqueta_normalizada: valor }  (para validar/mapear)
      - pares_orig: { etiqueta_ORIGINAL: valor }      (para guardar tal cual)
    """
    soup = BeautifulSoup(html, "html.parser")
    pares = {}       # normalizados
    pares_orig = {}  # etiqueta original tal como aparece en la página

    def _add(label_raw, valor):
        k = _norm(label_raw)
        etiqueta = re.sub(r"\s+", " ", str(label_raw)).strip()
        if k and valor:
            pares.setdefault(k, valor)
            pares_orig.setdefault(etiqueta, valor)

    # --- Estrategia 1: listas de definición <dl><dt><dd> ---
    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            _add(dt.get_text(), dd.get_text(strip=True))

    # --- Estrategia 2: filas de tabla con 2 celdas ---
    for tr in soup.find_all("tr"):
        celdas = tr.find_all(["th", "td"])
        if len(celdas) == 2:
            _add(celdas[0].get_text(), celdas[1].get_text(strip=True))

    # --- Estrategia 3: pares de hermanos (label/value en divs o spans) ---
    if not pares:
        etiquetas_conocidas = set(ETIQUETAS_CLAVE.keys())
        for el in soup.find_all(text=True):
            txt = _norm(el)
            if txt in etiquetas_conocidas:
                cont = el.parent
                sig = cont.find_next(text=lambda t: t and t.strip() and _norm(t) != txt)
                if sig:
                    _add(el.strip(), sig.strip())

    return pares, pares_orig


# NOTA: acá había una función de respaldo que buscaba specs en bloques JSON
# incrustados en la página. Se ELIMINÓ porque las páginas de Chileautos traen
# JSON de tracking con un campo "version" (el texto sucio del título), y el
# respaldo lo confundía con la versión oficial, fabricando datos falsos
# ("TX", "I"). Mejor devolver vacío que inventar.


def parsear_especificaciones(html):
    """
    Dado el HTML de la página de un aviso, devuelve dos cosas:
      - specs_limpios: dict con los campos clave normalizados (version_oficial,
                       cilindrada_cc, power_hp, ...) para agrupar/precio, o {}
                       si la ficha REAL no está en la página.
      - specs_todos:   dict con TODOS los pares etiqueta_ORIGINAL -> valor de la
                       ficha (los ~70 campos), o {} si no hay ficha real.

    VALIDACIÓN ESTRICTA: solo se acepta la ficha si aparecen al menos 3 campos
    "duros" que solo existen en la ficha real. Si no, se devuelve ({}, {}):
    no se guarda nada, para no colar basura de páginas sin ficha.
    """
    pares, pares_orig = _pares_desde_html(html)

    # Chileautos tiene (al menos) DOS formatos de ficha:
    #  - RICA: ~70 campos tecnicos (Cilindrada exacta, Power, Torque, medidas).
    #  - POBRE: equipamiento SI/NO + Version (ej. avisos GI-AD): Airbag,
    #    Alarma, Carroceria, Cilindrada, Color, Puertas, Transmision, Version.
    # Se acepta cualquiera de las dos; lo que no se acepta es un punado de
    # pares sueltos que no parezcan ficha (para no colar basura de la pagina).
    CAMPOS_DUROS = [
        "cilindrada exacta (cc)", "power", "torque",
        "distancia entre ejes (mm)", "peso (kg)", "largo (mm)",
    ]
    CAMPOS_BASICOS = [
        "version", "carroceria", "categoria", "combustible", "puertas",
        "transmision", "cilindrada", "airbag", "color", "tipo vehiculo",
        "alarma", "cierre centralizado", "frenos abs", "aire acondicionado",
    ]
    n_duros = sum(1 for c in CAMPOS_DUROS if c in pares)
    n_basicos = sum(1 for c in CAMPOS_BASICOS if c in pares)

    if n_duros < 3 and n_basicos < 5:
        return {}, {}

    specs_limpios = {}
    for etiqueta, valor in pares.items():
        if etiqueta in ETIQUETAS_CLAVE:
            specs_limpios[ETIQUETAS_CLAVE[etiqueta]] = valor

    return specs_limpios, pares_orig


# ---------------------------------------------------------------------------
# DESCARGA + PARSEO (la función que usaría main.py)
# ---------------------------------------------------------------------------
# Contador de 403 consecutivos (lo usa bajar_especificaciones.py para
# descansar unos minutos cuando Datadome empieza a bloquear en cadena).
BLOQUEOS_SEGUIDOS = 0


async def extract_specs(url, session, max_retries=4):
    """
    Baja la página del aviso y devuelve un dict con TODOS los campos de la
    ficha (etiquetas originales), o None si no hay ficha / hay bloqueo.
    El dict incluye además los campos clave normalizados (version_oficial,
    cilindrada_cc, ...) para que el motor los use directo sin re-mapear.
    """
    global BLOQUEOS_SEGUIDOS
    import asyncio, random

    intentos = 0
    while intentos < max_retries:
        try:
            # Referer apuntando al listado, como un navegador que llega al aviso.
            h = dict(headers_base)
            h["referer"] = "https://www.chileautos.cl/vehiculos/autos-veh%C3%ADculo/"
            cookies = {"datadome": DATADOME_COOKIE} if DATADOME_COOKIE else None
            response = None
            for imp in ("chrome99_android", "chrome110", "chrome120", None):
                try:
                    kw = dict(headers=h, cookies=cookies, timeout=8)
                    if imp:
                        kw["impersonate"] = imp
                    response = await session.get(url, **kw)
                    break
                except Exception:
                    continue
            if response is None:
                raise RuntimeError("no se pudo hacer la petición con ningún impersonate")
            if response.status_code == 200:
                BLOQUEOS_SEGUIDOS = 0
                specs_limpios, specs_todos = parsear_especificaciones(response.text)
                if not specs_todos:
                    return None
                # Unir: todos los campos originales + los clave normalizados.
                # Los normalizados van con prefijo claro para no chocar nombres.
                resultado = dict(specs_todos)
                resultado.update(specs_limpios)
                return resultado
            elif response.status_code in (403, 429):
                # NO reintentar: cada reintento es otro golpe a Datadome que
                # refuerza el bloqueo. Se anota y se devuelve de inmediato;
                # el que descansa es el bucle principal (bajar_especificaciones).
                BLOQUEOS_SEGUIDOS += 1
                return None
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
