import os
import requests
import threading
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from bs4 import BeautifulSoup
import pandas as pd
import telebot
from datetime import datetime, timedelta
from dotenv import load_dotenv
from collections import Counter
import re

# ==========================================
# CONFIGURACIÓN INICIAL
# ==========================================
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')

if not TOKEN:
    raise ValueError("❌ ERROR: No se encontró el TELEGRAM_TOKEN en las variables de entorno.")

bot = telebot.TeleBot(TOKEN)
CSV_FILE = 'historial_loterias.csv'

# ==========================================
# 1. MÓDULO WEB SCRAPER (RECOLECTOR MEJORADO)
# ==========================================

def normalizar_hora(texto_hora):
    """Convierte cualquier formato de hora de SuperGana a formato estándar."""
    texto = texto_hora.strip().lower()
    # Mapeo de formatos conocidos
    mapeo = {
        '9 am': '9 am', '9am': '9 am', '9:00': '9 am',
        '9 de la mañana': '9 am', '09:00': '9 am',
        '12 am': '12 am', '12:00': '12 am', '12 pm': '12 am',
        '1 pm': '1 pm', '1pm': '1 pm', '13:00': '1 pm',
        '1 de la tarde': '1 pm',
        '4 pm': '4 pm', '4pm': '4 pm', '16:00': '4 pm',
        '4 de la tarde': '4 pm',
        '7 pm': '7 pm', '7pm': '7 pm', '19:00': '7 pm',
        '7 de la noche': '7 pm',
        '10 pm': '10 pm', '10pm': '10 pm', '22:00': '10 pm',
        '10 de la noche': '10 pm',
    }
    if texto in mapeo:
        return mapeo[texto]
    # Intentar extraer hora numérica
    nums = re.findall(r'\d+', texto)
    if nums:
        h = int(nums[0])
        if h == 9: return '9 am'
        if h == 12: return '12 am'
        if h == 1 or h == 13: return '1 pm'
        if h == 4 or h == 16: return '4 pm'
        if h == 7 or h == 19: return '7 pm'
        if h == 10 or h == 22: return '10 pm'
    return texto_hora.strip()  # Devolver original si no se reconoce


def raspar_resultados():
    """
    Extrae resultados de los últimos 30 días.
    V3: Normaliza horas, reintenta fallos, filtra datos vacíos.
    """
    import time
    from datetime import timedelta

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "X-Requested-With": "XMLHttpRequest"
    }

    nuevos_registros = []
    dias_ok = 0
    dias_fail = []

    for i in range(30):
        fecha_obj = datetime.now() - timedelta(days=i)
        fecha_req = fecha_obj.strftime("%d/%m/%Y")
        url = f"https://supergana.com.ve/pruebah.php?bt={fecha_req}"

        exito = False
        for intento in range(3):
            try:
                response = requests.get(url, headers=headers, timeout=15, verify=False)
                if response.status_code != 200:
                    time.sleep(1)
                    continue
                soup = BeautifulSoup(response.text, 'html.parser')
                filas = soup.find_all('tr')
                registros_dia = 0
                for fila in filas:
                    th_hora = fila.find('th', scope='row')
                    columnas = fila.find_all('td')
                    if not th_hora or len(columnas) < 2: continue

                    # Normalizar la hora
                    hora_raw = th_hora.text.strip()
                    hora_sorteo = normalizar_hora(hora_raw)

                    # Buscar TODOS los h3.ger en las primeras 2 columnas
                    sg_obj = columnas[0].find('h3', class_='ger')
                    tg_obj = columnas[1].find('h3', class_='ger')

                    if sg_obj and tg_obj:
                        sg_texto = sg_obj.get_text(strip=True)
                        tg_texto = tg_obj.get_text(strip=True)

                        # Filtrar valores vacíos, '+', 'xxx', 'X'
                        if sg_texto in ('', '+', 'xxx', 'X', 'x') or tg_texto in ('', '+', 'xxx', 'X', 'x'):
                            continue

                        sg_limpio = ''.join(filter(str.isdigit, sg_texto))
                        tg_limpio = ''.join(filter(str.isdigit, tg_texto))

                        if len(sg_limpio) >= 4 and len(tg_limpio) >= 1:
                            nuevos_registros.append({
                                'Fecha': fecha_obj.strftime("%Y-%m-%d"),
                                'Sorteo': hora_sorteo,
                                'SuperGana': sg_limpio[-4:],
                                'TripleGana': tg_limpio[-1]
                            })
                            registros_dia += 1
                if registros_dia > 0:
                    exito = True
                    dias_ok += 1
                    break
                else:
                    time.sleep(1)
            except Exception as e:
                print(f"Error raspando {fecha_req} (intento {intento+1}): {e}")
                time.sleep(1)

        if not exito:
            dias_fail.append(fecha_req)

    if nuevos_registros:
        df_nuevos = pd.DataFrame(nuevos_registros)
        if os.path.exists(CSV_FILE):
            df_old = pd.read_csv(CSV_FILE)
            df_final = pd.concat([df_old, df_nuevos]).drop_duplicates(subset=['Fecha', 'Sorteo'], keep='last')
        else:
            df_final = df_nuevos

        # CRÍTICO: Ordenar cronológicamente y por hora del sorteo
        ORDEN_SORTEO = {'1 pm': 1, '4 pm': 2, '7 pm': 3, '10 pm': 4}
        df_final['Fecha_DT'] = pd.to_datetime(df_final['Fecha'], errors='coerce')
        df_final['Sorteo_Orden'] = df_final['Sorteo'].map(ORDEN_SORTEO).fillna(5)
        df_final = df_final.sort_values(by=['Fecha_DT', 'Sorteo_Orden'], ascending=True)
        df_final = df_final.drop(columns=['Fecha_DT', 'Sorteo_Orden'])
        df_final.to_csv(CSV_FILE, index=False)
        return {'ok': True, 'dias_ok': dias_ok, 'dias_fail': dias_fail,
                'total': len(df_final)}
    return {'ok': False, 'dias_ok': 0, 'dias_fail': dias_fail, 'total': 0}


# ==========================================
# 2. PREPARACIÓN DE DATOS (REUTILIZABLE)
# ==========================================

def cargar_y_preparar_datos():
    """Carga el CSV y prepara el DataFrame con columnas normalizadas."""
    if not os.path.exists(CSV_FILE):
        return None
    df = pd.read_csv(CSV_FILE)
    if df.empty:
        return None

    df['Fecha_DT'] = pd.to_datetime(df['Fecha'], errors='coerce')
    df = df.dropna(subset=['Fecha_DT'])
    df['SuperGana'] = df['SuperGana'].astype(str).str.zfill(4)
    df['TripleGana'] = df['TripleGana'].astype(str).str.extract(r'(\d)')[0]
    df = df.dropna(subset=['TripleGana'])
    df['Sorteo'] = df['Sorteo'].fillna('').astype(str)

    # Columnas de dígitos individuales
    df['D1'] = df['SuperGana'].str[0]
    df['D2'] = df['SuperGana'].str[1]
    df['D3'] = df['SuperGana'].str[2]
    df['D4'] = df['SuperGana'].str[3]
    df['Terminal2'] = df['SuperGana'].str[-2:]
    df['Terminal3'] = df['SuperGana'].str[-3:]
    df['Dia'] = df['Fecha_DT'].dt.day
    df['Mes'] = df['Fecha_DT'].dt.month
    df['DiaSemana'] = df['Fecha_DT'].dt.weekday
    df['SemanaMes'] = ((df['Fecha_DT'].dt.day - 1) // 7 + 1)

    # Asegurar orden cronológico
    ORDEN_SORTEO = {'1 pm': 1, '4 pm': 2, '7 pm': 3, '10 pm': 4}
    df['Sorteo_Orden'] = df['Sorteo'].map(ORDEN_SORTEO).fillna(5)
    df = df.sort_values(by=['Fecha_DT', 'Sorteo_Orden'], ascending=True).reset_index(drop=True)

    return df


# ==========================================
# 3. MOTOR DE PREDICCIÓN V2 (10 CAPAS)
# ==========================================

def calcular_prediccion(fecha_input, hora_input):
    """
    Motor de predicción V2 con 10 capas de análisis.
    Retorna dict con: top5, confianza, detalles, capas_activas
    """
    try:
        fecha_str_con_anio = f"{fecha_input}/{datetime.now().year}"
        fecha_parseada = datetime.strptime(fecha_str_con_anio, "%d/%m/%Y")
        dia_obj = fecha_parseada.day
        mes_obj = fecha_parseada.month
        dia_semana = fecha_parseada.weekday()
        semana_mes = (dia_obj - 1) // 7 + 1
    except ValueError:
        return None

    df = cargar_y_preparar_datos()
    if df is None:
        return None

    fecha_consulta_str = fecha_parseada.strftime("%Y-%m-%d")
    df_hora = df[df['Sorteo'].str.contains(hora_input, case=False, na=False)].copy()

    if df_hora.empty:
        return None

    # Diccionario para acumular puntos por número
    puntos = Counter()
    capas_activas = []
    detalles = {}

    # =========================================
    # CAPA 1: SUCESORES DIRECTOS (MUY ALTO PESO)
    # Busca: si a las 4pm salió X, qué salió a las 10pm históricamente
    # =========================================
    sugerencias_sucesoras = []

    if "10 pm" in hora_input.lower():
        # Buscar resultado de 4pm del mismo día
        res_prev = df[(df['Fecha'] == fecha_consulta_str) & (df['Sorteo'].str.contains("4 pm"))]
        hora_previa = "4 pm"
    elif "4 pm" in hora_input.lower():
        res_prev = df[(df['Fecha'] == fecha_consulta_str) & (df['Sorteo'].str.contains("1 pm"))]
        hora_previa = "1 pm"
    elif "7 pm" in hora_input.lower():
        res_prev = df[(df['Fecha'] == fecha_consulta_str) & (df['Sorteo'].str.contains("4 pm"))]
        hora_previa = "4 pm"
    else:
        res_prev = pd.DataFrame()
        hora_previa = None

    if not res_prev.empty and hora_previa:
        val_previo = str(res_prev.iloc[-1]['SuperGana'])
        terminal_prev = val_previo[-2:]

        # Buscar TODOS los sorteos del horario previo que terminen igual
        df_previo = df[df['Sorteo'].str.contains(hora_previa, case=False, na=False)]

        for idx in df_previo.index:
            row = df.loc[idx]
            if str(row['SuperGana']).endswith(terminal_prev):
                # Buscar la siguiente fila que sea del horario consultado Y del MISMO día
                fecha_row = row['Fecha']
                siguiente = df[(df['Fecha'] == fecha_row) &
                               (df['Sorteo'].str.contains(hora_input, case=False, na=False))]
                if not siguiente.empty:
                    sugerencias_sucesoras.append(siguiente.iloc[0]['SuperGana'])

        if sugerencias_sucesoras:
            capas_activas.append("🔗 Sucesores")
            detalles['sucesores'] = f"Terminal {hora_previa}: {terminal_prev}"
            for s in sugerencias_sucesoras:
                puntos[s] += 5  # Peso alto

    # =========================================
    # CAPA 2: FECHA EXACTA HISTÓRICA (ALTO PESO)
    # Mismo día + mes + hora en otros años
    # =========================================
    c_fecha = df_hora[(df_hora['Dia'] == dia_obj) & (df_hora['Mes'] == mes_obj)]
    if not c_fecha.empty:
        capas_activas.append("📅 Fecha exacta")
        detalles['fecha_exacta'] = [f"{r['Fecha']}→{r['SuperGana']}" for _, r in c_fecha.iterrows()]
        for _, r in c_fecha.iterrows():
            puntos[r['SuperGana']] += 4

    # =========================================
    # CAPA 3: DÍGITO INICIAL DOMINANTE (NUEVO)
    # Si el 18/03 de varios años siempre empieza con 7...
    # =========================================
    if not c_fecha.empty:
        digitos_iniciales = c_fecha['D1'].value_counts()
        if len(digitos_iniciales) > 0:
            digito_top = digitos_iniciales.index[0]
            frecuencia = digitos_iniciales.iloc[0]
            total = len(c_fecha)
            if frecuencia >= 2 or (total <= 2 and frecuencia == total):
                capas_activas.append(f"🔢 Dígito inicial '{digito_top}'")
                detalles['digito_inicial'] = f"'{digito_top}' domina en {frecuencia}/{total} sorteos"
                # Dar puntos a todos los números que empiecen con ese dígito en el pool del mes
                df_digito = df_hora[(df_hora['Mes'] == mes_obj) & (df_hora['D1'] == digito_top)]
                for _, r in df_digito.iterrows():
                    puntos[r['SuperGana']] += 3

    # =========================================
    # CAPA 4: TERMINALES CALIENTES (2 y 3 cifras)
    # =========================================
    df_mes_hora = df_hora[df_hora['Mes'] == mes_obj]

    # Terminal 2 cifras
    term2_freq = df_mes_hora['Terminal2'].value_counts()
    top_term2 = term2_freq.head(3).index.tolist() if not term2_freq.empty else []

    # Terminal 3 cifras
    term3_freq = df_mes_hora['Terminal3'].value_counts()
    top_term3 = term3_freq.head(2).index.tolist() if not term3_freq.empty else []

    if top_term2 or top_term3:
        capas_activas.append("🔥 Terminales calientes")
        detalles['terminales'] = {'t2': top_term2, 't3': top_term3}

        for term in top_term2:
            matches = df_hora[df_hora['Terminal2'] == term]
            for _, r in matches.iterrows():
                puntos[r['SuperGana']] += 2

        for term in top_term3:
            matches = df_hora[df_hora['Terminal3'] == term]
            for _, r in matches.iterrows():
                puntos[r['SuperGana']] += 3

    # =========================================
    # CAPA 5: SEMANA DEL MES (MEDIO PESO)
    # =========================================
    c_semana = df_hora[(df_hora['Mes'] == mes_obj) & (df_hora['SemanaMes'] == semana_mes)]
    if not c_semana.empty:
        capas_activas.append("📆 Semana del mes")
        for _, r in c_semana.iterrows():
            puntos[r['SuperGana']] += 2

    # =========================================
    # CAPA 6: DÍA DE LA SEMANA (MEDIO PESO)
    # =========================================
    c_diasem = df_hora[(df_hora['Mes'] == mes_obj) & (df_hora['DiaSemana'] == dia_semana)]
    if not c_diasem.empty:
        capas_activas.append("🗓 Día de semana")
        for _, r in c_diasem.iterrows():
            puntos[r['SuperGana']] += 2

    # =========================================
    # CAPA 7: NÚMEROS CALIENTES ÚLTIMOS 7 DÍAS
    # =========================================
    fecha_7d_atras = fecha_parseada - timedelta(days=7)
    df_recientes = df_hora[df_hora['Fecha_DT'] >= fecha_7d_atras]
    if not df_recientes.empty:
        capas_activas.append("🌡 Calientes 7 días")
        term2_recientes = df_recientes['Terminal2'].value_counts()
        for term, count in term2_recientes.head(3).items():
            matches = df_hora[df_hora['Terminal2'] == term]
            for _, r in matches.head(5).iterrows():
                puntos[r['SuperGana']] += count

    # =========================================
    # CAPA 8: NÚMEROS FRÍOS QUE ESTÁN POR SALIR
    # Terminales que llevan mucho sin salir en este horario
    # =========================================
    if len(df_hora) > 30:
        ultimos_30 = df_hora.tail(30)['Terminal2'].tolist()
        todos_term2 = df_hora['Terminal2'].value_counts().head(20).index.tolist()
        frios = [t for t in todos_term2 if t not in ultimos_30]
        if frios:
            capas_activas.append("❄️ Fríos por salir")
            detalles['frios'] = frios[:3]
            for term in frios[:3]:
                matches = df_hora[df_hora['Terminal2'] == term]
                if not matches.empty:
                    mejor = matches['SuperGana'].value_counts().head(1).index[0]
                    puntos[mejor] += 2

    # =========================================
    # CAPA 9: PATRONES CONSECUTIVOS
    # Si el día anterior salió X, qué tiende a salir al día siguiente
    # =========================================
    fecha_anterior_str = (fecha_parseada - timedelta(days=1)).strftime("%Y-%m-%d")
    res_ayer = df_hora[df_hora['Fecha'] == fecha_anterior_str]
    if not res_ayer.empty:
        val_ayer = str(res_ayer.iloc[-1]['SuperGana'])
        term_ayer = val_ayer[-2:]
        capas_activas.append("🔄 Patrón día anterior")
        detalles['dia_anterior'] = f"Ayer: {val_ayer}"

        # Buscar qué salió al día siguiente cada vez que este terminal apareció
        for idx in df_hora.index:
            row = df_hora.loc[idx]
            if str(row['SuperGana']).endswith(term_ayer):
                fecha_siguiente = row['Fecha_DT'] + timedelta(days=1)
                fecha_sig_str = fecha_siguiente.strftime("%Y-%m-%d")
                resultado_sig = df_hora[df_hora['Fecha'] == fecha_sig_str]
                if not resultado_sig.empty:
                    for _, r in resultado_sig.iterrows():
                        puntos[r['SuperGana']] += 3

    # =========================================
    # CAPA 10: ANÁLISIS DE POSICIÓN DE DÍGITOS
    # Para cada posición (1-4), cuál es el dígito más frecuente
    # en este mes+hora. Buscar números que tengan esos dígitos.
    # =========================================
    if not df_mes_hora.empty:
        d1_top = df_mes_hora['D1'].value_counts().head(2).index.tolist()
        d4_top = df_mes_hora['D4'].value_counts().head(2).index.tolist()

        if d1_top and d4_top:
            capas_activas.append("🎯 Posición de dígitos")
            detalles['digitos_posicion'] = {
                'inicio': d1_top,
                'final': d4_top
            }
            # Bonus a números que tengan tanto el inicio como el final frecuentes
            candidatos = df_hora[
                (df_hora['D1'].isin(d1_top)) & (df_hora['D4'].isin(d4_top))
            ]
            for _, r in candidatos.iterrows():
                puntos[r['SuperGana']] += 2

    # =========================================
    # RESULTADO FINAL
    # =========================================
    if not puntos:
        return None

    # Obtener top 5
    top5 = [num for num, _ in puntos.most_common(5)]

    # Calcular confianza real basada en cuántas capas contribuyeron
    max_capas = 10
    confianza = min(99, int((len(capas_activas) / max_capas) * 80 + 15))

    # Calcular la "fuerza" del #1 vs #2 para ajustar confianza
    if len(puntos) >= 2:
        top2 = puntos.most_common(2)
        ratio = top2[0][1] / max(top2[1][1], 1)
        if ratio >= 2.0:
            confianza = min(99, confianza + 10)  # #1 es muy dominante
        elif ratio <= 1.1:
            confianza = max(20, confianza - 10)   # Muy parejo, menos certeza

    # Top rareza (terminal más frecuente del mes)
    top_rareza = None
    if top_term3:
        rareza_matches = df[df['SuperGana'].str.endswith(top_term3[0])]
        if not rareza_matches.empty:
            top_rareza = rareza_matches['SuperGana'].value_counts().head(1).index[0]

    return {
        'top5': top5,
        'top3': top5[:3],
        'confianza': confianza,
        'capas_activas': capas_activas,
        'detalles': detalles,
        'top_term_2': top_term2,
        'top_term_3': top_term3,
        'top_rareza': top_rareza,
        'tiene_sucesores': len(sugerencias_sucesoras) > 0,
        'puntos': dict(puntos.most_common(5))
    }


# ==========================================
# 4. MÓDULO BOT DE TELEGRAM (UI MEJORADA)
# ==========================================

DISCLAIMER = "\n_⚠️ La lotería es azar. Estos números son sugerencias basadas en estadística histórica y no garantizan resultados futuros._"

@bot.message_handler(commands=['start', 'help'])
def comando_ayuda(message):
    bienvenida = (
        "💎 *RIFASTATS VE — INTELIGENCIA ESTADÍSTICA V2*\n\n"
        "Motor de análisis con *10 capas* de predicción.\n\n"
        "🧠 *Capas de análisis:*\n"
        "🔗 Sucesores directos entre sorteos\n"
        "📅 Fecha exacta histórica multi-año\n"
        "🔢 Dígito inicial dominante\n"
        "🔥 Terminales calientes (2 y 3 cifras)\n"
        "📆 Patrón semanal + día de semana\n"
        "🌡 Números calientes últimos 7 días\n"
        "❄️ Números fríos por salir\n"
        "🔄 Patrón del día anterior\n"
        "🎯 Análisis posicional de dígitos\n\n"
        "📌 *Comandos:*\n"
        "➥ `/patron DD/MM HORA` — Predicción con detalles\n"
        "➥ `/dia DD/MM` — Predicción de todo el día\n"
        "➥ `/actualizar` — Sincronizar resultados\n"
        "➥ `/stats` — Ver estadísticas del historial\n\n"
        "💡 *Ejemplo:*\n"
        "`/patron 19/03 10 pm`\n"
        "`/dia 19/03`"
    )
    bot.reply_to(message, bienvenida, parse_mode="Markdown")


@bot.message_handler(commands=['actualizar'])
def comando_actualizar(message):
    bot.reply_to(message, "⏳ _Iniciando módulo Scraper..._", parse_mode="Markdown")

    def bg_scrape():
        resultado = raspar_resultados()
        if resultado and resultado['ok']:
            try:
                df = pd.read_csv(CSV_FILE)
                total = len(df)
                fechas = pd.to_datetime(df['Fecha'], errors='coerce')
                fecha_min = fechas.min().strftime("%d/%m/%Y") if not fechas.empty else "?"
                fecha_max = fechas.max().strftime("%d/%m/%Y") if not fechas.empty else "?"

                msg = (f"✅ *¡Historial actualizado y ordenado!*\n"
                       f"📊 *{total}* sorteos en base de datos\n"
                       f"📅 Desde: `{fecha_min}` hasta: `{fecha_max}`\n"
                       f"🌐 Días raspados: *{resultado['dias_ok']}*/30\n")

                if resultado['dias_fail']:
                    msg += f"⚠️ Sin datos para: `{'`, `'.join(resultado['dias_fail'][:5])}`\n"

                msg += "🔄 Duplicados eliminados, orden cronológico verificado."
                bot.reply_to(message, msg, parse_mode="Markdown")
            except:
                bot.reply_to(message, "✅ *¡Historial actualizado!*", parse_mode="Markdown")
        else:
            fail_info = ""
            if resultado and resultado['dias_fail']:
                fail_info = f"\nDías fallidos: `{'`, `'.join(resultado['dias_fail'][:5])}`"
            bot.reply_to(message, f"❌ *Error* al procesar datos web.{fail_info}", parse_mode="Markdown")

    threading.Thread(target=bg_scrape).start()


@bot.message_handler(commands=['patron'])
def comando_patron(message):
    try:
        argumentos = message.text.split(" ", 2)
        if len(argumentos) < 3:
            bot.reply_to(message, "⚠️ *Formato:* `/patron DD/MM HORA`\nEj: `/patron 19/03 10 pm`", parse_mode="Markdown")
            return

        fecha_input = argumentos[1].strip()
        hora_input = argumentos[2].strip()

        bot.send_chat_action(message.chat.id, 'typing')
        resultado = calcular_prediccion(fecha_input, hora_input)

        if resultado is None:
            bot.reply_to(message, "⚠ Datos insuficientes. Ejecuta `/actualizar` primero.", parse_mode="Markdown")
            return

        # --- Construir respuesta visual ---
        res = f"🎯 *SISTEMA DE PROYECCIÓN V2 — TOP 5*\n"
        res += f"📅 *Análisis:* {fecha_input} | 🕒 *Sorteo:* {hora_input}\n"
        res += f"━━━━━━━━━━━━━━━━━━━━\n\n"

        # Top 5 números
        res += f"✨ *NÚMEROS CON MAYOR PROBABILIDAD:*\n"
        iconos = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, num in enumerate(resultado['top5']):
            pts = resultado['puntos'].get(num, 0)
            barra = "█" * min(pts, 15)
            res += f"{iconos[i]} `{num}` — {pts}pts {barra}\n"

        # Terminales calientes
        if resultado['top_term_2']:
            res += f"\n🔥 *TERMINALES CALIENTES:*\n"
            res += f"  2 cifras: `{'`, `'.join(resultado['top_term_2'][:3])}`\n"
        if resultado['top_term_3']:
            res += f"  3 cifras: `{'`, `'.join(resultado['top_term_3'][:2])}`\n"

        # Rareza
        if resultado['top_rareza']:
            res += f"\n🔮 *RAREZA SUGERIDA:* `{resultado['top_rareza']}`\n"

        # Capas activas
        res += f"\n📊 *ANÁLISIS ACTIVADOS ({len(resultado['capas_activas'])}/10):*\n"
        for capa in resultado['capas_activas']:
            res += f"  ✅ {capa}\n"

        # Detalles relevantes
        if 'digito_inicial' in resultado['detalles']:
            res += f"\n🔢 *Patrón dígito:* {resultado['detalles']['digito_inicial']}\n"
        if 'dia_anterior' in resultado['detalles']:
            res += f"🔄 *Ref. día anterior:* {resultado['detalles']['dia_anterior']}\n"
        if 'sucesores' in resultado['detalles']:
            res += f"🔗 *Sucesores:* {resultado['detalles']['sucesores']}\n"

        # Confianza real
        conf = resultado['confianza']
        if conf >= 70:
            emoji_conf = "🟢"
        elif conf >= 50:
            emoji_conf = "🟡"
        else:
            emoji_conf = "🔴"

        res += f"\n{emoji_conf} *Nivel de Confianza:* {conf}%"
        if conf >= 70:
            res += " _(Alta fuerza estadística)_"
        elif conf >= 50:
            res += " _(Fuerza moderada)_"
        else:
            res += " _(Datos limitados — usar con precaución)_"

        res += DISCLAIMER

        bot.reply_to(message, res, parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"❌ Error en motor: `{e}`")


# ==========================================
# COMANDO /dia - Predicción completa de un día
# ==========================================
DIAS_SEMANA_ES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

@bot.message_handler(commands=['dia'])
def comando_dia(message):
    try:
        argumentos = message.text.split(" ", 1)
        if len(argumentos) < 2:
            bot.reply_to(message, "⚠️ *Formato:* `/dia DD/MM` (Ej: `/dia 19/03`)", parse_mode="Markdown")
            return

        fecha_input = argumentos[1].strip()

        try:
            fecha_str_con_anio = f"{fecha_input}/{datetime.now().year}"
            fecha_parseada = datetime.strptime(fecha_str_con_anio, "%d/%m/%Y")
            nombre_dia = DIAS_SEMANA_ES[fecha_parseada.weekday()]
        except ValueError:
            bot.reply_to(message, "❌ *Error de fecha.* Usa DD/MM.", parse_mode="Markdown")
            return

        bot.send_chat_action(message.chat.id, 'typing')

        horas = ["1 pm", "4 pm", "10 pm"]
        emojis_hora = {"1 pm": "🌤", "4 pm": "🌅", "10 pm": "🌙"}

        res = f"📅 *PREDICCIÓN COMPLETA V2*\n"
        res += f"🗓 *{nombre_dia} {fecha_input}*\n"
        res += f"━━━━━━━━━━━━━━━━━━━━\n"

        for hora in horas:
            resultado = calcular_prediccion(fecha_input, hora)
            emoji = emojis_hora[hora]
            res += f"\n{emoji} *Sorteo {hora.upper()}:*\n"

            if resultado and resultado['top5']:
                iconos = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
                for i, num in enumerate(resultado['top5'][:3]):
                    pts = resultado['puntos'].get(num, 0)
                    res += f"  {iconos[i]} `{num}` ({pts}pts)\n"

                conf = resultado['confianza']
                if conf >= 70:
                    emoji_conf = "🟢"
                elif conf >= 50:
                    emoji_conf = "🟡"
                else:
                    emoji_conf = "🔴"
                res += f"  {emoji_conf} Confianza: {conf}%\n"

                if resultado['top_rareza']:
                    res += f"  🔮 Rareza: `{resultado['top_rareza']}`\n"

                # Mostrar capas activas resumidas
                res += f"  📊 {len(resultado['capas_activas'])}/10 capas activas\n"
            else:
                res += "  ⚠ Sin datos suficientes\n"

        res += f"\n━━━━━━━━━━━━━━━━━━━━"
        res += DISCLAIMER

        bot.reply_to(message, res, parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"❌ Error en motor: `{e}`")


# ==========================================
# COMANDO /stats - Estadísticas del historial
# ==========================================
@bot.message_handler(commands=['stats'])
def comando_stats(message):
    try:
        df = cargar_y_preparar_datos()
        if df is None:
            bot.reply_to(message, "⚠ Sin datos. Ejecuta `/actualizar`", parse_mode="Markdown")
            return

        total = len(df)
        fecha_min = df['Fecha_DT'].min().strftime("%d/%m/%Y")
        fecha_max = df['Fecha_DT'].max().strftime("%d/%m/%Y")

        # Número más frecuente
        top_num = df['SuperGana'].value_counts().head(3)
        # Terminal más frecuente
        top_term = df['Terminal2'].value_counts().head(3)
        # Dígito inicial más frecuente
        top_d1 = df['D1'].value_counts().head(3)

        res = "📊 *ESTADÍSTICAS DEL HISTORIAL*\n"
        res += f"━━━━━━━━━━━━━━━━━━━━\n\n"
        res += f"📁 Total de sorteos: *{total}*\n"
        res += f"📅 Desde: `{fecha_min}`\n"
        res += f"📅 Hasta: `{fecha_max}`\n\n"

        res += "🔢 *Números más frecuentes:*\n"
        for num, count in top_num.items():
            res += f"  `{num}` → {count} veces\n"

        res += "\n🎯 *Terminales más frecuentes (2 cifras):*\n"
        for term, count in top_term.items():
            res += f"  `{term}` → {count} veces\n"

        res += "\n🔤 *Dígito inicial más común:*\n"
        for d, count in top_d1.items():
            pct = round(count / total * 100, 1)
            res += f"  `{d}` → {pct}%\n"

        bot.reply_to(message, res, parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"❌ Error: `{e}`")


# ==========================================
# INICIO DE EJECUCIÓN
# ==========================================
if __name__ == "__main__":
    print("🤖 Iniciando RifaStats VE — Motor V2...")
    if not os.path.exists(CSV_FILE):
        pd.DataFrame(columns=['Fecha', 'Sorteo', 'SuperGana', 'TripleGana']).to_csv(CSV_FILE, index=False)

    print("✅ Bot funcionando. Presiona Ctrl+C para detener.")
    try:
        bot.infinity_polling(timeout=15, long_polling_timeout=5)
    except (KeyboardInterrupt, SystemExit):
        import sys
        sys.exit()
    except Exception as e:
        print(f"Error fatal: {e}")
