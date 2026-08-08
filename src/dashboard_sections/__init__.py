"""Dashboard section renderers, one module per story chapter."""

from src.dashboard_sections.composicion import render_composicion
from src.dashboard_sections.detalle import render_detalle
from src.dashboard_sections.fatal import render_fatal
from src.dashboard_sections.kpis import render_resumen
from src.dashboard_sections.mortalidad import render_mortalidad
from src.dashboard_sections.riesgo import render_riesgo
from src.dashboard_sections.temporal import render_temporal
from src.dashboard_sections.territorial import render_territorial

__all__ = [
    "render_composicion",
    "render_detalle",
    "render_fatal",
    "render_resumen",
    "render_mortalidad",
    "render_riesgo",
    "render_temporal",
    "render_territorial",
]