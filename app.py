"""Graficador de Encuestas · punto de entrada.

Uso:
    GraficadorEncuestas                       abre la ventana
    GraficadorEncuestas --autoprueba carpeta  prueba todo sin abrir la ventana y deja un reporte
    GraficadorEncuestas --datos archivo.db    usa otra base de datos
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(prog="GraficadorEncuestas", description="Ingreso de datos y gráficas automáticas.")
    parser.add_argument("--autoprueba", metavar="CARPETA", help="corre la autoprueba y deja el reporte en CARPETA")
    parser.add_argument("--datos", metavar="ARCHIVO", help="ruta de la base SQLite (por defecto, al lado del programa)")
    args = parser.parse_args()

    if args.autoprueba:
        from graficador.autoprueba import ejecutar
        sys.exit(0 if ejecutar(args.autoprueba) else 1)

    from graficador.interfaz import abrir
    abrir(args.datos)


if __name__ == "__main__":
    main()
