import pandas as pd

from src.fallecidos import (
    _deduplicate_fatality_records,
    aggregate_fatalities_by_crash_class,
    aggregate_fatalities_by_time_range,
    aggregate_fatalities_by_year,
    build_fatality_kpis,
    normalize_fatality_data,
)


def _raw_fatalities() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Departamento": "VALLE DEL CAUCA",
                "Municipio": "CALI",
                "EstadoVictima": "MUERTOS",
                "AnoHecho": "2024",
                "MesOCurrencia": "11.NOVIEMBRE",
                "DiaOcurrencia": "7.DOMINGO",
                "Rango3horas": "21:00 A 23:59",
                "Rango6horas": "18:00 A 23:59",
                "Sexo": "HOMBRE",
                "RangoEdad": "[20,25)",
                "ClaseAccidente": "CHOQUE",
                "Hipotesis": "SIN INFORMACIÓN",
                "TotalRegistros": "2",
            },
            {
                "Departamento": "VALLE DEL CAUCA",
                "Municipio": "CALI",
                "EstadoVictima": "MUERTOS",
                "AnoHecho": "2025",
                "MesOCurrencia": "03.MARZO",
                "DiaOcurrencia": "1.LUNES",
                "Rango3horas": "00:00 A 02:59",
                "Rango6horas": "00:00 A 05:59",
                "Sexo": "MUJER",
                "RangoEdad": "[30,35)",
                "ClaseAccidente": "ATROPELLO",
                "Hipotesis": "CRUZAR EN ESTADO DE EMBRIAGUEZ",
                "TotalRegistros": "1",
            },
            {
                "Departamento": "ANTIOQUIA",
                "Municipio": "MEDELLIN",
                "EstadoVictima": "MUERTOS",
                "AnoHecho": "2025",
                "MesOCurrencia": "03.MARZO",
                "DiaOcurrencia": "1.LUNES",
                "Rango3horas": "00:00 A 02:59",
                "Rango6horas": "00:00 A 05:59",
                "Sexo": "HOMBRE",
                "RangoEdad": "[30,35)",
                "ClaseAccidente": "CHOQUE",
                "Hipotesis": "SIN INFORMACIÓN",
                "TotalRegistros": "9",
            },
        ]
    )


def test_normalize_fatality_data_filters_cali_records() -> None:
    result = normalize_fatality_data(_raw_fatalities())

    assert len(result) == 2
    assert result["total_fallecidos"].sum() == 3
    assert result.loc[0, "mes"] == 11
    assert result.loc[0, "dia_semana"] == "domingo"


def test_build_fatality_kpis() -> None:
    fatalities = normalize_fatality_data(_raw_fatalities())

    result = build_fatality_kpis(fatalities)

    assert result.total_fatalities == 3
    assert result.top_year == "2024"
    assert result.top_time_range == "21:00 A 23:59"
    assert result.top_crash_class == "CHOQUE"


def test_fatality_aggregations() -> None:
    fatalities = normalize_fatality_data(_raw_fatalities())

    by_year = aggregate_fatalities_by_year(fatalities)
    by_time = aggregate_fatalities_by_time_range(fatalities)
    by_class = aggregate_fatalities_by_crash_class(fatalities)

    assert by_year.loc[0, "fallecidos"] == 2
    assert by_time.loc[0, "rango_3h"] == "21:00 A 23:59"
    assert by_class.loc[0, "clase_accidente"] == "CHOQUE"


def test_normalize_fatality_data_marks_unknown_time_ranges() -> None:
    raw = _raw_fatalities()
    raw.loc[0, "Rango3horas"] = "-1"

    result = normalize_fatality_data(raw)

    assert result.loc[0, "rango_3h"] == "Sin información"


def test_normalize_fatality_data_extracts_weekday_name_without_prefix() -> None:
    raw = _raw_fatalities()
    raw.loc[0, "DiaOcurrencia"] = "DOMINGO"
    raw.loc[1, "DiaOcurrencia"] = "SÁBADO"

    result = normalize_fatality_data(raw)

    assert result.loc[0, "dia_semana"] == "domingo"
    assert result.loc[1, "dia_semana"] == "sábado"


def test_deduplicate_fatality_records_removes_overlapping_snapshots() -> None:
    """Records appearing in multiple snapshot files must be deduplicated."""
    base = {
        "Departamento": "VALLE DEL CAUCA",
        "Municipio": "CALI",
        "AnoHecho": 2024,
        "MesOCurrencia": "11.NOVIEMBRE",
        "DiaOcurrencia": "7.DOMINGO",
        "Rango3horas": "21:00 A 23:59",
        "Rango6horas": "18:00 A 23:59",
        "Sexo": "HOMBRE",
        "RangoEdad": "[20,25)",
        "ClaseAccidente": "CHOQUE",
        "Hipotesis": "SIN INFORMACIÓN",
        "DiagnosticoTopografico": "TRAUMA CRANEANO",
        "CondicionVictima": "CONDUCTOR",
        "ActorVial": "USUARIO DE MOTO",
        "UsuarioVia": "USUARIO DE MOTO",
        "Zona": "URBANA",
        "ObjetoColision": "MOTOCICLETA",
        "TipoVehiculoGrupo": "MOTOCICLETA",
        "TipoServicio": "PARTICULAR",
        "EstadoVia": "BUENO",
        "ActividadVictima": "SIN INFORMACIÓN",
        "CausaMuerte": "CONTUNDENTE",
        "CondicionLugar": "NORMAL",
        "Muerte30Dias": "SI",
        "TotalRegistros": 1,
    }

    # Two identical records from different snapshot files
    duplicate = dict(base)
    # One record with a missing value (less complete) — should be dropped
    less_complete = dict(base)
    less_complete["EstadoVia"] = pd.NA
    # One unique record
    unique = dict(base)
    unique["ClaseAccidente"] = "ATROPELLO"

    raw = pd.DataFrame([duplicate, less_complete, unique])

    result = _deduplicate_fatality_records(raw)

    assert len(result) == 2
    # The more complete duplicate should be kept
    assert result["EstadoVia"].notna().sum() == 2
    assert set(result["ClaseAccidente"]) == {"CHOQUE", "ATROPELLO"}


def test_deduplicate_fatality_records_handles_empty_data() -> None:
    result = _deduplicate_fatality_records(pd.DataFrame())

    assert result.empty
