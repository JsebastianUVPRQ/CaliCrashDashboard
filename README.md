# CaliCrashDashboard - Siniestralidad Vial en Cali

Dashboard interactivo en Streamlit que modela la frecuencia de accidentes de tránsito en Cali, basado en datos abiertos de la Secretaría de Movilidad. La aplicación muestra un mapa con las zonas de mayor concentración de siniestros, permitiendo filtrar por comuna, intersección y franja horaria.

## 📊 Fuente de datos
- [Datos Abiertos de la Alcaldía de Cali – Secretaría de Movilidad]
- Archivos CSV/JSON con registros históricos de accidentes (georreferenciados).

## 🛠 Tecnologías
- **Python 3.10+**
- **Streamlit** (frontend/dashboard)
- **Pandas, GeoPandas** (manejo de datos)
- **PyDeck / Folium / Plotly** (visualización geoespacial interactiva; Folium queda como fallback)
- **Statsmodels / Scikit-learn** (modelado de frecuencias)
- **Streamlit Cloud** (despliegue sin servidor propio)

## ▶️ Ejecución local
```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m streamlit run app.py
```

Si no existe un archivo en `data/processed/accidentes_limpios.csv` o
`data/raw/accidentes.csv`, la aplicación usa una muestra mínima para validar
la interfaz.

## ☁️ Despliegue en Streamlit Cloud
- Conecta tu repositorio de GitHub a [Streamlit Cloud](https://share.streamlit.io).
- Selecciona el archivo principal `app.py`.
- En **Advanced settings**, selecciona Python 3.12 para mantener el entorno
  alineado con el desarrollo local y evitar builds contra versiones nuevas sin
  ruedas binarias para dependencias científicas.
- Listo, la app se actualizará con cada push.

## 📁 Estructura del proyecto
```
.
├── app.py               # Punto de entrada de la aplicación
├── src/
│   ├── config.py        # Rutas, centro del mapa y órdenes de categorías
│   ├── dashboard.py     # Composición de la interfaz Streamlit
│   ├── etl.py           # Carga, limpieza y normalización de datos
│   ├── insights.py      # Narrativa automática sobre patrones filtrados
│   ├── mapa.py          # Construcción del mapa WebGL y fallback Folium
│   ├── modelo.py        # Modelo base de frecuencia esperada
│   └── metrics.py       # Filtros, KPIs y agregaciones
├── data/
│   ├── fallecidos/      # CSV locales de fallecidos viales (gitignorados)
│   ├── raw/             # Datos crudos
│   └── processed/       # Datos procesados
├── notebooks/           # Análisis exploratorio y prototipos
├── tests/               # Pruebas unitarias de ETL y agregaciones
├── requirements.txt
├── AGENTS.md            # Instrucciones para agentes de IA
└── SPECS.md             # Especificaciones técnicas
```

## 📌 Estado del proyecto
En desarrollo activo. La app ya permite cargar CSV desde la barra lateral,
filtrar por comuna, fecha, franja horaria, tipo y gravedad, visualizar mapa de
calor WebGL con puntos interactivos, KPIs compactos, insights automáticos, patrones temporales,
rankings, una frecuencia diaria esperada basada en promedios históricos
observados y un módulo colapsable de mortalidad vial para Cali basado en
`data/fallecidos`.
