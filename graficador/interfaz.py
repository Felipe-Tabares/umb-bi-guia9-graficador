"""Ventana del Graficador de Encuestas (Tkinter).

A la izquierda la tabla y el formulario para ingresar datos; a la derecha la
gráfica, que se vuelve a dibujar sola cada vez que cambia un dato. La interfaz no
valida nada por su cuenta: todo pasa por graficador.datos, que es la única regla.
"""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from . import VERSION, graficas
from .datos import Almacen, ErrorValidacion

ROJO = "#A4262C"
VERDE = "#2E6B30"


def modo_claro(ventana):
    """En macOS con modo oscuro, Tk pinta la ventana oscura; se fija la apariencia clara para que se vea
    igual que en Windows y los textos grises se lean."""
    if ventana.tk.call("tk", "windowingsystem") == "aqua":
        ventana.update_idletasks()  # Tk exige la ventana creada antes de cambiar la apariencia
        try:
            ventana.tk.call("::tk::unsupported::MacWindowStyle", "appearance", ventana, "aqua")
        except tk.TclError:
            pass


class Aplicacion(ttk.Frame):
    def __init__(self, raiz, almacen):
        super().__init__(raiz, padding=10)
        self.raiz = raiz
        self.almacen = almacen
        self.tipo = tk.StringVar(value="barras")
        self.nombre = tk.StringVar()
        self.cantidad = tk.StringVar()
        self.poblacion = tk.StringVar(value=str(almacen.poblacion))
        self.titulo = tk.StringVar(value=almacen.titulo)
        self.seleccion = None  # id de la categoría que se está editando

        raiz.title(f"Graficador de Encuestas {VERSION}")
        modo_claro(raiz)
        raiz.geometry("1200x720")
        raiz.minsize(1000, 620)
        self.grid(sticky="nsew")
        raiz.columnconfigure(0, weight=1)
        raiz.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._panel_datos().grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        self._panel_grafica().grid(row=0, column=1, sticky="nsew")
        self.barra_estado = ttk.Label(self, anchor="w", foreground="#444444")
        self.barra_estado.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        raiz.bind("<Control-z>", lambda e: self.deshacer())
        raiz.bind("<Command-z>", lambda e: self.deshacer())
        self.refrescar(f"Datos guardados en {almacen.ruta}")

    # ---------- construcción ----------

    def _panel_datos(self):
        panel = ttk.Frame(self)

        encuesta = ttk.LabelFrame(panel, text="Encuesta", padding=8)
        encuesta.pack(fill="x")
        ttk.Label(encuesta, text="Título de la gráfica").grid(row=0, column=0, sticky="w")
        e_titulo = ttk.Entry(encuesta, textvariable=self.titulo, width=34)
        e_titulo.grid(row=1, column=0, sticky="ew")
        e_titulo.bind("<Return>", lambda e: self.aplicar_encuesta())
        ttk.Label(encuesta, text="Población (estudiantes encuestados)").grid(row=2, column=0, sticky="w", pady=(6, 0))
        fila = ttk.Frame(encuesta)
        fila.grid(row=3, column=0, sticky="ew")
        e_pob = ttk.Entry(fila, textvariable=self.poblacion, width=8)
        e_pob.pack(side="left")
        e_pob.bind("<Return>", lambda e: self.aplicar_encuesta())
        ttk.Button(fila, text="Aplicar", command=self.aplicar_encuesta).pack(side="left", padx=6)

        tabla = ttk.LabelFrame(panel, text="Actividades", padding=8)
        tabla.pack(fill="both", expand=True, pady=8)
        self.arbol = ttk.Treeview(tabla, columns=("nombre", "cantidad", "pct"), show="headings", height=7,
                                  selectmode="browse")
        for col, texto, ancho, ali in (("nombre", "Actividad", 200, "w"), ("cantidad", "Estudiantes", 80, "e"),
                                       ("pct", "%", 55, "e")):
            self.arbol.heading(col, text=texto)
            self.arbol.column(col, width=ancho, anchor=ali, stretch=col == "nombre")
        self.arbol.pack(fill="both", expand=True)
        self.arbol.bind("<<TreeviewSelect>>", self._al_seleccionar)
        self.suma = ttk.Label(tabla, wraplength=330)
        self.suma.pack(fill="x", pady=(6, 0))

        form = ttk.LabelFrame(panel, text="Agregar o editar", padding=8)
        form.pack(fill="x")
        ttk.Label(form, text="Actividad").grid(row=0, column=0, sticky="w")
        self.e_nombre = ttk.Entry(form, textvariable=self.nombre, width=26)
        self.e_nombre.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        ttk.Label(form, text="Estudiantes").grid(row=0, column=1, sticky="w")
        e_cant = ttk.Entry(form, textvariable=self.cantidad, width=8)
        e_cant.grid(row=1, column=1, sticky="w")
        for e in (self.e_nombre, e_cant):
            e.bind("<Return>", lambda ev: self.guardar())
        botones = ttk.Frame(form)
        botones.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.b_guardar = ttk.Button(botones, text="Agregar", command=self.guardar)
        self.b_guardar.pack(side="left")
        self.b_eliminar = ttk.Button(botones, text="Eliminar", command=self.eliminar, state="disabled")
        self.b_eliminar.pack(side="left", padx=6)
        ttk.Button(botones, text="Limpiar", command=self.limpiar_formulario).pack(side="left")
        self.aviso = ttk.Label(form, foreground=ROJO, wraplength=330)
        self.aviso.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        acciones = ttk.LabelFrame(panel, text="Datos", padding=8)
        acciones.pack(fill="x", pady=(8, 0))
        for i, (texto, accion) in enumerate((("Deshacer", self.deshacer),
                                             ("Restaurar guía", self.restaurar),
                                             ("Importar CSV", self.importar),
                                             ("Exportar CSV", self.exportar_csv),
                                             ("Ver bitácora", self.ver_bitacora))):
            ttk.Button(acciones, text=texto, command=accion).grid(row=i // 3, column=i % 3, sticky="ew", padx=2, pady=2)
        acciones.columnconfigure((0, 1, 2), weight=1)
        return panel

    def _panel_grafica(self):
        panel = ttk.Frame(self)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(2, weight=1)
        tipos = ttk.Frame(panel)
        tipos.grid(row=0, column=0, sticky="w")
        ttk.Label(tipos, text="Tipo de gráfica:").pack(side="left", padx=(0, 6))
        for clave, (nombre, _) in graficas.TIPOS.items():
            ttk.Radiobutton(tipos, text=nombre, value=clave, variable=self.tipo,
                            command=self.redibujar).pack(side="left", padx=4)
        self.explicacion = ttk.Label(panel, foreground="#444444")
        self.explicacion.grid(row=1, column=0, sticky="w", pady=(4, 4))
        self.figura = Figure(figsize=(8, 5), dpi=100, facecolor="white")
        self.lienzo = FigureCanvasTkAgg(self.figura, master=panel)
        self.lienzo.get_tk_widget().grid(row=2, column=0, sticky="nsew")
        pie = ttk.Frame(panel)
        pie.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        # El botón se empaca primero para que el texto largo nunca lo empuje fuera de la ventana.
        ttk.Button(pie, text="Exportar gráfica (PNG o PDF)", command=self.exportar_grafica).pack(side="right")
        self.lectura = ttk.Label(pie, wraplength=520)
        self.lectura.pack(side="left", fill="x", expand=True)
        return panel

    # ---------- refresco ----------

    def refrescar(self, mensaje=None):
        """Recarga tabla, estado de la suma y gráfica desde la base."""
        self.arbol.delete(*self.arbol.get_children())
        poblacion = self.almacen.poblacion
        for d in self.almacen.categorias():
            self.arbol.insert("", "end", iid=str(d["id"]),
                              values=(d["nombre"], d["cantidad"], f"{100 * d['cantidad'] / poblacion:.1f}"))
        estado = self.almacen.estado_suma()
        self.suma.configure(text=estado["mensaje"], foreground=VERDE if estado["cuadra"] else ROJO)
        self.poblacion.set(str(poblacion))
        self.titulo.set(self.almacen.titulo)
        if self.seleccion and not self.arbol.exists(str(self.seleccion)):
            self.limpiar_formulario()
        self.redibujar()
        if mensaje:
            self.barra_estado.configure(text=mensaje)

    def redibujar(self):
        datos = self.almacen.categorias()
        graficas.dibujar(self.figura, self.tipo.get(), datos, self.almacen.poblacion, self.almacen.titulo)
        self.lienzo.draw_idle()
        self.explicacion.configure(text=graficas.TIPOS[self.tipo.get()][1])
        r = self.almacen.resumen()
        if r:
            pob = self.almacen.poblacion
            self.lectura.configure(text=(
                f"Más frecuente: {', '.join(r['mayor'])} ({r['valor_mayor']}, {100 * r['valor_mayor'] / pob:.0f} %).  "
                f"Menos frecuente: {', '.join(r['menor'])} ({r['valor_menor']}, {100 * r['valor_menor'] / pob:.0f} %)."))
        else:
            self.lectura.configure(text="")

    # ---------- acciones ----------

    def _intentar(self, accion, exito):
        """Corre una escritura; si la base la rechaza, muestra el motivo sin cerrar nada."""
        try:
            accion()
        except ErrorValidacion as e:
            self.aviso.configure(text=str(e))
            self.raiz.bell()
            return False
        self.aviso.configure(text="")
        self.refrescar(exito)
        return True

    def guardar(self):
        nombre, cantidad = self.nombre.get(), self.cantidad.get()
        if self.seleccion:
            ok = self._intentar(lambda: self.almacen.actualizar(self.seleccion, nombre, cantidad),
                                f"Se actualizó «{nombre.strip()}».")
        else:
            ok = self._intentar(lambda: self.almacen.agregar(nombre, cantidad), f"Se agregó «{nombre.strip()}».")
        if ok:
            self.limpiar_formulario()

    def eliminar(self):
        if not self.seleccion:
            return
        nombre = self.nombre.get()
        if messagebox.askyesno("Eliminar", f"¿Eliminar «{nombre}»? Puede deshacerlo después.", parent=self.raiz):
            if self._intentar(lambda: self.almacen.eliminar(self.seleccion), f"Se eliminó «{nombre}»."):
                self.limpiar_formulario()

    def aplicar_encuesta(self):
        def aplicar():
            self.almacen.cambiar_titulo(self.titulo.get())
            self.almacen.cambiar_poblacion(self.poblacion.get())
        self._intentar(aplicar, "Encuesta actualizada.")

    def deshacer(self):
        hecho = self.almacen.deshacer()
        self.refrescar(f"Se deshizo: {hecho}" if hecho else "No hay cambios para deshacer.")

    def restaurar(self):
        if messagebox.askyesno("Restaurar", "¿Volver a los datos originales de la guía? Puede deshacerlo después.",
                               parent=self.raiz):
            self.almacen.restaurar_originales()
            self.limpiar_formulario()
            self.refrescar("Se restauraron los datos originales de la guía.")

    def importar(self):
        ruta = filedialog.askopenfilename(parent=self.raiz, title="Importar CSV",
                                          filetypes=[("CSV", "*.csv"), ("Texto", "*.txt"), ("Todos", "*.*")])
        if ruta:
            def accion():
                self._importadas = self.almacen.importar_csv(ruta)
            if not self._intentar(accion, "Importación lista."):
                messagebox.showerror("Importar CSV", self.aviso.cget("text"), parent=self.raiz)
            else:
                self.barra_estado.configure(text=f"Se importaron {self._importadas} actividades.")

    def exportar_csv(self):
        ruta = filedialog.asksaveasfilename(parent=self.raiz, title="Exportar CSV", defaultextension=".csv",
                                            initialfile="encuesta.csv", filetypes=[("CSV", "*.csv")])
        if ruta:
            self.almacen.exportar_csv(ruta)
            self.barra_estado.configure(text=f"Datos exportados a {ruta}")

    def exportar_grafica(self):
        ruta = filedialog.asksaveasfilename(parent=self.raiz, title="Exportar gráfica", defaultextension=".png",
                                            initialfile=f"grafica-{self.tipo.get()}.png",
                                            filetypes=[("Imagen PNG", "*.png"), ("Documento PDF", "*.pdf")])
        if ruta:
            graficas.exportar(ruta, self.tipo.get(), self.almacen.categorias(), self.almacen.poblacion,
                              self.almacen.titulo)
            self.barra_estado.configure(text=f"Gráfica guardada en {ruta}")

    def ver_bitacora(self):
        v = tk.Toplevel(self.raiz)
        v.title("Bitácora y trazabilidad")
        modo_claro(v)
        v.geometry("760x460")
        marco = ttk.Frame(v, padding=10)
        marco.pack(fill="both", expand=True)
        cambios = self.almacen.diferencias_con_originales()
        ttk.Label(marco, text="Diferencias con los datos originales de la guía", font=("", 11, "bold")).pack(anchor="w")
        ttk.Label(marco, wraplength=720, justify="left",
                  text="\n".join(cambios) if cambios else "Ninguna: los datos son exactamente los de la guía.").pack(
            anchor="w", pady=(2, 10))
        ttk.Label(marco, text="Historial de cambios", font=("", 11, "bold")).pack(anchor="w")
        arbol = ttk.Treeview(marco, columns=("fecha", "accion", "detalle"), show="headings")
        for col, texto, ancho in (("fecha", "Fecha", 150), ("accion", "Acción", 110), ("detalle", "Detalle", 460)):
            arbol.heading(col, text=texto)
            arbol.column(col, width=ancho, anchor="w")
        for f in self.almacen.bitacora():
            arbol.insert("", "end", values=(f["fecha"], f["accion"] + (" (deshecho)" if f["deshecho"] else ""),
                                            f["detalle"]))
        arbol.pack(fill="both", expand=True)

    def _al_seleccionar(self, _evento=None):
        sel = self.arbol.selection()
        if not sel:
            return
        valores = self.arbol.item(sel[0], "values")
        self.seleccion = int(sel[0])
        self.nombre.set(valores[0])
        self.cantidad.set(valores[1])
        self.b_guardar.configure(text="Guardar cambios")
        self.b_eliminar.configure(state="normal")
        self.aviso.configure(text="")

    def limpiar_formulario(self):
        self.seleccion = None
        self.nombre.set("")
        self.cantidad.set("")
        self.b_guardar.configure(text="Agregar")
        self.b_eliminar.configure(state="disabled")
        if self.arbol.selection():
            self.arbol.selection_remove(self.arbol.selection())
        self.e_nombre.focus_set()


def abrir(ruta_datos=None):
    """Punto de entrada de la ventana."""
    raiz = tk.Tk()
    almacen = Almacen(ruta_datos)
    Aplicacion(raiz, almacen)
    raiz.protocol("WM_DELETE_WINDOW", lambda: (almacen.cerrar(), raiz.destroy()))
    raiz.mainloop()
