import pandas as pd

from src.fallecidos import (
    _consolidado_age_band,
    _consolidado_time_range,
    _deduplicate_fatality_records,
    _normalize_consolidado_fatalities,
    aggregate_fatalities_by_crash_class,
    aggregate_fatalities_by_time_range,
    aggregate_fatalities_by_year,
    build_fatality_kpis,
    load_fatality_frames,
    merge_fatality_sources,
    normalize_fatality_data,
    reconcile_fatality_sources,
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

    # Two truly identical records from different snapshot files
    duplicate = dict(base)
    # One unique record (different crash class)
    unique = dict(base)
    unique["ClaseAccidente"] = "ATROPELLO"

    raw = pd.DataFrame([duplicate, dict(base), unique])

    result = _deduplicate_fatality_records(raw)

    assert len(result) == 2
    assert set(result["ClaseAccidente"]) == {"CHOQUE", "ATROPELLO"}


def test_deduplicate_fatality_records_handles_empty_data() -> None:
    result = _deduplicate_fatality_records(pd.DataFrame())

    assert result.empty


def _raw_consolidado() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "SEXO": "MASCULINO",
                "EDAD": "23",
                "HORA HECHO": "21:30",
                "FECHA HECHO": "03/11/2024",
                "FECHA FALL.": "04/11/2024",
                "CONDICION": "MOTOCICLISTA",
            },
            {
                "SEXO": "FEMENINO",
                "EDAD": "35-45",
                "HORA HECHO": ".",
                "FECHA HECHO": ".",
                "FECHA FALL.": "01/03/2025",
                "CONDICION": "PEATÓN",
            },
            {
                "SEXO": "FEMENINA",
                "EDAD": ".",
                "HORA HECHO": "05:10",
                "FECHA HECHO": "10/07/2024",
                "FECHA FALL.": "10/07/2024",
                "CONDICION": "SIN DATO",
            },
        ]
    )


def test_normalize_consolidado_uses_event_date_and_condition_class() -> None:
    result = _normalize_consolidado_fatalities(_raw_consolidado())

    assert len(result) == 3
    assert list(result.columns) == [
        "ano", "mes", "dia_semana", "rango_3h", "rango_6h", "sexo",
        "rango_edad", "clase_accidente", "hipotesis", "actor_vial",
        "total_fallecidos",
    ]
    assert result.loc[0, "ano"] == 2024
    assert result.loc[0, "mes"] == 11
    assert result.loc[0, "dia_semana"] == "domingo"
    assert result.loc[0, "clase_accidente"] == "CHOQUE"
    assert result.loc[0, "actor_vial"] == "MOTOCICLISTA"
    assert result.loc[0, "rango_edad"] == "[20,25)"
    assert result.loc[0, "total_fallecidos"] == 1


def test_normalize_consolidado_falls_back_to_death_date() -> None:
    result = _normalize_consolidado_fatalities(_raw_consolidado())

    row = result.iloc[1]
    assert row["ano"] == 2025
    assert row["mes"] == 3
    assert row["dia_semana"] == "sábado"
    assert row["rango_3h"] == "Sin información"
    assert row["sexo"] == "MUJER"
    assert row["rango_edad"] == "[35,45)"
    assert row["clase_accidente"] == "ATROPELLO"


def test_normalize_consolidado_handles_unknown_condition_and_sex() -> None:
    result = _normalize_consolidado_fatalities(_raw_consolidado())

    row = result.loc[2]
    assert row["rango_3h"] == "03:00 A 05:59"
    assert row["rango_6h"] == "00:00 A 05:59"
    assert row["sexo"] == "MUJER"
    assert row["rango_edad"] == "Sin información"
    assert row["clase_accidente"] == "Sin información"
    assert row["actor_vial"] == "Sin información"


def test_consolidado_time_range_builds_bands() -> None:
    hours = pd.Series([0, 3, 23, -1])

    r3 = _consolidado_time_range(hours, width=3)
    r6 = _consolidado_time_range(hours, width=6)

    assert r3.tolist() == [
        "00:00 A 02:59", "03:00 A 05:59", "21:00 A 23:59", "Sin información",
    ]
    assert r6.tolist() == [
        "00:00 A 05:59", "00:00 A 05:59", "18:00 A 23:59", "Sin información",
    ]


def test_consolidado_age_band_maps_noisy_values() -> None:
    values = pd.Series(["23", "25-30", "2M", "23h", "."])

    bands = _consolidado_age_band(values)

    assert bands.tolist() == [
        "[20,25)", "[25,30)", "[0,1)", "[0,1)", "Sin información",
    ]


def test_load_fatality_frames_splits_formats(tmp_path) -> None:
    consolidado = tmp_path / "consolidado.csv"
    consolidado.write_text(
        "SEXO;EDAD;HORA HECHO;FECHA HECHO;FECHA FALL.;CONDICION\n"
        "MASCULINO;30;12:00;01/01/2024;02/01/2024;JINETE\n",
        encoding="latin-1",
    )
    snapshot = tmp_path / "snapshot.csv"
    snapshot.write_text(
        "Departamento;Municipio;AnoHecho;MesOCurrencia;DiaOcurrencia;"
        "Rango3horas;Rango6horas;Sexo;RangoEdad;ClaseAccidente;Hipotesis;"
        "ActorVial;TotalRegistros\n"
        "VALLE DEL CAUCA;Cali;2024;11.NOVIEMBRE;7.DOMINGO;21:00 A 23:59;"
        "18:00 A 23:59;HOMBRE;SIN INFORMACIÓN;CHOQUE;SIN INFORMACIÓN;"
        "USUARIO DE MOTO;2\n",
        encoding="latin-1",
    )

    consolidated, snapshots = load_fatality_frames(tmp_path)

    assert not consolidated.empty and consolidated.loc[0, "actor_vial"] == "JINETE"
    assert consolidated.loc[0, "clase_accidente"] == "CHOQUE"
    assert not snapshots.empty and snapshots.loc[0, "mes"] == 11
    assert snapshots.loc[0, "total_fallecidos"] == 2


def test_merge_fatality_sources_prefers_most_complete_year() -> None:
    consolidado = pd.DataFrame(
        {
            "ano": [2024, 2024, 2024, 2023],
            "mes": [1, 2, 3, 1],
            "total_fallecidos": [1, 1, 1, 1],
        }
    )
    snapshot = pd.DataFrame(
        {
            "ano": [2024] * 6,
            "mes": list(range(1, 7)),
            "total_fallecidos": [1] * 6,
        }
    )

    merged = merge_fatality_sources(
        [consolidado, snapshot],
        labels=["consolidado_ckan", "inmlcf_snapshot"],
    )

    year_2024 = merged[merged["ano"] == 2024]
    assert (year_2024["fuente"] == "inmlcf_snapshot").all()
    assert len(year_2024) == 6
    year_2023 = merged[merged["ano"] == 2023]
    assert (year_2023["fuente"] == "consolidado_ckan").all()
    assert len(year_2023) == 1


def test_merge_fatality_sources_consolidado_wins_ties() -> None:
    consolidado = pd.DataFrame(
        {"ano": [2024, 2024], "mes": [1, 2], "total_fallecidos": [1, 1]}
    )
    snapshot = pd.DataFrame(
        {"ano": [2024, 2024], "mes": [1, 2], "total_fallecidos": [1, 1]}
    )

    result = merge_fatality_sources(
        [consolidado, snapshot],
        labels=["consolidado_ckan", "inmlcf_snapshot"],
    )

    assert (result["fuente"] == "consolidado_ckan").all()
    assert len(result) == 2


def test_merge_fatality_sources_default_labels() -> None:
    consolidado = pd.DataFrame(
        {"ano": [2024, 2024], "mes": [1, 2], "total_fallecidos": [1, 1]}
    )

    result = merge_fatality_sources([consolidado])

    assert (result["fuente"] == "consolidado_ckan").all()


def test_reconcile_fatality_sources_cross_checks_years() -> None:
    consolidado = pd.DataFrame(
        {"ano": [2023, 2024, 2024], "mes": [1, 1, 2], "total_fallecidos": [3, 1, 1]}
    )
    snapshot = pd.DataFrame(
        {"ano": [2024, 2024], "mes": [1, 2], "total_fallecidos": [4, 2]}
    )

    reconciliation = reconcile_fatality_sources(
        [consolidado, snapshot],
        labels=["consolidado_ckan", "inmlcf_snapshot"],
    )
    reconciliation = reconciliation.set_index("ano")

    assert reconciliation.loc[2023, "consolidado_ckan"] == 3
    assert reconciliation.loc[2023, "inmlcf_snapshot"] == 0
    assert reconciliation.loc[2023, "total"] == 3
    assert reconciliation.loc[2024, "consolidado_ckan"] == 2
    assert reconciliation.loc[2024, "inmlcf_snapshot"] == 6
    assert reconciliation.loc[2024, "total"] == 8
