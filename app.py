import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from openai import OpenAI
import csv
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import save  # Modulo di salvataggio

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="FATTURAGE", page_icon="🦁💰", layout="wide") # Layout WIDE per dare spazio alla tabella

# --- CSS PERSONALIZZATO ---
st.markdown("""
<style>
    /* Stile generale messaggi */
    div[data-testid="stChatMessage"] { background-color: #ffffff !important; border: 1px solid #f0f2f6; border-radius: 10px; padding: 15px; }
    div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li, div[data-testid="stChatMessage"] div {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 15px !important; /* Leggermente più grande */
        color: #000000 !important;
        line-height: 1.6 !important;
    }
    
    /* Intestazioni Blocchi */
    .block-header {
        background-color: #f8f9fa;
        border-left: 5px solid #ff4b4b;
        padding: 15px;
        margin-top: 25px !important;
        margin-bottom: 15px !important;
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

# --- FUNZIONE CALLBACK PER ABILITARE LOCATION ---
def enable_locations_callback():
    st.session_state.enable_locations_state = True

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
        
        # --- FIX LINK AUTOMATICO ---
        sanitized_list = []
        for riga in database_list:
            clean_riga = {}
            for k, v in riga.items():
                val_str = str(v) if v is not None else ""
                # Se è un link e contiene spazi, lo ripariamo QUI in Python
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

# --- CARICAMENTO DATI BASE (SOLO FORMAT) ---
master_database = carica_google_sheet('MasterTbGoogleAi') 
if master_database is None:
    st.error("⚠️ ERRORE CRITICO: Impossibile scaricare il database attività da Google Sheets.")
    st.stop()
csv_data_string = database_to_string(master_database)

# --- 4. CONFIGURAZIONE API E PASSWORD ---
PASSWORD_SEGRETA = "TeamBuilding2025#"
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.title("🔒 Area Riservata")
        pwd = st.text_input("Inserisci Password Staff", type="password")
        if st.button("Accedi"):
            if pwd == PASSWORD_SEGRETA:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Password errata")
    st.stop()

# --- 4.b INIZIALIZZAZIONE SESSION STATE ---
if "enable_locations_state" not in st.session_state:
    st.session_state.enable_locations_state = False 
if "total_tokens_used" not in st.session_state:
    st.session_state.total_tokens_used = 0
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Messaggio di benvenuto silenzioso (o visibile solo al primo avvio)
    st.session_state.messages.append({"role": "model", "content": "Ciao! Usa la barra laterale a sinistra per compilare i dati e generare il preventivo."})

# --- SIDEBAR: DATI PREVENTIVO E CONFIGURAZIONE ---
with st.sidebar:
    st.title("🦁 FATTURAGE 2.0")
    st.markdown("---")
    
    # 1. DATI CLIENTE (OBBLIGATORI/PRINCIPALI)
    st.subheader("📝 Dati Brief")
    cliente_input = st.text_input("Nome Cliente *", placeholder="es. Azienda Rossi SpA")
    
    col_pax, col_data = st.columns(2)
    with col_pax:
        pax_input = st.text_input("N. Pax", placeholder="50")
    with col_data:
        data_evento_input = st.text_input("Data", placeholder="12 Maggio")
    
    citta_input = st.text_input("Città / Location", placeholder="Milano / Villa Reale")
    durata_input = st.text_input("Durata Attività", placeholder="es. 2-3 ore, mezza giornata")
    
    obiettivo_input = st.text_area(
        "Obiettivo / Mood / Note", 
        placeholder="Descrivi cosa cercano: divertimento, formazione, integrazione, relax, qualcosa di tecnologico...",
        height=100
    )

    # 2. BOTTONE GENERA
    st.markdown("###")
    generate_btn = st.button("🚀 GENERA PREVENTIVO", type="primary")

    st.markdown("---")

    # 3. OPZIONI AVANZATE (LOCATION + AI)
    with st.expander("⚙️ Impostazioni Avanzate", expanded=False):
        use_location_db = st.checkbox("🏰 Abilita Database Location", key="enable_locations_state")
        
        st.markdown("---")
        provider = st.selectbox("Provider AI", ["Google Gemini", "Groq"])
        
        if provider == "Google Gemini":
            model_options = ["gemini-3-pro-preview", "gemini-2.0-flash-exp", "gemini-1.5-pro-latest"]
            if "gemini-3-pro-preview" not in model_options: model_options.insert(0, "gemini-3-pro-preview")
        elif provider == "Groq":
            model_options = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "mixtral-8x7b-32768"]
        
        selected_model_name = st.selectbox("Modello", model_options)
        
        api_key = None
        if provider == "Google Gemini": api_key = st.secrets.get("GOOGLE_API_KEY")
        elif provider == "Groq": api_key = st.secrets.get("GROQ_API_KEY")

        if not api_key: st.error(f"⚠️ Manca API Key per {provider}")

# --- LOGICA CARICAMENTO LOCATION ---
location_instructions_block = ""
if use_location_db:
    with st.spinner("Caricamento Location..."):
        location_database = carica_google_sheet('LocationGoogleAi')
        if location_database and locations_module:
            loc_db_string = database_to_string(location_database)
            location_instructions_block = locations_module.get_location_instructions(loc_db_string)
        elif not location_database:
            st.sidebar.warning("⚠️ Errore caricamento Location")

# --- 5. COSTRUZIONE SYSTEM PROMPT ---
context_brief = f"DATI BRIEF: Cliente: {cliente_input}, Pax: {pax_input}, Data: {data_evento_input}, Città: {citta_input}, Durata: {durata_input}, Obiettivo: {obiettivo_input}."

BASE_INSTRUCTIONS = f"""
SEI IL SENIOR EVENT MANAGER DI TEAMBUILDING.IT. Rispondi in Italiano.
{context_brief}

### 🛡️ PROTOCOLLO
1.  **USO DEL DATABASE:** Sei obbligato a usare i dati caricati da Google Sheets.
2.  **QUALIFICAZIONE:** Se mancano info essenziali (che non sono nel brief), chiedile.

### 🎨 REGOLE VISUALI
1.  **ICONE:** Una emoji SOLO nel titolo del format.
2.  **HTML:** Usa i div HTML forniti per i titoli delle sezioni.

### 🔢 CALCOLO PREVENTIVI (RIGOROSO)
* Usa le colonne del DB per P_BASE.
* Applica i moltiplicatori (M_PAX, M_DURATA, M_LINGUA, M_LOCATION, M_STAGIONE).
* Formula Standard: `P_BASE * M_PAX * ... * PAX`
* Arrotonda e applica Min Spending 1800+IVA.

---
### 🚦 FLUSSO DI LAVORO (ORDINE OBBLIGATORIO)

**FASE 0: CHECK INFORMAZIONI**

**FASE 1: LA REGOLA DEL 12 (Presentazione Format)**
Proponi ESATTAMENTE 12 FORMAT divisi in 4 blocchi, seguendo questa struttura numerica RIGIDA:

⚠️ **TITOLI BLOCCHI HTML:**
<div class="block-header"><span class="block-title">NOME BLOCCO</span><span class="block-claim">Claim</span></div>

**BLOCCO 1: I BEST SELLER** (Devi proporre 4 format)
* **CRITERIO:** Valore più alto in **"Ranking"** o **"Voto"**.

**BLOCCO 2: LE NOVITÀ** (Devi proporre 4 format)
* **CRITERIO:** "Sì"/"True" in **"Novità"** o **"Anno"** recente.

**BLOCCO 3: VIBE & RELAX** (Devi proporre 2 format)
* **CRITERIO:** Tag "Relax", "Soft", "Atmosphere", "Cena" in **"Categoria"**/**"Tag"**.

**BLOCCO 4: SOCIAL** (Devi proporre 2 format)
* **CRITERIO:** Tag "Social", "Charity", "Creativo" in **"Categoria"**/**"Tag"**.

**Struttura Format:**
### [Emoji] [Nome]
[Descrizione basata sul DB]

**FASE 2: SUGGERIMENTO LOCATION**
{location_instructions_block}

**FASE 3: TABELLA RIEPILOGATIVA (⛔️ TASSATIVA ⛔️)**
DEVI OBBLIGATORIAMENTE GENERARE QUESTA TABELLA ALLA FINE DELLA RISPOSTA.
NON TERMINARE MAI LA RISPOSTA SENZA QUESTA TABELLA.

Prima della tabella, inserisci il titolo usando ESATTAMENTE questo codice HTML:
<div class="block-header">
<span class="block-title">TABELLA RIEPILOGATIVA</span>
<span class="block-claim">Brief: {pax_input} pax | {data_evento_input} | {citta_input} | {durata_input}</span>
</div>

**⚠️ REGOLA LINK SCHEDA TECNICA (CRITICO - DO OR DIE):**
1. Cerca nel DB la colonna "Scheda Tecnica", "Link", "URL" o "Pdf".
2. **COPIA L'URL ESATTAMENTE COM'È.** (I link sono già stati puliti, NON modificarli).
3. **TESTO DEL LINK:** Deve essere il nome del format senza spazi, seguito da .pdf.
   - Esempio: `MysteryBox.pdf`.
4. FORMATO OBBLIGATORIO: `[NomeSenzaSpazi.pdf](URL_DAL_DATABASE)`.

| Nome Format | Costo Totale (+IVA) | Scheda Tecnica |
| :--- | :--- | :--- |
| 👨‍🍳 Cooking | € 2.400,00 | [Cooking.pdf](URL_ESATTO) |
| ... | ... | ... |

*(Inserisci qui tutti i 12 format proposti con i relativi prezzi calcolati)*.

**FASE 4: INFO UTILI (OBBLIGATORIO - COPIA ESATTA)**
Devi riportare ESATTAMENTE questo blocco, inclusi gli emoji:

### Informazioni Utili

✔️ **Tutti i format sono nostri** e possiamo personalizzarli senza alcun problema.

✔️ **La location non è inclusa** ma possiamo aiutarti a trovare quella perfetta per il tuo evento.

✔️ **Le attività di base** sono pensate per farvi stare insieme e divertirvi, ma il team building è anche formazione, aspetto che possiamo includere e approfondire.

✔️ **Prezzo all inclusive:** spese staff, trasferta e tutti i materiali sono inclusi, nessun costo a consuntivo.

✔️ **Assicurazione pioggia:** Se avete scelto un format oudoor ma le previsioni meteo sono avverse, due giorni prima dell'evento sceglieremo insieme un format indoor allo stesso costo.

✔️ **Chiedici anche** servizio video/foto e gadget.
"""

# Gestione Silenziosa del Guardrail Location
if not location_instructions_block:
    location_guardrail_silent = "ISTRUZIONE PER FASE 2: NON SCRIVERE NULLA. SALTA QUESTA FASE. VAI DIRETTAMENTE ALLA FASE 3."
    FULL_SYSTEM_PROMPT = f"{BASE_INSTRUCTIONS.replace('{location_instructions_block}', location_guardrail_silent)}\n\n### 💾 [DATABASE FORMATI DA GOOGLE SHEETS]\n\n{csv_data_string}"
else:
    FULL_SYSTEM_PROMPT = f"{BASE_INSTRUCTIONS.replace('{location_instructions_block}', location_instructions_block)}\n\n### 💾 [DATABASE FORMATI DA GOOGLE SHEETS]\n\n{csv_data_string}"


# --- 6. LOGICA DI GESTIONE INPUT (SIDEBAR VS CHAT) ---
prompt_to_process = None

# A) Se clicco GENERA dalla Sidebar
if generate_btn:
    if not cliente_input:
        st.sidebar.error("Inserisci il Nome Cliente!")
    else:
        # Costruiamo il prompt iniziale simulato
        prompt_to_process = f"Ciao, sono {cliente_input}. Vorrei un preventivo per {pax_input} persone, data {data_evento_input}, a {citta_input}. Durata: {durata_input}. Obiettivo: {obiettivo_input}."
        # Reset della storia per la nuova richiesta pulita
        st.session_state.messages = [{"role": "model", "content": f"Ciao! Elaboro subito la proposta per **{cliente_input}**."}]

# B) Se scrivo nella chat in basso (Refinement)
chat_input = st.chat_input("Chiedi una modifica (es. 'Cambia il cooking con un quiz')")
if chat_input:
    prompt_to_process = chat_input

# --- 7. RENDERING CHAT ---
st.title("🦁 💰 FATTURAGE 💰 🦁")

for message in st.session_state.messages:
    role_to_show = "assistant" if message["role"] == "model" else message["role"]
    with st.chat_message(role_to_show):
        st.markdown(message["content"], unsafe_allow_html=True)

# --- 8. ELABORAZIONE AI ---
if prompt_to_process:
    # Aggiungi messaggio utente alla storia
    st.session_state.messages.append({"role": "user", "content": prompt_to_process})
    with st.chat_message("user"):
        st.markdown(prompt_to_process)

    # Logica Location Check (Solo per input testuale, non per il primo prompt generato che è controllato dai campi)
    keywords_location = ["location", "dove", "villa", "castello", "spazio", "hotel", "tenuta", "cascina", "posto"]
    is_location_request = any(k in prompt_to_process.lower() for k in keywords_location)
    
    # Se chiede location e DB spento -> Stop e Bottone
    if is_location_request and not st.session_state.enable_locations_state:
        with st.chat_message("assistant"):
            st.warning("⚠️ **Il Database Location è spento per massimizzare la velocità.**")
            st.info("Attiva il database location dalla sidebar se ti servono suggerimenti sugli spazi.")
            if st.button("🟢 ATTIVA ORA", on_click=enable_locations_callback):
                st.rerun()
            st.stop() # Ferma qui, non chiamare l'AI

    # Chiamata AI
    with st.chat_message("assistant"):
        with st.spinner(f"Elaborazione con {provider}..."):
            try:
                if not api_key:
                     st.error("Chiave API mancante.")
                     st.stop()
                
                response_text = ""
                token_usage_info = ""

                # --- GOOGLE GEMINI ---
                if provider == "Google Gemini":
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(
                        model_name=selected_model_name, 
                        generation_config={"temperature": 0.0},
                        system_instruction=FULL_SYSTEM_PROMPT,
                        safety_settings={HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE},
                    )
                    
                    history_gemini = []
                    for m in st.session_state.messages:
                        if m["role"] != "model":
                            history_gemini.append({"role": "user", "parts": [m["content"]]})
                        else:
                            history_gemini.append({"role": "model", "parts": [m["content"]]})
                    
                    chat = model.start_chat(history=history_gemini[:-1])
                    response = chat.send_message(prompt_to_process)
                    response_text = response.text
                    
                    if response.usage_metadata:
                        in_tok = response.usage_metadata.prompt_token_count
                        out_tok = response.usage_metadata.candidates_token_count
                        tot_tok = response.usage_metadata.total_token_count
                        token_usage_info = f"📊 **Token:** {tot_tok} (In: {in_tok} / Out: {out_tok})"

                # --- GROQ ---
                elif provider == "Groq":
                    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                    messages_groq = [{"role": "system", "content": FULL_SYSTEM_PROMPT}]
                    # Ottimizzazione contesto per Groq (ultimi 6 messaggi)
                    recent_messages = st.session_state.messages[-6:] 
                    for m in recent_messages:
                        role = "assistant" if m["role"] == "model" else "user"
                        messages_groq.append({"role": role, "content": m["content"]})
                    
                    resp = client.chat.completions.create(
                        model=selected_model_name,
                        messages=messages_groq,
                        temperature=0.0
                    )
                    response_text = resp.choices[0].message.content
                    
                    if resp.usage:
                        tot_tok = resp.usage.total_tokens
                        token_usage_info = f"📊 **Token:** {tot_tok}"

                st.markdown(response_text, unsafe_allow_html=True) 
                if token_usage_info: st.caption(token_usage_info)

                st.session_state.messages.append({"role": "model", "content": response_text})
                
            except Exception as e:
                err_msg = str(e)
                if "rate_limit_exceeded" in err_msg.lower() or "413" in err_msg:
                    st.error(f"❌ **ERRORE LIMITE GROQ**: Il database è troppo grande per il piano gratuito. **Usa Google Gemini.**")
                else:
                    st.error(f"Errore tecnico con {provider}: {e}")

# --- PULSANTE DI SALVATAGGIO (SEMPRE VISIBILE SE C'È UNA RISPOSTA) ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "model":
    last_response = st.session_state.messages[-1]["content"]
    
    st.divider()
    c1, c2 = st.columns([1, 2])
    
    with c1:
        if st.button("💾 SALVA SU GOOGLE SHEET", use_container_width=True):
            if save.salva_preventivo(cliente_input, pax_input, data_evento_input, citta_input, last_response):
                st.success(f"✅ Preventivo per {cliente_input} salvato!")
            else:
                st.error("Errore salvataggio.")
    
    with c2:
        with st.expander("📋 CLICCA QUI PER COPIARE IL TESTO"):
            st.info("Clicca l'icona 📄 nell'angolo in alto a destra del blocco qui sotto.")
            st.code(last_response, language="markdown")
