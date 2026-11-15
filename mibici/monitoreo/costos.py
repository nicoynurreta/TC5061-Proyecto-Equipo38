import numpy as np
from sklearn.metrics import average_precision_score

from mibici import config


def metricas(real, alerta, probabilidad=None, costo_falso_negativo=config.COSTO_FALSO_NEGATIVO):
    """Métricas de P2 de un conjunto de horas-estación: tasas, recall, precisión, F1, PR-AUC y costo de los errores.

    El costo por mil horas-estación depende de cuántas horas en riesgo hay en el periodo, así que se
    acompaña del costo relativo: el costo dividido entre lo que costaría no emitir ninguna alerta
    (todas las horas en riesgo como falsos negativos). Vale 1 cuando el modelo no aporta nada.
    """
    real = np.asarray(real).astype(bool)
    alerta = np.asarray(alerta).astype(bool)
    aciertos = int(np.sum(real & alerta))
    falsos_positivos = int(np.sum(~real & alerta))
    falsos_negativos = int(np.sum(real & ~alerta))
    recall = aciertos / (aciertos + falsos_negativos) if aciertos + falsos_negativos else 0.0
    precision = aciertos / (aciertos + falsos_positivos) if aciertos + falsos_positivos else 0.0
    costo = falsos_positivos + costo_falso_negativo * falsos_negativos
    valores = {
        "filas": int(len(real)),
        "positivos": int(real.sum()),
        "tasa_riesgo": float(real.mean()) if len(real) else 0.0,
        "alertas": int(alerta.sum()),
        "tasa_alertas": float(alerta.mean()) if len(real) else 0.0,
        "recall": recall,
        "precision": precision,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "falsos_positivos": falsos_positivos,
        "falsos_negativos": falsos_negativos,
        "costo": costo,
        "costo_por_mil": 1000 * costo / len(real) if len(real) else 0.0,
        "costo_relativo": costo / (costo_falso_negativo * int(real.sum())) if real.any() else None,
    }
    if probabilidad is not None:
        valores["pr_auc"] = float(average_precision_score(real, probabilidad)) if real.any() else None
    return valores
