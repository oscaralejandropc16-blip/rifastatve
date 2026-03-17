import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import threading
import os
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
CSV_FILE = 'historial_loterias.csv'

def worker(lista_dias):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    registros = []
    for i in lista_dias:
        fecha_obj = datetime.now() - timedelta(days=i)
        fecha_req = fecha_obj.strftime("%d/%m/%Y") 
        url = f"https://supergana.com.ve/pruebah.php?bt={fecha_req}"
        
        try:
            r = requests.get(url, headers=headers, timeout=10, verify=False)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                filas = soup.find_all('tr')
                for fila in filas:
                    th_hora = fila.find('th', scope='row')
                    columnas = fila.find_all('td')
                    if not th_hora or len(columnas) < 2: continue
                    hora_sorteo = th_hora.text.strip()
                    sg_obj = columnas[0].find('h3', class_='ger')
                    tg_obj = columnas[1].find('h3', class_='ger')
                    if sg_obj and tg_obj:
                        sg_limpio = ''.join(filter(str.isdigit, sg_obj.text.strip()))
                        tg_limpio = ''.join(filter(str.isdigit, tg_obj.text.strip()))
                        if len(sg_limpio) >= 4 and len(tg_limpio) >= 1:
                            fecha_csv = fecha_obj.strftime("%Y-%m-%d %H:%M:%S")
                            registros.append({
                                'Fecha': fecha_csv,
                                'Sorteo': hora_sorteo,
                                'SuperGana': sg_limpio[-4:],
                                'TripleGana': tg_limpio[-1]
                            })
        except Exception as e:
            pass
            
    if registros:
        df = pd.DataFrame(registros)
        df.to_csv(CSV_FILE, mode='a', header=not os.path.exists(CSV_FILE), index=False)
        print(f"Guardados {len(registros)} registros. (Ej: dia {lista_dias[0]} al {lista_dias[-1]})")

def main():
    print("Iniciando descarga histórica de 2 años (730 días)...")
    threads = []
    # 730 días en bloques de 30 días
    for chunk in range(0, 730, 30):
        dias = list(range(chunk, chunk + 30))
        t = threading.Thread(target=worker, args=(dias,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    print("Descarga completada. Limpiando duplicados...")
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        df_limpio = df.drop_duplicates(subset=['Fecha', 'Sorteo'])
        # Sort by fecha
        df_limpio = df_limpio.sort_values(by='Fecha')
        df_limpio.to_csv(CSV_FILE, index=False)
        print(f"Archivo limpiado. Total de sorteos guardados: {len(df_limpio)}")

if __name__ == '__main__':
    main()
