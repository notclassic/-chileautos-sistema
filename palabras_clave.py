# -*- coding: utf-8 -*-
"""
CATALOGO DE PALABRAS CLAVE para clasificar comentarios de vendedores.
=====================================================================

Esto NO es codigo complicado: es una lista de palabras que podes editar.
Cada categoria tiene palabras/frases que, si aparecen en el comentario,
hacen que el auto reciba esa etiqueta.

Como editarlo (sin saber programar):
  - Para AGREGAR una forma de decir algo, sumala entre comillas con una coma.
    Ej: si ves que dicen "mantencion en agencia", agregala a MANTENCION_AL_DIA.
  - Para SACAR una palabra que da falsos positivos, borra esa linea.
  - Respeta el formato: cada palabra entre comillas, separadas por comas.
  - Escribi en minuscula y sin acentos: el sistema ya normaliza el texto
    (convierte el comentario a minuscula y le saca los acentos antes de buscar).

IMPORTANTE sobre negaciones:
  Las frases en NEGATIVO (ej "no chocado", "sin detalles") se manejan aparte
  en clasificar_comentarios.py para evitar marcar mal. No agregues "no choc..."
  aca; el sistema ya revisa si la palabra viene negada.
"""

# --- SEÑALES NEGATIVAS (banderas rojas: explican precios sospechosamente bajos) ---
DANIADO = [
    "chocado", "chocada", "choque", "siniestrado", "siniestro", "siniestrado total",
    "para desarme", "desarme", "desabolladura", "abollado", "abolladura",
    "con detalle", "detalle de", "detalles de chapa", "detalle estetico",
    "no funciona", "no enciende", "no anda", "fundido", "motor fundido",
    "motor malo", "falla", "fallo", "con problemas", "a reparar", "para reparar",
    "para repuesto", "repuestos", "tal cual esta", "tal como esta",
    "no rola", "no se mueve", "para restaurar", "proyecto",
    "volcado", "inundado", "quemado", "robado y recuperado",
    "trizadura", "trizado", "falla electrica", "falla en la caja",
    "se debe reparar", "computador malo", "perdida total",
    "comprado en remate", "vehiculo de aseguradora", "viene de aseguradora",
]

# --- PROBLEMA LEGAL / DOCUMENTAL (no se puede transferir facil o tiene deuda) ---
PROBLEMA_LEGAL = [
    "sin papeles", "no transferible", "no transferable", "sin transferencia",
    "con prenda", "prendado", "con deuda", "deuda prendaria", "saldo de prenda",
    "con multas", "multas pendientes", "permiso de circulacion vencido",
    "revision tecnica vencida", "sin revision tecnica",
    "documentos en tramite", "papeles en tramite", "encargo por robo",
    "retencion", "embargo", "judicializado", "leasing vigente",
    "factura pendiente", "no inscrito", "sin inscripcion",
]

# --- IMPORTADO / ORIGEN ESPECIAL (afecta valor y comparabilidad) ---
ORIGEN_ESPECIAL = [
    "internado", "internacion", "zona franca", "tributado", "sin tributar",
    "importado", "recien internado", "iquique", "zofri",
    "no liberada", "no liberado", "franquicia", "aduana", "cupo de discapacidad",
]

# --- ESTADO POSITIVO ---
IMPECABLE = [
    "impecable", "excelente estado", "muy buen estado", "como nuevo", "como nueva",
    "estado de coleccion", "perfecto estado", "estado impecable",
    "a toda prueba", "cuidado maniatico", "impeque", "flamante",
    "cero detalle", "sin detalles", "practicamente nuevo", "practicamente nueva",
    "todo original", "nunca chocado", "nunca chocada", "jamas chocado",
    "jamas chocada", "sin choques",
]

# --- PROCEDENCIA / DUEÑOS ---
UNICO_DUENIO = [
    "unico dueno", "un solo dueno", "1 dueno", "primer dueno",
    "unica duena", "solo un dueno",
]
POCOS_DUENIOS = [
    "dos duenos", "2 duenos", "segundo dueno",
]

# --- MANTENCION ---
MANTENCION_AL_DIA = [
    "mantenciones al dia", "mantencion al dia", "mantenimiento al dia",
    "mantenciones en la marca", "mantencion en la marca",
    "concesionario oficial", "en agencia", "mantenimiento en concesionario",
    "historial de servicio", "mantenciones realizadas",
]

# --- DOCUMENTACION / TRANSFERENCIA ---
LISTO_TRANSFERIR = [
    "listo para transferir", "papeles al dia", "documentos al dia",
    "transferencia inmediata", "se transfiere", "para transferir",
]

# --- FACILIDADES COMERCIALES (suelen indicar AUTOMOTORA, no particular) ---
FACILIDADES = [
    "financiamiento", "recibimos auto", "recibiriamos vehiculo",
    "parte de pago", "parte pago", "permuta", "permuto",
    "aceptamos tarjeta", "aceptariamos tarjeta", "reserva por",
    "garantia", "pie desde", "cuotas",
]

# --- VENTA URGENTE (vendedor apurado = precio negociable; oro para comprar) ---
# Ampliada con frases REALES de avisos chilenos (minadas de la BBDD)
VENTA_URGENTE = [
    "urge", "urgente", "urge vender", "vendo urgente", "necesito vender",
    "por viaje", "me voy del pais", "viaje al extranjero", "salida del pais",
    "por motivo de viaje", "no viven en chile", "fui a vivir a", "me voy a vivir",
    "remato", "se remata", "rematado", "precio de remate",
    "vendo hoy", "solo por hoy", "vendo ya", "rapida venta", "venta rapida",
    "por apuro", "apurado", "necesito el dinero", "necesito la plata",
    "urgencia economica", "motivos economicos", "por necesidad",
    "rebajada", "rebajado", "ultimo precio",
]

# --- PRECIO CONDICIONADO (bandera ROJA para comprador contado: el precio
#     publicado solo vale con financiamiento; al contado es MAS caro) ---
PRECIO_CONDICIONADO = [
    "bono de financiamiento", "con bono financiamiento", "bono financiamiento",
    "solo con financiamiento", "valido con financiamiento",
    "valido solo con financiamiento", "corresponde a precio con",
    "precio con financiamiento", "valor financiamiento",
    "precio credito", "valor publicado corresponde", "precio publicado corresponde",
    "exclusivo financiamiento", "con financiamiento gestionado",
    "credito forum", "producto chevy siempre",
]

# --- PRECIO MAS IVA (el precio real es ~19% mayor) ---
PRECIO_MAS_IVA = [
    "mas iva", "se le suma iva", "valores mas iva", "afecta a iva",
    "factura afecta", "valor referencial mas iva",
]

# --- MODIFICADO (alteraciones mecanicas: riesgo en revision tecnica/durabilidad) ---
MODIFICADO = [
    "dpf eliminado", "dpf fue eliminado", "sin dpf",
    "adblue desconectado", "ad-blue desconectado", "adblue eliminado",
    "conversion a gas", "convertido a gas", "kit glp",
    "reprogramado", "stage 1", "stage 2",
]

# --- TRATO DIRECTO (vende el dueño; rechaza automotoras) ---
TRATO_DIRECTO = [
    "no automotoras", "no llamar automotoras", "favor no llamar automotoras",
    "vende su dueno", "vende directamente", "venta directa", "trato directo",
    "sin comision", "sin concesionario", "contacto con el dueno",
]

# --- PRECIO NEGOCIABLE (abre la puerta a ofertar bajo) ---
PRECIO_CONVERSABLE = [
    "conversable", "negociable", "precio a convenir",
    "se conversa", "escucho ofertas", "se escuchan ofertas", "oferta razonable",
    "ofertas razonables", "atento a ofertas", "acepta oferta", "se acepta oferta",
    "propuestas serias", "flexible en el precio",
]

# --- USO ---
POCO_USO = [
    "poco uso", "bajo kilometraje", "uso de carretera", "solo carretera",
    "auto de garage", "siempre en garage",
]

# Mapa final: nombre de etiqueta -> lista de palabras
# (clasificar_comentarios.py recorre esto)
CATEGORIAS = {
    "daniado": DANIADO,
    "problema_legal": PROBLEMA_LEGAL,
    "origen_especial": ORIGEN_ESPECIAL,
    "impecable": IMPECABLE,
    "unico_dueno": UNICO_DUENIO,
    "pocos_duenos": POCOS_DUENIOS,
    "mantencion_al_dia": MANTENCION_AL_DIA,
    "listo_transferir": LISTO_TRANSFERIR,
    "facilidades": FACILIDADES,
    "poco_uso": POCO_USO,
    "venta_urgente": VENTA_URGENTE,
    "precio_conversable": PRECIO_CONVERSABLE,
    "precio_condicionado": PRECIO_CONDICIONADO,
    "precio_mas_iva": PRECIO_MAS_IVA,
    "modificado": MODIFICADO,
    "trato_directo": TRATO_DIRECTO,
}

# Palabras que, si aparecen ANTES de una señal negativa, la anulan.
# Ej: "no chocado", "sin detalles", "nunca chocado" -> NO marcar como daniado.
NEGADORES = ["no", "sin", "nunca", "jamas", "libre de", "cero", "poco"]
