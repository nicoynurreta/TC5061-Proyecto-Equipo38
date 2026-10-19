import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import ConfusionMatrixDisplay, PrecisionRecallDisplay


def grafica_real_vs_predicho(fechas, real, predicho, ruta):
    """Real contra predicho de P1: dispersión por estación y día y serie del total diario del sistema."""
    figura, ejes = plt.subplots(1, 2, figsize=(12, 4.5))
    ejes[0].scatter(real, predicho, s=6, alpha=0.25)
    maximo = float(max(np.max(real), np.max(predicho)))
    ejes[0].plot([0, maximo], [0, maximo], color="gray", linewidth=1)
    ejes[0].set_title("Viajes por estación y día en prueba")
    ejes[0].set_xlabel("Real (viajes)")
    ejes[0].set_ylabel("Predicho (viajes)")
    serie = pd.DataFrame({"fecha": pd.to_datetime(fechas), "real": np.asarray(real), "predicho": np.asarray(predicho)})
    serie = serie.groupby("fecha").sum()
    ejes[1].plot(serie.index, serie["real"], label="Real")
    ejes[1].plot(serie.index, serie["predicho"], label="Predicho")
    ejes[1].set_title("Total diario del sistema en prueba")
    ejes[1].set_xlabel("Fecha")
    ejes[1].set_ylabel("Viajes por día")
    ejes[1].legend()
    ejes[1].tick_params(axis="x", rotation=30)
    figura.tight_layout()
    figura.savefig(ruta, dpi=120)
    plt.close(figura)
    return ruta


def grafica_matriz_confusion(real, predicho, ruta):
    """Matriz de confusión de P2 en el conjunto de prueba."""
    figura, eje = plt.subplots(figsize=(5, 4.5))
    ConfusionMatrixDisplay.from_predictions(real, predicho, display_labels=["Sin riesgo", "Riesgo"],
                                            cmap="Blues", colorbar=False, values_format="d", ax=eje)
    eje.set_title("Matriz de confusión en prueba")
    eje.set_xlabel("Predicción")
    eje.set_ylabel("Real")
    figura.tight_layout()
    figura.savefig(ruta, dpi=120)
    plt.close(figura)
    return ruta


def grafica_curva_precision_recall(real, puntuacion, ruta):
    """Curva precisión-recall de P2 en prueba, con la proporción de positivos como referencia."""
    figura, eje = plt.subplots(figsize=(5.5, 4.5))
    PrecisionRecallDisplay.from_predictions(real, puntuacion, ax=eje, name="Modelo")
    tasa = float(np.mean(real))
    eje.axhline(tasa, color="gray", linestyle="--", linewidth=1, label=f"Proporción de positivos ({tasa:.3f})")
    eje.set_title("Curva precisión-recall en prueba")
    eje.set_xlabel("Recall")
    eje.set_ylabel("Precisión")
    eje.legend(loc="upper right")
    figura.tight_layout()
    figura.savefig(ruta, dpi=120)
    plt.close(figura)
    return ruta


def grafica_mapa_grupos(perfil, grupos, ruta):
    """Mapa de las estaciones (longitud y latitud) coloreadas por el grupo que les asignó P3."""
    figura, eje = plt.subplots(figsize=(7, 7))
    colores = plt.get_cmap("tab10")
    for grupo in sorted(np.unique(grupos)):
        parte = perfil[grupos == grupo]
        eje.scatter(parte["longitud"], parte["latitud"], s=22, color=colores(grupo % 10), label=f"Grupo {grupo} ({len(parte)} estaciones)")
    eje.set_aspect(1 / np.cos(np.radians(perfil["latitud"].mean())))
    eje.set_title(f"Grupos de estaciones de MiBici (k = {len(np.unique(grupos))})")
    eje.set_xlabel("Longitud")
    eje.set_ylabel("Latitud")
    eje.legend(fontsize=8)
    eje.grid(alpha=0.3)
    figura.tight_layout()
    figura.savefig(ruta, dpi=120)
    plt.close(figura)
    return ruta


def grafica_perfiles_grupos(perfil, grupos, ruta):
    """Perfil horario medio de salidas de cada grupo de P3, en días hábiles y en fines de semana."""
    figura, ejes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    colores = plt.get_cmap("tab10")
    horas = range(24)
    for eje, tipo, titulo in [(ejes[0], "habil", "Días hábiles"), (ejes[1], "finde", "Fines de semana")]:
        columnas = [f"salidas_{tipo}_{hora:02d}" for hora in horas]
        for grupo in sorted(np.unique(grupos)):
            medio = perfil.loc[grupos == grupo, columnas].mean(axis=0).to_numpy() * 100
            eje.plot(list(horas), medio, color=colores(grupo % 10), label=f"Grupo {grupo}")
        eje.set_title(titulo)
        eje.set_xlabel("Hora del día")
        eje.set_xticks(range(0, 24, 3))
        eje.grid(alpha=0.3)
    ejes[0].set_ylabel("Salidas de la estación (%)")
    ejes[0].legend()
    figura.suptitle("Perfil horario medio de salidas por grupo")
    figura.tight_layout()
    figura.savefig(ruta, dpi=120)
    plt.close(figura)
    return ruta
