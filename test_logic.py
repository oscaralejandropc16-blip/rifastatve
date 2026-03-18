import pandas as pd
from datetime import datetime

hora_input = "10 pm"
dia_obj = 17
mes_obj = 3
dia_semana = 1
fecha_input = "17/03/2026"

CSV_FILE = "historial_loterias.csv"
df = pd.read_csv(CSV_FILE)
df['Fecha_DT'] = pd.to_datetime(df['Fecha'], errors='coerce')
df['SuperGana'] = df['SuperGana'].astype(str).str.zfill(4)
df['Sorteo'] = df['Sorteo'].fillna('').astype(str)

df_hora = df[df['Sorteo'].str.contains(hora_input, case=False, na=False)].copy()

sugerencias_sucesoras = []
hoy_str = "2026-03-17" #datetime.now().strftime("%Y-%m-%d")

val_4pm = "7357"
terminal_4pm = str(val_4pm)[-2:]
print("Terminal 4pm:", terminal_4pm)

indices_4pm = df[df['Sorteo'].str.contains("4 pm", case=False, na=False)].index
print("Len indices 4pm:", len(indices_4pm))
for idx in indices_4pm:
    curr_row = df.iloc[idx]
    if str(curr_row['SuperGana']).endswith(terminal_4pm):
        if idx + 1 < len(df):
            next_row = df.iloc[idx + 1]
            if "10 pm" in str(next_row['Sorteo']).lower():
                sugerencias_sucesoras.append(next_row['SuperGana'])

print("Sugerencias sucesoras:", sugerencias_sucesoras)

c1 = df_hora[(df_hora['Fecha_DT'].dt.day == dia_obj) & (df_hora['Fecha_DT'].dt.month == mes_obj)]
semana_mes = (dia_obj - 1) // 7 + 1
c2 = df_hora[(df_hora['Fecha_DT'].dt.month == mes_obj) & (((df_hora['Fecha_DT'].dt.day - 1) // 7 + 1) == semana_mes)]
c3 = df_hora[(df_hora['Fecha_DT'].dt.month == mes_obj) & (df_hora['Fecha_DT'].dt.weekday == dia_semana)]

pool = []
pool.extend(sugerencias_sucesoras * 3)
pool.extend(c1['SuperGana'].tolist() * 2)
pool.extend(c2['SuperGana'].tolist())
pool.extend(c3['SuperGana'].tolist())

print("Pool size:", len(pool))
frecuencia_total = pd.Series(pool).value_counts()
print(frecuencia_total.head(10))
top3_estelares = frecuencia_total.head(3).index.tolist()
print("Top 3:", top3_estelares)
