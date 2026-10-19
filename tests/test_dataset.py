import pandas as pd

from mibici import dataset


def test_normalizar_nombre_quita_acentos_y_mayusculas():
    assert dataset.normalizar_nombre("Inicio_del_viaje") == "inicio_del_viaje"
    assert dataset.normalizar_nombre("Origen_Id") == "origen_id"
    assert dataset.normalizar_nombre("Año_de_nacimiento") == "anio_nacimiento"
    assert dataset.normalizar_nombre("A�o_de_nacimiento") == "anio_nacimiento"


def test_limpiar_viajes_descarta_invalidos_y_datos_personales():
    crudo = pd.DataFrame({
        "Viaje_Id": [1, 1, 2, 3, 4, 5],
        "Usuario_Id": [10, 10, 11, 12, 13, 14],
        "Genero": ["M", "M", "F", "M", "F", None],
        "Año_de_nacimiento": [1990, 1990, 1985, 2000, None, 1970],
        "Inicio_del_viaje": ["2025-01-01 08:00:00"] * 6,
        "Fin_del_viaje": ["2025-01-01 08:15:00", "2025-01-01 08:15:00", "2025-01-01 07:50:00",
                          "2025-01-01 08:00:30", "2025-01-03 08:00:00", "2025-01-01 08:30:00"],
        "Origen_Id": [2, 2, 3, 4, 5, 6],
        "Destino_Id": [3, 3, 4, 4, 6, 7],
    })
    limpio, conteo = dataset.limpiar_viajes(crudo)
    assert conteo["registros_crudos"] == 6
    assert conteo["duplicados"] == 1
    assert conteo["duracion_negativa"] == 1
    assert conteo["duracion_menor_1_min"] == 1
    assert conteo["duracion_mayor_24_h"] == 1
    assert limpio["viaje_id"].tolist() == [1, 5]
    assert limpio["duracion_min"].round(1).tolist() == [15.0, 30.0]
    assert not {"usuario_id", "genero", "anio_nacimiento"} & set(limpio.columns)
    assert str(limpio["inicio"].dtype).startswith("datetime64")
