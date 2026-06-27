#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MOTOR DE CALCULO - Capa 1 del sistema de inteligencia Chileautos
================================================================

Que hace:
  1. Lee TODAS las capturas (.xlsx) de la carpeta capturas/
  2. Limpia cada una con las mismas reglas validadas.
  3. Calcula precio justo y oportunidades sobre la captura mas reciente.
  4. Compara capturas consecutivas para medir ROTACION (avisos que
     desaparecen = proxy de venta) y CAMBIOS DE PRECIO.
  5. Escribe datos.json con todo lo calculado.

El dashboard lee datos.json. El motor no toca el dashboard.
Cuando se automatice, el robot solo vuelve a correr este script.

Uso:
    python motor.py
    (lee carpeta ./capturas, escribe ./datos.json)

Requiere: pandas, numpy, openpyxl
"""

import os, sys, json, glob, re
from datetime import datetime
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# CONFIGURACION
# ---------------------------------------------------------------------------
CARPETA_CAPTURAS = "capturas"
SALIDA = "datos.json"

COLUMNAS_ESPERADAS = [
    'fecha','marca','modelo','version','año','traccion','condicion','precio',
    'kilometraje','transmision','combustible','id','moneda','entidad',
    'Enlace Web','telefono','whatsapp','nombre_whatsapp'
]

# Reglas de limpieza (validadas con las bases reales)
PRECIO_MIN, PRECIO_MAX = 500_000, 300_000_000
KM_MIN, KM_MAX = 0, 500_000
ANIO_MIN, ANIO_MAX = 1990, 2027

# Reglas de oportunidad
DESCUENTO_MIN = 15.0      # % bajo precio justo para "bajo precio"
KM_ANUAL_MAX = 10_000     # umbral "bajo kilometraje"
MIN_COMPARABLES = 5       # minimo de comparables para tasar


def log(msg):
    print(f"[motor] {msg}")


# ---------------------------------------------------------------------------
# 1. CARGA Y LIMPIEZA
# ---------------------------------------------------------------------------
def fecha_de_captura(df):
    """Devuelve la fecha dominante de la captura como datetime (día)."""
    s = pd.to_datetime(df['fecha'], format='%d-%m-%Y %H:%M', errors='coerce')
    if s.isna().all():
        s = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
    return s.dt.normalize().mode().iloc[0]


def cargar_captura(path):
    """Lee un xlsx, valida columnas y extrae hipervinculos de Enlace Web."""
    df = pd.read_excel(path)
    faltan = [c for c in COLUMNAS_ESPERADAS if c not in df.columns]
    if faltan:
        raise ValueError(f"{os.path.basename(path)}: faltan columnas {faltan}")

    # Recuperar URL real (esta como hipervinculo de celda, no como texto)
    urls = {}
    try:
        from openpyxl import load_workbook
        wb = load_workbook(path)
        ws = wb.active
        hdr = [c.value for c in ws[1]]
        ci_link = hdr.index('Enlace Web') + 1
        ci_id = hdr.index('id') + 1
        for r in range(2, ws.max_row + 1):
            cell = ws.cell(row=r, column=ci_link)
            idv = ws.cell(row=r, column=ci_id).value
            if cell.hyperlink and cell.hyperlink.target:
                urls[idv] = cell.hyperlink.target
        wb.close()
    except Exception as e:
        log(f"  aviso: no se pudieron leer hipervinculos ({e})")

    df['url'] = df['id'].map(urls)
    return df


def limpiar(df):
    """Aplica las reglas de limpieza validadas. Devuelve df limpio."""
    df = df.drop_duplicates(subset='id', keep='first').copy()
    df = df[df['moneda'] == 'CLP']
    df['año'] = pd.to_numeric(df['año'], errors='coerce')
    df = df[(df['año'] >= ANIO_MIN) & (df['año'] <= ANIO_MAX)]
    df['precio'] = pd.to_numeric(df['precio'], errors='coerce')
    df['kilometraje'] = pd.to_numeric(df['kilometraje'], errors='coerce')
    df = df[(df['precio'] >= PRECIO_MIN) & (df['precio'] <= PRECIO_MAX)]
    df = df[(df['kilometraje'] >= KM_MIN) & (df['kilometraje'] <= KM_MAX)]
    df['marca'] = df['marca'].astype(str).str.strip().str.lower()
    df['modelo'] = df['modelo'].fillna('').astype(str).str.strip().str.lower()
    anio_actual = ANIO_MAX
    df['antiguedad'] = (anio_actual - df['año']).clip(lower=0)
    df['km_anual'] = np.where(df['antiguedad'] > 0,
                              df['kilometraje'] / df['antiguedad'],
                              df['kilometraje'])
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2. PRECIO JUSTO (peer group ±3 años, ajuste lineal por km)
# ---------------------------------------------------------------------------
def calcular_precio_justo(df):
    fair = np.full(len(df), np.nan)
    ncomp = np.zeros(len(df), dtype=int)
    metodo = np.array([''] * len(df), dtype=object)

    for (ma, mo), g in df.groupby(['marca', 'modelo']):
        yrs = g['año'].values
        kms = g['kilometraje'].values
        prs = g['precio'].values
        idxs = g.index.values
        for y, km, idx in zip(yrs, kms, idxs):
            mask = np.abs(yrs - y) <= 3
            n = int(mask.sum())
            if n < MIN_COMPARABLES:
                continue
            pp, kk = prs[mask], kms[mask]
            ncomp[idx] = n
            p10, p90 = np.percentile(pp, [10, 90])
            pmed = float(np.median(pp))
            if n >= 10:
                lo, hi = np.percentile(pp, [5, 95])
                sel = (pp >= lo) & (pp <= hi)
                if sel.sum() >= 8 and np.ptp(kk[sel]) > 0:
                    b, a = np.polyfit(kk[sel], pp[sel], 1)
                    if b < 0:
                        fair[idx] = float(np.clip(a + b * km, p10, p90))
                        metodo[idx] = 'km_adj'
                        continue
            fair[idx] = pmed
            metodo[idx] = 'mediana'

    df['precio_justo'] = fair
    df['comparables'] = ncomp
    df['metodo'] = metodo
    valido = df['precio_justo'].notna()
    df['descuento_pct'] = np.where(
        valido, (df['precio_justo'] - df['precio']) / df['precio_justo'] * 100, np.nan)
    df['op_precio'] = (df['descuento_pct'] >= DESCUENTO_MIN) & valido
    df['op_km'] = (df['km_anual'] < KM_ANUAL_MAX) & (df['antiguedad'] >= 1)
    df['op_oro'] = df['op_precio'] & df['op_km']
    return df


# ---------------------------------------------------------------------------
# 3. ROTACION (comparando capturas consecutivas)
# ---------------------------------------------------------------------------
def calcular_rotacion(capturas):
    """
    capturas: lista de dicts {fecha, df_limpio, ids:set}
    Mide, entre la primera y la ultima captura, que avisos desaparecieron
    (proxy de venta) y calcula tasa de salida por modelo.
    """
    if len(capturas) < 2:
        return None

    prim = capturas[0]
    ult = capturas[-1]
    dias = (ult['fecha'] - prim['fecha']).days or 1

    ids_prim = prim['ids']
    ids_ult = ult['ids']
    desaparecidos = ids_prim - ids_ult       # estaban, ya no -> proxy venta
    nuevos = ids_ult - ids_prim
    sobreviven = ids_prim & ids_ult

    dprim = prim['df'].set_index('id')

    # rotacion global
    glob = {
        'fecha_desde': prim['fecha'].strftime('%Y-%m-%d'),
        'fecha_hasta': ult['fecha'].strftime('%Y-%m-%d'),
        'dias': int(dias),
        'avisos_inicio': len(ids_prim),
        'avisos_fin': len(ids_ult),
        'desaparecidos': len(desaparecidos),
        'nuevos': len(nuevos),
        'tasa_salida_periodo': round(len(desaparecidos) / len(ids_prim) * 100, 1),
        'tasa_salida_diaria': round(len(desaparecidos) / len(ids_prim) / dias * 100, 2),
    }

    # rotacion por modelo: de los que estaban el dia 1, cuantos se fueron
    df_des = dprim.loc[list(desaparecidos)]
    base_modelo = dprim.groupby(['marca', 'modelo']).size()
    fueron_modelo = df_des.groupby(['marca', 'modelo']).size()
    rot = pd.DataFrame({'inicio': base_modelo, 'salieron': fueron_modelo}).fillna(0)
    rot['salieron'] = rot['salieron'].astype(int)
    rot = rot[rot['inicio'] >= 1]
    rot['tasa_salida'] = (rot['salieron'] / rot['inicio'] * 100).round(1)
    # categoria de inventario: el corte en 10 separa rotacion confiable de la ruidosa
    rot['inventario'] = np.where(rot['inicio'] >= 10, 'alto', 'bajo')
    # dias estimados para vender (vida media): dias del periodo / fraccion vendida
    rot['dias_venta_est'] = np.where(
        rot['salieron'] > 0,
        (dias / (rot['salieron'] / rot['inicio'])).round(0),
        np.nan)

    def cap(s):
        return ' '.join(w.capitalize() for w in str(s).split())

    por_modelo = []
    for (ma, mo), r in rot.iterrows():
        por_modelo.append({
            'marca': cap(ma), 'modelo': cap(mo),
            'stock': int(r['inicio']),
            'salieron': int(r['salieron']),
            'tasa_salida': float(r['tasa_salida']),
            'dias_venta_est': None if np.isnan(r['dias_venta_est']) else int(r['dias_venta_est']),
            'inventario': r['inventario'],
            'confiable': bool(r['inventario'] == 'alto'),
        })
    por_modelo.sort(key=lambda x: x['tasa_salida'], reverse=True)

    # cambios de precio en los que sobreviven
    dult = ult['df'].set_index('id')
    comun = list(sobreviven)
    p0 = dprim.loc[comun, 'precio']
    p1 = dult.loc[comun, 'precio']
    cambio = (p0 != p1)
    bajaron = (p1 < p0)
    glob['con_cambio_precio'] = int(cambio.sum())
    glob['bajaron_precio'] = int((cambio & bajaron).sum())
    glob['subieron_precio'] = int((cambio & ~bajaron).sum())

    return {'global': glob, 'por_modelo': por_modelo}


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    if not os.path.isdir(CARPETA_CAPTURAS):
        sys.exit(f"No existe la carpeta '{CARPETA_CAPTURAS}'. Crea la carpeta y "
                 f"pone adentro los .xlsx de cada dia.")

    archivos = sorted(glob.glob(os.path.join(CARPETA_CAPTURAS, "*.xlsx")))
    if not archivos:
        sys.exit(f"No hay archivos .xlsx en '{CARPETA_CAPTURAS}'.")

    log(f"Capturas encontradas: {len(archivos)}")
    capturas = []
    for path in archivos:
        df = cargar_captura(path)
        fecha = fecha_de_captura(df)
        dfl = limpiar(df)
        capturas.append({'fecha': fecha, 'df': dfl, 'ids': set(dfl['id'])})
        log(f"  {os.path.basename(path)} -> {fecha.date()} | "
            f"{len(df)} filas, {len(dfl)} limpias")

    capturas.sort(key=lambda c: c['fecha'])

    # Analisis de oportunidades sobre la captura mas reciente
    reciente = capturas[-1]
    log(f"Calculando precio justo sobre captura {reciente['fecha'].date()} ...")
    dfa = calcular_precio_justo(reciente['df'].copy())

    # Rotacion
    log("Calculando rotacion entre capturas ...")
    rotacion = calcular_rotacion(capturas)

    # Resumen para el JSON
    # Detalle de oportunidades para el dashboard (top por categoria)
    def cap2(s):
        return ' '.join(w.capitalize() for w in str(s).split())
    vol_modelo = dfa.groupby(['marca', 'modelo'])['precio'].size()

    def fila_op(r):
        return {
            'marca': cap2(r['marca']), 'modelo': cap2(r['modelo']),
            'version': (str(r['version'])[:42] if pd.notna(r['version']) else ''),
            'año': int(r['año']), 'km': int(r['kilometraje']), 'precio': int(r['precio']),
            'precio_justo': int(r['precio_justo']) if pd.notna(r['precio_justo']) else None,
            'descuento': round(float(r['descuento_pct']), 1) if pd.notna(r['descuento_pct']) else None,
            'km_anual': int(r['km_anual']),
            'entidad': r['entidad'], 'comparables': int(r['comparables']),
            'mercado': int(vol_modelo.get((r['marca'], r['modelo']), 0)),
            'url': r['url'] if pd.notna(r['url']) else '',
            'f_oro': bool(r['op_oro']), 'f_precio': bool(r['op_precio']), 'f_km': bool(r['op_km']),
        }

    valido = dfa[dfa['comparables'] >= MIN_COMPARABLES]
    pool = pd.concat([
        valido[valido['op_oro']].sort_values('descuento_pct', ascending=False).head(200),
        valido[valido['op_precio']].sort_values('descuento_pct', ascending=False).head(200),
        valido[valido['op_km']].sort_values('km_anual').head(200),
    ]).drop_duplicates(subset='id')
    oportunidades = [fila_op(r) for _, r in pool.iterrows()]

    salida = {
        'generado': datetime.now().isoformat(timespec='seconds'),
        'capturas': [c['fecha'].strftime('%Y-%m-%d') for c in capturas],
        'captura_analizada': reciente['fecha'].strftime('%Y-%m-%d'),
        'resumen': {
            'total': int(len(dfa)),
            'precio_mediano': int(dfa['precio'].median()),
            'op_oro': int(dfa['op_oro'].sum()),
            'op_precio': int(dfa['op_precio'].sum()),
            'op_km': int(dfa['op_km'].sum()),
        },
        'oportunidades': oportunidades,
        'rotacion': rotacion,
    }

    with open(SALIDA, 'w', encoding='utf-8') as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    log(f"Listo. Escrito '{SALIDA}'.")
    # Reporte en pantalla
    print("\n--- RESUMEN ---")
    print(f"Capturas: {', '.join(salida['capturas'])}")
    r = salida['resumen']
    print(f"Captura analizada: {salida['captura_analizada']} ({r['total']} avisos limpios)")
    print(f"Oportunidades -> oro: {r['op_oro']} | bajo precio: {r['op_precio']} | bajo km: {r['op_km']}")
    if rotacion:
        g = rotacion['global']
        print(f"\nRotacion {g['fecha_desde']} -> {g['fecha_hasta']} ({g['dias']} dias):")
        print(f"  Salieron del mercado: {g['desaparecidos']} de {g['avisos_inicio']} "
              f"({g['tasa_salida_periodo']}% | {g['tasa_salida_diaria']}%/dia)")
        print(f"  Cambios de precio: {g['con_cambio_precio']} "
              f"(bajaron {g['bajaron_precio']}, subieron {g['subieron_precio']})")
        alto = [m for m in rotacion['por_modelo'] if m['inventario'] == 'alto']
        bajo = [m for m in rotacion['por_modelo'] if m['inventario'] == 'bajo']
        print(f"\n  Modelos por inventario: {len(alto)} alto (>=10) | {len(bajo)} bajo (<10)")
        print("\n  ALTO INVENTARIO - rotacion confiable, mas rapidos:")
        for m in alto[:8]:
            dv = f"~{m['dias_venta_est']}d" if m['dias_venta_est'] else "s/d"
            print(f"    {m['marca']} {m['modelo']}: {m['tasa_salida']}% "
                  f"({m['salieron']}/{m['stock']}, venta est. {dv})")


if __name__ == '__main__':
    main()
