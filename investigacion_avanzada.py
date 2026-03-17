import pandas as pd
import numpy as np
from datetime import datetime

CSV_FILE = 'historial_loterias.csv'

def investigacion_avanzada():
    if not pd.io.common.file_exists(CSV_FILE):
        return

    df = pd.read_csv(CSV_FILE)
    df['SuperGana'] = df['SuperGana'].astype(str).str.zfill(4)
    df['TripleGana'] = df['TripleGana'].astype(str).str.extract(r'(\d)')[0]
    df['Fecha_DT'] = pd.to_datetime(df['Fecha'])
    df = df.sort_values('Fecha_DT')
    
    print("--- INVESTIGACIÓN DE NIVEL 2: REGLAS OCULTAS ---")

    # 1. LA REGLA DEL DÍA DE LA SEMANA (TRUCO SEMANAL)
    print("\n[1] ANÁLISIS POR DÍA DE LA SEMANA (0=Lunes, 1=Martes...):")
    df['DiaSemana'] = df['Fecha_DT'].dt.weekday
    for dia in range(7):
        nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        df_dia = df[df['DiaSemana'] == dia]
        if not df_dia.empty:
            moda_dia = df_dia['SuperGana'].mode().iloc[0]
            frec_moda = (df_dia['SuperGana'] == moda_dia).sum()
            print(f"  {nombres[dia]}: El sistema tiende a soltar el `{moda_dia}` ({frec_moda} veces).")

    # 2. LA REGLA DEL "NÚMERO SOMBRA" (CONCATENACIÓN)
    # ¿Si sale el X hoy, qué sale mañana?
    print("\n[2] NÚMEROS SOMBRA (Si sale A, suele salir B después):")
    df['Next_Num'] = df['SuperGana'].shift(-1)
    # Buscamos pares frecuentes
    df['Par'] = df['SuperGana'] + " -> " + df['Next_Num'].fillna('')
    pares_frecuentes = df['Par'].value_counts().head(5)
    print(f"  Secuencias de días seguidos más detectadas:\n{pares_frecuentes.to_string()}")

    # 3. EL TRUCO DEL "TERMINAL REPETIDO"
    # ¿Se repite el mismo terminal que ayer?
    df['Terminal'] = df['SuperGana'].str[-1]
    df['Prev_Terminal'] = df['Terminal'].shift(1)
    coincidencias = (df['Terminal'] == df['Prev_Terminal']).sum()
    print(f"\n[3] PERSISTENCIA DE TERMINAL: En {coincidencias} casos, el sorteo siguiente terminó en el mismo número que el anterior ({coincidencias/len(df)*100:.1f}%).")

    # 4. TRUCO DE LA SUMA (PESO DIGITAL)
    # ¿La suma de los dígitos suele ser la misma?
    df['SumaDigitos'] = df['SuperGana'].apply(lambda x: sum(int(d) for d in x if d.isdigit()))
    suma_moda = df['SumaDigitos'].mode().iloc[0]
    print(f"\n[4] PESO DIGITAL: El { (df['SumaDigitos'] == suma_moda).sum() / len(df) * 100:.1f}% de los números suman exactamente {suma_moda}.")
    
    # 5. ANOMALÍA DE FECHAS "PUENTE"
    print("\n[5] ANOMALÍA DE FECHAS CLAVE:")
    fechas_clave = ['15', '30', '17'] # Quincenas y hoy
    for f in fechas_clave:
        df_f = df[df['Fecha_DT'].dt.day == int(f)]
        if not df_f.empty:
            top_f = df_f['SuperGana'].value_counts().idxmax()
            print(f"  Los días {f} el sistema se inclina por el `{top_f}`.")

if __name__ == "__main__":
    investigacion_avanzada()
