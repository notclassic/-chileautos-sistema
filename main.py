import asyncio
import time
from colorama import init, Fore, Style
import sys

# Importar las funciones de scrapper.py
from scrapper import obtener_productos_con_sesion, formato_excel, guardar_excel_con_autoajuste, mostrar_banner
from curl_cffi.requests import AsyncSession

# Importar la función rápida de teléfonos
from telefono import extract_phone_fast

# Importar la función para el nombre de WhatsApp
from nombreWHAPP import extract_whatsapp_name

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
    
    NUM_WORKERS_TEL = 60
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
                        if url and vehiculo.get('entidad') == "Automotora":
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
            
    # 3. Consolidar los números únicos para extraer los nombres de WhatsApp
    telefonos_unicos = {v['whatsapp'] for v in vehiculos if v.get('whatsapp') and v['whatsapp'] != "No disponible"}
    print(Fore.CYAN + f"\nSe encontraron {len(telefonos_unicos)} números de WhatsApp únicos. Obteniendo nombres..." + Style.RESET_ALL)
    
    # 4. Consultar nombres de WhatsApp con Cola
    queue_nombres = asyncio.Queue()
    for t in telefonos_unicos:
        queue_nombres.put_nowait(t)
        
    NUM_WORKERS_WA = 10 
    nombres_cache = {}
    total_nombres = len(telefonos_unicos)
    completados_nombres = 0
    nombres_encontrados = 0
    
    start_time_wa = time.time()
    
    async with AsyncSession() as session_wa:
        async def trabajador_nombres():
            nonlocal completados_nombres, nombres_encontrados
            while True:
                try:
                    telefono = queue_nombres.get_nowait()
                except asyncio.QueueEmpty:
                    break
                    
                try:
                    nombre = await extract_whatsapp_name(telefono, session_wa)
                    if nombre:
                        nombres_cache[telefono] = nombre
                        if "Error" not in nombre and "no encontrado" not in nombre:
                            nombres_encontrados += 1
                    else:
                        nombres_cache[telefono] = "No disponible"
                except Exception as e:
                    nombres_cache[telefono] = "No disponible"
                    
                queue_nombres.task_done()
                completados_nombres += 1
                if completados_nombres % 10 == 0 or completados_nombres == total_nombres:
                    elapsed_wa = time.time() - start_time_wa
                    vel_wa = completados_nombres / elapsed_wa if elapsed_wa > 0 else 0
                    restantes_wa = total_nombres - completados_nombres
                    eta_sec_wa = restantes_wa / vel_wa if vel_wa > 0 else 0
                    eta_str_wa = time.strftime('%H:%M:%S', time.gmtime(eta_sec_wa))
                    
                    sys.stdout.write(f"\rProgreso nombres WA: {completados_nombres}/{total_nombres} completados. ({nombres_encontrados} nombres encontrados) | ETA: {eta_str_wa}   ")
                    sys.stdout.flush()
                    
        workers_nom = [asyncio.create_task(trabajador_nombres()) for _ in range(NUM_WORKERS_WA)]
        await asyncio.gather(*workers_nom)
        print()
    
    # 5. Asignar nombre_whatsapp a TODOS los vehículos consolidados (clones incluidos)
    for v in vehiculos:
        t = v.get('whatsapp')
        if t and t in nombres_cache:
            v['nombre_whatsapp'] = nombres_cache[t]
        else:
            v['nombre_whatsapp'] = "No disponible"
            
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
