"""Autoprueba: comprueba el programa ya empaquetado en el equipo donde se va a usar.

Se corre con `GraficadorEncuestas --autoprueba <carpeta>`. Trabaja sobre una base
temporal (no toca los datos del usuario), deja las gráficas y un reporte en la
carpeta y devuelve código 0 si todo pasó. Así se prueba en Windows, macOS y Linux
sin abrir la ventana a mano.
"""
import platform
import sys
import tempfile
from pathlib import Path

from . import VERSION, graficas
from .datos import DATOS_ORIGINALES, Almacen, ErrorValidacion


def ejecutar(carpeta):
    salida = Path(carpeta)
    salida.mkdir(parents=True, exist_ok=True)
    resultados = []

    def caso(nombre, funcion):
        try:
            funcion()
            resultados.append((True, nombre, ""))
        except Exception as e:  # la autoprueba reporta cualquier falla, no solo las esperadas
            resultados.append((False, nombre, f"{type(e).__name__}: {e}"))

    def rechaza(funcion, texto):
        try:
            funcion()
        except ErrorValidacion as e:
            assert texto.lower() in str(e).lower(), f"rechazó con otro motivo: {e}"
            return
        raise AssertionError("debía rechazar el dato y lo aceptó")

    with tempfile.TemporaryDirectory() as tmp:
        a = Almacen(Path(tmp) / "prueba.db")

        def carga_inicial():
            assert [(d["nombre"], d["cantidad"]) for d in a.categorias()] == list(DATOS_ORIGINALES)
            assert a.estado_suma()["cuadra"] and a.total() == 100
        caso("Carga los datos de la guía y suman 100", carga_inicial)
        caso("Rechaza nombre vacío", lambda: rechaza(lambda: a.agregar("  ", 3), "nombre"))
        caso("Rechaza nombre repetido aunque cambie tildes y mayúsculas",
             lambda: rechaza(lambda: a.agregar("LEER ", 1), "ya existe"))
        caso("Rechaza cantidad negativa", lambda: rechaza(lambda: a.agregar("Dormir", "-2"), "negativa"))
        caso("Rechaza cantidad con decimales", lambda: rechaza(lambda: a.agregar("Dormir", "2.5"), "entero"))
        caso("Rechaza texto en la cantidad", lambda: rechaza(lambda: a.agregar("Dormir", "dos"), "entero"))
        caso("Rechaza pasar de la población", lambda: rechaza(lambda: a.agregar("Dormir", 1), "población"))

        def crud():
            a.cambiar_poblacion(110)
            nuevo = a.agregar("Dormir", 10)
            assert a.estado_suma()["cuadra"]
            a.actualizar(nuevo, "Dormir siesta", 6)
            assert a.estado_suma()["faltan"] == 4
            a.eliminar(nuevo)
            assert a.total() == 100
        caso("Agrega, edita y elimina con la suma al día", crud)

        def deshacer():
            assert "Eliminar" in a.deshacer()
            assert any(d["nombre"] == "Dormir siesta" for d in a.categorias())
        caso("Deshacer recupera lo eliminado", deshacer)

        def trazabilidad():
            assert a.diferencias_con_originales(), "debía reportar diferencias"
            a.restaurar_originales()
            assert a.diferencias_con_originales() == []
            historial = [(f["accion"], f["deshecho"]) for f in reversed(a.bitacora())]
            esperado = [("Carga inicial", 0), ("Población", 0), ("Agregar", 0), ("Editar", 0),
                        ("Eliminar", 1), ("Deshacer", 0), ("Restaurar", 0)]
            assert historial == esperado, f"bitácora inesperada: {historial}"
        caso("Bitácora y restauración dejan rastro hasta los datos originales", trazabilidad)

        def csv_ida_y_vuelta():
            ruta = salida / "encuesta-exportada.csv"
            a.exportar_csv(ruta)
            a.agregar("Temporal", 0)
            assert a.importar_csv(ruta) == 6
            assert [(d["nombre"], d["cantidad"]) for d in a.categorias()] == list(DATOS_ORIGINALES)
        caso("Exporta e importa CSV sin perder datos", csv_ida_y_vuelta)

        def csv_malo():
            malo = Path(tmp) / "malo.csv"
            malo.write_text("actividad;cantidad\nCine;5\nCine;3\nTeatro;x\n", encoding="utf-8")
            antes = a.categorias()
            rechaza(lambda: a.importar_csv(malo), "no se importó")
            assert a.categorias() == antes, "un CSV con errores no debe cambiar nada"
        caso("Un CSV con errores no cambia nada", csv_malo)

        for tipo in graficas.TIPOS:
            caso(f"Genera la gráfica {graficas.TIPOS[tipo][0]}",
                 lambda tipo=tipo: graficas.exportar(salida / f"grafica-{tipo}.png", tipo, a.categorias(),
                                                     a.poblacion, a.titulo))
        caso("Gráfica sin datos no falla", lambda: graficas.exportar(salida / "grafica-vacia.png", "barras", [], 100, "Vacía"))
        caso("Ventana", lambda: _prueba_ventana(Path(tmp) / "ventana.db"))
        a.cerrar()

    lineas = [f"Graficador de Encuestas {VERSION} · autoprueba",
              f"Sistema: {platform.system()} {platform.release()} · Python {platform.python_version()}"
              f" · {'ejecutable empaquetado' if getattr(sys, 'frozen', False) else 'código fuente'}", ""]
    lineas += [f"{'OK  ' if ok else 'FALLA'} {n}" + (f"  -> {d}" if d else "") for ok, n, d in resultados]
    aprobadas = sum(ok for ok, _, _ in resultados)
    lineas += ["", f"{aprobadas} de {len(resultados)} pruebas aprobadas."]
    (salida / "reporte.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))
    return aprobadas == len(resultados)


def _prueba_ventana(ruta_db):
    """Abre la ventana real, usa el formulario y cambia de gráfica. Si no hay pantalla, lo dice."""
    import tkinter as tk
    from .interfaz import Aplicacion
    try:
        raiz = tk.Tk()
    except tk.TclError as e:
        raise RuntimeError(f"sin pantalla disponible ({e})")
    almacen = Almacen(ruta_db)
    try:
        app = Aplicacion(raiz, almacen)
        raiz.update()
        app.poblacion.set("120")
        app.aplicar_encuesta()
        app.nombre.set("Dormir")
        app.cantidad.set("12")
        app.guardar()
        assert len(app.arbol.get_children()) == 7, "la tabla no mostró la actividad nueva"
        app.nombre.set("Cocinar")
        app.cantidad.set("abc")
        app.guardar()
        assert "entero" in app.aviso.cget("text"), "la ventana no mostró el error de validación"
        for tipo in graficas.TIPOS:
            app.tipo.set(tipo)
            app.redibujar()
            raiz.update()
    finally:
        almacen.cerrar()
        raiz.destroy()
