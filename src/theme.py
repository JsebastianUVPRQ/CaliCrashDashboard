"""Design system for the crash dashboard: palette, Plotly theme and CSS."""

from plotly.graph_objects import Figure

# ---------------------------------------------------------------------------
# Core palette
# ---------------------------------------------------------------------------
BG = "#0b0f14"
PANEL = "#111820"
PANEL_SOFT = "#151f2b"
LINE = "rgba(148, 163, 184, 0.18)"
TEXT = "#f8fafc"
MUTED = "#94a3b8"
MUTED_LIGHT = "#cbd5e1"
ACCENT = "#f59e0b"
RISK = "#ef4444"
DATA = "#7dd3fc"
OK = "#22c55e"
GRID_X = "rgba(148, 163, 184, 0.16)"
GRID_Y = "rgba(148, 163, 184, 0.10)"
TRANSPARENT = "rgba(0,0,0,0)"

FONT_FAMILY = "Outfit, 'Segoe UI', sans-serif"

# ---------------------------------------------------------------------------
# Severity ramp (ordered: low -> high harm)
# ---------------------------------------------------------------------------
SEVERITY_RAMP_ORDER = ["Negativo", "Solo daños", "Con lesionado", "Con fallecido"]

SEVERITY_RAMP: dict[str, str] = {
    "Negativo": "#6b7280",
    "Solo daños": "#38bdf8",
    "Con lesionado": "#f59e0b",
    "Con fallecido": "#ef4444",
}

SEVERITY_FALLBACK = "#94a3b8"

FATAL_SEVERITY = "Con fallecido"
INJURY_SEVERITY = "Con lesionado"


def severity_color(gravedad: object) -> str:
    """Map a raw severity label to its fixed semantic color."""
    lowered = str(gravedad).strip().lower()
    if "fallecido" in lowered or "fatal" in lowered or "muert" in lowered:
        return SEVERITY_RAMP[FATAL_SEVERITY]
    if "lesion" in lowered or "herid" in lowered:
        return SEVERITY_RAMP[INJURY_SEVERITY]
    if "daño" in lowered or "dano" in lowered:
        return SEVERITY_RAMP["Solo daños"]
    if "negativo" in lowered:
        return SEVERITY_RAMP["Negativo"]
    return SEVERITY_FALLBACK


TIME_BAND_COLORS: dict[str, str] = {
    "madrugada": "#4f46e5",
    "mañana": "#38bdf8",
    "tarde": "#fbbf24",
    "noche": "#8b5cf6",
}

RISK_MATRIX_SCALE = [
    [0.0, "#152238"],
    [0.55, "#f59e0b"],
    [1.0, "#ef4444"],
]

# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------
def fmt_int(value: int | float) -> str:
    return f"{int(value):,}"


def fmt_pct(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%"


def fmt_decimal(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}"


# ---------------------------------------------------------------------------
# Shared Plotly styling
# ---------------------------------------------------------------------------
def style_figure(
    fig: Figure,
    *,
    height: int = 320,
    showlegend: bool = False,
    x_title: str | None = None,
    y_title: str | None = None,
    margins: dict[str, int] | None = None,
) -> Figure:
    """Apply the dark neutral look shared by every dashboard chart."""
    fig.update_layout(
        height=height,
        margin=margins or {"l": 8, "r": 8, "t": 10, "b": 6},
        paper_bgcolor=TRANSPARENT,
        plot_bgcolor=TRANSPARENT,
        font={"family": FONT_FAMILY, "color": "#d8dee9", "size": 12},
        xaxis_title=x_title,
        yaxis_title=y_title,
        showlegend=showlegend,
        hoverlabel={
            "bgcolor": PANEL,
            "bordercolor": LINE,
            "font": {"family": FONT_FAMILY, "color": TEXT, "size": 12},
        },
    )
    fig.update_xaxes(gridcolor=GRID_X, zeroline=False)
    fig.update_yaxes(gridcolor=GRID_Y, zeroline=False)
    return fig


def style_bars(fig: Figure, color: str | None = None) -> Figure:
    """Normalize bar traces: flat marker color, outside text labels."""
    marker = {}
    if color:
        marker["color"] = color
    marker["line"] = {"color": "rgba(255,255,255,0)", "width": 0}
    fig.update_traces(
        marker=marker,
        textposition="outside",
        cliponaxis=False,
    )
    return fig


# ---------------------------------------------------------------------------
# Dashboard CSS
# ---------------------------------------------------------------------------
DASHBOARD_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

:root {
    --bg: #0b0f14;
    --panel: #111820;
    --panel-soft: #151d2b;
    --line: rgba(148, 163, 184, 0.18);
    --text: #f8fafc;
    --muted: #94a3b8;
    --muted-light: #cbd5e1;
    --accent: #f59e0b;
    --risk: #ef4444;
    --data: #7dd3fc;
    --ok: #22c55e;
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
    margin-bottom: 0.9rem;
}

.eyebrow {
    color: var(--accent);
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.08em;
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
    white-space: nowrap;
}

.nav-bar {
    position: sticky;
    top: 0;
    z-index: 20;
    display: flex;
    flex-wrap: wrap;
    gap: 0.42rem;
    align-items: center;
    padding: 0.55rem 0;
    margin-bottom: 0.7rem;
    background: rgba(11, 15, 20, 0.94);
    backdrop-filter: blur(12px);
}

.nav-chip {
    border: 1px solid var(--line);
    border-radius: 999px;
    background: var(--panel);
    color: var(--muted-light);
    font-size: 0.78rem;
    font-weight: 600;
    padding: 0.26rem 0.7rem;
    text-decoration: none;
    transition: border-color 0.18s, color 0.18s, background 0.18s;
}

.nav-chip:hover {
    border-color: rgba(245, 158, 11, 0.5);
    color: #ffedd5;
    background: rgba(245, 158, 11, 0.08);
}

/* ---- section header ---- */
.section-head {
    margin: 1.1rem 0 0.55rem;
}

.kicker {
    color: var(--data);
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    margin: 0 0 0.15rem;
    text-transform: uppercase;
}

h2.section-title {
    color: var(--text);
    font-size: 1.45rem !important;
    line-height: 1.2;
    margin: 0;
    padding: 0;
}

.section-caption {
    color: var(--muted);
    font-size: 0.86rem;
    line-height: 1.4;
    margin: 0.28rem 0 0.55rem;
    max-width: 78ch;
}

h3.panel-title {
    color: var(--text);
    font-size: 1.02rem !important;
    line-height: 1.2;
    margin: 0.65rem 0 0.1rem;
    padding: 0;
}

/* ---- KPI strip ---- */
.kpi-strip {
    position: sticky;
    top: 2.6rem;
    z-index: 5;
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 0.7rem;
    padding: 0.6rem 0;
    margin-bottom: 0.6rem;
    background: rgba(11, 15, 20, 0.94);
    backdrop-filter: blur(12px);
}

.kpi-card {
    background: linear-gradient(180deg, var(--panel-soft), var(--panel));
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 0.72rem 0.85rem;
    min-height: 4.9rem;
    transition: transform 0.22s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.22s, box-shadow 0.22s;
}

.kpi-card:hover {
    transform: translateY(-2px);
    border-color: rgba(245, 158, 11, 0.35);
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3);
}

.kpi-card span,
.kpi-card small {
    display: block;
    color: var(--muted);
    font-size: 0.76rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.kpi-card strong {
    display: block;
    color: var(--text);
    font-size: 1.42rem;
    line-height: 1.25;
    margin: 0.16rem 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.kpi-card.kpi-risk {
    border-left: 3px solid var(--risk);
}

.kpi-card.kpi-risk:hover {
    border-color: rgba(239, 68, 68, 0.35);
    box-shadow: 0 6px 16px rgba(239, 68, 68, 0.08);
}

.kpi-card.kpi-risk strong {
    color: #fca5a5;
}

.kpi-card.kpi-well:hover {
    border-color: rgba(34, 197, 94, 0.35);
    box-shadow: 0 6px 16px rgba(34, 197, 94, 0.08);
}

.kpi-card.kpi-well strong {
    color: #86efac;
}

/* ---- Insight band ---- */
.insight-strip {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.7rem;
    margin: 0.4rem 0 0.9rem;
}

.insight-item {
    background: var(--panel);
    border: 1px solid var(--line);
    border-left: 3px solid var(--accent);
    border-radius: 8px;
    color: #e5e7eb;
    font-size: 0.9rem;
    line-height: 1.42;
    padding: 0.7rem 0.82rem;
}

.insight-item.insight-fatal {
    border-left-color: var(--risk);
}

.insight-item small {
    display: block;
    color: var(--muted);
    font-size: 0.72rem;
    letter-spacing: 0.06em;
    margin-bottom: 0.3rem;
    text-transform: uppercase;
}

/* ---- Sources / notes ---- */
.source-note {
    color: var(--muted);
    font-size: 0.74rem;
    line-height: 1.3;
    margin: -0.1rem 0 0.7rem;
    text-align: right;
}

.caveat-note {
    background: rgba(245, 158, 11, 0.09);
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: 8px;
    color: #fde68a;
    font-size: 0.82rem;
    line-height: 1.4;
    margin: 0.5rem 0 0.9rem;
    padding: 0.6rem 0.75rem;
}

/* ---- Temporal KPIs ---- */
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

/* ---- Chart notes ---- */
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

/* ---- Empty state ---- */
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

/* ---- Misc ---- */
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

.severity-key {
    display: flex;
    flex-wrap: wrap;
    gap: 0.9rem;
    color: var(--muted);
    font-size: 0.78rem;
    margin: 0.3rem 0 0.7rem;
}

.severity-key .swatch {
    display: inline-block;
    width: 0.65rem;
    height: 0.65rem;
    border-radius: 999px;
    margin-right: 0.3rem;
    vertical-align: baseline;
}

@media (max-width: 1200px) {
    .kpi-strip {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
}

@media (max-width: 700px) {
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

    .temporal-kpi-strip,
    .insight-strip {
        grid-template-columns: 1fr;
    }

    .empty-state {
        flex-direction: column;
    }
}
"""