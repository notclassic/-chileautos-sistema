import asyncio
import re
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup

# Mismos headers de navegador que el resto del proyecto, para pasar Datadome
headers_base = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "es,es-ES;q=0.9,en;q=0.8",
    "cache-control": "no-cache",
    "user-agent": "Mozilla/5.0 (Linux; Android 13; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
    "referer": "https://www.chileautos.cl/vehiculos/autos-veh%C3%ADculo/",
}

# Texto del boton de expandir que se cuela al final del bloque
_BASURA_FINAL = re.compile(r'\s*(seguir leyendo|leer m[aá]s|ver m[aá]s)\s*$', re.IGNORECASE)


def _limpiar_comentario(texto: str) -> str:
    """Normaliza el texto del comentario para guardarlo en una sola celda."""
    if not texto:
        return ""
    texto = _BASURA_FINAL.sub('', texto.strip())
    # colapsar saltos de linea multiples y espacios; mantener separacion por " | "
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    return " | ".join(lineas)


def extraer_comentario_de_html(html: str) -> str:
    """
    Extrae el comentario del vendedor del HTML de la pagina de detalle.
    Estrategia principal: el bloque marcado con data-id="details:body:comments".
    Respaldo: el contenedor que sigue al encabezado "Comentarios del vendedor".
    Las clases CSS del sitio son aleatorias y cambian entre builds, por eso NO
    se usan como ancla; el data-id y el texto del encabezado son estables.
    """
    soup = BeautifulSoup(html, 'html.parser')

    # 1) Ancla semantica estable
    bloque = soup.select_one('[data-id="details:body:comments"]')

    # 2) Respaldo: buscar encabezado "Comentarios del vendedor" y tomar su contenedor
    if bloque is None:
        for h in soup.find_all(['h2', 'h3']):
            if 'comentarios del vendedor' in h.get_text(strip=True).lower():
                bloque = h.parent
                break

    if bloque is None:
        return ""

    # Quitar el encabezado para quedarnos solo con el texto del vendedor
    for h in bloque.find_all(['h2', 'h3']):
        h.extract()

    return _limpiar_comentario(bloque.get_text("\n", strip=True))


async def extraer_comentario_fast(url, session, max_retries=4):
    """
    Descarga la pagina de detalle del aviso y devuelve el comentario del vendedor.
    Devuelve "" si no hay comentario, o None si fallo la descarga.
    """
    intentos = 0
    while intentos < max_retries:
        try:
            response = await session.get(
                url, headers=headers_base, impersonate="chrome99_android", timeout=6
            )
            if response.status_code == 200:
                return extraer_comentario_de_html(response.text)
            elif response.status_code in (403, 429):
                # Datadome: misma logica de espera que el resto del proyecto
                espera = 60 * (intentos + 1)
                print(f"[comentario] Bloqueo {response.status_code} en {url} "
                      f"(intento {intentos+1}/{max_retries}). Esperando {espera}s...")
                await asyncio.sleep(espera)
            else:
                print(f"[comentario] HTTP {response.status_code} en {url}")
                return None
        except Exception as e:
            print(f"[comentario] Excepcion en {url}: {e}")
            await asyncio.sleep(5)
        intentos += 1
    return None


# ---- Prueba sobre el HTML guardado (no toca la red) ----
# python comentario_vendedor.py web.html
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding='utf-8', errors='ignore') as f:
            html = f.read()
        print("Comentario extraido:")
        print(repr(extraer_comentario_de_html(html)))
    else:
        print("Uso: python comentario_vendedor.py <archivo.html>")
