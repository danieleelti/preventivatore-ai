# locations_module.py

def get_location_instructions(location_csv_string):
    """
    Restituisce il blocco di istruzioni per le Location.
    Versione PULITA: Zero Emoji, Zero Ranking visualizzato.
    """
    return f"""
### 🏰 MODULO GESTIONE LOCATION (PRIORITÀ DATABASE)

**ATTENZIONE:** L'utente ti ha fornito un DATABASE LOCATION INTERNO qui sotto.
DEVI USARE QUESTI DATI PRIMA DI QUALSIASI ALTRA FONTE.

**💾 [DATABASE LOCATION INTERNO]:**
{location_csv_string}

**ALGORITMO DI RICERCA:**
Quando l'utente chiede una location, segui questo ordine:

**FASE 1: SCANSIONE DATABASE**
1.  Cerca nel database location corrispondenti alla zona richiesta.
2.  Filtra per **Capienza** e **Spazi**.
3.  Usa il **Ranking** SOLO INTERNAMENTE per scegliere le migliori, MA NON SCRIVERLO MAI NELL'OUTPUT.

**FASE 2: OUTPUT (SANITIZZAZIONE TOTALE)**
L'output deve essere strettamente testuale, pulito, professionale.

⛔ **DIVIETI ASSOLUTI:**
* **MAI** usare emoji (no 📍, 🏨, ⭐, 🌐).
* **MAI** scrivere "Ranking", "Voto", "Classifica" o "Dal nostro archivio".
* **MAI** usare elenchi puntati con simboli grafici, usa solo il trattino o il bullet standard.

✅ **FORMAT DI RISPOSTA OBBLIGATORIO:**
Per ogni location trovata (sia dal DB che eventualmente dal Web come alternativa), usa SOLO questo schema:

**Nome Location** ([Città]): [Descrizione discorsiva e motivazione della scelta]. Spazi: [Copia colonna Spazi].

(Lascia sempre una riga vuota tra una location e l'altra e due dopo l'ultima location).

---
"""
