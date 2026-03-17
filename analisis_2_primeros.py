import pandas as pd
CSV_FILE = 'historial_loterias.csv'
df = pd.read_csv(CSV_FILE)
df['SuperGana'] = df['SuperGana'].astype(str).str.zfill(4)
df['Fecha_DT'] = pd.to_datetime(df['Fecha'])

# Filtramos solo por 10 pm
df_10pm = df[df['Sorteo'].str.contains('10 pm', case=False)].copy()
df_10pm['D1'] = df_10pm['SuperGana'].str[0]
df_10pm['D2'] = df_10pm['SuperGana'].str[1]
df_10pm['D12'] = df_10pm['SuperGana'].str[:2]
df_10pm['D34'] = df_10pm['SuperGana'].str[2:]

print("--- ANÁLISIS DE PRECISIÓN PARA LOS 2 PRIMEROS DÍGITOS (10 PM) ---")

# 1. Fuerza de las "Centenas" (2 primeros)
top_2_primeros = df_10pm['D12'].value_counts().head(10)
print(f"\n[1] TOP 10 'CENTENAS' MÁS FORZADAS A LAS 10 PM:\n{top_2_primeros.to_string()}")

# 2. Correlación: Si el terminal es X, ¿cuál suele ser el inicio?
# Hoy a las 4pm el terminal fue 57. Busquemos qué suele salir a las 10pm después de un 57 a las 4pm.
# Primero necesitamos alinear los sorteos del mismo día.

df = df.sort_values(['Fecha_DT', 'Sorteo'])
patrones_4_a_10 = []
indices_4pm = df[df['Sorteo'].str.contains('4 pm')].index

for idx in indices_4pm:
    if idx + 1 < len(df):
        next_row = df.iloc[idx + 1]
        if '10 pm' in next_row['Sorteo']:
            curr_row = df.iloc[idx]
            # Si el de las 4pm terminó en 57 (como hoy)
            if curr_row['SuperGana'].endswith('57'):
                patrones_4_a_10.append(next_row['SuperGana'])

print(f"\n[2] HISTÓRICO: Cuando a las 4pm termina en '57', a las 10pm ha salido:\n{patrones_4_a_10}")

# 3. Fuerza por día de la semana (Martes)
df_martes = df_10pm[df_10pm['Fecha_DT'].dt.weekday == 1]
print(f"\n[3] TOP 2 PRIMEROS LOS MARTES 10 PM:\n{df_martes['D12'].value_counts().head(5).to_string()}")
