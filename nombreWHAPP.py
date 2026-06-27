import asyncio
import re
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
import random

# Definir headers para simular un navegador real y evitar bloqueos base
headers_base = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "es,es-ES;q=0.9,en;q=0.8",
    "cache-control": "no-cache",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
}

async def extract_whatsapp_name(phone, session, max_retries=3):
    # Asegurarnos de que el teléfono tenga el formato correcto (solo números)
    phone_clean = re.sub(r'\D', '', phone)
    url = f"https://api.whatsapp.com/send/?phone={phone_clean}"
    
    intentos = 0
    while intentos < max_retries:
        try:
            # impersonate="chrome110" ayuda a evadir bloqueos básicos
            # Añadido timeout hiper-agresivo (4s) para evitar que proxies públicos mediocres congelen al trabajador
            response = await session.get(url, headers=headers_base, impersonate="chrome110", timeout=4)
            
            if response.status_code == 200:
                html = response.text
                soup = BeautifulSoup(html, 'html.parser')
                
                # Buscar el h3 que tiene el nombre del contacto.
                h3_tag = soup.find('h3', class_="_9vd5 _9scb _9scr")
                
                # A veces las clases cambian, otra alternativa es buscar el h3 padre de main_block
                if not h3_tag:
                    main_block = soup.find(id="main_block")
                    if main_block:
                        h3_tag = main_block.find('h3')

                if h3_tag:
                    nombre = h3_tag.text.strip()
                    return nombre
                else:
                    return None
                    
            elif response.status_code in [429, 403]:
                tiempo_espera = random.uniform(150, 200) * (intentos + 1)
                print(f"[{phone}] Bloqueo WA {response.status_code} (Intento {intentos+1}/{max_retries}). Esperando {tiempo_espera:.2f}s...")
                await asyncio.sleep(tiempo_espera)
            else:
                print(f"[{phone}] Error {response.status_code} al acceder a WhatsApp API")
                return "Error HTTP"
                
        except Exception as e:
            tiempo_espera = random.uniform(2, 5)
            print(f"[{phone}] Excepción WA: {e}. Esperando {tiempo_espera:.2f}s...")
            await asyncio.sleep(tiempo_espera)
            
        intentos += 1
        
    print(f"[{phone}] Falló WA definitivamente después de {max_retries} intentos.")
    return "Error de conexión"

async def main():
    telefono_prueba = "56225830605"
    print(f"Extrayendo nombre para el número: {telefono_prueba}")
    
    semaphore = asyncio.Semaphore(10)
    
    async with AsyncSession() as session:
        nombre = await extract_whatsapp_name(telefono_prueba, session)
        print(f"\nResultado:")
        print(f"Número: {telefono_prueba}")
        print(f"Nombre de Contacto: {nombre}")

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
