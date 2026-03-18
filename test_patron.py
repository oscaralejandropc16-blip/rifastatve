import pandas as pd
from datetime import datetime

CSV_FILE = 'historial_loterias.csv'
df = pd.read_csv(CSV_FILE)

fecha_input = "18/03"
hora_input = "1 pm"

fecha_parseada = datetime.strptime(f"{fecha_input}/2026", "%d/%m/%Y")
dia_obj = fecha_parseada.day
mes_obj = fecha_parseada.month
dia_semana = fecha_parseada.weekday()

df['Fecha_DT'] = pd.to_datetime(df['Fecha'], errors='coerce')
df = df.dropna(subset=['Fecha_DT'])
df['SuperGana'] = df['SuperGana'].astype(str).str.zfill(4)
df['TripleGana'] = df['TripleGana'].astype(str).str.extract(r'(\d)')[0]
df = df.dropna(subset=['TripleGana'])
df['Sorteo'] = df['Sorteo'].fillna('').astype(str)

df_hora = df[df['Sorteo'].str.contains(hora_input, case=False, na=False)].copy()

# Sucesores
sugerencias_sucesoras = []
# Para 1 pm, la logica de main.py no tiene reglas de predecesores diarios (solo para 4 pm -> 1 pm -> 4pm y 10 pm -> 4 pm)
# por lo que esto estará vacío.

# Rarezas Históricas
rarezas = []
df_mes_hora = df_hora[df_hora['Fecha_DT'].dt.month == mes_obj]

terminales_3_cifras = df_mes_hora['SuperGana'].str[-3:].value_counts()
if not terminales_3_cifras.empty:
    top_term_3 = terminales_3_cifras.head(2).index.tolist()
    for term in top_term_3:
        matches = df[df['SuperGana'].str.endswith(term)]
        if not matches.empty:
             rarezas.extend(matches['SuperGana'].tolist())

# Capas
c1 = df_hora[(df_hora['Fecha_DT'].dt.day == dia_obj) & (df_hora['Fecha_DT'].dt.month == mes_obj)]
semana_mes = (dia_obj - 1) // 7 + 1
c2 = df_hora[(df_hora['Fecha_DT'].dt.month == mes_obj) & (((df_hora['Fecha_DT'].dt.day - 1) // 7 + 1) == semana_mes)]
c3 = df_hora[(df_hora['Fecha_DT'].dt.month == mes_obj) & (df_hora['Fecha_DT'].dt.weekday == dia_semana)]

pool = []
pool.extend(sugerencias_sucesoras * 3)
pool.extend(rarezas * 3)
pool.extend(c1['SuperGana'].tolist() * 2)
pool.extend(c2['SuperGana'].tolist())
pool.extend(c3['SuperGana'].tolist())

frecuencia_total = pd.Series(pool).value_counts()
top3_estelares = frecuencia_total.head(3).index.tolist()

print("🎯 SISTEMA DE PROYECCIÓN - TOP 3 (ACTUALIZADO)")
print(f"Análisis {fecha_input} {hora_input}")
for i, n in enumerate(top3_estelares):
    print(f"#{i+1}: {n}")
