"""Gráficas del Graficador de Encuestas.

Cada tipo de gráfica es una función que dibuja sobre una Figure de matplotlib.
No se usa pyplot: la misma función sirve para la ventana (Tkinter) y para
exportar a PNG o PDF sin pantalla.
"""
from matplotlib.figure import Figure

AZUL = "#1F3B63"
GRIS = "#B8B8B8"
TEXTO = "#222222"

# Clave interna -> (nombre visible, cuándo conviene usarla)
TIPOS = {
    "barras": ("Barras verticales",
               "Compara cantidades entre actividades. Es la gráfica que trae la guía."),
    "horizontales": ("Barras horizontales ordenadas",
                     "Ordena de mayor a menor y muestra el porcentaje; los nombres largos se leen completos."),
    "torta": ("Torta (dona)",
              "Muestra qué parte del total es cada actividad. Sirve cuando son pocas categorías."),
    "pareto": ("Pareto",
               "Muestra cuántas actividades concentran la mayor parte de las respuestas."),
}


def _porcentaje(cantidad, poblacion):
    return 100 * cantidad / poblacion if poblacion else 0


def _subtitulo(poblacion, total):
    texto = f"Encuesta a {poblacion} estudiantes"
    if total < poblacion:
        texto += f" · faltan {poblacion - total} por clasificar"
    return texto


def _vacia(fig, titulo):
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.text(0.5, 0.5, "No hay datos para graficar.\nAgregue una actividad en la tabla.",
            ha="center", va="center", fontsize=12, color=TEXTO)
    fig.suptitle(titulo, fontsize=13, fontweight="bold", color=TEXTO)


def _ejes_limpios(ax):
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.tick_params(colors=TEXTO, labelsize=9)


def _corto(nombre, ancho=14):
    """Parte el nombre en dos líneas para que no se monten las etiquetas."""
    if len(nombre) <= ancho or " " not in nombre:
        return nombre
    corte = nombre.rfind(" ", 0, ancho + 1)
    corte = corte if corte > 0 else nombre.find(" ")
    return nombre[:corte] + "\n" + nombre[corte + 1:]


def barras(fig, datos, poblacion, titulo):
    ax = fig.add_subplot(111)
    nombres = [_corto(d["nombre"]) for d in datos]
    valores = [d["cantidad"] for d in datos]
    barras_ = ax.bar(nombres, valores, color=AZUL, width=0.6)
    ax.bar_label(barras_, labels=[str(v) for v in valores], padding=3, fontsize=9, color=TEXTO)
    ax.set_ylabel("Estudiantes", color=TEXTO)
    ax.set_ylim(0, max(valores) * 1.18 if max(valores) else 1)
    _ejes_limpios(ax)


def horizontales(fig, datos, poblacion, titulo):
    ax = fig.add_subplot(111)
    orden = sorted(datos, key=lambda d: d["cantidad"])  # barh dibuja de abajo hacia arriba
    valores = [d["cantidad"] for d in orden]
    barras_ = ax.barh([d["nombre"] for d in orden], valores, color=AZUL, height=0.6)
    ax.bar_label(barras_, labels=[f"{v}  ({_porcentaje(v, poblacion):.0f} %)" for v in valores],
                 padding=4, fontsize=9, color=TEXTO)
    ax.set_xlabel("Estudiantes", color=TEXTO)
    ax.set_xlim(0, max(valores) * 1.3 if max(valores) else 1)
    _ejes_limpios(ax)


def torta(fig, datos, poblacion, titulo):
    ax = fig.add_subplot(111)
    orden = sorted(datos, key=lambda d: -d["cantidad"])
    valores = [d["cantidad"] for d in orden]
    nombres = [d["nombre"] for d in orden]
    total = sum(valores)
    tonos = [_tono(i, len(valores)) for i in range(len(valores))]
    if total < poblacion:  # lo que falta también es parte de la población
        valores.append(poblacion - total)
        nombres.append("Sin clasificar")
        tonos.append(GRIS)
    if sum(valores) == 0:
        _vacia(fig, titulo)
        return
    cuñas, _, textos = ax.pie(valores, colors=tonos, startangle=90, counterclock=False,
                              autopct=lambda p: f"{p:.0f} %" if p >= 4 else "", pctdistance=0.78,
                              wedgeprops={"width": 0.45, "edgecolor": "white", "linewidth": 1.5},
                              textprops={"fontsize": 9})
    for t, color in zip(textos, tonos):
        t.set_color("white" if _es_oscuro(color) else TEXTO)
    ax.legend(cuñas, [f"{n} ({v})" for n, v in zip(nombres, valores)], loc="center left",
              bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=9)
    ax.set_aspect("equal")


def pareto(fig, datos, poblacion, titulo):
    ax = fig.add_subplot(111)
    orden = sorted(datos, key=lambda d: -d["cantidad"])
    valores = [d["cantidad"] for d in orden]
    nombres = [_corto(d["nombre"]) for d in orden]
    ax.bar(nombres, valores, color=AZUL, width=0.6)
    ax.set_ylabel("Estudiantes", color=TEXTO)
    ax.set_ylim(0, max(valores) * 1.18 if max(valores) else 1)
    _ejes_limpios(ax)
    acumulado, suma = [], 0
    for v in valores:
        suma += v
        acumulado.append(_porcentaje(suma, poblacion))
    ax2 = ax.twinx()
    ax2.plot(nombres, acumulado, color=TEXTO, marker="o", linewidth=1.5, markersize=4)
    for x, y in zip(nombres, acumulado):
        ax2.annotate(f"{y:.0f} %", (x, y), textcoords="offset points", xytext=(0, 8),
                     ha="center", fontsize=8, color=TEXTO,
                     bbox={"boxstyle": "round,pad=0.2", "facecolor": "white", "edgecolor": "none"})
    ax2.set_ylim(0, 112)
    ax2.set_ylabel("% acumulado de la población", color=TEXTO)
    ax2.spines["top"].set_visible(False)
    ax2.tick_params(colors=TEXTO, labelsize=9)


def _es_oscuro(color):
    """Para decidir si el porcentaje dentro de la torta va en blanco o en negro."""
    import matplotlib.colors as mc
    r, g, b = mc.to_rgb(color)
    return 0.299 * r + 0.587 * g + 0.114 * b < 0.55


def _tono(i, n):
    """Escala de un solo azul, de oscuro a claro, para la torta."""
    import matplotlib.colors as mc
    oscuro, claro = mc.to_rgb(AZUL), mc.to_rgb("#C9D5E6")
    t = i / max(n - 1, 1)
    return tuple(o + (c - o) * t for o, c in zip(oscuro, claro))


DIBUJAR = {"barras": barras, "horizontales": horizontales, "torta": torta, "pareto": pareto}


def dibujar(fig, tipo, datos, poblacion, titulo):
    """Limpia la figura y dibuja el tipo pedido con los datos actuales."""
    if tipo not in DIBUJAR:
        raise ValueError(f"Tipo de gráfica desconocido: {tipo}")
    fig.clear()
    if not datos:
        _vacia(fig, titulo)
        return fig
    DIBUJAR[tipo](fig, datos, poblacion, titulo)
    total = sum(d["cantidad"] for d in datos)
    fig.suptitle(titulo, fontsize=13, fontweight="bold", color=TEXTO, x=0.02, ha="left")
    fig.text(0.02, 0.905, _subtitulo(poblacion, total), fontsize=9.5, color="#555555", ha="left")
    fig.text(0.02, 0.015, "Fuente: datos ingresados en el Graficador de Encuestas", fontsize=7.5, color="#777777")
    fig.subplots_adjust(top=0.84, bottom=0.17 if tipo in ("barras", "pareto") else 0.1,
                        left=0.26 if tipo == "horizontales" else 0.09,
                        right=0.62 if tipo == "torta" else (0.9 if tipo == "pareto" else 0.96))
    return fig


def exportar(ruta, tipo, datos, poblacion, titulo):
    """Guarda la gráfica en PNG o PDF según la extensión. Funciona sin pantalla."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig = Figure(figsize=(9, 5.4), dpi=100)
    FigureCanvasAgg(fig)
    dibujar(fig, tipo, datos, poblacion, titulo)
    fig.savefig(ruta, dpi=200 if str(ruta).lower().endswith(".png") else None, facecolor="white")
    return ruta
