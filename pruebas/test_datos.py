"""Pruebas unitarias de la capa de datos y de las gráficas (python -m unittest discover -s pruebas)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graficador import graficas  # noqa: E402
from graficador.datos import (Almacen, DATOS_ORIGINALES, ErrorValidacion, clave_de,  # noqa: E402
                              validar_cantidad, validar_nombre, validar_poblacion)


class Validaciones(unittest.TestCase):
    def test_nombre_se_limpia(self):
        self.assertEqual(validar_nombre("  Ver   series "), "Ver series")

    def test_nombre_invalido(self):
        for malo in ("", "   ", "123", "x" * 41):
            with self.subTest(malo=malo), self.assertRaises(ErrorValidacion):
                validar_nombre(malo)

    def test_cantidad(self):
        self.assertEqual(validar_cantidad(" 28 "), 28)
        self.assertEqual(validar_cantidad(0), 0)
        for malo in ("", "-3", "2.5", "2,5", "veinte", True):
            with self.subTest(malo=malo), self.assertRaises(ErrorValidacion):
                validar_cantidad(malo)

    def test_poblacion_minimo_uno(self):
        with self.assertRaises(ErrorValidacion):
            validar_poblacion("0")

    def test_clave_ignora_tildes_y_mayusculas(self):
        self.assertEqual(clave_de("Escuchar Música"), clave_de("escuchar musica "))


class AlmacenPrueba(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.a = Almacen(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.a.cerrar()
        self.tmp.cleanup()

    def test_arranca_con_la_guia(self):
        self.assertEqual([(d["nombre"], d["cantidad"]) for d in self.a.categorias()], list(DATOS_ORIGINALES))
        self.assertEqual(self.a.poblacion, 100)
        self.assertTrue(self.a.estado_suma()["cuadra"])

    def test_resumen_mayor_y_menor(self):
        r = self.a.resumen()
        self.assertEqual((r["mayor"], r["valor_mayor"]), (["Ver series o películas"], 28))
        self.assertEqual((r["menor"], r["valor_menor"]), (["Otras actividades"], 7))

    def test_no_deja_pasar_la_poblacion(self):
        with self.assertRaises(ErrorValidacion):
            self.a.agregar("Dormir", 1)
        with self.assertRaises(ErrorValidacion):
            self.a.cambiar_poblacion(99)

    def test_editar_no_choca_consigo_mismo(self):
        leer = next(d for d in self.a.categorias() if d["nombre"] == "Leer")
        self.a.actualizar(leer["id"], "leer", 10)  # mismo nombre con otra mayúscula
        self.assertIn("leer", [d["nombre"] for d in self.a.categorias()])

    def test_deshacer_y_restaurar(self):
        self.a.cambiar_poblacion(105)
        self.a.agregar("Dormir", 5)
        self.a.deshacer()
        self.assertEqual(self.a.total(), 100)
        self.a.restaurar_originales()
        self.assertEqual(self.a.diferencias_con_originales(), [])

    def test_persistencia_en_disco(self):
        self.a.cambiar_poblacion(101)
        self.a.agregar("Dormir", 1)
        self.a.cerrar()
        otro = Almacen(self.a.ruta)
        self.assertIn("Dormir", [d["nombre"] for d in otro.categorias()])
        otro.cerrar()
        self.a = Almacen(self.a.ruta)

    def test_csv_con_coma_y_encabezado(self):
        ruta = Path(self.tmp.name) / "c.csv"
        ruta.write_text("Actividad,Cantidad\nCine,40\nTeatro,60\n", encoding="utf-8")
        self.assertEqual(self.a.importar_csv(ruta), 2)
        self.assertEqual(self.a.total(), 100)


class Graficas(unittest.TestCase):
    def test_todas_las_graficas_se_exportan(self):
        datos = [{"nombre": n, "cantidad": c} for n, c in DATOS_ORIGINALES]
        with tempfile.TemporaryDirectory() as tmp:
            for tipo in graficas.TIPOS:
                for ext in ("png", "pdf"):
                    ruta = Path(tmp) / f"{tipo}.{ext}"
                    graficas.exportar(ruta, tipo, datos, 100, "Prueba")
                    self.assertGreater(ruta.stat().st_size, 1000, f"{tipo}.{ext} quedó vacío")


if __name__ == "__main__":
    unittest.main()
