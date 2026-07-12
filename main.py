import asyncio
import time
from colorama import init, Fore, Style
import sys

# Importar las funciones de scrapper.py
from scrapper import obtener_productos_con_sesion, formato_excel, guardar_excel_con_autoajuste, mostrar_banner
from curl_cffi.requests import AsyncSession

# Importar la función rápida de teléfonos
from telefono import extract_phone_fast

# NOTA: el paso de nombres de WhatsApp (nombreWHAPP) está DESACTIVADO:
# ya no daba dato por esa vía y arriesgaba bloqueos de IP.

init(autoreset=True)

async def obtener_telefonos_masivo(vehiculos):
    # DEDUCPLICACIÓN DE URLS - Filtrar vehículos repetidos que vinieron del scrapper
    vehiculos_unicos_dict = {}
    for v in vehiculos:
        url = v.get('url_detalles')
        if url and url not in vehiculos_unicos_dict:
            vehiculos_unicos_dict[url] = v
        elif not url: # si no tiene url, lo agreamos usando un id fariseo
            vehiculos_unicos_dict[id(v)] = v
            
    vehiculos_limpios = list(vehiculos_unicos_dict.values())
    
    print(Fore.CYAN + f"\nIniciando extracción de teléfonos para {len(vehiculos_limpios)} vehículos únicos (se descartaron {len(vehiculos) - len(vehiculos_limpios)} duplicados)..." + Style.RESET_ALL)
    
    NUM_WORKERS_TEL = 12   # bajado de 60 a 12: con 60 saltaban bloqueos 403
    total = len(vehiculos_limpios)
    completados = 0
    con_telefono = 0
    start_time_tel = time.time()
    
    # Procesar en Chunks para evitar colapsar la Sesión y la Memoria a lo largo del tiempo
    CHUNK_SIZE = 500
    
    # Hacer slices del array en pedazos de 2500
    chunks_vehiculos = [vehiculos_limpios[i:i + CHUNK_SIZE] for i in range(0, len(vehiculos_limpios), CHUNK_SIZE)]
    
    print(f"Dividiendo el trabajo en {len(chunks_vehiculos)} bloques de memoria para mantener la velocidad al máximo...")
    
    for indice_chunk, chunk in enumerate(chunks_vehiculos, 1):
        queue_telefonos = asyncio.Queue()
        for v in chunk:
            queue_telefonos.put_nowait(v)
            
        async with AsyncSession() as session:
            async def trabajador_telefonos():
                nonlocal completados, con_telefono
                while True:
                    try:
                        vehiculo = queue_telefonos.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                        
                    try:
                        url = vehiculo.get('url_detalles')
                        # Consultamos TODOS los avisos, no solo automotoras:
                        # los particulares no publican teléfono pero sí WhatsApp,
                        # y antes el filtro == "Automotora" los salteaba a todos.
                        if url:
                            contacts = await extract_phone_fast(url, session)
                            if contacts:
                                vehiculo['telefono'] = contacts.get('telefono') or "No disponible"
                                vehiculo['whatsapp'] = contacts.get('whatsapp') or "No disponible"
                                if vehiculo['telefono'] != "No disponible" or vehiculo['whatsapp'] != "No disponible":
                                    con_telefono += 1
                            else:
                                vehiculo['telefono'] = "No disponible"
                                vehiculo['whatsapp'] = "No disponible"
                        else:
                            vehiculo['telefono'] = "No disponible"
                    except Exception as e:
                        vehiculo['telefono'] = "No disponible"
                    
                    queue_telefonos.task_done()
                    completados += 1
                    
                    if completados % 20 == 0 or completados == total:
                        elapsed = time.time() - start_time_tel
                        vel = completados / elapsed if elapsed > 0 else 0
                        restantes = total - completados
                        eta_sec = restantes / vel if vel > 0 else 0
                        eta_str = time.strftime('%H:%M:%S', time.gmtime(eta_sec))
                        
                        sys.stdout.write(f"\rProgreso teléfonos [Bloque {indice_chunk}/{len(chunks_vehiculos)}]: {completados}/{total} completados. ({con_telefono} teléfonos hallados) | ETA: {eta_str}   ")
                        sys.stdout.flush()
                        
            workers_tel = [asyncio.create_task(trabajador_telefonos()) for _ in range(NUM_WORKERS_TEL)]
            await asyncio.gather(*workers_tel)
            
    print() # Salto de línea limpio al terminar la fase de teléfonos
    
    # 2. Re-asignar los teléfonos descubiertos a TODOS los vehículos (incluyendo clones)
    for v in vehiculos:
        url = v.get('url_detalles')
        if url and url in vehiculos_unicos_dict:
            # Transferir el resultado del vehículo único a sus clones
            v['telefono'] = vehiculos_unicos_dict[url].get('telefono', "No disponible")
            v['whatsapp'] = vehiculos_unicos_dict[url].get('whatsapp', "No disponible")
        else:
            if 'telefono' not in v:
                v['telefono'] = "No disponible"
            if 'whatsapp' not in v:
                v['whatsapp'] = "No disponible"
            
    # 3. Paso de nombres de WhatsApp DESACTIVADO.
    #    Antes acá se consultaba el nombre del dueño de cada WhatsApp, pero esa
    #    vía dejó de dar dato y aumentaba el riesgo de bloqueo de IP.
    #    Dejamos la columna nombre_whatsapp en "No disponible" para no romper el
    #    formato del Excel de salida.
    for v in vehiculos:
        v['nombre_whatsapp'] = "No disponible"

    telefonos_unicos = {v['whatsapp'] for v in vehiculos if v.get('whatsapp') and v['whatsapp'] != "No disponible"}

    print(Fore.GREEN + f"\nExtracción terminada. Total vehículos exportados: {len(vehiculos)} | Teléfonos hallados: {con_telefono} ( {len(telefonos_unicos)} números únicos )." + Style.RESET_ALL)

def main():
    mostrar_banner()
    time.sleep(2)
    print(Fore.YELLOW + Style.BRIGHT + "\n--- PASO 1: OBTENER TODOS LOS VEHÍCULOS ---" + Style.RESET_ALL)
    
    # 1. Obtener todos los vehículos usando la lógica existente
    # Nota: Si el scrapper saca miles de autos, esto tomará su tiempo original
    vehiculos = obtener_productos_con_sesion()
    
    if not vehiculos:
        print(Fore.RED + "No se obtuvieron vehículos. Finalizando proceso." + Style.RESET_ALL)
        return
        
    print(Fore.YELLOW + Style.BRIGHT + "\n--- PASO 2: OBTENER TELÉFONOS DE WHATSAPP ---" + Style.RESET_ALL)
    
    # 2. Correr la extracción asíncrona de teléfonos
    # En Windows aveces se necesita WindowsSelectorEventLoopPolicy pero obtener_productos_con_sesion ya lo establece.
    asyncio.run(obtener_telefonos_masivo(vehiculos))
    
    print(Fore.YELLOW + Style.BRIGHT + "\n--- PASO 3: GUARDAR EN EXCEL ---" + Style.RESET_ALL)
    
    # 3. Formatear a Excel y guardar
    df = formato_excel(vehiculos)
    guardar_excel_con_autoajuste(df)
    
    print(Fore.GREEN + Style.BRIGHT + "\nPROCESO COMPLETADO EXITOSAMENTE" + Style.RESET_ALL)

if __name__ == "__main__":
    main()
