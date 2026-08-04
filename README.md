# CaliCrashDashboard — Siniestralidad Vial en Cali

Dashboard interactivo en Streamlit que modela la frecuencia de accidentes de tránsito en Cali, basado en datos abiertos de la Secretaría de Movilidad. La aplicación muestra un mapa con las zonas de mayor concentración de siniestros, permitiendo filtrar por comuna, intersección y franja horaria.

## 📊 Características

- **Pipeline ETL reproducible** — Extract → Validate → Transform → Load con contratos de datos, reportes de calidad y manifiesto de linaje
- **Modelo estadístico Poisson GLM** — Coeficientes, errores estándar, p-valores, intervalos de confianza, diagnóstico de sobre-dispersión
- **Mapa interactivo** — Mapa de calor, clusters de marcadores y popups con detalle
- **KPIs y narrativas** — Indicadores clave, insights automáticos y patrones temporales
- **Mortalidad vial** — Análisis de fallecidos con agregaciones por año, horario y clase de siniestro

## 🛠 Tecnologías

- **Python 3.10+**
- **Streamlit** (frontend/dashboard)
- **Pandas, NumPy** (manejo de datos)
- **Statsmodels** (modelado Poisson GLM)
- **Folium / Streamlit-Folium** (visualización geoespacial)
- **Plotly** (gráficos interactivos)
- **Pytest, Ruff, Mypy, Black, Pre-commit** (calidad de código)
- **GitHub Actions** (CI/CD)

## ▶️ Ejecución local

```powershell
# 1. Crear entorno virtual e instalar dependencias
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# 2. Ejecutar el pipeline ETL
venv\Scripts\python.exe scripts\run_pipeline.py

# 3. Lanzar el dashboard
venv\Scripts\python.exe -m streamlit run app.py
```

O usando Make (en Windows: `make` disponibles via Git Bash/WSL):

```bash
make setup      # Instalar entorno
make pipeline   # Ejecutar ETL
make test       # Ejecutar tests
make lint       # Ejecutar ruff + mypy
make dashboard  # Lanzar dashboard
```

## 📁 Estructura del proyecto

```
.
├── app.py                    # Punto de entrada Streamlit
├── pyproject.toml            # Metadatos, dependencias, config de herramientas
├── requirements.txt          # Dependencias de producción
├── requirements-dev.txt      # Dependencias de desarrollo
├── Makefile                  # Comandos de automatización
├── .pre-commit-config.yaml   # Hooks de pre-commit
├── .github/workflows/ci.yml  # CI/CD con GitHub Actions
├── src/
│   ├── config.py             # Configuración compartida
│   ├── schema.py             # Contratos de datos (schema registry)
│   ├── dashboard.py          # Composición de la interfaz Streamlit
│   ├── etl.py                # Carga y normalización de accidentes
│   ├── fallecidos.py         # Carga y agregación de mortalidad
│   ├── insights.py           # Narrativa automática
│   ├── mapa.py               # Mapas Folium
│   ├── metrics.py            # KPIs, filtros y agregaciones
│   ├── modelo.py             # Modelo base de frecuencia esperada
│   ├── pipeline/             # Pipeline ETL (extract, validate, transform, load)
│   └── stats/                # Modelo estadístico Poisson GLM
├── scripts/
│   └── run_pipeline.py       # CLI del pipeline ETL
├── docs/
│   ├── data_dictionary.md    # Diccionario de datos
│   ├── methodology.md        # Metodología estadística
│   ├── pipeline.md           # Documentación del pipeline
│   └── architecture.md       # Arquitectura del sistema
├── data/
│   ├── fallecidos/           # Snapshot de fallecidos (gitignored)
│   ├── raw/                  # Datos crudos (gitignored)
│   └── processed/            # Datos procesados (gitignored)
├── notebooks/                # Análisis exploratorio
├── tests/                    # Pruebas unitarias
├── AGENTS.md                 # Instrucciones para agentes de IA
└── SPECS.md                  # Especificaciones técnicas
```

## ☁️ Despliegue en Streamlit Cloud

1. Conecta tu repositorio de GitHub a [Streamlit Cloud](https://share.streamlit.io).
2. Selecciona el archivo principal `app.py`.
3. En **Advanced settings**, selecciona Python 3.12.
4. Listo, la app se actualizará con cada push.

## 📚 Documentación

- [Diccionario de datos](docs/data_dictionary.md)
- [Metodología estadística](docs/methodology.md)
- [Pipeline ETL](docs/pipeline.md)
- [Arquitectura](docs/architecture.md)

## 📌 Estado del proyecto

En desarrollo activo. Infraestructura profesional implementada: pipeline ETL con contratos de datos y reportes de calidad, modelo estadístico Poisson GLM con diagnóstico completo, herramientas de calidad de código (ruff, mypy, black, pre-commit), CI/CD y documentación técnica.