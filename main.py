import os
import requests
import threading
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from bs4 import BeautifulSoup
import pandas as pd
import telebot
from datetime import datetime
from dotenv import load_dotenv

# ==========================================
# CONFIGURACIÓN INICIAL
# ==========================================

# Carga las variables de entorno desde el archivo .env
load_dotenv()

# Obtenemos el token. Asegúrate de tener un archivo .env con TELEGRAM_TOKEN=tu_token_aqui
TOKEN = os.getenv('TELEGRAM_TOKEN')

if not TOKEN:
    raise ValueError("❌ ERROR: No se encontró el TELEGRAM_TOKEN en las variables de entorno. Por favor, configúralo en el archivo .env")

# Inicializar el bot de Telegram
bot = telebot.TeleBot(TOKEN)
CSV_FILE = 'historial_loterias.csv'

# ==========================================
# 1. MÓDULO WEB SCRAPER (RECOLECTOR)
# ==========================================

def raspar_resultados():
    """
    Recolecta los resultados históricos desde el endpoint oculto AJAX de supergana.com.ve
    Hace un escaneo de los últimos 30 días para alimentar la base de datos.
    """
    import time
    from datetime import timedelta
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    registros_salvados = 0
    
    # Vamos a buscar los últimos 30 días
    for i in range(30):
        fecha_obj = datetime.now() - timedelta(days=i)
        # Formato que pide el JS de la página: DD/MM/YYYY
        fecha_req = fecha_obj.strftime("%d/%m/%Y") 
        url = f"https://supergana.com.ve/pruebah.php?bt={fecha_req}"
        
        try:
            response = requests.get(url, headers=headers, timeout=15, verify=False) # Disable verify for VE govt sites usually
            if response.status_code != 200:
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            # Buscamos todas las filas de la tabla generada
            filas = soup.find_all('tr')
            
            for fila in filas:
                # El th contiene la hora (Ej: '10 pm')
                th_hora = fila.find('th', scope='row')
                columnas = fila.find_all('td')
                
                # Para evitar procesar el Thead o filas rotas
                if not th_hora or len(columnas) < 2:
                    continue
                    
                hora_sorteo = th_hora.text.strip()
                
                # Super Gana está en la columna 0 (la primera de <td>)
                # Triple Gana está en la columna 1 (la segunda de <td>)
                sg_obj = columnas[0].find('h3', class_='ger')
                tg_obj = columnas[1].find('h3', class_='ger')
                
                # Validar que los objetos h3 existan y tengan números (evitando las imágenes de ppp.png cuando "no hay sorteo")
                if sg_obj and tg_obj:
                    sg_text = sg_obj.text.strip()
                    tg_text = tg_obj.text.strip()
                    
                    if sg_text and tg_text:
                        # Extraer solo números
                        sg_limpio = ''.join(filter(str.isdigit, sg_text))
                        tg_limpio = ''.join(filter(str.isdigit, tg_text))
                        
                        if len(sg_limpio) >= 4 and len(tg_limpio) >= 1:
                            super_gana_final = sg_limpio[-4:]
                            triple_gana_terminal = tg_limpio[-1]
                            
                            # Normalizar la fecha para el CSV a formato YYYY-MM-DD
                            fecha_csv = fecha_obj.strftime("%Y-%m-%d %H:%M:%S")
                            
                            guardar_en_csv(fecha_csv, hora_sorteo, super_gana_final, triple_gana_terminal)
                            registros_salvados += 1
                            
        except Exception as e:
            print(f"Error raspando fecha {fecha_req}: {e}")
            continue

    print(f"✅ Extracción AJAX finalizada. Se guardaron {registros_salvados} resultados en total de los últimos 30 días.")
    return registros_salvados > 0

def guardar_en_csv(fecha, sorteo, super_gana, triple_gana):
    """Guarda los datos extraídos en el archivo histórico local."""
    nuevo_registro = pd.DataFrame([{
        'Fecha': fecha,
        'Sorteo': sorteo,
        'SuperGana': str(super_gana),
        'TripleGana': str(triple_gana)
    }])
    
    # Validar si el archivo existe para añadir cabeceras o solo datos (append)
    if not os.path.exists(CSV_FILE):
        nuevo_registro.to_csv(CSV_FILE, index=False)
    else:
        nuevo_registro.to_csv(CSV_FILE, mode='a', header=False, index=False)
    print(f"💾 Guardado: {super_gana} (S.Gana) - {triple_gana} (T.Gana)")

# ==========================================
# 2. MÓDULO DE ANÁLISIS ESTADÍSTICO (PANDAS)
# ==========================================

def procesar_estadisticas(serie_numeros):
    """
    Función core del análisis probabilístico basado en el pasado.
    Recibe una serie de pandas y calcula los "Calientes" y "Fríos".
    """
    # 1. NÚMEROS CALIENTES (Mayor frecuencia de aparición global)
    frecuencias = serie_numeros.value_counts()
    calientes = frecuencias.head(5).index.tolist()
    
    # 2. NÚMEROS REZAGADOS / FRÍOS (Mayor tiempo de rezago sin salir)
    # Como el DataFrame va añadiendo datos al final, el índice más alto es el más reciente.
    df_temp = pd.DataFrame({'Numero': serie_numeros}).reset_index()
    # Mantenemos solo la ÚLTIMA aparición cronológica de cada número (keep='last')
    ultima_aparicion = df_temp.drop_duplicates(subset=['Numero'], keep='last')
    
    # Ordenamos de forma ascendente: los de menor índice son los que salieron hace más tiempo
    frios_df = ultima_aparicion.sort_values(by='index', ascending=True)
    
    # Filtramos para que un número "frío" no esté también en el top de "calientes" (mejora de lógica)
    frios_df = frios_df[~frios_df['Numero'].isin(calientes)]
    frios = frios_df['Numero'].head(5).tolist()
    
    # Relleno de seguridad por si no hay historial suficiente
    if len(calientes) < 5:
        calientes.extend(["-" for _ in range(5 - len(calientes))])
    if len(frios) < 5:
        frios.extend(["-" for _ in range(5 - len(frios))])
        
    return calientes, frios

def generar_sugerencias_4_digitos():
    """Analiza la frecuencia de la columna estricta de Super Gana (4 dígitos)."""
    try:
        if not os.path.exists(CSV_FILE): return [], []
        df = pd.read_csv(CSV_FILE)
        if df.empty: return [], []
        
        # Normalizar datos (por si pandas lo lee como número int perdiendo ceros a la izq)
        df['SuperGana'] = df['SuperGana'].astype(str).str.zfill(4)
        
        calientes, frios = procesar_estadisticas(df['SuperGana'])
        return calientes, frios
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return [], []

def generar_sugerencias_5_digitos():
    """Analiza la unión de Super Gana + Triple Gana (5 dígitos)."""
    try:
        if not os.path.exists(CSV_FILE): return [], []
        df = pd.read_csv(CSV_FILE)
        if df.empty: return [], []
        
        # Normalizar datos
        df['SuperGana'] = df['SuperGana'].astype(str).str.zfill(4)
        # Extraer terminal numérico por si llegó con basura HTML 
        df['TripleGana'] = df['TripleGana'].astype(str).str.extract(r'(\d)')[0]
        
        # Eliminar filas donde el terminal sea NaN a causa de mala extracción
        df = df.dropna(subset=['TripleGana'])
        
        # Concatenar para la modalidad de 5 cifras
        serie_5_digitos = df['SuperGana'] + df['TripleGana']
        
        calientes, frios = procesar_estadisticas(serie_5_digitos)
        return calientes, frios
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return [], []

# ==========================================
# 3. MÓDULO BOT DE TELEGRAM (UI)
# ==========================================

DISCLAIMER = "\n_⚠️ La lotería es azar. Estos números son sugerencias basadas en estadística histórica y no garantizan resultados futuros._"

@bot.message_handler(commands=['start', 'help'])
def comando_ayuda(message):
    bienvenida = (
        "¡Hola! Soy tu 🧠 Bot Analista de Loterías.\n\n"
        "Analizo el historial para buscar tendencias.\n\n"
        "📌 *Comandos Disponibles:*\n"
        "🔹 /rifa4 - Sugerencias de 4 cifras (Super Gana)\n"
        "🔹 /rifa5 - Sugerencias de 5 cifras (Super + Terminal Triple)\n\n"
        "🔹 /patron DD/MM HORA - Análisis estacional detallado (Ej: `/patron 17/03 1 pm`)\n\n"
        "🔹 /actualizar - Extraer últimos resultados web (Te avisaré al terminar)"
    )
    bot.reply_to(message, bienvenida, parse_mode="Markdown")

@bot.message_handler(commands=['actualizar'])
def comando_actualizar(message):
    bot.reply_to(message, "⏳ _Iniciando módulo Scraper en segundo plano... Te avisaré al terminar._", parse_mode="Markdown")
    
    def bg_scrape():
        if raspar_resultados():
            bot.reply_to(message, "✅ *¡Historial actualizado!* Los datos han sido importados. Prueba los comandos.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ *Error* al procesar datos web. Revisa la consola o asegúrate de que el DOM no haya cambiado.", parse_mode="Markdown")
            
    threading.Thread(target=bg_scrape).start()

def formatear_y_enviar_respuesta(message, calientes, frios, tipo_rifa):
    """Función de ayuda para armar el bloque Markdown estándar."""
    if not calientes and not frios:
        bot.reply_to(message, "⚠ Aún no hay registros en la base de datos local. Por favor ejecuta /actualizar primero.")
        return

    texto = f"🎯 *Resultados del Análisis Estadístico: {tipo_rifa}*\n\n"
    
    texto += "🔥 *NÚMEROS CALIENTES* (Alta frecuencia de aparición):\n"
    for num in calientes:
        texto += f" ➥ `{num}`\n"
        
    texto += "\n🧊 *NÚMEROS REZAGADOS* (Mayor tiempo en la congeladora):\n"
    for num in frios:
        texto += f" ➥ `{num}`\n"
        
    texto += DISCLAIMER
    
    bot.reply_to(message, texto, parse_mode="Markdown")

@bot.message_handler(commands=['rifa4'])
def comando_rifa4(message):
    bot.send_chat_action(message.chat.id, 'typing')
    calientes, frios = generar_sugerencias_4_digitos()
    formatear_y_enviar_respuesta(message, calientes, frios, "Módulo 4 Dígitos")

@bot.message_handler(commands=['rifa5'])
def comando_rifa5(message):
    bot.send_chat_action(message.chat.id, 'typing')
    calientes, frios = generar_sugerencias_5_digitos()
    formatear_y_enviar_respuesta(message, calientes, frios, "Módulo 5 Dígitos")

@bot.message_handler(commands=['patron'])
def comando_patron_estacional_hora(message):
    try:
        # 1. Validar input
        argumentos = message.text.split(" ", 2) 
        if len(argumentos) < 3:
            bot.reply_to(message, "⚠️ *Formato incorrecto.*\nPor favor usa: `/patron DD/MM HORA`\nEjemplo: `/patron 17/03 1 pm`", parse_mode="Markdown")
            return
            
        fecha_input = argumentos[1].strip()
        hora_input = argumentos[2].strip() 
        
        # 2. Parseo de fecha
        try:
            fecha_str_con_anio = f"{fecha_input}/{datetime.now().year}"
            fecha_parseada = datetime.strptime(fecha_str_con_anio, "%d/%m/%Y")
            dia_obj = fecha_parseada.day
            mes_obj = fecha_parseada.month
            dia_semana = fecha_parseada.weekday() # 0=Lunes
        except ValueError:
            bot.reply_to(message, "❌ *Error de fecha.* Usa DD/MM. Ej: `/patron 17/03 1 pm`", parse_mode="Markdown")
            return
            
        bot.send_chat_action(message.chat.id, 'typing')
        if not os.path.exists(CSV_FILE):
             bot.reply_to(message, "⚠ Base de datos no encontrada. Ejecuta /actualizar.")
             return
             
        df = pd.read_csv(CSV_FILE)
        if df.empty:
            bot.reply_to(message, "⚠ Base de datos vacía. Ejecuta /actualizar.")
            return

        # Preparar datos
        df['Fecha_DT'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha_DT'])
        df['Sorteo'] = df['Sorteo'].fillna('').astype(str)
        df['SuperGana'] = df['SuperGana'].astype(str).str.zfill(4)
        df['TripleGana'] = df['TripleGana'].astype(str).str.extract(r'(\d)')[0]
        df = df.dropna(subset=['TripleGana'])
        df['Combo5'] = df['SuperGana'] + df['TripleGana']
        
        # Filtro de Hora Global
        filtro_hora = df['Sorteo'].str.contains(hora_input, case=False, na=False)
        df_hora = df[filtro_hora].copy()

        # CAPAS DE ANÁLISIS
        # C1: Fecha exacta
        c1 = df_hora[(df_hora['Fecha_DT'].dt.day == dia_obj) & (df_hora['Fecha_DT'].dt.month == mes_obj)]
        # C2: Mismo Mes + Mismo día de la semana
        c2 = df_hora[(df_hora['Fecha_DT'].dt.month == mes_obj) & (df_hora['Fecha_DT'].dt.weekday == dia_semana)]
        # C3: Todo el Mes
        c3 = df_hora[df_hora['Fecha_DT'].dt.month == mes_obj]

        # RECOLECCIÓN
        fuente_top = c2 if len(c2) >= 8 else c3
        top3_4 = fuente_top['SuperGana'].value_counts().head(3).index.tolist()
        top3_5 = fuente_top['Combo5'].value_counts().head(3).index.tolist()

        # Posicional (Mes completo)
        p1 = c3['SuperGana'].str[0].mode()[0] if not c3.empty else '?'
        p2 = c3['SuperGana'].str[1].mode()[0] if not c3.empty else '?'
        p3 = c3['SuperGana'].str[2].mode()[0] if not c3.empty else '?'
        p4 = c3['SuperGana'].str[3].mode()[0] if not c3.empty else '?'
        term = c3['TripleGana'].mode()[0] if not c3.empty else '?'

        res = f"📅 *ANÁLISIS DE PATRÓN: {fecha_input} | 🕒 {hora_input}*\n"
        res += f"_Muestra histórica analizada: {len(c3)} sorteos de este mes._\n\n"
        res += "� *TOP 3 NÚMEROS RECOMENDADOS (4 Cifras):*\n"
        for i, n in enumerate(top3_4, 1):
            medalla = ["🥇", "🥈", "🥉"][i-1]
            res += f"{medalla} `{n}`\n"
        res += "\n� *TOP 3 NÚMEROS RECOMENDADOS (5 Cifras):*\n"
        for i, n in enumerate(top3_5, 1):
            medalla = ["🥇", "🥈", "🥉"][i-1]
            res += f"{medalla} `{n}`\n"
        res += f"\n🧠 *NÚMERO POR POSICIÓN (Tendencia):*\n➥ `{p1}{p2}{p3}{p4}` | Terminal: `{term}`\n"
        if len(c1) > 0:
            res += f"\n📜 *En fechas exactas anteriores salió:* `{', '.join(c1['SuperGana'].unique())}`"
        res += DISCLAIMER
        bot.reply_to(message, res, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error en motor: `{e}`")

# ==========================================
# INICIO DE EJECUCIÓN
# ==========================================
if __name__ == "__main__":
    print("🤖 Iniciando Bot de Telegram...")
    if not os.path.exists(CSV_FILE):
        pd.DataFrame(columns=['Fecha', 'Sorteo', 'SuperGana', 'TripleGana']).to_csv(CSV_FILE, index=False)
    
    print("✅ Bot funcionando fluido. Presiona Ctrl+C para detener.")
    try:
        bot.infinity_polling(timeout=15, long_polling_timeout=5)
    except (KeyboardInterrupt, SystemExit):
        import sys
        sys.exit()
    except Exception as e:
        print(f"Error fatal: {e}")
