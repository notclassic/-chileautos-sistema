# -*- coding: utf-8 -*-
"""
panel.py — Panel de control local del sistema Chileautos
========================================================

Levanta http://localhost:8777 y ejecuta las corridas que le piden los botones
(los de esta página o los de la barra del dashboard). Cada corrida se abre en
su propia ventana de comandos para ver el progreso.

Esto corre EN ESTA PC: una página web no puede ejecutar programas por sí
sola; este mini servidor local es el que los lanza.

Uso:  doble clic en DASHBOARD.bat (lo arranca de fondo) o PANEL.bat (lo abre).
Cerrar: Ctrl+C en la ventana del panel.
"""

import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

PUERTO = 8777
CARPETA = os.path.dirname(os.path.abspath(__file__))


# Título fijo de la ventana de corrida: permite cerrarla con taskkill.
TITULO_CORRIDA = "ChileautosCorrida"


def lanzar_en_ventana(titulo, comando):
    """Abre una ventana de cmd nueva que ejecuta el comando y queda abierta.
    El título real es fijo (TITULO_CORRIDA) para poder detenerla desde el
    dashboard; se muestra el título descriptivo dentro de la ventana."""
    os.system(f'start "{TITULO_CORRIDA}" cmd /k "cd /d "{CARPETA}" '
              f'&& echo === {titulo} === && {comando}"')


def acciones(params):
    """Arma los comandos según el límite y el selector de teléfonos."""
    limite = params.get("limite", ["800"])[0]
    try:
        limite = str(max(1, int(limite)))
    except ValueError:
        limite = "300"
    tel = " --telefonos" if params.get("tel", ["0"])[0] == "1" else ""

    def _cmd_continuar(_tel):
        etapa = ""
        try:
            with open(os.path.join(CARPETA, "etapa_actual.txt"),
                      encoding="utf-8", errors="replace") as f:
                etapa = f.read().strip()
        except OSError:
            pass
        pasos = [
            ("1/5", f"(echo 1/5 bajando catalogo)> etapa_actual.txt"
                    f" & python actualizar_incremental.py{_tel}"),
            ("2/5", "(echo 2/5 descripciones)> etapa_actual.txt"
                    " && python enriquecer_comentarios.py --solo-nuevos"),
            ("3/5", "(echo 3/5 fichas tecnicas)> etapa_actual.txt"
                    " && python bajar_especificaciones.py --solo-nuevos --limite 0"),
            ("4/5", "(echo 4/5 relleno historico)> etapa_actual.txt"
                    " && python relleno_condicional.py"),
            ("5/5", "(echo 5/5 clasificar y armar)> etapa_actual.txt"
                    " && python clasificar_ia.py && python ver_comentarios.py"),
        ]
        desde = 0
        for i, (tag, _) in enumerate(pasos):
            if etapa.startswith(tag):
                desde = i
                break
        cola = " && ".join(c.lstrip(" &") for _, c in pasos[desde:])
        return ("python marcar.py inicio & " + cola
                + " && (echo listo)> etapa_actual.txt && python marcar.py fin")
    con_tel = " CON telefonos" if tel else ""
    return {
        # LA corrida diaria, en orden: base -> descripciones de nuevos ->
        # specs de nuevos -> clasificar + motor + dashboard.
        "todo": (
            "Bajar base" + con_tel,
            f"python marcar.py inicio"
            f" & (echo 1/5 bajando catalogo)> etapa_actual.txt"
            f" & python actualizar_incremental.py{tel}"
            f" && (echo 2/5 descripciones)> etapa_actual.txt"
            f" && python enriquecer_comentarios.py --solo-nuevos"
            f" && (echo 3/5 fichas tecnicas)> etapa_actual.txt"
            f" && python bajar_especificaciones.py --solo-nuevos --limite 0"
            f" && (echo 4/5 relleno historico)> etapa_actual.txt"
            f" && python relleno_condicional.py"
            f" && (echo 5/5 clasificar y armar)> etapa_actual.txt"
            f" && python clasificar_ia.py && python ver_comentarios.py"
            f" && (echo listo)> etapa_actual.txt && python marcar.py fin",
        ),
        # retoma la cadena DESDE la etapa donde quedo etapa_actual.txt
        "continuar": (
            "Continuar la bajada donde quedo",
            _cmd_continuar(tel),
        ),
        # Piezas sueltas, para recuperación
        "incremental": (
            "Solo base" + con_tel,
            f"python marcar.py inicio & python actualizar_incremental.py{tel}"
            f" && python actualizar.py --solo-motor && python marcar.py fin",
        ),
        # espejo de la cadena, para retomar donde se cayó (sin límite)
        "descripciones": (
            "Descripciones de los nuevos",
            "python enriquecer_comentarios.py --solo-nuevos",
        ),
        "specs": (
            "Especificaciones de los nuevos",
            "python bajar_especificaciones.py --solo-nuevos --limite 0",
        ),
        # relleno del fondo histórico, en tandas con fusible
        "descripciones_viejas": (
            f"Rellenar descripciones antiguas (hasta {limite})",
            f"python enriquecer_comentarios.py --limite {limite}",
        ),
        "specs_viejas": (
            f"Rellenar specs antiguas (hasta {limite})",
            f"python bajar_especificaciones.py --limite {limite}",
        ),
        "regenerar": (
            "Regenerar dashboard (motor + armado)",
            "python ver_comentarios.py",
        ),
        "clasificar": (
            "Clasificar comentarios (IA + palabras) + dashboard",
            "python clasificar_ia.py && python ver_comentarios.py",
        ),
        "dashboard": (
            "Recalcular motor + dashboard",
            "python actualizar.py --solo-motor",
        ),
        # Operación ocasional pesada (horas): la descarga total clásica
        "completa": (
            "Base completa (con telefonos)",
            "DESCARGAR_BASE.bat",
        ),
    }


PAGINA = """<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Panel Chileautos</title>
<style>
  body{{font-family:system-ui,sans-serif;background:#eef3f8;color:#16314a;margin:0;padding:32px}}
  .card{{background:#fff;border:1px solid #dde6ee;border-radius:12px;padding:20px 24px;max-width:560px;
        margin:0 auto 16px;box-shadow:0 1px 3px rgba(20,49,74,.08)}}
  h1{{font-size:20px;margin:0 auto 20px;max-width:560px}}
  h2{{font-size:15px;margin:0 0 6px}}
  p{{font-size:13px;color:#5e7488;margin:0 0 14px}}
  button{{background:#1689d4;color:#fff;border:none;border-radius:8px;padding:10px 18px;
         font-size:14px;font-weight:600;cursor:pointer;margin:0 8px 8px 0}}
  button.sec{{background:#fff;color:#1689d4;border:1px solid #1689d4}}
  button:hover{{opacity:.88}}
  input[type=number]{{width:90px;padding:8px;border:1px solid #dde6ee;border-radius:8px;font-size:14px}}
  label{{font-size:13px}}
  .aviso{{background:#fff7ec;border:1px solid #f4c894;border-radius:10px;padding:12px 16px;
         max-width:560px;margin:0 auto 20px;font-size:13px;color:#7a4b12}}
  .ok{{color:#1a9b54;font-weight:600;font-size:13px;margin-left:10px}}
</style></head><body>
<h1>Panel Chileautos</h1>
<div class="aviso">Cada botón abre una ventana negra con el progreso. Una corrida a la
vez: no lances otra hasta que termine la anterior.</div>

<div class="card">
  <h2>Bajar base</h2>
  <p>La corrida completa en orden: base &rarr; descripciones de los nuevos &rarr;
     specs de los nuevos &rarr; clasificar y dashboard.</p>
  <label><input type="checkbox" id="tel"> incluir teléfonos de los nuevos</label>
  &nbsp;&nbsp; límite por goteo: <input type="number" id="limite" value="800" min="1">
  <div style="margin-top:12px"><button onclick="ir('todo',this)">&#9654; Bajar base</button></div>
</div>

<div class="card">
  <h2>Por partes (recuperación)</h2>
  <p>Si una corrida se cayó a mitad de camino, corré solo la pieza que faltó.
     Usan el mismo selector y límite de arriba.</p>
  <button class="sec" onclick="ir('incremental',this)">Solo base</button>
  <button class="sec" onclick="ir('descripciones',this)">Solo descripciones</button>
  <button class="sec" onclick="ir('specs',this)">Solo specs</button>
  <button class="sec" onclick="ir('clasificar',this)">Clasificar + dashboard</button>
  <button class="sec" onclick="ir('dashboard',this)">Recalcular dashboard</button>
</div>

<div class="card">
  <h2>Base completa (lenta, horas)</h2>
  <p>La descarga total clásica con teléfonos de toda la base. Solo para refrescos
     ocasionales.</p>
  <button class="sec" onclick="ir('completa',this)">Descargar base completa</button>
</div>

<script>
function ir(a, btn){{
  const lim = document.getElementById('limite').value || 300;
  const tel = document.getElementById('tel').checked ? 1 : 0;
  fetch('/lanzar?a=' + a + '&limite=' + lim + '&tel=' + tel).then(r => r.text()).then(t => {{
    const s = document.createElement('span'); s.className = 'ok'; s.textContent = '✓ lanzado';
    btn.after(s); setTimeout(() => s.remove(), 4000);
  }});
}}
</script>
</body></html>"""


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/depurar_versiones":
            # Correcciones de versiones por modelo (herramienta Arreglar versiones).
            # Guarda en correcciones_versiones.json: {modelo_key: {renombres, fusiones, excluidas}}
            import json as _json
            try:
                n = int(self.headers.get("Content-Length", 0))
                datos = _json.loads(self.rfile.read(n).decode("utf-8"))
                ruta = os.path.join(CARPETA, "correcciones_versiones.json")
                existentes = {}
                if os.path.exists(ruta):
                    try:
                        with open(ruta, encoding="utf-8") as f:
                            existentes = _json.load(f)
                    except Exception:
                        pass
                    import shutil
                    from datetime import datetime as _dtv
                    resp = os.path.join(CARPETA, "respaldos")
                    os.makedirs(resp, exist_ok=True)
                    shutil.copy2(ruta, os.path.join(resp,
                        f"correcciones_versiones_{_dtv.now().strftime('%Y-%m-%d_%H-%M')}.json"))
                mod = datos.get("modelo")
                existentes[mod] = datos.get("cambios", {})
                tmp = ruta + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    _json.dump(existentes, f, ensure_ascii=False, indent=1)
                os.replace(tmp, ruta)
                print(f"[panel] Versiones del modelo {mod} corregidas desde el dashboard.")
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"ok")
            except Exception as e:
                self.send_response(500)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(str(e).encode())
            return
        if u.path == "/depurar_aviso":
            # Correcciones POR AVISO (confirmadas mirando las fotos):
            # {"cl-ad-123": {"gen": "III"}} o {"cl-ad-123": {"excluir": true}}
            import json as _json
            try:
                n = int(self.headers.get("Content-Length", 0))
                datos = _json.loads(self.rfile.read(n).decode("utf-8"))
                ruta = os.path.join(CARPETA, "correcciones_avisos.json")
                existentes = {}
                if os.path.exists(ruta):
                    try:
                        with open(ruta, encoding="utf-8") as f:
                            existentes = _json.load(f)
                    except Exception:
                        pass
                    import shutil
                    from datetime import datetime as _dta
                    carpeta_resp = os.path.join(CARPETA, "respaldos")
                    os.makedirs(carpeta_resp, exist_ok=True)
                    shutil.copy2(ruta, os.path.join(
                        carpeta_resp,
                        f"correcciones_avisos_{_dta.now().strftime('%Y-%m-%d_%H-%M')}.json"))
                import csv as _csva
                from datetime import datetime as _dta2
                log_path = os.path.join(CARPETA, "depuracion_log.csv")
                log_nuevo = not os.path.exists(log_path)
                with open(log_path, "a", encoding="utf-8", newline="") as lf:
                    w = _csva.writer(lf)
                    if log_nuevo:
                        w.writerow(["fecha", "clave", "campo",
                                    "valor_anterior", "valor_nuevo"])
                    ahora = _dta2.now().strftime("%Y-%m-%d %H:%M")
                    for vid, cambio in datos.items():
                        previo = existentes.get(vid) or {}
                        for campo in ("gen", "version", "excluir"):
                            if campo in cambio and cambio.get(campo) != previo.get(campo):
                                w.writerow([ahora, f"aviso:{vid}", campo,
                                            previo.get(campo, ""),
                                            cambio.get(campo, "")])
                for vid, cambio in datos.items():
                    existentes[vid] = {**(existentes.get(vid) or {}), **cambio}
                tmp = ruta + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    _json.dump(existentes, f, ensure_ascii=False, indent=1)
                os.replace(tmp, ruta)
                print(f"[panel] Fotos: {len(datos)} correcciones de aviso guardadas.")
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"ok")
            except Exception as e:
                self.send_response(500)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(str(e).encode())
            return
        if u.path == "/depurar":
            import json as _json
            try:
                n = int(self.headers.get("Content-Length", 0))
                datos = _json.loads(self.rfile.read(n).decode("utf-8"))
                ruta = os.path.join(CARPETA, "versiones_canonicas.json")
                existentes = {}
                if os.path.exists(ruta):
                    try:
                        with open(ruta, encoding="utf-8") as f:
                            existentes = _json.load(f)
                    except Exception:
                        pass
                # --- Respaldo con fecha antes de tocar nada ---
                if os.path.exists(ruta):
                    import shutil
                    from datetime import datetime as _dt
                    carpeta_resp = os.path.join(CARPETA, "respaldos")
                    os.makedirs(carpeta_resp, exist_ok=True)
                    marca_t = _dt.now().strftime("%Y-%m-%d_%H-%M")
                    shutil.copy2(ruta, os.path.join(
                        carpeta_resp, f"versiones_canonicas_{marca_t}.json"))

                # --- Bitácora append-only: qué cambió, de qué a qué ---
                import csv as _csv
                from datetime import datetime as _dt2
                log_path = os.path.join(CARPETA, "depuracion_log.csv")
                log_nuevo = not os.path.exists(log_path)
                with open(log_path, "a", encoding="utf-8", newline="") as lf:
                    w = _csv.writer(lf)
                    if log_nuevo:
                        w.writerow(["fecha", "clave", "campo",
                                    "valor_anterior", "valor_nuevo"])
                    ahora = _dt2.now().strftime("%Y-%m-%d %H:%M")
                    for clave, cambio in datos.items():
                        previo = existentes.get(clave) or {}
                        for campo in ("canonica", "excluir"):
                            if campo in cambio and cambio.get(campo) != previo.get(campo):
                                w.writerow([ahora, clave, campo,
                                            previo.get(campo, ""),
                                            cambio.get(campo, "")])

                existentes.update(datos)  # merge: solo pisa las claves enviadas
                tmp = ruta + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    _json.dump(existentes, f, ensure_ascii=False, indent=1)
                os.replace(tmp, ruta)
                print(f"[panel] Depurador: {len(datos)} correcciones guardadas.")
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"ok")
            except Exception as e:
                self.send_response(500)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            cuerpo = PAGINA.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
        elif u.path == "/estado":
            import json as _json
            from datetime import datetime as _dt
            flag = os.path.join(CARPETA, "corrida_en_curso.txt")
            ult = os.path.join(CARPETA, "ultima_base.txt")
            en_curso, inicio, colgada, ultima = False, None, False, None
            if os.path.exists(flag):
                try:
                    inicio = open(flag, encoding="utf-8").read().strip()
                    t0 = _dt.strptime(inicio, "%d-%m-%Y %H:%M")
                    if (_dt.now() - t0).total_seconds() > 12 * 3600:
                        colgada = True   # 12 h sin terminar: algo se cayó (sin tope, un día grande puede tomar 8h)
                    else:
                        en_curso = True
                except Exception:
                    en_curso = True
            if os.path.exists(ult):
                try:
                    ultima = open(ult, encoding="utf-8").read().strip()
                except Exception:
                    pass
            etapa = ""
            try:
                with open(os.path.join(CARPETA, "etapa_actual.txt"),
                          encoding="utf-8", errors="replace") as f:
                    etapa = f.read().strip()
            except OSError:
                pass
            cuerpo = _json.dumps({"en_curso": en_curso, "inicio": inicio,
                                  "etapa": etapa,
                                  "colgada": colgada, "ultima": ultima}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
        elif u.path == "/ping":
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"ok")
        elif u.path == "/detener_corrida":
            # Cierra la ventana de la corrida en curso (taskkill por título)
            # y limpia la marca. Lo ya descargado queda guardado en disco.
            cerrado = False
            if sys.platform == "win32":
                try:
                    rc = os.system(
                        f'taskkill /FI "WINDOWTITLE eq {TITULO_CORRIDA}*" /T /F >nul 2>&1')
                    cerrado = (rc == 0)
                except Exception as e:
                    print(f"[panel] No pude cerrar la ventana: {e}")
            flag = os.path.join(CARPETA, "corrida_en_curso.txt")
            if os.path.exists(flag):
                try:
                    os.remove(flag)
                except Exception:
                    pass
            print("[panel] Corrida detenida desde el dashboard "
                  f"({'ventana cerrada' if cerrado else 'sin ventana activa'}).")
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"1" if cerrado else b"0")
        elif u.path == "/descartar_corrida":
            # Borra la marca de corrida colgada (sin registrarla como exitosa).
            flag = os.path.join(CARPETA, "corrida_en_curso.txt")
            borrado = False
            if os.path.exists(flag):
                try:
                    os.remove(flag)
                    borrado = True
                    print("[panel] Marca de corrida colgada descartada desde el dashboard.")
                except Exception as e:
                    print(f"[panel] No pude borrar la marca: {e}")
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"1" if borrado else b"0")
        elif u.path == "/relleno_estado":
            import json as _json
            ruta = os.path.join(CARPETA, "relleno_activo.txt")
            activo = False
            try:
                activo = open(ruta, encoding="utf-8").read().strip() == "1"
            except Exception:
                activo = False
            cuerpo = _json.dumps({"activo": activo}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
        elif u.path == "/guardar_generaciones":
            # Editar los cortes de generación por modelo, desde el dashboard.
            # Reemplaza las filas de ESE modelo en generaciones.xlsx.
            # Payload: {"marca","modelo","rangos":[{"gen","desde","hasta"},...]}
            import json as _json
            try:
                import pandas as _pd
                n = int(self.headers.get("Content-Length", 0))
                datos = _json.loads(self.rfile.read(n).decode("utf-8"))
                ruta = os.path.join(CARPETA, "generaciones.xlsx")
                # cargar tabla actual (o crear vacía con las columnas correctas)
                cols = ["MARCA", "MODELO", "GENERACION", "AÑO_DESDE", "AÑO_HASTA"]
                if os.path.exists(ruta):
                    df = _pd.read_excel(ruta)
                    # respaldo
                    import shutil
                    from datetime import datetime as _dtg
                    resp = os.path.join(CARPETA, "respaldos")
                    os.makedirs(resp, exist_ok=True)
                    shutil.copy2(ruta, os.path.join(resp,
                        f"generaciones_{_dtg.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"))
                else:
                    df = _pd.DataFrame(columns=cols)
                # normalizar nombres de columna existentes
                df.columns = [str(c).strip().upper() for c in df.columns]
                for c in cols:
                    if c not in df.columns:
                        df[c] = ""
                ma = str(datos.get("marca", "")).strip()
                mo = str(datos.get("modelo", "")).strip()
                # sacar las filas viejas de ese modelo (case-insensitive)
                mask = ~((df["MARCA"].astype(str).str.strip().str.lower() == ma.lower())
                         & (df["MODELO"].astype(str).str.strip().str.lower() == mo.lower()))
                df = df[mask]
                # agregar las nuevas
                filas = []
                for r in datos.get("rangos", []):
                    g = str(r.get("gen", "")).strip()
                    d = r.get("desde"); h = r.get("hasta")
                    if not g or d in (None, ""):
                        continue
                    filas.append({"MARCA": ma, "MODELO": mo, "GENERACION": g,
                                  "AÑO_DESDE": int(d),
                                  "AÑO_HASTA": (int(h) if h not in (None, "") else "")})
                if filas:
                    df = _pd.concat([df, _pd.DataFrame(filas)], ignore_index=True)
                df = df.sort_values(["MARCA", "MODELO", "AÑO_DESDE"], na_position="last")
                tmp = ruta + ".tmp"
                df[cols].to_excel(tmp, index=False, sheet_name="Generaciones")
                os.replace(tmp, ruta)
                print(f"[panel] Generaciones de {ma} {mo} actualizadas desde el dashboard "
                      f"({len(filas)} rangos).")
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"ok")
            except Exception as e:
                self.send_response(500)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(str(e).encode())
            return
        elif u.path == "/relleno_set":
            params = parse_qs(u.query)
            on = params.get("on", ["0"])[0] == "1"
            ruta = os.path.join(CARPETA, "relleno_activo.txt")
            with open(ruta, "w", encoding="utf-8") as f:
                f.write("1" if on else "0")
            print(f"[panel] Relleno histórico {'ACTIVADO' if on else 'en stand by'} "
                  f"desde el dashboard.")
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"1" if on else b"0")
        elif u.path == "/lanzar":
            params = parse_qs(u.query)
            a = params.get("a", [""])[0]
            acc = acciones(params)
            # Candado: con una corrida en curso, no se lanza otra descarga.
            # (clasificar/recalcular sí se permiten: no le pegan a Chileautos)
            flag = os.path.join(CARPETA, "corrida_en_curso.txt")
            descarga = a in ("todo", "incremental", "descripciones", "specs",
                             "descripciones_viejas", "specs_viejas", "completa")
            if descarga and os.path.exists(flag):
                from datetime import datetime as _dt
                try:
                    t0 = _dt.strptime(open(flag, encoding="utf-8").read().strip(), "%d-%m-%Y %H:%M")
                    reciente = (_dt.now() - t0).total_seconds() < 12 * 3600
                except Exception:
                    reciente = True
                if reciente:
                    self.send_response(409)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write("ocupado: ya hay una corrida en curso".encode("utf-8"))
                    return
                os.remove(flag)  # flag viejo de una corrida caída: se limpia y se sigue
            if a in acc:
                titulo, comando = acc[a]
                print(f"[panel] Lanzando: {titulo} -> {comando}")
                lanzar_en_ventana(titulo, comando)
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"ok")
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


def main():
    silencioso = "--silencioso" in sys.argv
    if sys.platform != "win32":
        print("Aviso: este panel abre ventanas con 'start', que es de Windows.")
    try:
        servidor = HTTPServer(("127.0.0.1", PUERTO), Manejador)
    except OSError:
        print("El panel ya estaba corriendo. Esta ventana se puede cerrar.")
        return
    url = f"http://localhost:{PUERTO}"
    print(f"Panel Chileautos en {url}  (Ctrl+C para cerrar)")
    if not silencioso:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nPanel cerrado.")


if __name__ == "__main__":
    main()
