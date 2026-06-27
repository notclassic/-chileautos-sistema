import asyncio
import re
import urllib.parse
from urllib.parse import urlparse, parse_qs
from curl_cffi.requests import AsyncSession

headers_base = {
    "accept": "application/json",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "es,es-ES;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "cache-control": "no-cache",
    "content-type": "application/json",
    "user-agent": "Mozilla/5.0 (Linux; Android 13; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36 Edg/132.0.0.0",  
    "referer": "https://www.chileautos.cl/vehiculos/autos-veh%C3%ADculo/",
    "sec-ch-ua": "\"Not A(Brand\";v=\"8\", \"Chromium\";v=\"132\", \"Microsoft Edge\";v=\"132\"",
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": "\"Android\"",
}

async def extract_phone_fast(url, session, max_retries=5):
    # Extraer el ID de la URL. Ej: ".../CP-AD-8511086" o ".../CP-AD-8511086/"
    parts = [p for p in url.split('/') if p]
    item_id = parts[-1]
    
    api_url = f"https://www.chileautos.cl/_api/enquiry-core/{item_id}/"
    
    intentos = 0
    while intentos < max_retries:
        try:
            # Realizar petición de forma directa (sin rotar proxy público)
            # Timeout de 4 segundos para evitar enganches prolongados
            response = await session.get(api_url, headers=headers_base, impersonate="chrome99_android", timeout=4)
            
            if response.status_code == 200:
                data = response.json()
                # Extraemos ambos telefonos (linea normal y whatsapp)
                contacts = extract_contacts(data)
                return contacts
                
                
            elif response.status_code in [403, 429]:
                # Ya no rotamos IP, por lo tanto si Datadome nos frena en seco, hay que dormir forzosamente
                tiempo_espera = 60 * (intentos + 1)
                print(f"[{item_id}] Bloqueo Oficial {response.status_code} (Intento {intentos+1}/{max_retries}). Debes esperar {tiempo_espera}s...")
                await asyncio.sleep(tiempo_espera)
            else:
                print(f"[{item_id}] Error {response.status_code} al consultar API.")
                return None
                
        except Exception as e:
            tiempo_espera = 5
            print(f"[{item_id}] Excepción: {e}. Esperando {tiempo_espera}s...")
            await asyncio.sleep(tiempo_espera)
            
        intentos += 1
        
    print(f"[{item_id}] Falló definitivamente después de {max_retries} intentos.")
    return None

def extract_whatsapp_number_from_url(url: str):
    if not url:
        return None

    # Caso 1: viene directo como https://wa.me/56229949429?text=...
    match = re.search(r"wa\.me/(\d+)", url)
    if match:
        return "+" + match.group(1)

    # Caso 2: viene dentro de targetUrl=...
    try:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        target_url = query.get("targetUrl", [""])[0]

        match = re.search(r"wa\.me/(\d+)", target_url)
        if match:
            return "+" + match.group(1)
    except Exception:
        pass

    return None

def extract_phone_number_from_url(url: str):
    if not url:
        return None

    if url.startswith("tel:"):
        return url.replace("tel:", "", 1)

    return None

def extract_contacts(data):
    result = {
        "telefono": None,
        "whatsapp": None
    }

    def walk(obj):
        if isinstance(obj, dict):
            # Buscar teléfono en acciones tipo tel
            action = obj.get("action", {})
            if isinstance(action, dict):
                if action.get("key") == "tel":
                    tel_url = action.get("data", {}).get("url", "")
                    phone = extract_phone_number_from_url(tel_url)
                    if phone and not result["telefono"]:
                        result["telefono"] = phone

                # A veces el postBackUrl viene dentro de action.data
                postback_in_action = action.get("data", {}).get("postBackUrl", "")
                wa = extract_whatsapp_number_from_url(postback_in_action)
                if wa and not result["whatsapp"]:
                    result["whatsapp"] = wa

            # Buscar WhatsApp en postBackUrl directo del nodo
            postback_url = obj.get("postBackUrl", "")
            wa = extract_whatsapp_number_from_url(postback_url)
            if wa and not result["whatsapp"]:
                result["whatsapp"] = wa

            # Seguir recorriendo
            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return result

async def main():
    url_prueba = "https://www.chileautos.cl/vehiculos/detalles/2022-peugeot-3008-1-5-bluehdi-130-auto-gt/CP-AD-8511086"
    
    # Usar un semáforo (ej: 10 a 30 conexiones concurrentes)
    semaphore = asyncio.Semaphore(20)
    
    print(f"Iniciando extracción por API rápida para: {url_prueba}")
    
    async with AsyncSession() as session:
        # Aquí podrías iterar sobre una lista inmensa de URLs
        contacts = await extract_phone_fast(url_prueba, session)
        
        if contacts:
            print(f"\n--- Resultado Final ---\nTeléfonos extraídos al instante: {contacts}")
        else:
            print("\n--- Resultado Final ---\nNo se pudo extraer el teléfono mediante la API.")

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
