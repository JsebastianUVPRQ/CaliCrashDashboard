"""Streamlit dashboard composition for Cali traffic crash analysis."""

from dataclasses import dataclass
from datetime import date
from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from src.config import DATA_CANDIDATES, FATALITY_DATA_DIR, TIME_BAND_ORDER
from src.etl import build_sample_accidents, normalize_accident_data, read_csv_flexible
from src.fallecidos import (
    aggregate_fatalities_by_crash_class,
    aggregate_fatalities_by_time_range,
    aggregate_fatalities_by_year,
    build_fatality_kpis,
    load_fatality_data,
)
from src.insights import build_insights
from src.mapa import build_accident_map
from src.metrics import (
    aggregate_by_comuna,
    aggregate_by_hour,
    aggregate_by_intersection,
    aggregate_by_time_band,
    build_kpis,
    filter_accidents,
)
from src.modelo import estimate_frequency


MONTH_ABBR_ES = {
    1: "ene",
    2: "feb",
    3: "mar",
    4: "abr",
    5: "may",
    6: "jun",
    7: "jul",
    8: "ago",
    9: "sep",
    10: "oct",
    11: "nov",
    12: "dic",
}


@dataclass(frozen=True)
class DashboardFilters:
    """Selected dashboard filters."""

    comunas: list[str]
    direcciones: list[str]
    franjas_horarias: list[str]
    tipos_accidente: list[str]
    gravedades: list[str]
    date_range: tuple[date, date] | list[date] | None
    show_heatmap: bool


@dataclass(frozen=True)
class TemporalSummary:
    """Narrative indicators for temporal accident patterns."""

    total_accidents: int
    daily_average: float
    critical_hour: str
    critical_hour_count: int
    critical_day: str
    critical_day_count: int
    daily_variation: str
    hourly_insight: str
    daily_insight: str


def render_dashboard() -> None:
    """Render the full Streamlit app."""
    st.set_page_config(
        page_title="Siniestralidad vial — Cali 2025",
        page_icon="🚦",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _inject_dashboard_css()

    uploaded_file = st.sidebar.file_uploader("CSV de accidentes", type=["csv"])
    accidents, raw_accidents = _load_data_with_raw(uploaded_file)
    fatalities = _load_fatalities()

    _render_header(accidents)
    if accidents.empty:
        st.warning("No hay registros válidos para visualizar.")
        st_folium(build_accident_map(accidents), use_container_width=True, height=560, key="mapa_vacio", returned_objects=[])
        return

    filters = _render_filters(accidents)
    filtered = filter_accidents(
        accidents,
        comunas=filters.comunas,
        direcciones=filters.direcciones,
        franjas_horarias=filters.franjas_horarias,
        tipos_accidente=filters.tipos_accidente,
        gravedades=filters.gravedades,
        date_range=filters.date_range,
    )

    _render_kpi_strip(filtered)
    _render_operations_view(filtered, filters.show_heatmap)
    _render_temporal_story(filtered)
    _render_fatalities_section(fatalities)
    _render_technical_detail(filtered, accidents, raw_accidents)


@st.cache_data(show_spinner=False)
def _load_data_with_raw(uploaded_file: object | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    if uploaded_file is not None:
        raw = read_csv_flexible(uploaded_file)
        return normalize_accident_data(raw), raw

    for path in DATA_CANDIDATES:
        if path.exists():
            suffix = path.suffix.lower()
            if suffix == ".parquet":
                raw = pd.read_parquet(path)
            else:
                raw = read_csv_flexible(path)
            return normalize_accident_data(raw), raw

    sample = build_sample_accidents()
    return normalize_accident_data(sample), sample


@st.cache_data(show_spinner=False)
def _load_fatalities() -> pd.DataFrame:
    return load_fatality_data(FATALITY_DATA_DIR)


def _render_header(accidents: pd.DataFrame) -> None:
    min_date = accidents["fecha"].min().date() if not accidents.empty else "sin datos"
    max_date = accidents["fecha"].max().date() if not accidents.empty else "sin datos"
    st.markdown(
        f"""
        <section class="app-header">
            <div>
                <p class="eyebrow">Observatorio de movilidad urbana</p>
                <h1>Siniestralidad vial — Cali 2025</h1>
            </div>
            <div class="date-range">{min_date} · {max_date}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_filters(accidents: pd.DataFrame) -> DashboardFilters:
    with st.sidebar:
        st.markdown("### Filtros")

        comunas = _sorted_known_unique(accidents, "comuna")
        selected_comunas = (
            st.multiselect("Comuna", comunas, default=comunas)
            if comunas
            else []
        )

        direcciones = _top_known_values(accidents, "interseccion", limit=250)
        selected_directions = st.multiselect(
            "Dirección / punto",
            direcciones,
            default=[],
            help="Dejar vacío para incluir todas las direcciones.",
        )

        available_bands = [
            band
            for band in TIME_BAND_ORDER
            if band in set(accidents["franja_horaria"].astype(str))
        ]
        selected_bands = st.multiselect(
            "Franja horaria",
            available_bands,
            default=available_bands,
        )

        tipos_accidente = _sorted_unique(accidents, "tipo_accidente")
        selected_types = st.multiselect(
            "Tipo de accidente",
            tipos_accidente,
            default=tipos_accidente,
        )

        gravedades = _sorted_unique(accidents, "gravedad")
        selected_severities = st.multiselect(
            "Gravedad",
            gravedades,
            default=gravedades,
        )

        min_date = accidents["fecha"].min().date()
        max_date = accidents["fecha"].max().date()
        selected_dates = st.date_input(
            "Rango de fechas",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

        show_heatmap = st.toggle("Mapa de calor", value=True)

    return DashboardFilters(
        comunas=selected_comunas,
        direcciones=selected_directions,
        franjas_horarias=selected_bands,
        tipos_accidente=selected_types,
        gravedades=selected_severities,
        date_range=selected_dates,
        show_heatmap=show_heatmap,
    )


def _render_kpi_strip(accidents: pd.DataFrame) -> None:
    kpis = build_kpis(accidents)
    delta = _format_delta(kpis.weekly_trend_delta)
    territorial_label = "Comuna crítica"
    territorial_value = kpis.top_comuna
    territorial_caption = "Mayor concentración"
    if kpis.top_comuna == "Sin datos" and kpis.top_intersection != "Sin datos":
        territorial_label = "Punto crítico"
        territorial_value = kpis.top_intersection
        territorial_caption = "Dirección con más registros"

    cards = [
        ("Total accidentes", f"{kpis.total_accidents:,}", "Registros filtrados"),
        (territorial_label, territorial_value, territorial_caption),
        ("Hora crítica", kpis.critical_hour, "Pico observado"),
        ("Tendencia semanal", kpis.weekly_trend, delta),
    ]
    card_html = "".join(
        (
            '<article class="kpi-card">'
            f"<span>{label}</span>"
            f"<strong>{value}</strong>"
            f"<small>{caption}</small>"
            "</article>"
        )
        for label, value, caption in cards
    )
    st.markdown(
        f'<section class="kpi-strip">{card_html}</section>',
        unsafe_allow_html=True,
    )


def _render_operations_view(accidents: pd.DataFrame, show_heatmap: bool) -> None:
    map_col, insight_col = st.columns((2.35, 1), gap="large")
    with map_col:
        st.markdown(
            '<h2 class="section-title">Mapa operativo</h2>',
            unsafe_allow_html=True,
        )
        has_geocoded_points = _has_geocoded_points(accidents)
        if has_geocoded_points and len(accidents) > 1500:
            st.info(
                "💡 **Rendimiento:** Se muestra una muestra representativa de 1,500 marcadores individuales para "
                "evitar ralentizar el navegador, pero el mapa de calor y las estadísticas utilizan el 100% de los datos."
            )
        if has_geocoded_points:
            accident_map = build_accident_map(accidents, show_heatmap=show_heatmap)
            st_folium(accident_map, use_container_width=True, height=600, key="mapa_operativo", returned_objects=[])
        else:
            _render_address_operations_view(accidents)

    with insight_col:
        _render_insight_panel(accidents)
        _render_risk_rankings(accidents)


def _has_geocoded_points(accidents: pd.DataFrame) -> bool:
    if accidents.empty or {"latitud", "longitud"}.difference(accidents.columns):
        return False
    return bool(accidents[["latitud", "longitud"]].dropna().shape[0])


def _render_address_operations_view(accidents: pd.DataFrame) -> None:
    by_intersection = aggregate_by_intersection(accidents)
    if by_intersection.empty:
        _render_empty_state(
            "No hay puntos georreferenciados ni direcciones válidas para mapear.",
            [
                "Cargar un archivo con latitud y longitud para activar el mapa.",
                "O incluir una columna de dirección para analizar concentración territorial.",
            ],
        )
        return

    st.caption(
        "La fuente actual no trae coordenadas. Se muestra concentración por dirección reportada."
    )
    top_points = by_intersection.head(15)
    fig = px.bar(
        top_points.sort_values("accidentes"),
        x="accidentes",
        y="interseccion",
        orientation="h",
        text="accidentes",
        labels={"accidentes": "Accidentes", "interseccion": "Dirección"},
    )
    _style_bar_figure(fig, height=430)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.dataframe(
        by_intersection.head(50),
        hide_index=True,
        width="stretch",
        column_config={
            "interseccion": st.column_config.TextColumn("Dirección / punto"),
            "accidentes": st.column_config.NumberColumn("Accidentes", format="%d"),
        },
    )


def _render_insight_panel(accidents: pd.DataFrame) -> None:
    insights = build_insights(accidents)
    st.markdown(
        '<h2 class="section-title">Lectura rápida</h2>',
        unsafe_allow_html=True,
    )
    if not insights:
        st.info("Sin datos suficientes para generar insights.")
        return

    for insight in insights:
        st.markdown(
            f'<div class="insight-item">{insight}</div>',
            unsafe_allow_html=True,
        )


def _render_risk_rankings(accidents: pd.DataFrame) -> None:
    by_comuna = aggregate_by_comuna(accidents).head(5)
    if by_comuna.empty:
        st.markdown('<h3 class="panel-title">Top direcciones</h3>', unsafe_allow_html=True)
        by_intersection = aggregate_by_intersection(accidents).head(5)
        if by_intersection.empty:
            st.info("Sin direcciones para mostrar.")
        else:
            fig = px.bar(
                by_intersection.sort_values("accidentes"),
                x="accidentes",
                y="interseccion",
                orientation="h",
                text="accidentes",
                labels={"accidentes": "Accidentes", "interseccion": "Dirección"},
            )
            _style_bar_figure(fig, height=240)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    else:
        st.markdown('<h3 class="panel-title">Top comunas</h3>', unsafe_allow_html=True)
        fig = px.bar(
            by_comuna.sort_values("accidentes"),
            x="accidentes",
            y="comuna",
            orientation="h",
            text="accidentes",
            labels={"accidentes": "Accidentes", "comuna": "Comuna"},
        )
        _style_bar_figure(fig, height=240)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    st.markdown('<h3 class="panel-title">Franja horaria</h3>', unsafe_allow_html=True)
    by_band = aggregate_by_time_band(accidents)
    if by_band.empty:
        st.info("Sin datos de franja horaria para mostrar.")
    else:
        fig = px.bar(
            by_band,
            x="franja_horaria",
            y="accidentes",
            text="accidentes",
            labels={"accidentes": "Accidentes", "franja_horaria": ""},
        )
        _style_bar_figure(fig, height=220)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _render_temporal_story(accidents: pd.DataFrame) -> None:
    st.markdown(
        '<h2 class="section-title">Patrones temporales</h2>',
        unsafe_allow_html=True,
    )
    hourly = aggregate_by_hour(accidents)
    daily = _daily_counts(accidents)
    summary = _build_temporal_summary(accidents, hourly, daily)
    _render_temporal_kpis(summary)

    trend_col, hour_col = st.columns((1.35, 1), gap="large")

    with trend_col:
        st.markdown(
            '<h3 class="panel-title">Tendencia diaria</h3>',
            unsafe_allow_html=True,
        )
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=daily["dia"],
                y=daily["accidentes"],
                mode="lines+markers",
                line={"color": "#f59e0b", "width": 3},
                marker={"color": "#f97316", "size": 7},
                fill="tozeroy",
                fillcolor="rgba(245, 158, 11, 0.12)",
            )
        )
        max_daily = max(int(daily["accidentes"].max()), 1) if not daily.empty else 1
        fig.update_layout(
            height=260,
            margin={"l": 8, "r": 8, "t": 8, "b": 2},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"color": "#d8dee9", "size": 12},
            yaxis_title="Accidentes",
            xaxis_title="Día",
            showlegend=False,
        )
        fig.update_xaxes(
            gridcolor="rgba(148, 163, 184, 0.16)",
            tickformat="%d/%m",
            ticklabelmode="period",
            nticks=min(len(daily), 6) if not daily.empty else 3,
            zeroline=False,
        )
        fig.update_yaxes(
            gridcolor="rgba(148, 163, 184, 0.16)",
            range=[0, max_daily * 1.18],
            zeroline=False,
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        _render_chart_note(summary.daily_insight, "daily-insight")

    with hour_col:
        st.markdown(
            '<h3 class="panel-title">Distribución por hora</h3>',
            unsafe_allow_html=True,
        )
        fig = px.bar(
            hourly,
            x="hora_dia",
            y="accidentes",
            labels={"hora_dia": "Hora", "accidentes": "Accidentes"},
        )
        fig.update_xaxes(tickmode="array", tickvals=list(range(0, 24, 4)))
        _style_bar_figure(fig, height=260)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        _render_chart_note(summary.hourly_insight, "hourly-insight")


def _render_fatalities_section(fatalities: pd.DataFrame) -> None:
    with st.expander("Mortalidad vial en Cali", expanded=False):
        if fatalities.empty:
            _render_empty_state(
                "No se encontraron registros de mortalidad para Cali.",
                [
                    "Verificar que el archivo de mortalidad esté cargado.",
                    "Revisar el rango temporal disponible.",
                    "Restablecer filtros o cambiar la zona analizada.",
                ],
            )
            return

        kpis = build_fatality_kpis(fatalities)
        fatality_cards = [
            ("Total Fallecidos", f"{kpis.total_fatalities:,}", "Registros históricos"),
            ("Año crítico", str(kpis.top_year), "Mayor mortalidad"),
            ("Horario crítico", str(kpis.top_time_range), "Franja de mayor riesgo"),
            ("Clase de siniestro", str(kpis.top_crash_class), "Tipo más frecuente"),
        ]
        card_html = "".join(
            (
                '<article class="kpi-card kpi-card-fatality">'
                f"<span>{label}</span>"
                f"<strong>{value}</strong>"
                f"<small>{caption}</small>"
                "</article>"
            )
            for label, value, caption in fatality_cards
        )
        st.markdown(
            f'<section class="kpi-strip fatality-strip">{card_html}</section>',
            unsafe_allow_html=True,
        )

        year_col, profile_col = st.columns(2, gap="large")
        with year_col:
            yearly = aggregate_fatalities_by_year(fatalities).sort_values("Año")
            fig = px.line(
                yearly,
                x="Año",
                y="fallecidos",
                markers=True,
                labels={"fallecidos": "Fallecidos"},
            )
            _style_line_figure(fig, height=300)
            st.plotly_chart(
                fig,
                width="stretch",
                config={"displayModeBar": False},
            )

        with profile_col:
            by_time = aggregate_fatalities_by_time_range(fatalities).head(8)
            fig = px.bar(
                by_time.sort_values("fallecidos"),
                x="fallecidos",
                y="rango_3h",
                orientation="h",
                text="fallecidos",
                labels={"fallecidos": "Fallecidos", "rango_3h": ""},
            )
            _style_bar_figure(fig, height=300, color="#ef4444")
            st.plotly_chart(
                fig,
                width="stretch",
                config={"displayModeBar": False},
            )

        crash_class = aggregate_fatalities_by_crash_class(fatalities).head(10)
        st.dataframe(
            crash_class,
            hide_index=True,
            width="stretch",
            column_config={
                "clase_accidente": st.column_config.TextColumn("Clase de siniestro"),
                "fallecidos": st.column_config.ProgressColumn(
                    "Fallecidos",
                    format="%d",
                    min_value=0,
                    max_value=int(crash_class["fallecidos"].max()) if not crash_class.empty else 100,
                ),
            },
        )


def _render_technical_detail(filtered: pd.DataFrame, clean_full: pd.DataFrame, raw_full: pd.DataFrame) -> None:
    with st.expander("Ver detalle técnico y control de calidad", expanded=False):
        st.markdown("### Control de calidad de importación")
        from src.etl import data_quality_report
        quality = data_quality_report(raw_full, clean_full)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Registros cargados", f"{quality.total_raw:,}")
        col2.metric("Registros válidos", f"{quality.total_clean:,}")
        col3.metric("Fechas inválidas", f"{quality.null_fecha:,}")
        col4.metric("Coordenadas inválidas (o fuera de Cali)", f"{quality.null_coords + quality.out_of_bounds:,}")

        if quality.out_of_bounds > 0:
            st.caption(
                f"ℹ️ {quality.out_of_bounds:,} registros fueron filtrados por estar fuera de los límites geográficos de Cali."
            )

        st.write("---")
        st.markdown("### Frecuencia esperada por Comuna y Franja Horaria")
        frequency = estimate_frequency(filtered)
        st.dataframe(
            frequency,
            hide_index=True,
            width="stretch",
            column_config={
                "comuna": st.column_config.TextColumn("Comuna"),
                "franja_horaria": st.column_config.TextColumn("Franja Horaria"),
                "accidentes_observados": st.column_config.NumberColumn("Accidentes Observados", format="%d"),
                "dias_observados": st.column_config.NumberColumn("Días Observados", format="%d"),
                "frecuencia_diaria_esperada": st.column_config.NumberColumn(
                    "Frecuencia diaria",
                    format="%.2f",
                ),
                "intervalo_inferior": st.column_config.NumberColumn(
                    "IC 95 % inf.",
                    format="%.2f",
                ),
                "intervalo_superior": st.column_config.NumberColumn(
                    "IC 95 % sup.",
                    format="%.2f",
                ),
                "nivel_riesgo": st.column_config.TextColumn("Nivel de Riesgo"),
            },
        )
        st.download_button(
            "Descargar datos filtrados (CSV)",
            data=filtered.to_csv(index=False).encode("utf-8"),
            file_name="accidentes_filtrados.csv",
            mime="text/csv",
        )


def _daily_counts(accidents: pd.DataFrame) -> pd.DataFrame:
    return (
        accidents.assign(dia=accidents["fecha"].dt.floor("D"))
        .groupby("dia")
        .size()
        .reset_index(name="accidentes")
    )


def _build_temporal_summary(
    accidents: pd.DataFrame,
    hourly: pd.DataFrame,
    daily: pd.DataFrame,
) -> TemporalSummary:
    total = len(accidents)
    if total == 0 or daily.empty:
        return TemporalSummary(
            total_accidents=0,
            daily_average=0.0,
            critical_hour="Sin datos",
            critical_hour_count=0,
            critical_day="Sin datos",
            critical_day_count=0,
            daily_variation="Sin tendencia",
            hourly_insight="No hay accidentes para interpretar con los filtros actuales.",
            daily_insight="No hay registros diarios para analizar en el periodo seleccionado.",
        )

    critical_hour_row = hourly.sort_values(
        ["accidentes", "hora_dia"],
        ascending=[False, True],
    ).iloc[0]
    critical_hour = int(critical_hour_row["hora_dia"])
    critical_hour_count = int(critical_hour_row["accidentes"])

    critical_day_row = daily.sort_values(
        ["accidentes", "dia"],
        ascending=[False, True],
    ).iloc[0]
    critical_day = pd.Timestamp(critical_day_row["dia"])
    critical_day_count = int(critical_day_row["accidentes"])
    daily_average = total / max(len(daily), 1)
    daily_variation = _daily_variation_label(daily)

    return TemporalSummary(
        total_accidents=total,
        daily_average=daily_average,
        critical_hour=f"{critical_hour:02d}:00",
        critical_hour_count=critical_hour_count,
        critical_day=_format_day_label(critical_day),
        critical_day_count=critical_day_count,
        daily_variation=daily_variation,
        hourly_insight=_hourly_insight(hourly, total),
        daily_insight=_daily_insight(daily, daily_average, daily_variation),
    )


def _render_temporal_kpis(summary: TemporalSummary) -> None:
    cards = [
        ("Accidentes", f"{summary.total_accidents:,}", "Registros filtrados"),
        ("Promedio diario", f"{summary.daily_average:.1f}", "Accidentes por día"),
        ("Hora crítica", summary.critical_hour, f"{summary.critical_hour_count} registros"),
        ("Día crítico", summary.critical_day, f"{summary.critical_day_count} registros"),
    ]
    card_html = "".join(
        (
            '<article class="temporal-kpi">'
            f"<span>{escape(label)}</span>"
            f"<strong>{escape(value)}</strong>"
            f"<small>{escape(caption)}</small>"
            "</article>"
        )
        for label, value, caption in cards
    )
    st.markdown(
        f'<section class="temporal-kpi-strip">{card_html}</section>',
        unsafe_allow_html=True,
    )


def _render_chart_note(message: str, key: str) -> None:
    st.markdown(
        f'<div class="chart-note" data-note="{key}">{escape(message)}</div>',
        unsafe_allow_html=True,
    )


def _render_empty_state(title: str, actions: list[str]) -> None:
    items = "".join(f"<li>{escape(action)}</li>" for action in actions)
    st.markdown(
        f"""
        <div class="empty-state">
            <div class="empty-state-badge">Info</div>
            <div>
                <strong>{escape(title)}</strong>
                <p>Esto no necesariamente indica un error de la aplicación.</p>
                <ul>{items}</ul>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _hourly_insight(hourly: pd.DataFrame, total: int) -> str:
    if total == 0 or hourly.empty:
        return "No hay datos suficientes para identificar una concentración horaria."

    max_count = int(hourly["accidentes"].max())
    if max_count == 0:
        return "No hay datos suficientes para identificar una concentración horaria."

    active_hours = hourly[hourly["accidentes"].gt(0)]
    peak_hours = active_hours[active_hours["accidentes"].eq(max_count)]["hora_dia"].astype(int)
    share = max_count / total
    if len(peak_hours) > 3 or share < 0.2:
        return "La distribución horaria no presenta un patrón dominante; los eventos están dispersos durante el día."

    if len(peak_hours) == 1:
        hour = int(peak_hours.iloc[0])
        return f"La mayor frecuencia se observa a las {hour:02d}:00, con {max_count} accidentes registrados."

    formatted = ", ".join(f"{int(hour):02d}:00" for hour in peak_hours.tolist())
    return f"Las horas con mayor frecuencia son {formatted}, cada una con {max_count} accidentes registrados."


def _daily_insight(
    daily: pd.DataFrame,
    daily_average: float,
    daily_variation: str,
) -> str:
    if daily.empty:
        return "No hay registros diarios para analizar en el periodo seleccionado."

    max_row = daily.sort_values(["accidentes", "dia"], ascending=[False, True]).iloc[0]
    max_day = _format_day_label(pd.Timestamp(max_row["dia"]))
    max_count = int(max_row["accidentes"])
    if len(daily) == 1:
        return f"El periodo filtrado contiene un solo día: {max_day}, con {max_count} accidentes."

    return (
        f"La tendencia diaria se mantiene {daily_variation.lower()}; el máximo fue "
        f"{max_day} con {max_count} accidentes, frente a un promedio de {daily_average:.1f}."
    )


def _daily_variation_label(daily: pd.DataFrame) -> str:
    if len(daily) < 2:
        return "Sin tendencia"

    first = float(daily.iloc[0]["accidentes"])
    last = float(daily.iloc[-1]["accidentes"])
    if first == 0:
        delta = 100.0 if last > 0 else 0.0
    else:
        delta = ((last - first) / first) * 100

    if abs(delta) < 10:
        return "Estable"
    if delta > 0:
        return "Al alza"
    return "A la baja"


def _format_day_label(value: pd.Timestamp) -> str:
    month = MONTH_ABBR_ES.get(value.month, f"{value.month:02d}")
    return f"{value.day:02d} {month} {value.year}"


def _style_bar_figure(fig: go.Figure, height: int, color: str = "#7dd3fc") -> None:
    fig.update_traces(
        marker_color=color,
        marker_line_color="rgba(255,255,255,0)",
        textposition="outside",
        cliponaxis=False,
    )
    fig.update_layout(
        height=height,
        margin={"l": 8, "r": 8, "t": 12, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#d8dee9", "size": 12},
        showlegend=False,
    )
    fig.update_xaxes(gridcolor="rgba(148, 163, 184, 0.16)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(148, 163, 184, 0.10)", zeroline=False)


def _style_line_figure(fig: go.Figure, height: int) -> None:
    fig.update_traces(
        line={"color": "#ef4444", "width": 3},
        marker={"color": "#f87171", "size": 7},
    )
    fig.update_layout(
        height=height,
        margin={"l": 8, "r": 8, "t": 12, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#d8dee9", "size": 12},
        showlegend=False,
    )
    fig.update_xaxes(gridcolor="rgba(148, 163, 184, 0.16)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(148, 163, 184, 0.10)", zeroline=False)


def _format_delta(delta: float) -> str:
    if delta == 0:
        return "0% vs. periodo previo"
    return f"{delta:+.0f}% vs. periodo previo"


def _sorted_unique(data: pd.DataFrame, column: str) -> list[str]:
    return sorted(data[column].dropna().astype(str).unique())


def _sorted_known_unique(data: pd.DataFrame, column: str) -> list[str]:
    if column not in data.columns:
        return []
    values = data[column].dropna().astype(str).str.strip()
    return sorted(values[_known_value_mask(values)].unique())


def _top_known_values(data: pd.DataFrame, column: str, limit: int) -> list[str]:
    if column not in data.columns:
        return []
    values = data[column].dropna().astype(str).str.strip()
    counts = values[_known_value_mask(values)].value_counts()
    return counts.head(limit).index.tolist()


def _known_value_mask(values: pd.Series) -> pd.Series:
    lowered = values.str.lower()
    return (
        values.ne("")
        & lowered.ne("sin dato")
        & lowered.ne("nan")
        & lowered.ne("none")
        & values.ne(".")
    )


def _inject_dashboard_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

        :root {
            --bg: #0b0f14;
            --panel: #111820;
            --panel-soft: #151d27;
            --line: rgba(148, 163, 184, 0.18);
            --text: #f8fafc;
            --muted: #94a3b8;
            --accent: #f59e0b;
            --risk: #ef4444;
            --data: #7dd3fc;
        }

        .stApp, .stApp label, .stApp p, .stApp h1, .stApp h2, .stApp h3 {
            font-family: 'Outfit', sans-serif !important;
        }

        .stApp {
            background: var(--bg);
            color: var(--text);
        }

        [data-testid="stAppViewContainer"] > .main .block-container {
            max-width: 1480px;
            padding: 2rem 2.2rem 3rem;
        }

        [data-testid="stSidebar"] {
            background: #171b24;
            border-right: 1px solid var(--line);
        }

        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
            padding: 0.7rem;
            min-height: 5.5rem;
            border: 1px solid var(--line);
            background: #0f141b;
        }

        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p {
            font-size: 0.82rem;
        }

        [data-baseweb="tag"] {
            background: rgba(245, 158, 11, 0.16) !important;
            color: #ffedd5 !important;
            border-radius: 6px !important;
            min-height: 1.45rem !important;
        }

        .app-header {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 1rem;
        }

        .eyebrow {
            color: var(--accent);
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0;
            margin: 0 0 0.2rem;
            text-transform: uppercase;
        }

        .app-header h1 {
            color: var(--text);
            font-size: 1.95rem;
            line-height: 1.1;
            margin: 0;
        }

        .date-range {
            color: var(--muted);
            font-size: 0.9rem;
            padding-bottom: 0.22rem;
        }

        .kpi-strip {
            position: sticky;
            top: 0;
            z-index: 5;
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.75rem;
            padding: 0.75rem 0;
            margin-bottom: 0.8rem;
            background: rgba(11, 15, 20, 0.94);
            backdrop-filter: blur(12px);
        }

        .kpi-card {
            background: linear-gradient(180deg, var(--panel-soft), var(--panel));
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 0.78rem 0.9rem;
            min-height: 5rem;
            transition: transform 0.22s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.22s, box-shadow 0.22s;
        }

        .kpi-card:hover {
            transform: translateY(-2px);
            border-color: rgba(245, 158, 11, 0.35);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3);
        }

        .kpi-card-fatality {
            border-left: 3px solid var(--risk) !important;
        }

        .kpi-card-fatality:hover {
            border-color: rgba(239, 68, 68, 0.35);
            box-shadow: 0 6px 16px rgba(239, 68, 68, 0.08);
        }

        .kpi-card-fatality strong {
            color: #fca5a5 !important;
        }

        .fatality-strip {
            position: static !important;
            backdrop-filter: none !important;
            background: transparent !important;
            padding: 0 0 1rem 0 !important;
            margin-bottom: 0.5rem !important;
        }

        .kpi-card span,
        .kpi-card small {
            display: block;
            color: var(--muted);
            font-size: 0.78rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .kpi-card strong {
            display: block;
            color: var(--text);
            font-size: 1.55rem;
            line-height: 1.25;
            margin: 0.2rem 0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        h2.section-title {
            color: var(--text);
            font-size: 1.45rem !important;
            line-height: 1.2;
            margin: 0.3rem 0 0.7rem;
            padding: 0;
        }

        h3.panel-title {
            color: var(--text);
            font-size: 1.05rem !important;
            line-height: 1.2;
            margin: 0.65rem 0 0.1rem;
            padding: 0;
        }

        .temporal-kpi-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.65rem;
            margin: -0.2rem 0 0.5rem;
        }

        .temporal-kpi {
            background: #0f1720;
            border: 1px solid var(--line);
            border-radius: 8px;
            min-height: 4.2rem;
            padding: 0.62rem 0.75rem;
        }

        .temporal-kpi span,
        .temporal-kpi small {
            display: block;
            color: var(--muted);
            font-size: 0.74rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .temporal-kpi strong {
            display: block;
            color: var(--text);
            font-size: 1.12rem;
            line-height: 1.2;
            margin: 0.16rem 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .chart-note {
            background: rgba(15, 23, 32, 0.94);
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-left: 3px solid var(--accent);
            border-radius: 8px;
            color: #e2e8f0;
            font-size: 0.84rem;
            line-height: 1.35;
            margin: -0.15rem 0 0.65rem;
            padding: 0.62rem 0.72rem;
        }

        .chart-note[data-note="hourly-insight"] {
            border-left-color: var(--data);
        }

        .empty-state {
            display: flex;
            gap: 0.85rem;
            align-items: flex-start;
            background: #101923;
            border: 1px solid rgba(148, 163, 184, 0.24);
            border-radius: 8px;
            color: #e5e7eb;
            margin: 0.75rem 0 0.15rem;
            padding: 0.9rem 1rem;
        }

        .empty-state-badge {
            flex: 0 0 auto;
            border: 1px solid rgba(125, 211, 252, 0.38);
            border-radius: 999px;
            color: #bae6fd;
            font-size: 0.72rem;
            font-weight: 700;
            padding: 0.18rem 0.48rem;
            text-transform: uppercase;
        }

        .empty-state strong {
            color: var(--text);
            display: block;
            font-size: 0.94rem;
            margin-bottom: 0.2rem;
        }

        .empty-state p {
            color: var(--muted);
            font-size: 0.84rem;
            margin: 0 0 0.35rem;
        }

        .empty-state ul {
            color: #cbd5e1;
            font-size: 0.82rem;
            margin: 0;
            padding-left: 1rem;
        }

        .empty-state li {
            margin: 0.12rem 0;
        }

        .insight-item {
            background: var(--panel);
            border: 1px solid var(--line);
            border-left: 3px solid var(--accent);
            border-radius: 8px;
            color: #e5e7eb;
            font-size: 0.9rem;
            line-height: 1.38;
            margin-bottom: 0.65rem;
            padding: 0.78rem 0.85rem;
        }

        div[data-testid="stExpander"] {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
        }

        .stButton button,
        .stDownloadButton button {
            background: var(--accent);
            border: 0;
            color: #111827;
            border-radius: 7px;
            font-weight: 700;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .stButton button:hover,
        .stDownloadButton button:hover {
            opacity: 0.9;
            transform: scale(1.02);
            box-shadow: 0 4px 12px rgba(245, 158, 11, 0.25);
        }

        @media (max-width: 900px) {
            [data-testid="stAppViewContainer"] > .main .block-container {
                padding: 1.2rem 1rem 2rem;
            }

            .app-header {
                align-items: flex-start;
                flex-direction: column;
            }

            .kpi-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .temporal-kpi-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .empty-state {
                flex-direction: column;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
