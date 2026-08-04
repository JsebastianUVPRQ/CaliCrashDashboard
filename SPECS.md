# Especificaciones técnicas – Pronóstico de Siniestralidad Vial en Cali

## 1. Objetivo
Desarrollar un dashboard Streamlit que:
- Cargue datos abiertos de accidentes de tránsito en Cali.
- Procese, limpie y georreferencie los incidentes.
- Modele la frecuencia de accidentes por zona (comuna / intersección) y franja horaria.
- Muestre un mapa interactivo con la densidad de siniestros y filtros dinámicos.

## 2. Fuente y formato de datos
- **Origen:** Portal de datos abiertos (JSON/CSV) de la Secretaría de Movilidad de Cali.
- **Campos esperados:** fecha, hora, latitud, longitud, comuna, barrio, tipo de accidente, tipo de vehículo, gravedad, intersección (opcional).
- **Frecuencia de actualización:** mensual (se descargará un snapshot acumulado, o se usará API si está disponible).

## 3. Arquitectura de software
```mermaid
graph TD
    A[Datos abiertos] --> B[ETL: limpieza, imputación, geocodificación]
    B --> C[Base procesada en Parquet/CSV]
    C --> D[Modelado estadístico (Poisson, NB, SARIMA?)]
    D --> E[Resultados: frecuencias esperadas por zona/hora]
    E --> F[Dashboard Streamlit]
    F --> G[Mapa interactivo + filtros]
    G --> H[Visualización en Streamlit Cloud]
```

- **Librerías clave:** pandas, geopandas, folium, streamlit-folium, plotly, statsmodels/scikit-learn.
- **Modelado:** análisis de series temporales por zona (frecuencia diaria/horaria) o modelo de regresión para identificar factores de riesgo. El dashboard mostrará valores observados y, opcionalmente, predicciones.

### Módulos actuales
- `app.py`: entrada Streamlit ligera.
- `src/config.py`: configuración compartida de rutas, centro del mapa y orden de categorías.
- `src/dashboard.py`: composición de la interfaz, carga automática desde `data/processed/`, filtros, KPIs, visualizaciones y descarga.
- `src/etl.py`: carga CSV desde `data/processed/accidentes_limpios.csv` o `data/raw/accidentes.csv`, normaliza columnas (incluyendo `tipo_vehiculo`) y deriva `franja_horaria`, `dia_semana` y `mes`.
- `src/fallecidos.py`: carga CSV separados por `;` desde `data/fallecidos`, filtra registros de Cali y agrega mortalidad vial.
- `src/geocode.py`: georreferencia el campo `interseccion` con tres capas — ancla OSM exacta, cuadrícula afín calibrada por zona cardinal y diccionario de lugares.
- `scripts/build_processed_data.py`: ETL que limpia las fuentes crudas, geocodifica las intersecciones y escribe `accidentes_limpios.parquet` y `geocoded_intersections.parquet`.
- `notebooks/fetch_anchors.py`: descarga one-shot de las anclas OSM (`data/processed/anclas_osm.csv`).
- `src/insights.py`: narrativa automática de concentración por comuna, franja horaria y gravedad.
- `src/metrics.py`: filtros, KPIs y agregaciones por comuna, franja horaria, tipo de vehículo y vehículo × gravedad.
- `src/mapa.py`: mapa Folium centrado en Cali con marcadores agrupados.
- `src/modelo.py`: modelo base de frecuencia esperada con promedios históricos por comuna y franja horaria.
- `tests/`: pruebas unitarias para normalización, filtros, agregaciones y frecuencia esperada.

## 4. Funcionalidades del dashboard
1. **Mapa de calor/ clusters** con accidentes agregados por comuna o intersección.
2. **Selectores de fecha/hora** y día de la semana (franjas: madrugada, mañana, tarde, noche).
3. **Gráficos de barras** comparando siniestros por comuna en el período seleccionado.
4. **Indicadores clave:** total de accidentes, promedio diario, comuna más peligrosa.
5. **Opciones de descarga** de datos filtrados.

Estado implementado:
- Carga automática desde `data/processed/accidentes_limpios.parquet` (con coordenadas georreferenciadas) con fallback a otros candidatos o datos de muestra.
- Filtros por comuna, franja horaria, tipo, gravedad y rango de fechas.
- KPIs de total, promedio diario, comuna crítica e intersección crítica.
- KPIs compactos de total, comuna crítica, hora crítica y tendencia semanal.
- **Sección de cruces peligrosos** con ranking de las 15 intersecciones más críticas, desglose por gravedad y mapa de concentración.
- **Sección de composición** por tipo de vehículo, vehículo × gravedad, tipo de siniestro y distribución de gravedad.
- Mapa Folium con capa de calor opcional, clusters de marcadores y popups compactos.
- Panel lateral derecho con insights automáticos, top comunas y franja horaria.
- Gráficos narrativos de accidentes por hora del día y tendencia diaria.
- Sección colapsable de mortalidad vial con KPIs, serie anual, rangos horarios y clase de accidente.
- Tabla técnica colapsada de frecuencia diaria esperada por comuna y franja horaria.

## 5. Procesamiento de datos
- Georreferenciación de intersecciones sin coordenadas: ancla OSM exacta → cuadrícula afín calibrada por zona cardinal → diccionario de lugares (cobertura ~80% de registros; ~91% sobre los geocodificables).
- Conversión de coordenadas si es necesario (EPSG:4326 → proyección local).
- Unión con shapefiles de comunas (disponibles en SIG de Cali).
- Agregación temporal: generar columnas `franja_horaria`, `dia_semana`, `mes`.
- Normalización de `tipo_vehiculo` con alias de columnas (`vehiculo`, `tipo_vehiculo_1`, `tipo_de_vehiculo`, etc.) y relleno con `"Sin dato"` cuando falta.
- Los CSV de `data/fallecidos` son snapshots locales y se excluyen de Git por tamaño; solo se conserva `.gitkeep`.

## 6. Modelo de frecuencia
- Agregación de conteos por comuna y franja horaria.
- Ajuste de modelos de series de tiempo (por ejemplo, Prophet o SARIMA) para cada comuna, o un modelo global con variables dummy. El dashboard prioriza la visualización de datos históricos; la predicción es un plus.

## 7. Despliegue
- **Streamlit Cloud:** conecta directamente con GitHub. El `requirements.txt` debe incluir todas las dependencias. No se necesita servidor propio.
- **Secreto de API:** si los datos se consumen desde una API, se manejará con `st.secrets`.

## 8. Limitaciones
- Los datos abiertos pueden tener retrasos o campos incompletos.
- La georreferenciación por intersección requiere un diccionario de nombres de calles.
- No se construye aplicación móvil ni backend adicional; todo corre en Streamlit.

## 9. Próximos pasos
- Conectar el dataset real de datos abiertos y documentar su esquema final.
- Incorporar shapefiles de comunas para agregaciones espaciales.
- Añadir modelo de frecuencia cuando exista suficiente histórico limpio.
- Incorporar notificaciones o reportes automáticos.
- Integrar datos meteorológicos para mejorar la predicción.
