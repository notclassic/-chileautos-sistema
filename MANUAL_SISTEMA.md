# Manual del sistema Chileautos

Manual de referencia de los archivos que componen el sistema de inteligencia
de mercado para autos usados de Chileautos.cl. Explica qué hace cada archivo,
cómo se conectan entre sí y qué tener en cuenta al usarlos.

Repositorio: `notclassic/-chileautos-sistema` (GitHub público)
Dashboard online: https://notclassic.github.io/-chileautos-sistema/dashboard.html
Carpeta local: `C:\Users\Maria Nery\OneDrive\Documentos\GitHub\-chileautos-sistema\`

---

## Cómo funciona el sistema, en una frase

El sistema baja autos publicados en Chileautos, los limpia, calcula cuáles
están baratos respecto al mercado, y arma un dashboard que se ve online desde
cualquier lugar. Por separado, va juntando de noche los comentarios de los
vendedores para no levantar sospechas de bot.

---

## Las dos partes que conviene no confundir

El sistema tiene dos procesos que son independientes:

La **descarga de autos** (scraper). Baja el catálogo entero de Chileautos,
con precios, kilómetros y datos de contacto. Es rápido y aguanta correrlo un
par de veces al día.

El **goteo de comentarios**. Entra aviso por aviso a leer el comentario del
vendedor. Es lento a propósito: corre de noche para que Chileautos no lo
detecte como robot y lo bloquee. Esto es lo delicado del sistema.

Mezclar estas dos cosas es el error más común. El horario nocturno aplica solo
al goteo de comentarios, no a la descarga de autos.

---

## Archivos del sistema

### `actualizar.py` — el director de orquesta

Es el archivo que coordina todo. No baja autos ni calcula nada por sí mismo:
llama a los otros archivos en orden.

Cuando lo corrés, hace cuatro pasos seguidos:

1. Corre el scraper (baja autos nuevos) — salvo que uses `--solo-motor`
2. Corre el motor (calcula oportunidades) → genera `datos.json`
3. Mete esos datos dentro del `dashboard.html` para que funcione online
4. Sube todo a GitHub, que es lo que actualiza el dashboard online

Formas de usarlo:

- `python actualizar.py` → hace todo: scraper + motor + dashboard + subir
- `python actualizar.py --solo-motor` → salta el scraper, solo recalcula y sube
  (útil cuando ya bajaste autos hace poco y solo querés recalcular)

Para que funcione necesita que estén en la carpeta los otros archivos del
proyecto y la `plantilla_dashboard.html`.

### `main.py` — el que baja autos y consigue los contactos

Es el corazón de la descarga. `actualizar.py` lo llama en el paso 1. Hace
tres cosas en orden:

1. Baja todos los vehículos de Chileautos (usando `scrapper.py`)
2. Para cada aviso, consulta la API y saca teléfono y WhatsApp
   (usando `telefono.py`)
3. Guarda todo en un Excel dentro de la carpeta `capturas/`

Puntos importantes de este archivo:

**Consulta todos los avisos.** Antes solo pedía contacto a las automotoras y
se saltaba a los particulares, que quedaban siempre en "No disponible". Ahora
consulta a todos, porque el WhatsApp del particular viene en la misma API.

**Concurrencia: 12 trabajadores** (`NUM_WORKERS_TEL = 12`). Significa que hace
12 pedidos a Chileautos al mismo tiempo. Antes eran 60, pero con tantos avisos
eso gatillaba el bloqueo de Chileautos (Datadome). Si lo subís mucho, te van a
bloquear y vas a perder números. Si lo bajás, tarda más pero recuperás más.

**El paso de nombres de WhatsApp está desactivado.** Antes entraba a
`api.whatsapp.com` a buscar el nombre del dueño de cada número. Se desactivó
porque esa página ya no muestra el nombre sin login (devolvía siempre
"No disponible") y porque pegarle a los servidores de Meta arriesga que
bloqueen la IP. El código viejo quedó guardado en el archivo, comentado, por
si algún día se quiere reactivar por goteo.

### `scrapper_auto.py` — el que habla con Chileautos

Es la pieza técnica que arma los pedidos a la API de Chileautos y trae la
lista de autos. `actualizar.py` lo copia temporalmente como `scrapper.py` para
que `main.py` lo use, y después lo borra.

Lo más frágil de este archivo son las **cookies**. Si están vencidas, el
scraper no baja nada aunque el resto del código esté perfecto. Cuando el
scraper "no trae autos" sin dar error claro, lo primero a revisar son las
cookies.

### `telefono.py` — saca teléfono y WhatsApp de cada aviso

Recibe la URL de un aviso, consulta su API
(`https://www.chileautos.cl/_api/enquiry-core/[ID]/`) y devuelve el teléfono y
el WhatsApp del vendedor.

Cómo vienen los datos en la API (esto cambió en 2026):

- **Teléfono para llamar**: aparece como `tel:+56...` dentro de un botón
  "Llamar al vendedor". Las automotoras lo suelen tener. Los particulares
  casi nunca.
- **WhatsApp del vendedor**: aparece como `dealerNumber=+56...` dentro del
  botón de WhatsApp. Lo tienen tanto automotoras como particulares.

Detalle clave del WhatsApp: en los particulares el número viene con espacios
codificados, así: `dealerNumber=9%208209%200285`. Eso es el celular
`9 8209 0285` sin el prefijo de país. El código lo decodifica, le saca los
espacios y le antepone `+56` para dejarlo como `+56982090285`.

El formato viejo (`wa.me/...`) ya no se usa en Chileautos, pero el código lo
sigue soportando por si aparece en algún aviso antiguo.

### `nombreWHAPP.py` — saca el nombre del dueño (ya no se usa)

Entraba a `api.whatsapp.com` para leer el nombre del perfil de WhatsApp del
vendedor. **Está fuera de uso**: esa página ya no muestra el nombre sin estar
logueado, así que devolvía siempre "No disponible". El nombre se ve igual al
escribir por WhatsApp. El archivo sigue en la carpeta pero `main.py` ya no lo
llama.

### `motor.py` — calcula qué autos están baratos

Lee los Excel que dejó el scraper en `capturas/`, limpia los datos (saca
basura, kilómetros imposibles, etc.) y calcula para cada auto:

- Un **precio justo** según lo que vale ese modelo en el mercado
- Cuánto está por **debajo o encima** de ese precio justo (el descuento)
- Las **oportunidades** (autos bien por debajo de su precio justo)
- Comparables (otros autos parecidos, para justificar el precio justo)
- La **rotación** del mercado (qué tan rápido se venden)

Genera dos cosas:

- `datos.json` → lo que alimenta el dashboard
- `base_FECHA.xlsx` → un Excel con toda la base procesada, por si querés
  mirarla a mano

### `ver_comentarios.py` — clasifica los comentarios

Toma los comentarios de los vendedores que se fueron goteando, los clasifica
(les pone etiquetas como "financia", "permuta", banderas rojas) y los cruza
con los autos. Lo usa el botón `ACTUALIZAR_DASHBOARD.bat`.

### `enriquecer_comentarios.py` — el goteo nocturno

Es el que va, despacio y de noche (aprox. 10 PM a 8 AM), entrando aviso por
aviso a leer el comentario del vendedor. Se corre con `--continuo`. Es la
parte más delicada del sistema: si se apura, Chileautos lo bloquea.

### `plantilla_dashboard.html` — el molde del dashboard

Es el dashboard vacío, con un hueco marcado `/*__DATA__*/` donde
`actualizar.py` mete los datos. **No se toca a mano salvo para cambiar el
diseño.** Tiene la tabla de autos, los filtros, el popup de comparables y el
popup del comentario del vendedor.

### `dashboard.html` — el dashboard final

Es el resultado: la plantilla ya rellena con los datos del día. Es el archivo
que se sube a GitHub y se ve online. Se regenera solo cada vez que corrés
`actualizar.py`, así que no tiene sentido editarlo a mano (se pisa en la
próxima corrida).

---

## Los archivos `.bat` (los de doble clic)

Son atajos para no escribir comandos. Hacés doble clic y corren solos.

### `DESCARGAR_BASE.bat`
Corre `actualizar.py` completo: baja autos nuevos, recalcula y sube el
dashboard. Es el que usás cuando querés traer autos frescos de Chileautos.

### `ACTUALIZAR_DASHBOARD.bat`
Clasifica los comentarios goteados, corre el motor y sube el dashboard.
**No baja autos nuevos.** Es para refrescar el dashboard con los comentarios
nuevos sin volver a descargar todo.

---

## Carpetas

### `capturas/`
Donde el scraper guarda los Excel de cada descarga, con nombre por fecha
(ej: `Chileautos 2026-06-27.xlsx`). El motor lee de acá.

---

## El recorrido completo, paso a paso

Cuando hacés doble clic en `DESCARGAR_BASE.bat`, pasa esto:

1. `DESCARGAR_BASE.bat` arranca `actualizar.py`
2. `actualizar.py` llama a `main.py`
3. `main.py` usa `scrapper.py` para bajar todos los autos
4. `main.py` usa `telefono.py` para sacar teléfono y WhatsApp de cada uno
5. `main.py` guarda el Excel en `capturas/`
6. `actualizar.py` llama a `motor.py`, que lee ese Excel y calcula
   oportunidades → `datos.json` + `base_FECHA.xlsx`
7. `actualizar.py` mete `datos.json` dentro de `plantilla_dashboard.html` →
   genera `dashboard.html`
8. `actualizar.py` sube a GitHub → el dashboard online se actualiza en 1-2 min

---

## Cosas a tener en cuenta

**Los particulares no ponen teléfono, ponen WhatsApp.** La mayoría de los
avisos sin teléfono no es por bloqueo: es que el particular solo publicó
WhatsApp. Eso es normal y esperado.

**No todos los avisos van a tener contacto.** Algunos no publican ni teléfono
ni WhatsApp (solo formulario). Eso no es un error del sistema.

**Si te bloquean (errores 403), bajá la concurrencia.** El número de
trabajadores en `main.py` (`NUM_WORKERS_TEL`) es la perilla. Menos
trabajadores = más lento pero menos bloqueos.

**Las cookies vencen.** Si el scraper deja de traer autos sin error claro, lo
primero a revisar son las cookies del scraper.

**El dashboard online tarda 1-2 minutos** en actualizarse después de subir a
GitHub. No es instantáneo.
