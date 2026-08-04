import pandas as pd

from src.insights import build_insights


def test_build_insights_handles_empty_data() -> None:
    result = build_insights(pd.DataFrame())

    assert result == []


def test_build_insights_reports_dominant_comuna_percentage() -> None:
    accidents = pd.DataFrame(
        {
            "comuna": ["17", "17", "2", "3"],
            "franja_horaria": ["noche", "noche", "mañana", "tarde"],
            "gravedad": ["Herido", "Herido", "Solo daños", "Herido"],
        }
    )

    result = build_insights(accidents)

    assert "La comuna 17 concentra 50% de los accidentes con comuna registrada." in result


def test_build_insights_reports_dominant_time_band() -> None:
    accidents = pd.DataFrame(
        {
            "comuna": ["17", "17", "2", "3"],
            "franja_horaria": ["noche", "noche", "noche", "tarde"],
            "gravedad": ["Herido", "Herido", "Solo daños", "Fatal"],
        }
    )

    result = build_insights(accidents)

    assert "La franja noche domina el riesgo con 75% de los casos." in result


def test_build_insights_ignores_unknown_comuna_and_time_band() -> None:
    accidents = pd.DataFrame(
        {
            "comuna": ["Sin dato", "Sin dato"],
            "franja_horaria": ["Sin dato", "Sin dato"],
            "gravedad": ["Con lesionado", "Con lesionado"],
        }
    )

    result = build_insights(accidents)

    assert "La comuna Sin dato concentra 100% de los accidentes filtrados." not in result
    assert "La franja Sin dato domina el riesgo con 100% de los casos." not in result
    assert "No hay dirección válida en los datos cargados para distribuir el riesgo territorial." in result


def test_build_insights_uses_intersection_when_comuna_is_unknown() -> None:
    accidents = pd.DataFrame(
        {
            "comuna": ["Sin dato", "Sin dato", "Sin dato"],
            "interseccion": ["Calle 5", "Calle 5", "Calle 8"],
            "franja_horaria": ["mañana", "mañana", "tarde"],
            "gravedad": ["Con lesionado", "Con lesionado", "Con lesionado"],
        }
    )

    result = build_insights(accidents)

    assert "El punto Calle 5 concentra 67% de los accidentes con dirección registrada." in result


def test_build_insights_keeps_small_intersection_percentages_visible() -> None:
    accidents = pd.DataFrame(
        {
            "comuna": ["Sin dato"] * 500,
            "interseccion": ["CLINICA COLOMBIA", *[f"Calle {index}" for index in range(499)]],
            "franja_horaria": ["tarde"] * 500,
            "gravedad": ["Con lesionado"] * 500,
        }
    )

    result = build_insights(accidents)

    assert any("concentra 0.2%" in insight for insight in result)
