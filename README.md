# Graficador de Encuestas

Programa de escritorio para ingresar los datos de una encuesta, validarlos y graficarlos de forma automática.
Arranca con la encuesta de la Guía 9 de Inteligencia de Negocios (UMB): 100 estudiantes y las actividades
que hacen en su tiempo libre.

## Cómo se usa (sin instalar nada)

1. Descargue el `.zip` de su sistema en la sección **Releases** del repositorio (versión v1.0).
2. Descomprímalo.
3. Windows: abra `GraficadorEncuestas\GraficadorEncuestas.exe`. macOS: abra `GraficadorEncuestas.app`
   (la primera vez, clic derecho y Abrir). Linux: `GraficadorEncuestas/GraficadorEncuestas`.

Los datos se guardan en `datos_encuesta.db`, en la misma carpeta del programa. Si esa carpeta no permite
escribir, se guardan en la carpeta `GraficadorEncuestas` del usuario.

Si Windows muestra "Windows protegió su PC", es porque el ejecutable no tiene firma comercial: clic en
**Más información** y luego en **Ejecutar de todas formas**.

## Qué hace

- Tabla con las actividades, editable: agregar, editar, eliminar, deshacer y restaurar los datos de la guía.
- Validación: nombre obligatorio y sin repetir (aunque cambien tildes o mayúsculas), cantidad entera no
  negativa, y la suma nunca puede pasar de la población declarada. Si no llega, avisa cuántos faltan.
- Bitácora de cambios con la fecha y el estado anterior, y una vista de diferencias con los datos originales.
- Cuatro gráficas que se redibujan solas: barras verticales, barras horizontales ordenadas con porcentaje,
  torta (dona) y Pareto. Se exportan a PNG o PDF.
- Importar y exportar CSV (separado por punto y coma, abre directo en Excel).

## Para desarrolladores

```
pip install -r requirements.txt
python app.py                          # ventana
python app.py --autoprueba salida      # 18 pruebas sin abrir la ventana, deja reporte y gráficas
python -m unittest discover -s pruebas # pruebas unitarias
pyinstaller --onedir --windowed --name GraficadorEncuestas app.py
```

Cada push a `main` compila y prueba el ejecutable en Windows, macOS y Linux con GitHub Actions
(`.github/workflows/compilar.yml`) y publica los `.zip` en la versión v1.0.

| Archivo | Función |
|---|---|
| `app.py` | Punto de entrada y argumentos |
| `graficador/datos.py` | Base SQLite, validaciones, bitácora, deshacer, CSV |
| `graficador/graficas.py` | Los cuatro tipos de gráfica con matplotlib |
| `graficador/interfaz.py` | Ventana en Tkinter |
| `graficador/autoprueba.py` | Prueba del programa empaquetado en el equipo donde corre |
| `pruebas/test_datos.py` | Pruebas unitarias |

Autor: Andrés Felipe Tabares Benavides · Universidad Manuela Beltrán · Inteligencia de Negocios · 2026
