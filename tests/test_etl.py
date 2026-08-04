import pandas as pd

from src.etl import assign_time_band, data_quality_report, normalize_accident_data


def test_assign_time_band_from_hour_string() -> None:
    assert assign_time_band("02:15") == "madrugada"
    assert assign_time_band("08:00") == "mañana"
    assert assign_time_band("15:30") == "tarde"
    assert assign_time_band("21") == "noche"
    assert assign_time_band("21:45") == "noche"


def test_normalize_accident_data_adds_derived_columns() -> None:
    raw = pd.DataFrame(
        [
            {
                "Fecha Accidente": "2025-02-01",
                "Hora Accidente": "07:10",
                "lat": "3.45",
                "lng": "-76.53",
                "comuna": "2",
                "barrio": "Granada",
                "tipo": "Choque",
                "Vehiculo": "Motocicleta",
                "severidad": "Solo daños",
            }
        ]
    )

    result = normalize_accident_data(raw)

    assert len(result) == 1
    assert result.loc[0, "franja_horaria"] == "mañana"
    assert result.loc[0, "mes"] == "2025-02"
    assert result.loc[0, "interseccion"] == "Sin dato"
    assert result.loc[0, "tipo_vehiculo"] == "Motocicleta"


def test_normalize_accident_data_filters_outside_cali_coordinates() -> None:
    raw = pd.DataFrame(
        [
            {
                "fecha": "2025-02-01",
                "hora": "07:10",
                "latitud": 4.80,
                "longitud": -74.05,
                "comuna": "Bogotá",
            }
        ]
    )

    result = normalize_accident_data(raw)

    assert result.empty


def test_data_quality_report_counts_dropped_rows() -> None:
    raw = pd.DataFrame(
        {
            "fecha": ["2025-01-01", pd.NA, "2025-01-03"],
            "hora": ["10:00", "10:00", "10:00"],
            "latitud": [3.45, 3.45, 4.80],
            "longitud": [-76.53, -76.53, -74.05],
            "comuna": ["2", "2", "Bogotá"],
            "barrio": ["A", "B", "C"],
            "tipo_accidente": ["Choque", "Choque", "Choque"],
            "gravedad": ["Daños", "Daños", "Daños"],
            "interseccion": ["X", "Y", "Z"],
        }
    )

    cleaned = normalize_accident_data(raw)
    report = data_quality_report(raw, cleaned)

    assert report.total_raw == 3
    assert report.total_clean == 1
    assert report.null_fecha == 1
    assert report.null_coords == 0
    assert report.out_of_bounds == 1


def test_data_quality_report_uses_normalized_columns() -> None:
    raw = pd.DataFrame(
        {
            "Fecha": ["1/01/2016", "2/01/2016"],
            "Hora": ["10:00", "11:00"],
            "Dirección_Reporte": ["Calle 1", "Calle 2"],
        }
    )

    cleaned = normalize_accident_data(raw)
    report = data_quality_report(raw, cleaned)

    assert report.total_raw == 2
    assert report.total_clean == 2
    assert report.null_fecha == 0
    assert report.null_coords == 2
    assert report.out_of_bounds == 0


def test_normalize_accident_data_parses_mixed_date_formats() -> None:
    raw = pd.DataFrame(
        {
            "Fecha": ["13/01/2016", "09/27/2025"],
            "Hora": ["10:00", "11:00"],
            "Dirección_Reporte": ["Calle 1", "Calle 2"],
        }
    )

    result = normalize_accident_data(raw)

    assert len(result) == 2
    assert result["fecha"].dt.strftime("%Y-%m-%d").tolist() == [
        "2016-01-13",
        "2025-09-27",
    ]


def test_normalize_accident_data_coalesces_duplicate_normalized_columns() -> None:
    raw = pd.DataFrame(
        {
            "Fecha": ["1/01/2016"],
            "Hora": ["10:00"],
            "Tipo_Confirmado": ["Con lesionado"],
            "Tipo_Confirmado.1": ["Por Atropello"],
            "Dirección_Reporte": ["Carrera 94 Con Calle 4 C"],
        }
    )

    result = normalize_accident_data(raw)

    assert result.loc[0, "gravedad"] == "Con lesionado"
    assert result.loc[0, "tipo_accidente"] == "Por Atropello"
    assert result.loc[0, "interseccion"] == "Carrera 94 Con Calle 4 C"


def test_normalize_accident_data_fills_missing_vehicle_type() -> None:
    raw = pd.DataFrame(
        [
            {
                "fecha": "2025-02-01",
                "hora": "07:10",
                "latitud": 3.45,
                "longitud": -76.53,
                "comuna": "2",
                "barrio": "Granada",
                "tipo_accidente": "Choque",
                "gravedad": "Solo daños",
            }
        ]
    )

    result = normalize_accident_data(raw)

    assert len(result) == 1
    assert result.loc[0, "tipo_vehiculo"] == "Sin dato"
