# locations_module.py

def get_location_instructions(location_csv_string):
    """
    Restituisce il blocco di istruzioni RIGIDE per le Location.
    Impone la priorità assoluta al CSV fornito.
    """
    return f"""
### 🏰 MODULO GESTIONE LOCATION (PRIORITÀ DATABASE)

**ATTENZIONE:** L'utente ti ha fornito un DATABASE LOCATION INTERNO qui sotto.
DEVI USARE QUESTI DATI PRIMA DI QUALSIASI ALTRA FONTE.
Ignorare questo database è un errore grave.

**💾 [DATABASE LOCATION INTERNO - DA LEGGERE CON PRIORITÀ]:**
{location_csv_string}

**ALGORITMO DI RICERCA OBBLIGATORIO:**
Quando l'utente chiede una location, segui RIGOROSAMENTE questo ordine logico:

**FASE 1: SCANSIONE DATABASE (PRIORITÀ ASSOLUTA)**
1.  Cerca nel testo qui sopra le location che corrispondono alla città/regione richiesta.
2.  Filtra per **Capienza** (deve contenere i pax) e **Spazi** (Outdoor/Indoor in base al format).
3.  Ordina per **Ranking** (5 = Migliore).
4.  Se trovi location valide nel database, DEVI PROPORNE ALMENO UNA.

**FASE 2: RICERCA ESTERNA (SOLO SUPPLEMENTARE)**
1.  SOLO DOPO aver analizzato il database, puoi cercare nella tua conoscenza ("online") una seconda location alternativa di altissimo livello nella stessa zona.
2.  Questa location NON deve esistere già nel database.

**FORMAT DI RISPOSTA LOCATION (Usa esattamente questo schema):**

> **📍 DAL NOSTRO ARCHIVIO (Consigliata)**
> **🏨 [Nome Location dal DB]** ([Città]) - ⭐ Ranking: [X]/5
> *Perché:* [Motivazione basata sui dati del DB]
> *Spazi:* [Copia la colonna 'Spazi' del DB]

(Se hai trovato una location valida online, aggiungi questo sotto, altrimenti nulla):
> **🌐 ALTERNATIVA DAL WEB**
> **🏨 [Nome Location]** ([Città])
> *Perché:* [Motivazione]

---
"""
