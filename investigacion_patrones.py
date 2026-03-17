import pandas as pd
import numpy as np
from datetime import datetime

CSV_FILE = 'historial_loterias.csv'

def detectar_anomalias():
    if not pd.io.common.file_exists(CSV_FILE):
        print("CSV no encontrado.")
        return

    df = pd.read_csv(CSV_FILE)
    df['SuperGana'] = df['SuperGana'].astype(str).str.zfill(4)
    df['TripleGana'] = df['TripleGana'].astype(str).str.extract(r'(\d)')[0]
    df = df.dropna(subset=['TripleGana'])
    
    print("--- INVESTIGACIÓN DE 'PATRONES NO ALEATORIOS' ---")
    
    # 1. ¿Hay dígitos "bloqueados" en ciertas posiciones?
    print("\n[1] ANÁLISIS POR POSICIÓN (Dígitos 0-9):")
    for pos in range(4):
        digitos = df['SuperGana'].str[pos].value_counts(normalize=True).sort_index() * 100
        min_digito = digitos.idxmin()
        max_digito = digitos.idxmax()
        print(f"  Posición {pos+1}: El dígito {max_digito} sale mucho ({digitos[max_digito]:.1f}%), mientras que el {min_digito} casi no sale ({digitos[min_digito]:.1f}%).")
        if (digitos[max_digito] - digitos[min_digito]) > 5:
            print(f"  ⚠️ ANOMALÍA DETECTADA: Desequilibrio mayor al 5% en posición {pos+1}.")

    # 2. Análisis de "Números Gemelos" o "Escaleras"
    gemelos = df[df['SuperGana'].str[0] == df['SuperGana'].str[1]]
    print(f"\n[2] NÚMEROS REPETITIVOS: El {len(gemelos)/len(df)*100:.1f}% de los sorteos empiezan con números gemelos (Ej: 11xx).")

    # 3. Análisis de Terminal Triple Gana (El más sospechoso)
    print("\n[3] TERMINAL TRIPLE GANA (Última Cifra):")
    terminal_freq = df['TripleGana'].value_counts(normalize=True).sort_index() * 100
    print(f"  Frecuencia de terminales: {terminal_freq.to_dict()}")
    
    # 4. Análisis de "Ciclos" (¿Se repite el mismo número cada cierto tiempo?)
    df['Fecha_DT'] = pd.to_datetime(df['Fecha'])
    df = df.sort_values('Fecha_DT')
    
    # Buscar si hay números que se repiten en menos de 10 días
    duplicados_cerca = 0
    df['diff_dias'] = df.groupby('SuperGana')['Fecha_DT'].diff().dt.days
    sospechosos = df[df['diff_dias'] < 15]
    if not sospechosos.empty:
        print(f"\n[4] DETECCIÓN DE 'BUCLES': Hay {len(sospechosos)} números que se repitieron en menos de 15 días.")
        print(f"  Ejemplos sospechosos: {sospechosos[['Fecha', 'Sorteo', 'SuperGana']].head(5).to_string(index=False)}")

    # 5. Análisis de la Hora (¿Cambia el truco según la hora?)
    print("\n[5] COMPORTAMIENTO POR HORA:")
    for hora in ['1 pm', '4 pm', '10 pm']:
        df_h = df[df['Sorteo'].str.contains(hora, case=False, na=False)]
        if not df_h.empty:
            moda = df_h['SuperGana'].mode().tolist()
            print(f"  A las {hora}: El número que más 'fuerzan' es el {moda[:2]}")

if __name__ == "__main__":
    detectar_anomalias()
