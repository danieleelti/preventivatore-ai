import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from openai import OpenAI
import csv
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="FATTURAGE", page_icon="🦁💰", layout="wide")

# --- CSS PERSONALIZZATO (TUTTA LA FORMATTAZIONE ORIGINALE MANTENUTA) ---
st.markdown("""
<style>
    /* Stile generale messaggi CHAT */
    div[data-testid="stChatMessage"] { background-color: #ffffff !important; border: 1px solid #f0f2f6; border-radius: 10px; padding: 15px; }
    
    /* Font e Testi */
    div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li, div[data-testid="stChatMessage"] div {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 15px !important;
        color: #000000 !important;
        line-height: 1.6 !important;
    }
    
    /* TITOLI FORMAT (H3) */
    div[data-testid="stChatMessage"] h3 {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 17px !important;
        font-weight: 800 !important;
        color: #000000 !important;
        margin-top: 20px !important; 
        margin-bottom: 5px !important;
        text-transform: uppercase !important;
    }

    /* BLOCCHI ROSSI (Titoli Categorie e Tabella) */
    .block-header {
        background-color: #f8f9fa;
        border-left: 5px solid #ff4b4b;
        padding: 15px;
        margin-top: 30px !important;
        margin-bottom: 20px !important;
        border-radius: 0 8px 8px 0;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .block-title {
        font-family: 'Arial Black', sans-serif !important;
        font-size: 18px !important;
        font-weight: 900 !important;
        text-transform: uppercase;
        color: #333 !important;
        display: block;
        margin-bottom: 4px;
    }
    .block-claim {
        font-family: 'Arial', sans-serif !important;
        font-size: 13px !important;
        font-style: italic !important;
        color: #666 !important;
        display: block;
    }

    /* Tabelle */
    div[data-testid="stChatMessage"] table {
        width: 100% !important;
        border-collapse: collapse !important;
        border: 1px solid #e0e0e0 !important;
        font-size: 14px !important;
        margin-top: 10px !important;
    }
    div[data-testid="stChatMessage"] th {
        background-color: #f1f3f4 !important;
        color: #000 !important;
        font-weight: bold;
        text-align: left;
        padding: 12px !important;
        border-bottom: 2px solid #ddd !important;
    }
    div[data-testid="stChatMessage"] td {
        padding: 10px !important;
        border-bottom: 1px solid #eee !important;
    }
    
    /* Sidebar Button */
    .stButton button {
        background-color: #ff4b4b !important;
        color: white !important;
        font-weight: bold !important;
        border: none !important;
        width: 100%;
        height: 50px;
        font-size: 16px !important;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- IMPORTAZIONE MODULO ESTERNO ---
try:
    import locations_module
except ImportError:
    locations_module = None

# --- FUNZIONI DI UTILITÀ ---
def enable_locations_callback():
    st.session_state.enable_locations_state = True
    # FIX: Attiviamo un flag per dire "al prossimo riavvio, riprocessa l'ultimo messaggio"
    st.session_state.retry_trigger = True

def reset_preventivo():
    """Resetta la chat e svuota i campi di input."""
    st.session_state.messages = []
    # Svuota i widget tramite le loro chiavi
    keys_to_clear = ["wdg_cliente", "wdg_pax", "wdg_data", "wdg_citta", "wdg_durata", "wdg_obiettivo"]
    for key in keys_to_clear:
        if key in st.session_state:
            st.session_state[key] = ""

# --- 2. GESTIONE DATABASE (GOOGLE SHEETS) ---
def get_gspread_client():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if "\\n" in creds_dict["private_key"]:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        else:
            st.error("⚠️ Chiave 'gcp_service_account' mancante in secrets.toml")
            return None
    except Exception as e:
        st.error(f"Errore connessione Google: {e}")
        return None

@st.cache_data(ttl=600, show_spinner=False)
def carica_google_sheet(sheet_name):
    client = get_gspread_client()
    if not client: return None
    try:
        sheet = client.open(sheet_name).get_worksheet(0)
        data = sheet.get_all_records()
        return data
    except Exception as e:
        st.error(f"Errore caricamento Sheet '{sheet_name}': {e}")
        return None

def database_to_string(database_list):
    """Converte la lista di dizionari in stringa per il prompt con sanitizzazione link."""
    if not database_list: return "Nessun dato disponibile."
    try:
        if not isinstance(database_list[0], dict): return "" 
        sanitized_list = []
        for riga in database_list:
            clean_riga = {}
            for k, v in riga.items():
                val_str = str(v) if v is not None else ""
                # Pulizia automatica spazi nei link
                if val_str.strip().lower().startswith("http") and " " in val_str:
                    val_str = val_str.replace(" ", "%20")
                clean_riga[k] = val_str
            sanitized_list.append(clean_riga)
        header = " | ".join(sanitized_list[0].keys())
        rows = []
        for riga in sanitized_list:
            clean_values = list(riga.values())
            rows.append(" | ".join(clean_values))
        return header + "\n" + "\n".join(rows)
    except Exception: return ""

# --- FUNZIONE DI SALVATAGGIO ---
def salva_preventivo_su_db(cliente, utente, pax, data_evento, citta, contenuto):
    """Salva una riga nel foglio PreventiviInviatiAi."""
    client = get_gspread_client()
    if not client: return False
    try:
        sheet = client.open("PreventiviInviatiAi").get_worksheet(0)
        tz_ita = pytz.timezone('Europe/Rome')
        now = datetime.now(tz_ita)
        data_oggi = now.strftime("%Y-%m-%d")
        ora_oggi = now.strftime("%H:%M:%S")
        
        # Colonne: Nome Cliente | Utente | Data Prev | Ora Prev | Pax | Data Evento | Città | Contenuto
        row = [cliente, utente, data_oggi, ora_oggi, pax, data_evento, citta, contenuto]
        sheet.append_row(row)
        return True
    except Exception as e:
        st.error(f"❌ Errore durante il salvataggio su Sheet: {e}")
        return False

# --- CARICAMENTO DATI BASE ---
master_database = carica_google_sheet('MasterTbGoogleAi') 
if master_database is None:
    st.error("⚠️ ERRORE CRITICO: Impossibile scaricare il database attività da Google Sheets.")
    st.stop()
csv_data_string = database_to_string(master_database)

# --- 4. CONFIGURAZIONE LOGIN SICURO ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None

if not st.session_state.authenticated:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.title("🔒 Area Riservata")
        pwd = st.text_input("Inserisci Password Staff", type="password")
        
        if st.button("Accedi"):
            users_db = st.secrets.get("passwords", {})
            if pwd in users_db:
                st.session_state.authenticated = True
                st.session_state.username = users_db[pwd]
                st.session_state.messages = [] # Reset chat al login
                st.rerun()
            else:
                st.error("Password errata")
    st.stop()

# --- 4.b INIZIALIZZAZIONE SESSION STATE ---
if "enable_locations_state" not in st.session_state:
    st.session_state.enable_locations_state = False 
if "retry_trigger" not in st.session_state:
    st.session_state.retry_trigger = False

if "messages" not in st.session_state or not st.session_state.messages:
    st.session_state.messages = []
    
    # SALUTO PERSONALIZZATO
    if st.session_state.username == "Francesca":
        welcome_msg = "Ciao squirtina..." 
    else:
        welcome_msg = f"Ciao **{st.session_state.username}**! Usa la barra laterale a sinistra per compilare i dati."
        
    st.session_state.messages.append({"role": "model", "content": welcome_msg})

# --- SIDEBAR ---
with st.sidebar:
    st.title("🦁 FATTURAGE 2.0")
    st.caption(f"Utente: **{st.session_state.username}**") 
    st.markdown("---")
    
    st.subheader("📝 Dati Brief")
    
    # PULSANTE NUOVO PREVENTIVO (Solo se c'è storia)
    if len(st.session_state.messages) > 1:
        if st.button("🔄 NUOVO PREVENTIVO", type="secondary"):
            reset_preventivo()
            st.rerun()
        st.markdown("---")

    # WIDGET INPUT
    cliente_input = st.text_input("Nome Cliente *", placeholder="es. Azienda Rossi SpA", key="wdg_cliente")
    col_pax, col_data = st.columns(2)
    with col_pax: pax_input = st.text_input("N. Pax", placeholder="50", key="wdg_pax")
    with col_data: data_evento_input = st.text_input("Data", placeholder="12 Maggio", key="wdg_data")
    citta_input = st.text_input("Città / Location", placeholder="Milano / Villa Reale", key="wdg_citta")
    durata_input = st.text_input("Durata Attività", placeholder="es. 2-3 ore", key="wdg_durata")
    obiettivo_input = st.text_area("Obiettivo / Mood / Note", placeholder="Descrivi l'obiettivo...", height=100, key="wdg_obiettivo")

    st.markdown("###")
    generate_btn = st.button("🚀 GENERA PREVENTIVO", type="primary")
    st.markdown("---")

    with st.expander("⚙️ Impostazioni Avanzate", expanded=False):
        use_location_db = st.checkbox("🏰 Abilita Database Location", key="enable_locations_state")
        st.markdown("---")
        provider = st.selectbox("Provider AI", ["Google Gemini", "Groq"])
        if provider == "Google Gemini":
            model_options = ["gemini-3-pro-preview", "gemini-2.0-flash-exp", "gemini-1.5-pro-latest", "gemini-1.5-flash"]
            if "gemini-3-pro-preview" not in model_options: model_options.insert(0, "gemini-3-pro-preview")
        elif provider == "Groq":
            model_options = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "mixtral-8x7b-32768"]
        selected_model_name = st.selectbox("Modello", model_options)
        
        api_key = st.secrets.get("GOOGLE_API_KEY") if provider == "Google Gemini" else st.secrets.get("GROQ_API_KEY")
        if not api_key: st.error(f"⚠️ Manca API Key per {provider}")

# --- GESTIONE LOGICA LOCATION ---
location_instructions_block = ""
location_guardrail_prompt = ""

if use_location_db:
    with st.spinner("Caricamento Location..."):
        location_database = carica_google_sheet('LocationGoogleAi')
        if location_database and locations_module:
            loc_db_string = database_to_string(location_database)
            location_instructions_block = locations_module.get_location_instructions(loc_db_string)
            location_guardrail_prompt = f"SUGGERIMENTO LOCATION:\n{location_instructions_block}"
        elif not location_database:
            st.sidebar.warning("⚠️ Errore caricamento Location")
else:
    # Se disabilitato, istruisco l'AI a saltare completamente.
    location_guardrail_prompt = """
    ISTRUZIONE TASSATIVA LOCATION: IL DATABASE LOCATION È SPENTO.
    NON SCRIVERE NULLA SU LOCATION.
    NON INVENTARE LOCATION.
    PASSA DIRETTAMENTE ALLA TABELLA.
    """

# --- 5. SYSTEM PROMPT (AGGIORNATO CON INTRODUZIONE WARM) ---
context_brief = f"DATI BRIEF: Cliente: {cliente_input}, Pax: {pax_input}, Data: {data_evento_input}, Città: {citta_input}, Durata: {durata_input}, Obiettivo: {obiettivo_input}."

BASE_INSTRUCTIONS = f"""
SEI IL SENIOR EVENT MANAGER DI TEAMBUILDING.IT. Rispondi in Italiano.
{context_brief}

⚠️ **IMPORTANTE: ISTRUZIONI DI OUTPUT CLEAN (TASSATIVO)** ⚠️
1. **DIVIETO ASSOLUTO DI META-TESTO:** NON scrivere MAI frasi come "Fase 1", "Analisi del brief", "Ecco le proposte".
2. **STRUTTURA DIRETTA:** L'output deve seguire RIGOROSAMENTE quest'ordine:
   - Paragrafo introduttivo discorsivo.
   - I Blocchi HTML delle categorie con i format.
   - La Tabella Riepilogativa HTML.
   - Il blocco finale "Informazioni Utili".
3. **DIVIETO EMOJI NEL TESTO:** Usa emoji SOLO prima del titolo (es. "### 🍳 Cooking"). MAI nelle descrizioni.
4. **HTML:** Usa SOLO i codici HTML forniti per i titoli di sezione (i blocchi rossi).

### 🎨 REGOLE VISUALI
1.  **ICONE:** Inserisci un'emoji SOLO ed ESCLUSIVAMENTE prima del titolo del format.
2.  **HTML:** Usa ESCLUSIVAMENTE il codice HTML fornito per i titoli delle sezioni.
3.  **DIVIETO:** NON scrivere mai "BLOCCO 1", "BLOCCO 2" come testo.

### 🔢 CALCOLO PREVENTIVI (CALCOLO NASCOSTO)
⚠️ **REGOLA SUPREMA:** NON spiegare MAI la formula. Solo prezzo finale.

**1. P_BASE:** Dal database.
**2. MOLTIPLICATORI:**
* **M_PAX:** <5: x3.20 | 5-10: x1.60 | 11-20: x1.05 | 21-30: x0.95 | 31-60: x0.90 | 61-90: x0.90 | 91-150: x0.85 | 151-250: x0.70 | >250: x0.60
* **M_STAGIONE:** Alta (Mag,Giu,Lug,Set,Ott,Dic): x1.10 | Bassa: x1.02
* **M_LOCATION:** MI: x1.00 | RM: x0.95 | Venezia: x1.30 | Centro: x1.05 | Altro: x1.15 | Isole: x1.30
* **M_DURATA:** 0-2h: x1.00 | Mezza: x1.10 | Intera: x1.20

**3. FORMULA:** `PREZZO = (P_BASE * M_PAX * M_STAGIONE * M_LOCATION * M_DURATA) * PAX`
**4. MINIMUM:** Se < 1800 -> 1800.
**5. ARROTONDAMENTO:** `ARROTONDA((PREZZO + 60) / 100) * 100`

---
### 🚦 ORDINE DI PRESENTAZIONE

**1. INTRODUZIONE DISCORSIVA (Obbligatoria)**
Scrivi un paragrafo di 3-4 righe (testo semplice, NO titoli).
- Saluta il cliente con calore e professionalità.
- Cita esplicitamente i dettagli del brief (Pax, Data, Città) per dimostrare di aver compreso.
- Anticipa con entusiasmo che hai selezionato le migliori soluzioni per il loro obiettivo.
- Tono: Empatico, accogliente e sicuro.

**2. PRESENTAZIONE CATEGORIE (La Regola del 12)**
Proponi 12 FORMAT in 4 categorie.
Usa SOLO questo HTML per i titoli delle categorie:
<div class="block-header"><span class="block-title">TITOLO CATEGORIA</span><span class="block-claim">CLAIM</span></div>

Le categorie sono:
1.  **I BEST SELLER** (Claim: "I più amati dai nostri clienti")
2.  **LE NOVITÀ** (Claim: "Freschi di lancio")
3.  **VIBE & RELAX** (Claim: "Atmosfera e condivisione")
4.  **SOCIAL** (Claim: "Impatto positivo")

**Struttura Singolo Format:**
### [Emoji] [Nome Format]
[Descrizione di max 2-3 righe accattivanti. TESTO PULITO SENZA EMOJI.]

{location_guardrail_prompt}

**3. TABELLA RIEPILOGATIVA**
Usa ESCLUSIVAMENTE questo HTML per il titolo:
<div class="block-header"><span class="block-title">TABELLA RIEPILOGATIVA</span><span class="block-claim">Brief: {pax_input} pax | {data_evento_input} | {citta_input}</span></div>

**LINK SCHEDA TECNICA:**
* Copia URL esatto dal DB.
* Formato: `[NomeSenzaSpazi.pdf](URL_ESATTO)`.

| Nome Format | Costo Totale (+IVA) | Scheda Tecnica |
| :--- | :--- | :--- |
| 👨‍🍳 Cooking | € 2.400,00 | [Cooking.pdf](URL_ESATTO) |

**4. INFO UTILI**
Riporta questo blocco ESATTAMENTE così com'è:

### Informazioni Utili

✔️ **Tutti i format sono nostri** e possiamo personalizzarli senza alcun problema.

✔️ **La location non è inclusa** ma possiamo aiutarti a trovare quella perfetta per il tuo evento.

✔️ **Le attività di base** sono pensate per farvi stare insieme e divertirvi, ma il team building è anche formazione, aspetto che possiamo includere e approfondire.

✔️ **Prezzo all inclusive:** spese staff, trasferta e tutti i materiali sono inclusi, nessun costo a consuntivo.

✔️ **Assicurazione pioggia:** Se avete scelto un format oudoor ma le previsioni meteo sono avverse, due giorni prima dell'evento sceglieremo insieme un format indoor allo stesso costo.

✔️ **Chiedici anche** servizio video/foto e gadget.
"""

FULL_SYSTEM_PROMPT = f"{BASE_INSTRUCTIONS}\n\n### 💾 [DATABASE FORMATI]\n\n{csv_data_string}"

# --- 6. GESTIONE INPUT ---
prompt_to_process = None

# FIX: GESTIONE RETRY AUTOMATICO (Quando si accende il DB Location)
if st.session_state.retry_trigger:
    # Se c'è un retry pending, recuperiamo l'ultimo messaggio dell'utente
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        prompt_to_process = st.session_state.messages[-1]["content"]
    st.session_state.retry_trigger = False # Reset immediato per evitare loop

# GESTIONE PULSANTE GENERA
if generate_btn:
    # --- CONTROLLO OBBLIGATORIETÀ NOME CLIENTE ---
    if not cliente_input:
        st.sidebar.error("⚠️ ERRORE: Inserisci il Nome Cliente per procedere!")
        st.stop()
    # ---------------------------------------------
    
    prompt_to_process = f"Ciao, sono {cliente_input}. Vorrei un preventivo per {pax_input} persone, data {data_evento_input}, a {citta_input}. Durata: {durata_input}. Obiettivo: {obiettivo_input}."
    
    welcome_user = f"Ciao **{st.session_state.username}**!"
    if st.session_state.username == "Francesca":
            welcome_user = "Ciao squirtina..."
            
    st.session_state.messages = [{"role": "model", "content": f"{welcome_user} Elaboro la proposta per **{cliente_input}**."}]

chat_input = st.chat_input("Chiedi una modifica...")
if chat_input: prompt_to_process = chat_input

# --- 7. RENDERING CHAT ---
st.title("🦁 💰 FATTURAGE 💰 🦁")
for message in st.session_state.messages:
    role_to_show = "assistant" if message["role"] == "model" else message["role"]
    with st.chat_message(role_to_show): st.markdown(message["content"], unsafe_allow_html=True)

# --- 8. ELABORAZIONE AI ---
if prompt_to_process:
    # FIX: Evita di duplicare il messaggio nella chat se stiamo facendo un retry
    if not st.session_state.messages or st.session_state.messages[-1]["content"] != prompt_to_process:
        st.session_state.messages.append({"role": "user", "content": prompt_to_process})
    
    with st.chat_message("user"): st.markdown(prompt_to_process)

    # Controllo Location
    keywords_location = ["location", "dove", "villa", "castello", "spazio", "hotel", "tenuta", "cascina", "posto"]
    is_location_request = any(k in prompt_to_process.lower() for k in keywords_location)
    
    should_generate = True
    if is_location_request and not st.session_state.enable_locations_state:
        should_generate = False
        with st.chat_message("assistant"):
            st.warning("⚠️ **Il Database Location è spento.**")
            # Il click su questo pulsante attiverà 'enable_locations_callback' che setta 'retry_trigger'
            st.button("🟢 ATTIVA DATABASE LOCATION", on_click=enable_locations_callback)

    if should_generate:
        with st.chat_message("assistant"):
            with st.spinner(f"Elaborazione con {provider}..."):
                try:
                    if not api_key: st.error("Chiave API mancante."); st.stop()
                    
                    response_text = ""

                    if provider == "Google Gemini":
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel(model_name=selected_model_name, generation_config={"temperature": 0.0}, system_instruction=FULL_SYSTEM_PROMPT, safety_settings={HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE})
                        
                        history_gemini = []
                        for m in st.session_state.messages:
                            if m["role"] != "model": history_gemini.append({"role": "user", "parts": [m["content"]]})
                            else: history_gemini.append({"role": "model", "parts": [m["content"]]})
                        
                        chat = model.start_chat(history=history_gemini[:-1])
                        response = chat.send_message(prompt_to_process)
                        response_text = response.text

                    elif provider == "Groq":
                        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                        messages_groq = [{"role": "system", "content": FULL_SYSTEM_PROMPT}]
                        for m in st.session_state.messages[-6:]:
                            role = "assistant" if m["role"] == "model" else "user"
                            messages_groq.append({"role": role, "content": m["content"]})
                        
                        resp = client.chat.completions.create(model=selected_model_name, messages=messages_groq, temperature=0.0)
                        response_text = resp.choices[0].message.content

                    st.markdown(response_text, unsafe_allow_html=True) 
                    st.session_state.messages.append({"role": "model", "content": response_text})
                    
                except Exception as e:
                    st.error(f"Errore: {e}")

# --- PULSANTE SALVATAGGIO (SOLO LUI, COME RICHIESTO) ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "model":
    last_response = st.session_state.messages[-1]["content"]
    st.divider()
    # Solo pulsante di salvataggio
    if st.button("💾 SALVA SU GOOGLE SHEET", use_container_width=True):
        if salva_preventivo_su_db(cliente_input, st.session_state.username, pax_input, data_evento_input, citta_input, last_response):
            st.success(f"✅ Preventivo per {cliente_input} salvato!")
        else:
            st.error("Errore salvataggio.")
