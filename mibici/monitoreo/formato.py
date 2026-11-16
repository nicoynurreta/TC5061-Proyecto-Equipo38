def tabla_markdown(encabezados, filas):
    """Tabla en Markdown a partir de los encabezados y de una lista de filas."""
    lineas = ["| " + " | ".join(encabezados) + " |", "|" + "---|" * len(encabezados)]
    for fila in filas:
        lineas.append("| " + " | ".join(str(celda) for celda in fila) + " |")
    return "\n".join(lineas)


def numero(valor):
    """Entero con separador de miles."""
    return f"{int(round(valor)):,}"


def porcentaje(valor, decimales=2):
    """Proporción escrita como porcentaje."""
    return f"{valor * 100:.{decimales}f} %"


def decimal(valor, decimales=3):
    """Número con decimales fijos; n. a. cuando no hay valor."""
    if valor is None or valor != valor:
        return "n. a."
    return f"{valor:.{decimales}f}"


def con_signo(valor, decimales=1):
    """Cambio relativo con signo, en porcentaje; n. a. cuando no hay valor."""
    if valor is None or valor != valor:
        return "n. a."
    return f"{valor * 100:+.{decimales}f} %"
