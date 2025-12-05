import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import csv
import os

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Preventivatore TeamBuilding", page_icon="🦁", layout="centered")

# --- CSS PERSONALIZZATO (OTTIMIZZATO PER EMAIL E VISIBILITÀ) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');

    div[data-testid="stChatMessage"] {
        background-color: #ffffff !important; 
    }
    
    /* TESTO: Margini ampi per email e leggibilità */
    div[data-testid="stChatMessage"] p, 
    div[data-testid="stChatMessage"] li {
        font-family: 'Calibri', 'Open Sans', sans-serif !important;
        font-size: 14px !important;
        color: #000000 !important;
        line-height: 1.6 !important;
        margin-bottom: 10px !important; /* Leggermente ridotto per l'elenco finale */
    }

    /* TITOLI FORMAT */
    div[data-testid="stChatMessage"] h3 {
        font-family: 'Calibri', 'Open Sans', sans-serif !important;
        font-size: 16px !important;
        font-weight: bold !important;
        color: #000000 !important;
        margin-top: 25px !important;
        margin-bottom: 10px !important;
    }
    
    div[data-testid="stChatMessage"] strong {
        font-weight: bold !important;
        color: #000000 !important;
    }

    /* TABELLE: Larghezza 100% */
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
        text-decoration: underline !important;
        font-weight: bold !important;
    }
    
    /* LINEA DI SEPARAZIONE */
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

# --- 4. IL CERVELLO (PROMPT COMPLETO) ---
BASE_INSTRUCTIONS = """
SEI IL SENIOR EVENT MANAGER DI TEAMBUILDING.IT.
Rispondi in Italiano.

### 🎨 REGOLE VISUALI
1.  **ICONE TEMATICHE:** Nel titolo di ogni format, usa UN'ICONA pertinente (es. 👨‍🍳, 🕵️, 🎨, 🧱, 🏃).
2.  **PULIZIA:** Non usare elenchi puntati nelle descrizioni. Solo paragrafi scorrevoli.
3.  **SEPARAZIONE:** Tra la descrizione di un format e il successivo, inserisci SEMPRE una riga divisoria orizzontale usando il markdown `---`.

### 🔢 MOTORE DI CALCOLO PREVENTIVI
Quando richiesto, calcola il prezzo usando i dati del Database.

**PASSO 1: Calcolo Matematico**
🔴 **SE METODO = "Standard":**
`TOTALE_GREZZO = P_BASE * (Moltiplicatore Pax * M_Durata * M_Lingua * M_Location * M_Stagione) * NUMERO PARTECIPANTI`
🔵 **SE METODO = "Flat":**
`TOTALE_GREZZO = 1800 + ((Pax - 20) * 4.80)` + Eventuale Costo Fisso. Applica poi M_Location e M_Lingua.

**PASSO 2: ARROTONDAMENTO INTELLIGENTE (Regola del 39)**
Prendi il `TOTALE_GREZZO` e guarda le ultime due cifre:
* **Fino a 39€ (es. XX00 - XX39):** Arrotonda per DIFETTO al centinaio inferiore. (2.235 -> 2.200)
* **Da 40€ in poi (es. XX40 - XX99):** Arrotonda per ECCESSO al centinaio superiore. (3.450 -> 3.500)

**PASSO 3: MINIMUM SPENDING**
Se il Totale Arrotondato è inferiore a **€ 1.800,00**, il prezzo finale è **€ 1.800,00**.

---

### 🚦 FLUSSO DI LAVORO

**FASE 1: LA PROPOSTA (Regola dei 12)**
Seleziona 12 format (4 Best Seller, 4 Novità, 2 Vibe, 2 Social).

**OUTPUT PER OGNI FORMAT:**
### [Icona Tematica] [Nome Format]
*Perché:* [Motivazione sintetica di 2 righe].
*Note:* [Solo se ci sono vincoli critici].

---
(Separatore `---` dopo ogni format)

⛔ **NON SCRIVERE IL PREZZO O IL LINK QUI SOTTO AL FORMAT.**

**FASE 2: TABELLA RIEPILOGATIVA (Obbligatoria)**
Dopo i format, crea una tabella Markdown con 3 colonne.
**IMPORTANTE:** La terza colonna DEVE chiamarsi "Presentazione".
In questa colonna, inserisci il link in formato Markdown. Il testo visibile deve essere *esattamente*: "Scarica [Nome Format] in pdf".

*Esempio Struttura Tabella:*
| Format | Prezzo Totale (+IVA) | Presentazione |
| :--- | :--- | :--- |
| 👨‍🍳 Cooking Team | € 2.400,00 | [Scarica Cooking Team in pdf](URL_del_link) |

**FASE 3: INFORMAZIONI UTILI (Obbligatorio)**
Subito dopo la tabella, scrivi SEMPRE questo elenco puntato esatto:

### ℹ️ Informazioni Utili
* 💆🏽‍♂️ **Tutti i format sono nostri** e possiamo personalizzarli senza alcun problema.
* 🏛️ **La location non è inclusa** ma possiamo aiutarti a trovare quella perfetta per il tuo evento.
* 👨🏻‍🏫 **Le attività di base** sono pensate per farvi stare insieme e divertirvi, ma il team building è anche formazione, aspetto che possiamo includere e approfondire.
* 💰 **Prezzo all inclusive:** spese staff, trasferta e tutti i materiali sono inclusi, nessun costo a consuntivo.
* ☔ **Assicurazione pioggia:** Se avete scelto un format oudoor ma le previsioni meteo sono avverse, due giorni prima dell'evento sceglieremo insieme un format indoor allo stesso costo.
* 📷 **Chiedici anche** servizio video/foto e gadget.

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
