"""Shared configuration for the Cali crash dashboard."""

from pathlib import Path


CALI_CENTER = (3.4516, -76.5320)

DATA_CANDIDATES = (
    Path("data/processed/accidentes_limpios.parquet"),
    Path("data/processed/accidentes_limpios.csv"),
    Path("data/processed/accidentes_cali_ampliados.csv"),
    Path("data/processed/accidentes_ampliados.csv"),
    Path("data/raw/accidentes.csv"),
    Path("data/raw/cali_lesionados_2016_2025.csv"),
    Path("data/raw/cali_siniestralidad_2016_2024.csv"),
)

REMOTE_DATA_CANDIDATES = (
    "https://datos.cali.gov.co/dataset/75c089ba-7df3-4816-b80f-c69c6e5362ae/resource/b5e009ef-8739-487d-bb0a-ffab613ce5cb/download/lesionados-en-santiago-de-cali-del-2016-2025.csv",
    "https://datos.cali.gov.co/dataset/cb62a408-9029-4331-8815-ca2caeb126c0/resource/e0572389-cc41-4c1f-b443-862be10b6cc3/download/siniestralidad_2016_2024.csv",
)

FATALITY_DATA_DIR = Path("data/fallecidos")

TIME_BAND_ORDER = ["madrugada", "mañana", "tarde", "noche", "Sin dato"]

WEEKDAY_ORDER = [
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
]

RISK_THRESHOLDS = {"bajo": 0.40, "medio": 0.75}
