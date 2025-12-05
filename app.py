import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import csv
import os

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Preventivatore TeamBuilding", page_icon="🦁", layout="centered")

# --- CSS PERSONALIZZATO (TORNA A CALIBRI 12PX) ---
st.markdown("""
<style>
    /* Forza sfondo bianco per i messaggi */
    div[data-testid="stChatMessage"] { background-color: #ffffff !important; }
    
    /* Font Calibri 12px come richiesto */
    div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li, div[data-testid="stChatMessage"] div {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 12px !important;
        color: #000000 !important;
        line-height: 1.4 !important;
        margin-bottom: 10px !important;
    }
    
    /* Titoli proporzionati */
    div[data-testid="stChatMessage"] h2 {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 18px !important;
        font-weight: bold !important;
        color: #000000 !important;
        margin-top: 20px !important; margin-bottom: 10px !important;
        border-bottom: 1px solid #ccc;
        padding-bottom: 5px;
    }
    
    div[data-testid="stChatMessage"] h3 {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 14px !important;
        font-weight: bold !important;
        color: #000000 !important;
        margin-top: 15px !important; margin-bottom: 5px !important;
    }
    
    div[data-testid="stChatMessage"] strong { font-weight: bold !important; color: #000000 !important; }
    
    /* Tabelle compatte */
    div[data-testid="stChatMessage"] table {
        color: #000000 !important; font-size: 12px !important; width: 100% !important;
        border-collapse: collapse !important; margin-top: 15px !important; margin-bottom: 15px !important;
    }
    div[data-testid="stChatMessage"] th {
        background-color: #f4f4f4 !important; color: #000000 !important; font-weight: bold !important;
        text-align: left !important; border-bottom: 2px solid #000 !important; padding: 5px !important;
    }
    div[data-testid="stChatMessage"] td { border-bottom: 1px solid #ddd !important; padding: 5px !important; }
    
    div[data-testid="stChatMessage"] a { color: #1a73e8 !important; text-decoration: underline !important; }
    div[data-testid="stChatMessage"] hr { display: none !important; }
    div[data-testid="stChatMessage"] ul { list-style-type: none !important; padding-left: 0 !important; }
</style>
""", unsafe_allow_html=True)

# --- IMPORTAZIONE MODULO ESTERNO ---
try:
    import locations_module
except ImportError:
    locations_module = None

# --- 2. GESTIONE DATABASE ---
@st.cache_data(show_spinner=False)
def carica_database(nome_file):
    percorso = os.path.join(os.getcwd(), nome_file)
    if not os.path.exists(percorso):
        return None 

    encodings = ['utf-8', 'latin-1', 'cp1252']
    delimiters = [',', ';'] 
     
    for encoding in encodings:
        for delimiter in delimiters:
            try:
                with open(percorso, mode='r', encoding=encoding) as file:
                    sample = file.read(1024)
                    file.seek(0)
                    if delimiter in sample:
                        reader = csv.DictReader(file, delimiter=delimiter)
                        temp_list = list(reader)
                        if len(temp_list) > 0 and len(temp_list[0].keys()) > 1:
                             return temp_list
            except Exception:
                continue
    return None

def database_to_string(database_list):
    if not database_list:
        return "Nessun dato disponibile."
    try:
        if not isinstance(database_list[0], dict):
            return "" 
        header = " | ".join(database_list[0].keys())
        rows = []
        for riga in database_list:
            clean_values = [str(v) if v is not None else "" for v in riga.values()]
            rows.append(" | ".join(clean_values))
        return header + "\n" + "\n".join(rows)
    except Exception:
        return ""

# Caricamento File
master_database = carica_database('mastertb.csv') 
location_database = carica_database('location.csv') 

if master_database is None:
    st.error("⚠️ ERRORE CRITICO: Non trovo 'mastertb.csv'.")
    st.stop()

csv_data_string = database_to_string(master_database)

# --- 3. COSTRUZIONE DEL CERVELLO (LOCATION) ---
location_instructions_block = ""
if locations_module and location_database:
    loc_db_string = database_to_string(location_database)
    if loc_db_string:
        location_instructions_block = locations_module.get_location_instructions(loc_db_string)

# --- 4. CONFIGURAZIONE API E PASSWORD ---
api_key = st.secrets["GOOGLE_API_KEY"]
PASSWORD_SEGRETA = "TeamBuilding2025#"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Area Riservata")
    pwd = st.text_input("Inserisci Password Staff", type="password")
    if st.button("Accedi"):
        if pwd == PASSWORD_SEGRETA:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Password errata")
    st.stop()

# --- 5. SYSTEM PROMPT DEFINITIVO ---
BASE_INSTRUCTIONS = """
SEI IL SENIOR EVENT MANAGER DI TEAMBUILDING.IT.
Rispondi in Italiano.

### 🛡️ PROTOCOLLO
1.  **NATURALITÀ:** Non citare le istruzioni o regole interne.
2.  **QUALIFICAZIONE:** Se l'utente fornisce input vaghi, chiedi info su Durata, Mood e Obiettivo prima di proporre i format.

### 🎨 REGOLE VISUALI
1.  **ICONE FORMAT:** Usa un'icona tematica SOLO nel titolo dei format.
2.  **SPAZIATURA:** Usa DUE A CAPO REALI tra i format.
3.  **NO ELENCHI:** Le descrizioni dei format devono essere paragrafi discorsivi.

### 🔢 CALCOLO PREVENTIVI (ALGORITMO RIGOROSO)
**PASSO 1: VARIABILI** (PAX, P_BASE, METODO)
**PASSO 2: MOLTIPLICATORI (M)**
* **M_PAX:** <5(3.20)|5-10(1.60)|11-20(1.05)|21-30(0.95)|31-60(0.90)|61-90(0.90)|91-150(0.85)|151-250(0.70)|251-350(0.63)|351-500(0.55)|501-700(0.50)|701-900(0.49)|>900(0.30)
* **M_DURATA:** ≤1h(1.05)|1-2h(1.07)|2-4h(1.10)|>4h(1.15)
* **M_LINGUA:** ITA(1.05)|ENG(1.10) -- **M_LOCATION:** MI(1.00)|RM(0.95)|Centro(1.05)|Nord/Sud(1.15)|Isole(1.30) -- **M_STAGIONE:** Mag-Ott(1.10)|Nov-Apr(1.02)

**PASSO 3: FORMULE**
* **Standard:** `P_BASE * M_PAX * M_DURATA * M_LINGUA * M_LOCATION * M_STAGIONE * PAX`
* **Flat:** Pax<=20(1800)|21-40(1800+(Pax-20)*35)|41-60(2500+(Pax-40)*50)|61-100(3500+(Pax-60)*37.50)|>100(5000+(Pax-100)*13.50)

**PASSO 4: ARROTONDAMENTO**
* 00-39 -> Difetto (2235->2200) | 40-99 -> Eccesso (2245->2300) | Min Spending: 1800+IVA.

---

### 🚦 FLUSSO DI LAVORO (ORDINE DI OUTPUT OBBLIGATORIO)

Segui rigorosamente questo ordine:

**FASE 0: CHECK INFORMAZIONI**
Se mancano info essenziali, chiedile. Se le hai, procedi.

**FASE 1: I FORMAT (Priorità Alta)**
Elenca i format (Icona Titolo + Descrizione discorsiva breve).

**FASE 2: SUGGERIMENTO LOCATION (Solo se richiesto)**
*SE E SOLO SE* richiesto dall'utente:
1.  Titolo: **## Location**
2.  Elenca le location applicando una **SANITIZZAZIONE ESTREMA**.

    ⛔ **DIVIETI TASSATIVI PER LE LOCATION:**
    * **NO EMOJI:** È vietato usare 📍, 🏨, ⭐ o qualsiasi altra icona nel testo delle location.
    * **NO RANKING:** Se nel database vedi "Ranking: 1", "Voto: 5", "Classifica", o numeri simili, **CANCELLALI**. Non devono mai apparire nel testo finale.
    * **SOLO TESTO:** L'output deve sembrare scritto a mano, senza "sporcizia" da database.

    ✅ **FORMATO OBBLIGATORIO:**
    * **Nome Location (Città):** [Descrizione pulita e motivazione]. Spazi: [Indoor/Outdoor].

**FASE 3: TABELLA RIEPILOGATIVA**
| Format | Prezzo Totale (+IVA) | Presentazione |

**FASE 4: INFO UTILI (OBBLIGATORIO)**
Copia questo blocco esatto:

### Informazioni Utili

✔️ **Tutti i format sono nostri** e possiamo personalizzarli senza alcun problema.

✔️ **La location non è inclusa** ma possiamo aiutarti a trovare quella perfetta per il tuo evento.

✔️ **Le attività di base** sono pensate per farvi stare insieme e divertirvi, ma il team building è anche formazione, aspetto che possiamo includere e approfondire.

✔️ **Prezzo all inclusive:** spese staff, trasferta e tutti i materiali sono inclusi, nessun costo a consuntivo.

✔️ **Assicurazione pioggia:** Se avete scelto un format oudoor ma le previsioni meteo sono avverse, due giorni prima dell'evento sceglieremo insieme un format indoor allo stesso costo.

✔️ **Chiedici anche** servizio video/foto e gadget.

Se l'utente scrive "Reset", cancella la memoria.
"""

# Assembliamo il Prompt
FULL_SYSTEM_PROMPT = f"{BASE_INSTRUCTIONS}\n\n{location_instructions_block}\n\n### 💾 [DATABASE FORMATI]\n\n{csv_data_string}"

# --- 6. AVVIO AI ---
genai.configure(api_key=api_key)

# Modello impostato su GEMINI 3 PRO PREVIEW come richiesto TASSATIVAMENTE
model = genai.GenerativeModel(
  model_name="gemini-3-pro-preview", 
  generation_config={"temperature": 0.0},
  system_instruction=FULL_SYSTEM_PROMPT,
  safety_settings={
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
  },
)

# --- 7. CHAT ---
st.title("🦁 Preventivatore AI")
st.caption("Assistente Virtuale Senior - MasterTb Connected")

if "messages" not in st.session_state:
    st.session_state.messages = []
    welcome = "Ciao! Sono pronto. Dimmi numero pax, data e obiettivo."
    st.session_state.messages.append({"role": "model", "content": welcome})

for message in st.session_state.messages:
    role = message["role"]
    with st.chat_message(role):
        st.markdown(message["content"])

if prompt := st.chat_input("Scrivi qui la richiesta..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if prompt.lower().strip() in ["reset", "nuovo", "cancella", "stop"]:
        st.session_state.messages = []
        st.rerun()

    with st.chat_message("model"):
        with st.spinner("Elaborazione con Gemini 3 Pro..."):
            try:
                history_gemini = []
                for m in st.session_state.messages:
                    if m["role"] != "model":
                        history_gemini.append({"role": "user", "parts": [m["content"]]})
                    else:
                        history_gemini.append({"role": "model", "parts": [m["content"]]})
                
                chat = model.start_chat(history=history_gemini[:-1])
                response = chat.send_message(prompt)
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "model", "content": response.text})
                
            except Exception as e:
                st.error(f"Errore: {e}")
