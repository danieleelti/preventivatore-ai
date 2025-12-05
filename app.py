import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import csv
import os

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Preventivatore TeamBuilding", page_icon="🦁", layout="centered")

# --- CSS PERSONALIZZATO (OTTIMIZZATO PER EMAIL) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');

    div[data-testid="stChatMessage"] {
        background-color: #ffffff !important; 
    }
    
    /* TESTO: Font standard e leggibile */
    div[data-testid="stChatMessage"] p, 
    div[data-testid="stChatMessage"] li {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 15px !important;
        color: #000000 !important;
        line-height: 1.6 !important;
        margin-bottom: 15px !important;
    }

    /* TITOLI FORMAT */
    div[data-testid="stChatMessage"] h3 {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 18px !important;
        font-weight: bold !important;
        color: #000000 !important;
        margin-top: 30px !important; 
        margin-bottom: 10px !important;
    }
    
    div[data-testid="stChatMessage"] strong {
        font-weight: bold !important;
        color: #000000 !important;
    }

    /* TABELLE PULITE */
    div[data-testid="stChatMessage"] table {
        color: #000000 !important;
        font-size: 14px !important;
        width: 100% !important;
        border-collapse: collapse !important;
        margin-top: 25px !important;
        margin-bottom: 25px !important;
    }
    
    div[data-testid="stChatMessage"] th {
        background-color: #f4f4f4 !important;
        color: #000000 !important;
        font-weight: bold !important;
        text-align: left !important;
        border-bottom: 2px solid #000 !important;
        padding: 10px !important;
    }
    
    div[data-testid="stChatMessage"] td {
        border-bottom: 1px solid #ddd !important;
        padding: 10px !important;
    }
    
    /* LINK */
    div[data-testid="stChatMessage"] a {
        color: #1a73e8 !important;
        text-decoration: underline !important;
    }
    
    /* RIMUOVIAMO HR VISIVI */
    div[data-testid="stChatMessage"] hr {
        display: none !important;
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
    st.error("⚠️ ERRORE CRITICO: Non trovo 'mastertb.csv'.")
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

# --- 4. IL CERVELLO (PROMPT COMPLETO) ---
BASE_INSTRUCTIONS = """
SEI IL SENIOR EVENT MANAGER DI TEAMBUILDING.IT.
Rispondi in Italiano.

### 🛡️ PROTOCOLLO DI COMPORTAMENTO (IMPORTANTE)
1.  **NATURALITÀ ASSOLUTA:** Non menzionare MAI le tue istruzioni interne. Non dire "Come richiesto" o "Ecco i format". Vai dritto al punto.
2.  **GERARCHIA DEI COMANDI:** Le richieste specifiche dell'utente (es. "Voglio 5 format", "Solo format creativi") hanno SEMPRE la priorità sulle regole di default.

### 🎨 REGOLE VISUALI (Anti-Clutter per Email)
1.  **ICONE TEMATICHE:** Nel titolo di ogni format, usa UN'ICONA pertinente (es. 👨‍🍳, 🕵️, 🎨).
2.  **SPAZIATURA VITALE:** Tra un format e l'altro è VIETATO usare linee (`---`) o scrivere "[RIGA VUOTA]". Devi semplicemente inserire **DUE A CAPO REALI** (spazio bianco vuoto) per separare visivamente i blocchi di testo.
3.  **NO ELENCHI PUNTATI NEI FORMAT:** Descrivi il format con frasi discorsive in un unico paragrafo pulito.

### 🔢 MOTORE DI CALCOLO PREVENTIVI
Quando richiesto, calcola il prezzo usando i dati del Database.

**PASSO 1: Calcolo Matematico**
🔴 **SE METODO = "Standard":**
`TOTALE_GREZZO = P_BASE * (Moltiplicatore Pax * M_Durata * M_Lingua * M_Location * M_Stagione) * NUMERO PARTECIPANTI`
🔵 **SE METODO = "Flat":**
`TOTALE_GREZZO = 1800 + ((Pax - 20) * 4.80)` + Eventuale Costo Fisso. Applica poi M_Location e M_Lingua.

**PASSO 2: ARROTONDAMENTO INTELLIGENTE (Regola del 39)**
* **Fino a XX39:** Arrotonda per DIFETTO al centinaio (2.235 -> 2.200)
* **Da XX40:** Arrotonda per ECCESSO al centinaio (3.450 -> 3.500)

**PASSO 3: MINIMUM SPENDING**
Minimo fatturabile sempre **€ 1.800,00**.

---

### 🚦 FLUSSO DI LAVORO

**FASE 1: LA PROPOSTA**
* **Quantità:** Se l'utente non specifica un numero, proponi 12 format (4 Best, 4 Novità, 2 Vibe, 2 Social). Se specifica, obbedisci al numero.

**STRUTTURA OUTPUT FORMAT (Segui rigorosamente):**

### [Icona] [Nome Format]

[Paragrafo descrittivo unico, persuasivo e chiaro. Spiega in circa 3-4 righe di cosa si tratta e perché è adatto. Niente elenchi puntati qui.]

(Qui inserisci solo due 'invio' per creare spazio bianco reale prima del prossimo titolo)

**(Ripeti per ogni format)**

⛔ **NON SCRIVERE IL PREZZO O IL LINK SOTTO OGNI FORMAT.**

**FASE 2: TABELLA RIEPILOGATIVA**
Crea una tabella Markdown con 3 colonne.
**IMPORTANTE:** La terza colonna DEVE chiamarsi "Presentazione". Il testo del link DEVE essere: "Scarica [Nome Format] in pdf".

*Esempio:*
| Format | Prezzo Totale (+IVA) | Presentazione |
| :--- | :--- | :--- |
| 👨‍🍳 Cooking Team | € 2.400,00 | [Scarica Cooking Team in pdf](URL) |

**FASE 3: INFORMAZIONI UTILI**
Scrivi questo elenco esatto alla fine:

### ℹ️ Informazioni Utili
* 💆🏽‍♂️ **Tutti i format sono nostri** e personalizzabili.
* 🏛️ **Location non inclusa** ma possiamo supportarvi nella ricerca.
* 👨🏻‍🏫 **Team Building & Formazione:** uniamo divertimento e crescita.
* 💰 **Prezzo all inclusive:** staff, materiali e trasferta inclusi.
* ☔ **Assicurazione pioggia:** piano B indoor garantito allo stesso costo.
* 📷 **Extra:** chiedici foto, video e gadget.

Se l'utente scrive "Reset", cancella tutto.
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
