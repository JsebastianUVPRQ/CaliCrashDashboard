# Instrucciones para agentes de IA (Codex, OpenCode, etc.)

## 📌 Entorno
- **Sistema operativo:** Windows 11
- **Editor:** VSCode
- **IA assistants:** Codex, OpenCode
- **Control de versiones:** Git + GitHub
- **Entorno virtual Python:** siempre usar `venv` (ubicado en `venv/`)

## 🧱 Reglas de código
- Escribir código Python 3.10+ siguiendo PEP 8.
- Usar tipado estático donde sea posible.
- Funciones modulares, documentadas con docstrings.
- Separar el pipeline ETL, el modelo y el dashboard en módulos dentro de `src/`.
- El archivo `app.py` debe ser ligero, delegando lógica a `src/`.
- Los datos procesados se guardan en `data/processed/`, los crudos en `data/raw/` (no incluir en Git si >10MB, usar `.gitignore`).

## 🔁 Flujo de trabajo con Git
1. Crear rama por funcionalidad: `feat/<descripcion>`.
2. Hacer commits atómicos con mensajes claros.
3. Abrir Pull Request hacia `main`; debe pasar tests (si hay) y ser revisado.
4. No subir archivos binarios o datos a menos que sean indispensables.

## 🤖 Uso de Codex / OpenCode
- Al pedir código, especificar siempre el contexto: “en el módulo src/mapa.py, agrega una función para …”.
- Incluir ejemplos de entrada/salida en los comentarios.
- Si se requiere geolocalización, recordar que el sistema trabaja con coordenadas de Cali (latitud ~3.4, longitud ~-76.5).
- Preferir `folium` para mapas base; integrar con `streamlit-folium`.

## 🧪 Pruebas
- Añadir tests unitarios para transformaciones de datos y agregaciones en `tests/`.
- Ejecutar `pytest` antes de hacer commit si existen tests.
- El dashboard no se testea automáticamente, pero validar con `streamlit run app.py` localmente o con `streamlit.testing.v1.AppTest.from_file("app.py")` para un smoke test completo (secciones + presets).

## 📦 Dependencias
- Mantener `requirements.txt` actualizado con versiones fijas (`pandas==2.3.3`).
- Incluir SIEMPRE `pyarrow` (el dataset principal se lee como `.parquet` desde `src/config.py`) y `numpy`; sin ellos el dashboard falla en Streamlit Cloud.
- No incluir librerías pesadas innecesarias (como TensorFlow) a menos que se justifique.

## 🎨 Diseño del dashboard
- El sistema de diseño vive en `src/theme.py`: paleta semántica (rampa fija de gravedad `Negativo → Solo daños → Con lesionado → Con fallecido`), template Plotly oscuro, formateadores y todo el CSS (`DASHBOARD_CSS`).
- Los gráficos se construyen con `src/charts.py` (constructores tipados) y SIEMPRE pasan por `theme.style_figure`/`style_bars`; no hardcodear colores ni estilos por figura.
- `src/dashboard.py` delega cada capítulo del relato a `src/dashboard_sections/` (kpis, territorial, temporal, composicion, fatal, mortalidad, riesgo, detalle). La severidad canónica y sus rampas se gestionan en `src/metrics.py` (`canonical_severity`, `severity_counts`, `fatal_mask`).
- La sección de mortalidad (`mortalidad.py`) muestra SOLO resultados finales (personas fallecidas); no exponer reconciliación de fuentes ni procesos ETL en la UI.

## 🗺 Datos geoespaciales
- Usar `geopandas` y archivos shapefile de comunas de Cali (descargar de IDESC o repositorio auxiliar).
- Las coordenadas de accidentes se asumen en WGS84 (EPSG:4326). Convertir a proyección métrica para cálculos de áreas si es necesario.
- La georreferenciación de intersecciones vive en `src/geocode.py` (anclas OSM + cuadrícula afín por zona + diccionario de lugares). Si cambian las fuentes o la normalización, regenerar con `scripts/build_processed_data.py` y validar cobertura con `tests/test_geocode.py`.

## 📥 Fuentes de datos oficiales (CKAN)
- Las tres fuentes viven en el portal datos.cali.gov.co (API CKAN) y se descargan con `src/fetch.py` / `scripts/fetch_sources.py`.
- La descarga es idempotente: `src/fetch.py` usa el manifest `data/raw/manifiesto_linaje.json` (SHA-256 + `last_modified`) y omite archivos sin cambios; `--force` fuerza re-descarga.
- La mortalidad se compone del consolidado oficial `cali_muertes_2016_2023.csv` (una fila por fallecido, encoding latin-1, separador `;`) más los snapshots INMLCF en `data/fallecidos/`. `src/fallecidos.py` normaliza ambos formatos al contrato común (`NORMALIZED_COLUMNS`) y `merge_fatality_sources` elige por año la fuente con más meses documentados (empate → consolidado). Cambios en normalización/fusión requieren regenerar con `scripts/build_processed_data.py` (o `--fetch` para descargar antes) y correr pytest.
- Los tests de la cadena de fuentes están en `tests/test_fetch.py` (sin red, vía monkeypatch) y `tests/test_fallecidos.py`.

## 🔐 MCP (Model Context Protocol)
- Si el agente necesita acceder a la fuente de datos dinámicamente, puede configurarse un servidor MCP local (ver `.mcp.json`). Actualmente el proyecto no lo requiere, pero está preparado para futuras integraciones.

## 📄 Documentación
- Mantener actualizados `README.md`, `SPECS.md` y este `AGENTS.md`.
- Cualquier cambio en la estructura del proyecto se reflejará aquí.