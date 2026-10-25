// Graficador de Encuestas: algoritmo de ingreso y validacion de un dato.
// Abrir en PSeInt y usar "Dibujar diagrama de flujo" para ver el diagrama.
Algoritmo IngresoYValidacion
	Definir nombre, nombres Como Caracter
	Definir cantidad, total, poblacion, n, i Como Entero
	Definir valido, repetido Como Logico
	Dimension nombres[50]

	poblacion <- 100
	total <- 0
	n <- 0

	Repetir
		Escribir "Nombre de la actividad (FIN para terminar):"
		Leer nombre
		Si nombre <> "FIN" Entonces
			Escribir "Cantidad de estudiantes:"
			Leer cantidad
			valido <- Verdadero

			Si Longitud(nombre) = 0 O Longitud(nombre) > 40 Entonces
				Escribir "Rechazado: el nombre es obligatorio y admite maximo 40 caracteres."
				valido <- Falso
			FinSi

			repetido <- Falso
			Para i <- 1 Hasta n Hacer
				Si Minusculas(nombres[i]) = Minusculas(nombre) Entonces
					repetido <- Verdadero
				FinSi
			FinPara
			Si valido Y repetido Entonces
				Escribir "Rechazado: esa actividad ya existe, editela en vez de repetirla."
				valido <- Falso
			FinSi

			Si valido Y (cantidad < 0 O cantidad <> Trunc(cantidad)) Entonces
				Escribir "Rechazado: la cantidad debe ser un entero mayor o igual a 0."
				valido <- Falso
			FinSi

			Si valido Y total + cantidad > poblacion Entonces
				Escribir "Rechazado: la suma pasaria de la poblacion (", poblacion, ")."
				valido <- Falso
			FinSi

			Si valido Entonces
				n <- n + 1
				nombres[n] <- nombre
				total <- total + cantidad
				Escribir "Guardado. Se registra en la bitacora y se redibuja la grafica."
				Escribir "Porcentaje de ", nombre, ": ", cantidad * 100 / poblacion, " %"
				Si total = poblacion Entonces
					Escribir "La suma cuadra con la poblacion."
				SiNo
					Escribir "Faltan ", poblacion - total, " estudiantes por clasificar."
				FinSi
			FinSi
		FinSi
	Hasta Que nombre = "FIN"
FinAlgoritmo
