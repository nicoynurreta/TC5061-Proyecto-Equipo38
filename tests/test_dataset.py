import pandas as pd
import pytest

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


def _crudo(viaje_id, inicio, fin):
    return pd.DataFrame({
        "Viaje_Id": viaje_id,
        "Usuario_Id": [100 + i for i in range(len(viaje_id))],
        "Genero": ["M"] * len(viaje_id),
        "Año_de_nacimiento": [1990] * len(viaje_id),
        "Inicio_del_viaje": inicio,
        "Fin_del_viaje": fin,
        "Origen_Id": [2] * len(viaje_id),
        "Destino_Id": [3] * len(viaje_id),
    })


def test_limpiar_viajes_falla_si_falta_una_columna_necesaria():
    crudo = _crudo([1], ["2025-01-01 08:00:00"], ["2025-01-01 08:20:00"]).drop(columns=["Fin_del_viaje"])
    with pytest.raises(ValueError, match="faltan columnas"):
        dataset.limpiar_viajes(crudo)


def test_limpiar_viajes_conserva_la_primera_aparicion_de_un_viaje_duplicado():
    fines = ["2025-01-01 08:10:00", "2025-01-01 08:20:00", "2025-01-01 08:30:00", "2025-01-01 08:40:00"]
    limpio, conteo = dataset.limpiar_viajes(_crudo([7, 7, 7, 8], ["2025-01-01 08:00:00"] * 4, fines))
    assert conteo["duplicados"] == 2
    assert limpio["viaje_id"].tolist() == [7, 8]
    assert limpio["duracion_min"].tolist() == [10.0, 40.0]


def test_limpiar_viajes_en_los_limites_de_duracion():
    fines = ["2025-01-01 07:59:59", "2025-01-01 08:00:00", "2025-01-01 08:00:59", "2025-01-01 08:01:00",
             "2025-01-02 08:00:00", "2025-01-02 08:00:01"]
    limpio, conteo = dataset.limpiar_viajes(_crudo([1, 2, 3, 4, 5, 6], ["2025-01-01 08:00:00"] * 6, fines))
    assert conteo["duracion_negativa"] == 1
    assert conteo["duracion_menor_1_min"] == 2
    assert conteo["duracion_mayor_24_h"] == 1
    assert limpio["viaje_id"].tolist() == [4, 5]
    assert limpio["duracion_min"].tolist() == [1.0, 1440.0]


def test_limpiar_viajes_con_tabla_vacia_devuelve_vacia_con_conteos_en_cero():
    limpio, conteo = dataset.limpiar_viajes(_crudo([], [], []))
    assert limpio.empty
    assert list(limpio.columns) == dataset.COLUMNAS_NECESARIAS + ["duracion_min"]
    assert set(conteo.values()) == {0}
    assert str(limpio["inicio"].dtype).startswith("datetime64")


def test_normalizar_nombre_con_cadena_vacia_acentos_y_espacios():
    assert dataset.normalizar_nombre("") == ""
    assert dataset.normalizar_nombre("   ") == ""
    assert dataset.normalizar_nombre("Género") == "genero"
    assert dataset.normalizar_nombre("Duración (min)") == "duracion_min"
    assert dataset.normalizar_nombre("  Inicio del viaje  ") == "inicio_del_viaje"
    assert dataset.normalizar_nombre("Origen__Id") == "origen_id"
