"""Capa de datos del Graficador de Encuestas.

Guarda las categorías de la encuesta en SQLite, valida todo lo que entra y deja
cada cambio en una bitácora con el estado anterior, para poder deshacerlo y para
que cualquier cifra se pueda rastrear hasta los datos originales de la guía.
"""
import csv
import json
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

FUENTE_ORIGINAL = "Guía 9: encuesta a 100 estudiantes sobre las actividades de su tiempo libre"
TITULO_ORIGINAL = "Actividades realizadas en el tiempo libre"
POBLACION_ORIGINAL = 100
DATOS_ORIGINALES = (
    ("Ver series o películas", 28),
    ("Escuchar música", 22),
    ("Practicar deporte", 18),
    ("Jugar videojuegos", 15),
    ("Leer", 10),
    ("Otras actividades", 7),
)
LARGO_MAXIMO_NOMBRE = 40
NOMBRE_BASE = "datos_encuesta.db"


class ErrorValidacion(ValueError):
    """Dato rechazado. El mensaje está escrito para mostrárselo al usuario tal cual."""


def carpeta_portable():
    """Carpeta donde vive el programa: los datos se guardan al lado, sin instalar nada.

    Si esa carpeta no deja escribir (por ejemplo, un disco protegido de la sala),
    se usa una carpeta en el perfil del usuario.
    """
    if getattr(sys, "frozen", False):
        carpeta = Path(sys.executable).resolve().parent
        if carpeta.name == "MacOS" and carpeta.parent.name == "Contents":
            carpeta = carpeta.parent.parent.parent  # al lado del .app, no adentro
    else:
        carpeta = Path(__file__).resolve().parent.parent
    try:
        prueba = carpeta / ".escritura"
        prueba.write_text("ok", encoding="utf-8")
        prueba.unlink()
        return carpeta
    except OSError:
        respaldo = Path.home() / "GraficadorEncuestas"
        respaldo.mkdir(exist_ok=True)
        return respaldo


def clave_de(nombre):
    """Llave para comparar nombres: sin tildes, sin mayúsculas y sin espacios de más."""
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes).strip().lower()


def validar_nombre(nombre):
    """Devuelve el nombre limpio o lanza ErrorValidacion."""
    limpio = re.sub(r"\s+", " ", str(nombre or "")).strip()
    if not limpio:
        raise ErrorValidacion("Escriba el nombre de la actividad.")
    if len(limpio) > LARGO_MAXIMO_NOMBRE:
        raise ErrorValidacion(f"El nombre tiene {len(limpio)} caracteres; el máximo es {LARGO_MAXIMO_NOMBRE}.")
    if re.fullmatch(r"[\d\s.,]+", limpio):
        raise ErrorValidacion("El nombre no puede ser solo un número.")
    return limpio


def validar_entero(texto, campo, minimo):
    """Convierte a entero un número de estudiantes y revisa que no baje del mínimo."""
    if isinstance(texto, bool):
        raise ErrorValidacion(f"{campo} debe ser un número entero.")
    if isinstance(texto, int):
        valor = texto
    else:
        limpio = str(texto or "").strip()
        if not limpio:
            raise ErrorValidacion(f"Escriba {campo.lower()}.")
        if re.fullmatch(r"-\s*\d+", limpio):
            raise ErrorValidacion(f"{campo} no puede ser negativa.")
        if re.fullmatch(r"\d+[.,]\d+", limpio):
            raise ErrorValidacion(f"{campo} cuenta estudiantes, así que debe ser un número entero, sin decimales.")
        if not re.fullmatch(r"\d+", limpio):
            raise ErrorValidacion(f"{campo} debe ser un número entero; recibí «{limpio}».")
        valor = int(limpio)
    if valor < minimo:
        raise ErrorValidacion(f"{campo} no puede ser menor que {minimo}.")
    return valor


def validar_cantidad(texto):
    return validar_entero(texto, "La cantidad", 0)


def validar_poblacion(texto):
    return validar_entero(texto, "La población", 1)


class Almacen:
    """Base SQLite de la encuesta. Toda escritura pasa por aquí y queda en la bitácora."""

    def __init__(self, ruta=None):
        self.ruta = Path(ruta) if ruta else carpeta_portable() / NOMBRE_BASE
        self.db = sqlite3.connect(self.ruta)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS configuracion (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS datos_originales (
                orden INTEGER PRIMARY KEY, nombre TEXT NOT NULL, cantidad INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                clave TEXT NOT NULL UNIQUE,
                cantidad INTEGER NOT NULL CHECK (cantidad >= 0),
                orden INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS bitacora (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                accion TEXT NOT NULL,
                detalle TEXT NOT NULL,
                estado_previo TEXT NOT NULL,
                deshecho INTEGER NOT NULL DEFAULT 0);
            """
        )
        if not self.db.execute("SELECT 1 FROM datos_originales").fetchone():
            # Primera vez: se guarda la copia fija de la guía y se arranca con ella.
            with self.db:
                self.db.executemany("INSERT INTO datos_originales VALUES (?, ?, ?)",
                                    [(i, n, c) for i, (n, c) in enumerate(DATOS_ORIGINALES, 1)])
                self._poner_estado(self._estado_original())
                self._registrar("Carga inicial", FUENTE_ORIGINAL, self._estado_original())

    # ---------- lectura ----------

    def categorias(self):
        filas = self.db.execute("SELECT id, nombre, cantidad FROM categorias ORDER BY orden, id")
        return [dict(f) for f in filas]

    def config(self, clave):
        fila = self.db.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,)).fetchone()
        return fila["valor"] if fila else None

    @property
    def poblacion(self):
        return int(self.config("poblacion"))

    @property
    def titulo(self):
        return self.config("titulo")

    def total(self):
        return self.db.execute("SELECT COALESCE(SUM(cantidad), 0) FROM categorias").fetchone()[0]

    def estado_suma(self):
        """Coherencia entre la población declarada y lo que suman las categorías."""
        total, poblacion = self.total(), self.poblacion
        faltan = poblacion - total
        if faltan == 0:
            mensaje = f"La suma da {total} de {poblacion}: cuadra con la población."
        else:
            mensaje = f"La suma da {total} de {poblacion}: faltan {faltan} estudiantes por clasificar."
        return {"total": total, "poblacion": poblacion, "faltan": faltan, "cuadra": faltan == 0, "mensaje": mensaje}

    def resumen(self):
        """Mayor y menor categoría, con empates, para el texto bajo la gráfica."""
        datos = self.categorias()
        if not datos:
            return None
        alto = max(d["cantidad"] for d in datos)
        bajo = min(d["cantidad"] for d in datos)
        return {
            "mayor": [d["nombre"] for d in datos if d["cantidad"] == alto], "valor_mayor": alto,
            "menor": [d["nombre"] for d in datos if d["cantidad"] == bajo], "valor_menor": bajo,
        }

    def originales(self):
        filas = self.db.execute("SELECT nombre, cantidad FROM datos_originales ORDER BY orden")
        return [dict(f) for f in filas]

    def diferencias_con_originales(self):
        """Lista en palabras de lo que cambió frente a la guía. Vacía si no cambió nada."""
        actuales = {clave_de(d["nombre"]): d for d in self.categorias()}
        cambios = []
        for o in self.originales():
            a = actuales.pop(clave_de(o["nombre"]), None)
            if a is None:
                cambios.append(f"Se quitó «{o['nombre']}» ({o['cantidad']} en la guía).")
            elif a["cantidad"] != o["cantidad"]:
                cambios.append(f"«{o['nombre']}»: {o['cantidad']} en la guía, {a['cantidad']} ahora.")
        for a in actuales.values():
            cambios.append(f"Se agregó «{a['nombre']}» con {a['cantidad']}.")
        if self.poblacion != POBLACION_ORIGINAL:
            cambios.append(f"Población: {POBLACION_ORIGINAL} en la guía, {self.poblacion} ahora.")
        return cambios

    def bitacora(self):
        filas = self.db.execute("SELECT id, fecha, accion, detalle, deshecho FROM bitacora ORDER BY id DESC")
        return [dict(f) for f in filas]

    # ---------- escritura ----------

    def agregar(self, nombre, cantidad):
        nombre, cantidad = validar_nombre(nombre), validar_cantidad(cantidad)
        self._revisar_repetido(nombre)
        self._revisar_tope(self.total() + cantidad)
        previo = self._estado()
        orden = self.db.execute("SELECT COALESCE(MAX(orden), 0) + 1 FROM categorias").fetchone()[0]
        with self.db:
            cur = self.db.execute("INSERT INTO categorias (nombre, clave, cantidad, orden) VALUES (?, ?, ?, ?)",
                                  (nombre, clave_de(nombre), cantidad, orden))
            self._registrar("Agregar", f"{nombre}: {cantidad}", previo)
        return cur.lastrowid

    def actualizar(self, id_categoria, nombre, cantidad):
        actual = self._buscar(id_categoria)
        nombre, cantidad = validar_nombre(nombre), validar_cantidad(cantidad)
        self._revisar_repetido(nombre, excepto=id_categoria)
        self._revisar_tope(self.total() - actual["cantidad"] + cantidad)
        if nombre == actual["nombre"] and cantidad == actual["cantidad"]:
            return
        previo = self._estado()
        with self.db:
            self.db.execute("UPDATE categorias SET nombre = ?, clave = ?, cantidad = ? WHERE id = ?",
                            (nombre, clave_de(nombre), cantidad, id_categoria))
            self._registrar("Editar", f"{actual['nombre']}: {actual['cantidad']} → {nombre}: {cantidad}", previo)

    def eliminar(self, id_categoria):
        actual = self._buscar(id_categoria)
        previo = self._estado()
        with self.db:
            self.db.execute("DELETE FROM categorias WHERE id = ?", (id_categoria,))
            self._registrar("Eliminar", f"{actual['nombre']}: {actual['cantidad']}", previo)

    def cambiar_poblacion(self, valor):
        valor = validar_poblacion(valor)
        if valor < self.total():
            raise ErrorValidacion(f"Las categorías ya suman {self.total()}; la población no puede ser menor.")
        if valor == self.poblacion:
            return
        previo = self._estado()
        with self.db:
            self._poner_config("poblacion", valor)
            self._registrar("Población", f"{previo['poblacion']} → {valor}", previo)

    def cambiar_titulo(self, titulo):
        titulo = re.sub(r"\s+", " ", str(titulo or "")).strip()
        if not titulo:
            raise ErrorValidacion("El título de la gráfica no puede quedar vacío.")
        if len(titulo) > 80:
            raise ErrorValidacion("El título admite máximo 80 caracteres.")
        if titulo == self.titulo:
            return
        previo = self._estado()
        with self.db:
            self._poner_config("titulo", titulo)
            self._registrar("Título", titulo, previo)

    def restaurar_originales(self):
        previo = self._estado()
        with self.db:
            self._poner_estado(self._estado_original())
            self._registrar("Restaurar", FUENTE_ORIGINAL, previo)

    def deshacer(self):
        """Vuelve al estado anterior al último cambio. Devuelve qué se deshizo, o None."""
        fila = self.db.execute(
            "SELECT id, accion, detalle, estado_previo FROM bitacora "
            "WHERE deshecho = 0 AND accion NOT IN ('Carga inicial', 'Deshacer') ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not fila:
            return None
        previo = self._estado()
        with self.db:
            self._poner_estado(json.loads(fila["estado_previo"]))
            self.db.execute("UPDATE bitacora SET deshecho = 1 WHERE id = ?", (fila["id"],))
            self._registrar("Deshacer", f"{fila['accion']} ({fila['detalle']})", previo)
        return f"{fila['accion']}: {fila['detalle']}"

    def importar_csv(self, ruta):
        """Reemplaza las categorías con las de un CSV (actividad;cantidad). Todo o nada."""
        texto = Path(ruta).read_text(encoding="utf-8-sig")
        try:
            dialecto = csv.Sniffer().sniff(texto[:2048], delimiters=";,\t")
        except csv.Error:
            dialecto = csv.excel
        filas = [f for f in csv.reader(texto.splitlines(), dialecto) if any(c.strip() for c in f)]
        if filas and not re.fullmatch(r"\s*-?\d+([.,]\d+)?\s*", filas[0][1] if len(filas[0]) > 1 else ""):
            filas = filas[1:]  # encabezado
        if not filas:
            raise ErrorValidacion("El archivo no trae filas de datos.")
        nuevas, errores, vistas = [], [], set()
        for n, fila in enumerate(filas, 1):
            try:
                if len(fila) < 2:
                    raise ErrorValidacion("faltan columnas; se esperan actividad y cantidad.")
                nombre, cantidad = validar_nombre(fila[0]), validar_cantidad(fila[1])
                if clave_de(nombre) in vistas:
                    raise ErrorValidacion(f"«{nombre}» está repetida.")
                vistas.add(clave_de(nombre))
                nuevas.append((nombre, cantidad))
            except ErrorValidacion as e:
                errores.append(f"Fila {n}: {e}")
        if errores:
            raise ErrorValidacion("No se importó nada.\n" + "\n".join(errores[:6]))
        suma = sum(c for _, c in nuevas)
        if suma > self.poblacion:
            raise ErrorValidacion(f"El archivo suma {suma} y la población es {self.poblacion}. Ajuste la población primero.")
        previo = self._estado()
        with self.db:
            self._poner_estado({**previo, "categorias": [{"nombre": n, "cantidad": c} for n, c in nuevas]})
            self._registrar("Importar CSV", f"{Path(ruta).name}: {len(nuevas)} categorías", previo)
        return len(nuevas)

    def exportar_csv(self, ruta):
        """Escribe actividad;estudiantes;porcentaje. Con BOM y punto y coma, para que Excel lo abra bien."""
        poblacion = self.poblacion
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["actividad", "estudiantes", "porcentaje"])
            for d in self.categorias():
                w.writerow([d["nombre"], d["cantidad"], f"{100 * d['cantidad'] / poblacion:.1f}".replace(".", ",")])
        return ruta

    def cerrar(self):
        self.db.close()

    # ---------- internos ----------

    def _buscar(self, id_categoria):
        fila = self.db.execute("SELECT id, nombre, cantidad FROM categorias WHERE id = ?", (id_categoria,)).fetchone()
        if not fila:
            raise ErrorValidacion("Esa categoría ya no existe; seleccione otra en la tabla.")
        return dict(fila)

    def _revisar_repetido(self, nombre, excepto=None):
        fila = self.db.execute("SELECT id, nombre FROM categorias WHERE clave = ?", (clave_de(nombre),)).fetchone()
        if fila and fila["id"] != excepto:
            raise ErrorValidacion(f"Ya existe «{fila['nombre']}». Edítela en vez de repetirla.")

    def _revisar_tope(self, nuevo_total):
        if nuevo_total > self.poblacion:
            raise ErrorValidacion(
                f"Con ese dato la suma sería {nuevo_total} y la población es {self.poblacion}. "
                "Revise la cantidad o ajuste la población.")

    def _estado(self):
        return {"poblacion": self.poblacion, "titulo": self.titulo,
                "categorias": [{"nombre": d["nombre"], "cantidad": d["cantidad"]} for d in self.categorias()]}

    @staticmethod
    def _estado_original():
        return {"poblacion": POBLACION_ORIGINAL, "titulo": TITULO_ORIGINAL,
                "categorias": [{"nombre": n, "cantidad": c} for n, c in DATOS_ORIGINALES]}

    def _poner_estado(self, estado):
        """Reemplaza todo el contenido. Se llama dentro de una transacción."""
        self.db.execute("DELETE FROM categorias")
        self.db.executemany("INSERT INTO categorias (nombre, clave, cantidad, orden) VALUES (?, ?, ?, ?)",
                            [(c["nombre"], clave_de(c["nombre"]), c["cantidad"], i)
                             for i, c in enumerate(estado["categorias"], 1)])
        self._poner_config("poblacion", estado["poblacion"])
        self._poner_config("titulo", estado["titulo"])

    def _poner_config(self, clave, valor):
        self.db.execute("INSERT INTO configuracion VALUES (?, ?) ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
                        (clave, str(valor)))

    def _registrar(self, accion, detalle, estado_previo):
        self.db.execute("INSERT INTO bitacora (fecha, accion, detalle, estado_previo) VALUES (?, ?, ?, ?)",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), accion, detalle,
                         json.dumps(estado_previo, ensure_ascii=False)))
