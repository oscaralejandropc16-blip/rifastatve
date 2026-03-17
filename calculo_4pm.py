import pandas as pd
CSV_FILE = 'historial_loterias.csv'
df = pd.read_csv(CSV_FILE)
df['SuperGana'] = df['SuperGana'].astype(str).str.zfill(4)
# Sort by date/time
df['Fecha_DT'] = pd.to_datetime(df['Fecha'])
# Assuming the file is ordered, but let's be sure
df = df.sort_values(['Fecha_DT', 'Sorteo'])

# Target 4pm after 1pm 7049
# Find instances where 1pm was 7049 and look at the next 4pm
indices = df[(df['Sorteo'].str.contains('1 pm')) & (df['SuperGana'] == '7049')].index
sucesores = []
for idx in indices:
    # Check if next row is 4pm same day
    if idx + 1 < len(df):
        next_row = df.iloc[idx + 1]
        if '4 pm' in next_row['Sorteo']:
            sucesores.append(next_row['SuperGana'])

print(f"Sucesores de 7049 (1pm -> 4pm): {sucesores}")

# Check Tuesday + 17th + 4pm intersection
df['Dia'] = df['Fecha_DT'].dt.day
df['Mes'] = df['Fecha_DT'].dt.month
df['DiaSemana'] = df['Fecha_DT'].dt.weekday

filtro = df[(df['DiaSemana'] == 1) & (df['Sorteo'].str.contains('4 pm'))]
print(f"Top Martes 4pm: {filtro['SuperGana'].value_counts().head(3).index.tolist()}")

filtro_17 = df[(df['Dia'] == 17) & (df['Sorteo'].str.contains('4 pm'))]
print(f"Top Dia 17 4pm: {filtro_17['SuperGana'].value_counts().head(3).index.tolist()}")
