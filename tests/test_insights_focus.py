"""Tests for the executive focus insights (fatal / territorial / trend)."""

import pandas as pd

from src.insights import build_focus_insights


def test_focus_insights_empty() -> None:
    assert build_focus_insights(pd.DataFrame()) == []


def test_focus_insights_reports_fatal_share() -> None:
    frame = _accidents_with_fatal(total=6, fatal=2)

    insights = build_focus_insights(frame)

    assert any("2 siniestros con fallecido" in text for text in insights)
    assert any("33%" in text for text in insights)


def test_focus_insights_report_no_fatal() -> None:
    frame = _accidents_with_fatal(total=6, fatal=0)

    insights = build_focus_insights(frame)

    assert any("no se registraron siniestros con fallecido" in text for text in insights)


def test_focus_insights_trend_shown() -> None:
    frame = _accidents_with_fatal(total=6, fatal=0)

    insights = build_focus_insights(frame)

    assert any("tendencia" in text for text in insights)


def _accidents_with_fatal(total: int, fatal: int) -> pd.DataFrame:
    rows = []
    for index in range(total):
        rows.append(
            {
                "fecha": pd.Timestamp(f"2025-01-{(index % 5) + 1:02d}"),
                "hora": "12:00",
                "comuna": "2",
                "interseccion": "A",
                "franja_horaria": "tarde",
                "tipo_accidente": "Choque",
                "gravedad": "Con fallecido" if index < fatal else "Con lesionado",
            }
        )
    return pd.DataFrame(rows)