# -*- coding: utf-8 -*-
"""Muestra las ofertas de ayer/hoy desde TU base. Correr:  python ofertas_ayer.py
Lee datos.json (el del dashboard) y responde dos preguntas:
  A) ¿Qué avisos ENTRARON ayer u hoy? (los nuevos)
  B) ¿Cuántas ofertas tiene el archivo completo?
Y exporta los nuevos a nuevos_recientes.csv para abrir en Excel."""
import csv
import json
import os

if not os.path.exists('datos.json'):
    print("No encuentro datos.json. Corre esto en la carpeta del sistema.")
    raise SystemExit(1)

print("Leyendo tu base (30-60 segundos)...")
d = json.load(open('datos.json', encoding='utf-8'))

ops = d.get('oportunidades', [])
oro = [o for o in ops if o.get('f_oro')]
precio = [o for o in ops if o.get('f_precio')]

nuevos = []
for k, rows in (d.get('depuracion_avisos') or {}).items():
    marca, modelo = (k.split('|') + [''])[:2]
    for r in rows:
        dias = r[15] if len(r) > 15 and isinstance(r[15], int) else None
        if dias is not None and 0 <= dias <= 1:
            nuevos.append({
                'marca': marca, 'modelo': modelo, 'gen': r[1] or '',
                'año': r[2] or '', 'version': r[3] or '',
                'km_miles': r[5] or '', 'precio': r[6] or '',
                'dias': dias, 'url': (r[13] if len(r) > 13 else '') or '',
            })

ids_nuevos = None  # oportunidades entre los nuevos
ops_nuevas = [o for o in ops if o.get('dias_publicado') is not None
              and o['dias_publicado'] <= 1 and (o.get('f_oro') or o.get('f_precio'))]

print("=" * 56)
print("B) EL ARCHIVO COMPLETO (captura", d.get('captura_analizada', '?'), ")")
print(f"   {len(ops):,} oportunidades totales | oro: {len(oro):,} | "
      f"bajo precio: {len(precio):,}".replace(',', '.'))
print("   -> Estas se ven en el radar con 'Detectado: siempre'.")
print("-" * 56)
print("A) LO QUE ENTRO AYER U HOY (avisos nuevos)")
print(f"   {len(nuevos)} avisos nuevos | {len(ops_nuevas)} califican como oportunidad")
if len(nuevos) < 100:
    print("   (pocos: el scraper leia 20 paginas; con el parche a 3500,")
    print("    la proxima bajada va a traer cientos por dia)")
print("-" * 56)
for n in sorted(nuevos, key=lambda x: (x['precio'] or 9e12))[:30]:
    p = f"${n['precio']:,}".replace(',', '.') if n['precio'] else '—'
    print(f"   {n['marca']} {n['modelo']} {n['año']} · {p} · "
          f"{'HOY' if n['dias'] == 0 else 'ayer'}")
if len(nuevos) > 30:
    print(f"   ... y {len(nuevos)-30} mas")

with open('nuevos_recientes.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['marca', 'modelo', 'gen', 'año', 'version',
                                      'km_miles', 'precio', 'dias', 'url'])
    w.writeheader()
    w.writerows(nuevos)
print("=" * 56)
print(f"Detalle completo exportado a: nuevos_recientes.csv ({len(nuevos)} filas)")
