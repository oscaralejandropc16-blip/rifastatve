import pandas as pd

df = pd.read_csv('historial_loterias.csv')
df['Fecha_DT'] = pd.to_datetime(df['Fecha'], errors='coerce')
df['SuperGana'] = df['SuperGana'].astype(str).str.zfill(4)

# Mostramos los resultados exactos del 17 de marzo:
print("--- RESULTADOS DEL 17/03/2026 ---")
ayer = df[df['Fecha'].str.contains('2026-03-17')]
for idx, row in ayer.iterrows():
    print(f"Sorteo: {row['Sorteo']} | SuperGana: {row['SuperGana']} | TripleGana: {row['TripleGana']}")

# Buscamos cuándo ha salido 6009 históricamente:
print("\n--- HISTÓRICO DEL 6009 ---")
hist_6009 = df[df['SuperGana'] == '6009']
for idx, row in hist_6009.iterrows():
    print(f"Fecha: {row['Fecha']} | Sorteo: {row['Sorteo']} | TripleGana: {row['TripleGana']}")

# Buscamos cuándo ha salido 009 históricamente (como terminal 3 cifras):
print("\n--- HISTÓRICO DEL TERMINAL 009 ---")
hist_009 = df[df['SuperGana'].str.endswith('009')]
for idx, row in hist_009.head(10).iterrows():
    print(f"Fecha: {row['Fecha']} | Sorteo: {row['Sorteo']} | SG: {row['SuperGana']} | TG: {row['TripleGana']}")
