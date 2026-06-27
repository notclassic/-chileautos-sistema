# 🚗 Chileautos Advanced Scraper

Un potente y optimizado web scraper asíncrono diseñado para extraer vehículos, obtener números de teléfono (resolviendo callbacks de WhatsApp) y capturar nombres de contacto de perfiles de empresa en **Chileautos.cl**.

## 📊 Diagrama de Flujo del Proyecto

A continuación, se presenta la arquitectura en bloques de cómo fluye la información desde la extracción inicial hasta la generación del archivo Excel estilizado:

```mermaid
flowchart TD
    A[Inicio: main.py] -->|1. llama a| B(scrapper.py)
    
    subgraph Fase 1: Extracción de Vehículos
        B --> B1{Fetch Inicial Automático}
        B1 -->|Obtiene Cookies| B2[Queue Workers: 3500 Páginas]
        B2 -->|impersonate='chrome99_android'| B3[Descarga Masiva de JSON]
        B3 --> B4[Parseo y Extracción de Datos]
    end
    
    B4 -->|Retorna Lista de Autos| C[main.py: Deduplicación]
    
    C -->|Elimina Clonados por URL| D[Chunks de Memoria]
    D -->|Bloques de 2500 Autos| E{Fase 2: Extracción de Teléfonos}
    
    subgraph Fase 2: Extracción de Teléfonos
        E -->|Queue: 60 Trabajadores| F(telefono.py)
        F --> F1{¿Es 'Automotora'?}
        F1 -- No --> F2[Omitir / No Disponible]
        F1 -- Sí --> F3[Llamada API /_api/enquiry-core/]
        F3 -->|Busca wa.me| F4[Teléfono Encontrado]
        F3 -.->|Rotación de Proxy Continua| F3
    end
    
    F4 -->|Consolida Números Únicos| G[main.py: Nombres WA]
    
    subgraph Fase 3: Identidad Corporativa
        G -->|Queue: 10 Trabajadores| H(nombreWHAPP.py)
        H --> H1[Llamada a api.whatsapp.com]
        H1 --> H2[Extrae nombre de empresa (h1)]
    end
    
    H2 --> I[Mapeo Nombre->Auto]
    I --> J{Fase Final: Exportación}
    
    subgraph Exportación y Estilos
        J --> K[scrapper.py: formato_excel]
        K --> L[guardar_excel_con_autoajuste]
        L --> M((Archivo Excel Corporativo))
    end
```

## 🛡️ Manejo de Rate Limits y Evasión Anti-Bots (Datadome)

El sitio de Chileautos protege furiosamente sus endpoints usando sistemas como Datadome. Este proyecto aplica técnicas avanzadas y agresivas para evadir estos escudos y mantener una velocidad abrumadora:

1. **Huellas Dactilares de Navegadores (TLS Fingerprinting):** 
   En lugar de usar la clásica librería `requests` de Python, toda la arquitectura HTTP está construida sobre `curl_cffi`, permitiendo inyectar parámetros como `impersonate="chrome99_android"` o `impersonate="chrome110"`. Esto falsifica profundamente las entrañas de la conexión SSL/TLS, engañando al servidor para que crea que somos un celular humano visitándolo, no un Bot de Python.
2. **Concurrencia por Colas (Queue Workers):**
   A diferencia del uso de `asyncio.gather` puro, los trabajadores (Workers) se alimentan de una "Cola" (`asyncio.Queue`) que nunca supera los 60 procesos activos de HTTP cruzados (para teléfonos). Esto previene ráfagas de picos masivos que levantarían banderas rojas en la red.
3. **Manejo de Memoria por Chunks (Lotes):**
   Las listas gigantescas (como 25,000 vehículos) se dividen en "Bloques o Chunks" de 2,500. Se crea y se destruye la `AsyncSession` entre cada bloque. Esto previene fugas de memoria, agotamiento de WebSockets locales y resetea contadores internos que Datadome pudiese estar monitoreando pasivamente.
4. **Rotación Instantánea de Proxys (Fail-Fast):**
   Contamos con un grupo masivo de Proxies HTTP gratuitos inyectados. El sistema aplica Lógica **Fail-Fast**:
   - Limitación estricta de `timeout=4`. Si un proxy demora más de 4 segundos, el script lo ignora y pasa al siguiente, evitando detener la fila de producción.
   - Rotación con `0.1s` de retraso ante código `403` o `429` en lugar del método estándar que frena los bots penalizando con "Sleeps" eternos.
5. **Deduplicación Masiva Temprana:**
   Antes de empezar peticiones externas se depura la lista filtrando IDs duplicados. Extrae el jugo necesario ahorrando miles de peticiones HTTP en clones vacíos, evadiendo Rate Limits innecesarios.

## 📂 Descripción de Archivos

| Archivo | Funcionalidad Principal |
| :--- | :--- |
| **`main.py`** | El **Director de Orquesta**. Inicializa todo, procesa y manda a ejecutar la lógica del `scrapper.py`, administra las listas, filtra URLs duplicadas, divide en fragmentos de memoria (Chunks), levanta los `Queue Workers` de teléfono y de WhatsApp, consolida la información y despacha la petición para su exportación final a Excel. |
| **`scrapper.py`** | El corazón de la primera etapa y del embotellado. Engaña al sistema obteniendo las Cookies "semilla", roza el paginador de la API base de Chileautos en profundidad, limpia el texto de caracteres nocivos (Unicode Formatting), extrae el JSON vital (precio, km, año, etc) y lo inserta en arreglos. También contiene las funciones de Pandas/OpenpyXL para darle diseño corporativo dinámico al Excel final (`guardar_excel_con_autoajuste`). |
| **`telefono.py`** | Módulo "Raptor". Ataca directamente el corazón del endpoint reservado `_api/enquiry-core/{item_id}` esquivando bloqueos con proxys. Escanea velozmente todo el JSON de respuesta para detectar el botón "postBackUrl" recursivamente y capturar desde la redacción el link en bruto de `wa.me/numerodetelefono`. |
| **`nombreWHAPP.py`** | Módulo de Inteligencia de Mercado. Abre una micropetición contra los servidores públicos de WhatsApp usando el número anterior descubierto para hacer ingeniería inversa en el perfil. Navega el código HTML retornado sacando provecho de BeautifulSoup para arrebatar el `<h1>` y deducir corporativamente, con un 98% de precisión, el nombre comercial exacto de la "Automotora" responsable de la venta. |

## 🚀 Cómo Empezar

Simplemente levanta el motor principal asíncrono y observa tu terminal hacer historia:

```bash
python main.py
```
*(Al finalizar te pedirá dónde guardar un increíble Excel pre-estilizado en tu Computadora).*
