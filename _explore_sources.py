"""Temporary script: explore datos.gov.co catalog results."""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

# 1. Read the previously downloaded catalog output
catalog_file = r"C:\Users\juand\AppData\Local\Temp\cline\large-output-1785826389506-9swhoep.log"
with open(catalog_file, encoding="utf-8") as fh:
    content = fh.read()
    if content.strip().startswith("{"):
        data = json.loads(content)
    else:
        data = json.loads(content[content.index("{"):])

print("=== RESULTADOS BUSQUEDA 'accidente transito' ===")
for r in data.get("results", []):
    res = r.get("resource", {})
    print(f"{res.get('id', '?'):12s} | {res.get('name', '?')[:70]}")
print(f"\nTotal: {data.get('resultSetSize', len(data.get('results', [])))}")

# 2. Search specifically for Cali datasets
print("\n=== BUSQUEDA 'cali siniestralidad' ===")
search_url = "https://www.datos.gov.co/api/catalog/v1?q=cali%20siniestralidad&limit=15"
try:
    with urllib.request.urlopen(search_url, timeout=30) as resp:
        cali_data = json.loads(resp.read().decode("utf-8"))
    for r in cali_data.get("results", []):
        res = r.get("resource", {})
        print(f"{res.get('id', '?'):12s} | {res.get('name', '?')[:70]}")
    print(f"Total: {cali_data.get('resultSetSize', len(cali_data.get('results', [])))}")
except Exception as exc:
    print(f"Error: {exc}")

# 3. Search for national road safety data
print("\n=== BUSQUEDA 'seguridad vial' ===")
search_url = "https://www.datos.gov.co/api/catalog/v1?q=seguridad%20vial&limit=15"
try:
    with urllib.request.urlopen(search_url, timeout=30) as resp:
        vial_data = json.loads(resp.read().decode("utf-8"))
    for r in vial_data.get("results", []):
        res = r.get("resource", {})
        print(f"{res.get('id', '?'):12s} | {res.get('name', '?')[:70]}")
    print(f"Total: {vial_data.get('resultSetSize', len(vial_data.get('results', [])))}")
except Exception as exc:
    print(f"Error: {exc}")

# 4. Search for fatal accident data
print("\n=== BUSQUEDA 'muertes accidentes transito' ===")
search_url = "https://www.datos.gov.co/api/catalog/v1?q=muertes%20accidentes%20transito&limit=15"
try:
    with urllib.request.urlopen(search_url, timeout=30) as resp:
        muertes_data = json.loads(resp.read().decode("utf-8"))
    for r in muertes_data.get("results", []):
        res = r.get("resource", {})
        print(f"{res.get('id', '?'):12s} | {res.get('name', '?')[:70]}")
    print(f"Total: {muertes_data.get('resultSetSize', len(muertes_data.get('results', [])))}")
except Exception as exc:
    print(f"Error: {exc}")