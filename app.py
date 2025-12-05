import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import csv
import os

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Preventivatore TeamBuilding", page_icon="🦁", layout="centered")

# --- CSS PERSONALIZZATO (OTTIMIZZATO PER COPIA-INCOLLA EMAIL) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');

    div[data-testid="stChatMessage"] {
        background-color: #ffffff !important; 
    }
    
    /* TESTO: Margini ampi per evitare l'effetto "muro di testo" nelle mail */
    div[data-testid="stChatMessage"] p, 
    div[data-testid="stChatMessage"] li {
        font-family: 'Calibri', 'Open Sans', sans-serif !important;
        font-size: 14px !important;
        color: #000000 !important;
        line-height: 1.6 !important;
        margin-bottom: 20px !important; /* FORZA SPAZIO SOTTO OGNI PARAGRAFO */
    }

    /* TITOLI FORMAT */
    div[data-testid="stChatMessage"] h3 {
        font-family: 'Calibri', 'Open Sans', sans-serif !important;
        font-size: 16px !important;
        font-weight: bold !important;
        color: #000000 !important;
        margin-top: 25px !important; /* Più aria sopra */
        margin-bottom: 10px !important;
    }
    
    div[data-testid="stChatMessage"] strong {
        font-weight: bold !important;
        color: #000000 !important;
    }

    /* TABELLE: Larghezza 100% e spaziature comode */
    div[data-testid="stChatMessage"] table {
        color: #000000 !important;
        font-size: 14px !important;
        width: 100% !important;
        display: table !important;
        border-collapse: collapse !important;
        margin-top: 20px !important;
        margin-bottom: 20px !important;
    }
    
    div[data-testid="stChatMessage"] th {
        background-color: #f0f0f0 !important;
        color: #000000 !important;
        font-weight: bold !important;
        padding: 12px !important;
        text-align: left !important;
        border-bottom: 2px solid #000 !important;
    }
    
    div[data-testid="stChatMessage"] td {
        padding: 10px 12px !important;
        border-bottom: 1px solid #ccc !important;
        vertical-align: middle !important;
    }
    
    /* LINK */
    div[data-testid="stChatMessage"] a {
        color: #0066cc !important;
        text-decoration: underline !important; /* Sottolineato aiuta nelle mail */
        font-weight: bold !important;
    }
    
    /* LINEA DI SEPARAZIONE (HR) */
    div[data-testid="stChatMessage"] hr {
        margin-top: 20px !important;
        margin-bottom: 20px !important;
        border: 0;
        border-top: 1px solid #ddd !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. GESTIONE DATABASE ---
@st.cache_data(show_spinner=False)
def carica_database(nome_file):
    percorso = os.path.join(os.getcwd(), nome_file)
    if not os.path.exists(percorso):
        return None 

    lista_dati = []
    encodings = ['utf-8', 'latin-1', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(percorso, mode='r', encoding=encoding) as file:
                reader = csv.DictReader(file, delimiter=',')
                for riga in reader:
                    lista_dati.append(riga)
            return lista_dati
        except UnicodeDecodeError:
            continue
        except Exception:
            return None 
    return None

def database_to_string(database_list):
    if not database_list:
        return "Nessun dato disponibile."
    header = " | ".join(database_list[0].keys())
    rows = []
    for riga in database_list:
        rows.append(" | ".join(str(v) for v in riga.values()))
    return header + "\n" + "\n".join(rows)

# Caricamento
master_database = carica_database('mastertb.csv') 
faq_database = carica_database('faq.csv')
location_database = carica_database('location.csv')

if master_database is None:
    st.error("⚠️ ERRORE CRITICO: Non trovo 'mastertb.csv'. Verifica che il file su GitHub sia scritto TUTTO MINUSCOLO.")
    st.stop()

csv_data_string = database_to_string(master_database)
if faq_database is None: faq_database = [] 
if location_database is None: location_database = []

# --- 3. CONFIGURAZIONE API E PASSWORD ---
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

# --- 4. IL CERVELLO (PROMPT OTTIMIZZATO MAIL) ---
BASE_INSTRUCTIONS = """
SEI IL SENIOR EVENT MANAGER DI TEAMBUILDING.IT.
Rispondi in Italiano.

### 🎨 REGOLE VISUALI (FONDAMENTALI PER EMAIL)
1.  **ICONE TEMATICHE:** Nel titolo di ogni format, usa UN'ICONA pertinente (es. 👨‍🍳, 🕵️, 🎨, 🧱, 🏃).
2.  **PULIZIA:** Non usare elenchi puntati. Solo paragrafi scorrevoli.
3.  **SEPARAZIONE:** Tra la descrizione di un format e il successivo, inserisci SEMPRE una riga divisoria orizzontale usando il markdown `---`. Questo è fondamentale per l'impaginazione via email.

### 🔢 MOTORE DI CALCOLO PREVENTIVI
Quando richiesto, calcola il prezzo usando i dati del Database.

**PASSO 1: Trova i dati**
Cerca il format e prendi `P_BASE` e `METODO`.

**PASSO 2: Calcola il Totale**
🔴 **SE METODO = "Standard":**
`TOTALE = P_BASE * (Moltiplicatore Pax * M_Durata * M_Lingua * M_Location * M_Stagione) * NUMERO PARTECIPANTI`

* **M_PAX:** <5 (3.20) | 5-10 (1.60) | 11-20 (1.05) | 21-30 (0.95) | 31-60 (0.90) | 61-90 (0.90) | 91-150 (0.85) | 151-250 (0.70) | 251-350 (0.63) | 351-500 (0.55) | 501-700 (0.50) | >900 (0.30)
* **M_DURATA:** ≤1h (1.05) | 1-2h (1.07) | 2-4h (1.10) | >4h (1.15)
* **M_LINGUA:** Ita (1.05) | Eng (1.10)
* **M_LOCATION:** Mi (1.00) | Rm (0.95) | Centro (1.05) | Nord/Sud (1.15) | Isole (1.30)
* **M_STAGIONE:** Mag-Ott (1.10) | Nov-Apr (1.02)

🔵 **SE METODO = "Flat":**
`1800 + ((Pax - 20) * 4.80)` + Eventuale Costo Fisso. Applica poi M_Location e M_Lingua.

**MINIMUM SPENDING:** Se Totale < 1.800€ -> Arrotonda a 1.800€.

---

### 🚦 FLUSSO DI LAVORO

**FASE 1: LA PROPOSTA (Regola dei 12)**
Seleziona 12 format (4 Best Seller, 4 Novità, 2 Vibe, 2 Social).

**OUTPUT PER OGNI FORMAT:**
Devi scrivere SOLO:
### [Icona Tematica] [Nome Format]
*Perché:* [Motivazione sintetica di 2 righe].
*Note:* [Solo se ci sono vincoli critici].

---
(Inserisci qui il separatore `---` dopo ogni format)

⛔ **NON SCRIVERE IL PREZZO O IL LINK QUI SOTTO AL FORMAT.**

**FASE 2: TABELLA RIEPILOGATIVA (Obbligatoria alla fine)**
Dopo i format, crea una tabella Markdown con 3 colonne.
**IMPORTANTE:** Nella terza colonna il testo del link DEVE essere "Scarica [Nome Format] in pdf".

*Esempio Struttura Tabella:*
| Format | Prezzo Totale (+IVA) | Scheda Tecnica |
| :--- | :--- | :--- |
| 👨‍🍳 Cooking Team | € 2.400,00 | [Scarica Cooking Team in pdf](link) |
| 🕵️ CSI Crime | € 1.800,00 | [Scarica CSI Crime in pdf](link) |

Se l'utente scrive "Reset", cancella la memoria.
"""

FULL_SYSTEM_PROMPT = f"{BASE_INSTRUCTIONS}\n\n### 💾 [DATABASE DATI]\n\n{csv_data_string}"

# --- 5. CONFIGURAZIONE AI ---
genai.configure(api_key=api_key)

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

# --- 6. INTERFACCIA CHAT ---
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
