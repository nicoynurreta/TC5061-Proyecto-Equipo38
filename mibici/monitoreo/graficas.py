import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

AZUL = "steelblue"
ROJO = "crimson"
GRIS = "gray"
FONDOS = ["#f2f2f2", "#ffffff"]
MAXIMO_BARRAS = 40
RESOLUCION = 150


def grafica_puntuaciones(principal, controles, umbral, ruta):
    """Estadístico de drift de cada columna en la comparación principal y, con marcadores, en las de control."""
    orden = principal.sort_values("estadistico").reset_index(drop=True)
    posiciones = np.arange(len(orden))
    figura, eje = plt.subplots(figsize=(9, 0.42 * len(orden) + 1.8))
    eje.barh(posiciones, orden["estadistico"], color=[ROJO if deriva else AZUL for deriva in orden["deriva"]], height=0.6)
    leyenda = [Patch(color=ROJO, label="Referencia contra actual, con deriva"),
               Patch(color=AZUL, label="Referencia contra actual, sin deriva")]
    for (nombre, serie), marcador in zip(controles.items(), ["o", "s", "^", "D"]):
        puntos = eje.scatter(serie.reindex(orden["columna"]).to_numpy(), posiciones, marker=marcador, s=30,
                             facecolors="none", edgecolors="black", linewidths=0.9, zorder=3, label=nombre)
        leyenda.append(puntos)
    leyenda.append(eje.axvline(umbral, color=GRIS, linestyle="--", linewidth=1, label=f"Umbral de deriva ({umbral})"))
    eje.set_yticks(posiciones)
    eje.set_yticklabels(orden["columna"])
    eje.set_xlabel("Estadístico de drift (distancia entre distribuciones)")
    eje.set_title("Drift por variable del modelo de riesgo (P2)")
    eje.legend(handles=leyenda, loc="lower right", fontsize=8)
    eje.grid(axis="x", alpha=0.3)
    figura.tight_layout()
    figura.savefig(ruta, dpi=RESOLUCION)
    plt.close(figura)
    return ruta


def _panel_distribucion(eje, referencia, actual, etiquetas):
    valores = np.union1d(referencia.unique(), actual.unique()).astype(float)
    minimo, maximo = float(valores.min()), float(valores.max())
    if len(valores) > MAXIMO_BARRAS:
        minimo, maximo = (float(limite) for limite in np.quantile(np.concatenate([referencia.to_numpy(), actual.to_numpy()]), [0.005, 0.995]))
        valores = valores[(valores >= minimo) & (valores <= maximo)]
    if len(valores) <= MAXIMO_BARRAS:
        ancho = 0.4 * float(np.min(np.diff(valores))) if len(valores) > 1 else 0.4
        for serie, desplazamiento, color, etiqueta in [(referencia, -ancho / 2, AZUL, etiquetas[0]), (actual, ancho / 2, ROJO, etiquetas[1])]:
            frecuencia = serie.value_counts(normalize=True).reindex(valores, fill_value=0).to_numpy() * 100
            eje.bar(valores + desplazamiento, frecuencia, width=ancho, color=color, label=etiqueta)
        eje.set_ylabel("Horas-estación (%)")
    else:
        cortes = np.linspace(minimo, maximo, 41)
        eje.hist(referencia, bins=cortes, density=True, histtype="step", color=AZUL, linewidth=1.4, label=etiquetas[0])
        eje.hist(actual, bins=cortes, density=True, histtype="step", color=ROJO, linewidth=1.4, label=etiquetas[1])
        eje.set_yscale("log")
        eje.set_ylabel("Densidad (escala logarítmica)")
    eje.grid(axis="y", alpha=0.3)


def grafica_distribuciones(referencia, actual, columnas, estadisticos, ruta, etiquetas=("Referencia", "Actual")):
    """Distribución de las columnas con mayor estadístico de drift en la referencia y en el periodo actual."""
    filas = int(np.ceil(len(columnas) / 2))
    figura, ejes = plt.subplots(filas, 2, figsize=(12, 3.6 * filas), squeeze=False)
    for eje, columna in zip(ejes.ravel(), columnas):
        _panel_distribucion(eje, referencia[columna], actual[columna], etiquetas)
        eje.set_title(f"{columna} (estadístico {estadisticos[columna]:.3f})")
        eje.set_xlabel(columna)
        eje.legend(fontsize=8)
    for eje in ejes.ravel()[len(columnas):]:
        eje.axis("off")
    figura.suptitle("Variables con mayor drift entre la referencia y el periodo actual")
    figura.tight_layout()
    figura.savefig(ruta, dpi=RESOLUCION)
    plt.close(figura)
    return ruta


def _sombrear_conjuntos(eje, mensual, nombres, con_meses=True):
    meses = list(mensual.index)
    conjuntos = list(mensual["conjunto"])
    inicio = 0
    for posicion in range(1, len(meses) + 1):
        if posicion == len(meses) or conjuntos[posicion] != conjuntos[inicio]:
            bloque = len(set(conjuntos[:inicio + 1]))
            eje.axvspan(inicio - 0.5, posicion - 0.5, color=FONDOS[bloque % 2], zorder=0)
            eje.text((inicio + posicion - 1) / 2, 1.01, nombres.get(conjuntos[inicio], conjuntos[inicio]), ha="center", va="bottom",
                     fontsize=8, transform=eje.get_xaxis_transform())
            inicio = posicion
    eje.set_xlim(-0.5, len(meses) - 0.5)
    eje.set_xticks(range(len(meses)))
    eje.set_xticklabels(meses if con_meses else [""] * len(meses), rotation=60, ha="right", fontsize=8)


def grafica_objetivo(mensual, nombres, ruta):
    """Tasa de horas en riesgo observada y tasa de alertas del modelo vigente por mes, con el conjunto de cada tramo."""
    figura, eje = plt.subplots(figsize=(12, 4.8))
    posiciones = range(len(mensual))
    eje.plot(posiciones, mensual["tasa_riesgo"] * 100, color=ROJO, marker="o", label="Horas en riesgo observadas (objetivo)")
    eje.plot(posiciones, mensual["tasa_alertas"] * 100, color=AZUL, marker="s", linestyle="--", label="Alertas del modelo vigente (predicción)")
    _sombrear_conjuntos(eje, mensual, nombres)
    eje.set_ylabel("Horas-estación (%)")
    eje.set_xlabel("Mes")
    eje.set_ylim(bottom=0)
    eje.set_title("Deriva del objetivo y de la predicción de P2 por mes", pad=22)
    eje.legend(loc="lower left", fontsize=8)
    eje.grid(axis="y", alpha=0.3)
    figura.tight_layout()
    figura.savefig(ruta, dpi=RESOLUCION)
    plt.close(figura)
    return ruta


def grafica_drift_mensual(matriz, con_deriva, umbral, ruta):
    """Estadístico de drift de cada columna contra la referencia en cada mes del periodo actual."""
    figura, eje = plt.subplots(figsize=(1.0 * len(matriz.columns) + 3.5, 0.42 * len(matriz) + 2.2))
    imagen = eje.imshow(matriz.to_numpy(), cmap="Reds", vmin=0, vmax=max(3 * umbral, float(matriz.to_numpy().max())), aspect="auto")
    for fila in range(len(matriz)):
        for columna in range(len(matriz.columns)):
            valor = matriz.iat[fila, columna]
            eje.text(columna, fila, f"{valor:.2f}", ha="center", va="center", fontsize=8,
                     fontweight="bold" if valor >= umbral else "normal",
                     color="white" if valor >= 2 * umbral else "black")
    eje.set_xticks(range(len(matriz.columns)))
    eje.set_xticklabels([f"{mes}\n{con_deriva[mes]} de {len(matriz)}" for mes in matriz.columns], fontsize=8)
    eje.set_yticks(range(len(matriz)))
    eje.set_yticklabels(matriz.index)
    eje.set_xlabel("Mes del periodo actual y columnas con deriva")
    eje.set_title(f"Drift mensual contra la referencia (en negritas, estadístico mayor o igual a {umbral})")
    figura.colorbar(imagen, ax=eje, label="Estadístico de drift")
    figura.tight_layout()
    figura.savefig(ruta, dpi=RESOLUCION)
    plt.close(figura)
    return ruta


def grafica_desempeno_mensual(mensual, base, nombres, ruta):
    """Recall y precisión, costo por mil horas-estación y costo frente a no alertar del modelo vigente por mes, con la prueba de 2025 como referencia."""
    figura, ejes = plt.subplots(3, 1, figsize=(11, 10))
    posiciones = range(len(mensual))
    ejes[0].plot(posiciones, mensual["recall"], color=AZUL, marker="o", label="Recall")
    ejes[0].plot(posiciones, mensual["precision"], color=ROJO, marker="s", label="Precisión")
    ejes[0].axhline(base["recall"], color=AZUL, linestyle="--", linewidth=1, label=f"Recall en la prueba de 2025 ({base['recall']:.3f})")
    ejes[0].axhline(base["precision"], color=ROJO, linestyle="--", linewidth=1, label=f"Precisión en la prueba de 2025 ({base['precision']:.3f})")
    ejes[0].set_ylabel("Recall y precisión")
    ejes[1].plot(posiciones, mensual["costo_por_mil"], color=AZUL, marker="o", label="Costo por mil horas-estación")
    ejes[1].axhline(base["costo_por_mil"], color=AZUL, linestyle="--", linewidth=1, label=f"Prueba de 2025 ({base['costo_por_mil']:.1f})")
    ejes[1].set_ylabel("Costo por mil horas-estación")
    ejes[2].plot(posiciones, mensual["costo_relativo"], color=AZUL, marker="o", label="Costo frente a no emitir alertas")
    ejes[2].axhline(base["costo_relativo"], color=AZUL, linestyle="--", linewidth=1, label=f"Prueba de 2025 ({base['costo_relativo']:.3f})")
    ejes[2].axhline(1, color=GRIS, linewidth=1, label="Igual que no alertar (1)")
    ejes[2].set_ylabel("Costo relativo")
    for eje in ejes:
        _sombrear_conjuntos(eje, mensual, nombres, con_meses=eje is ejes[2])
        eje.set_ylim(bottom=0)
        eje.legend(fontsize=8, loc="lower left", ncol=2)
        eje.grid(axis="y", alpha=0.3)
    ejes[2].set_xlabel("Mes")
    figura.suptitle("Desempeño mensual del modelo vigente de P2 fuera de su entrenamiento")
    figura.tight_layout()
    figura.savefig(ruta, dpi=RESOLUCION)
    plt.close(figura)
    return ruta


def grafica_cohortes(cohortes, ruta):
    """Tasa de riesgo, recall y precisión del modelo vigente en las estaciones de la referencia y en las nuevas."""
    figura, ejes = plt.subplots(1, 3, figsize=(13, 4.2))
    etiquetas = list(cohortes.index)
    for eje, (columna, titulo) in zip(ejes, [("tasa_riesgo", "Horas en riesgo (%)"), ("recall", "Recall"), ("precision", "Precisión")]):
        valores = cohortes[columna].astype(float) * (100 if columna == "tasa_riesgo" else 1)
        barras = eje.bar(etiquetas, valores, color=[AZUL, ROJO][:len(etiquetas)])
        eje.bar_label(barras, fmt="%.2f" if columna == "tasa_riesgo" else "%.3f", fontsize=8)
        eje.set_title(titulo)
        eje.grid(axis="y", alpha=0.3)
        eje.tick_params(axis="x", labelsize=8)
    figura.suptitle("Modelo vigente en el periodo actual por antigüedad de la estación")
    figura.tight_layout()
    figura.savefig(ruta, dpi=RESOLUCION)
    plt.close(figura)
    return ruta
