import streamlit as st
import gspread
import requests

# --- INSTÄLLNINGAR ---
SHEET_NAME = "kalorikollen"
TAB_NAME = "Databas"

# Koppla upp oss (cache gör att vi slipper logga in vid varje klick)
@st.cache_resource
def get_sheet():
    gc = gspread.service_account(filename='service_account.json')
    return gc.open(SHEET_NAME).worksheet(TAB_NAME)

def hamta_matdata(streckkod):
    url = f"https://world.openfoodfacts.org/api/v0/product/{streckkod}.json"
    try:
        response = requests.get(url, timeout=5).json()
        if response.get('status') == 1:
            prod = response['product']
            nutri = prod.get('nutriments', {})
            return {
                'Namn': prod.get('product_name', 'Okänt'),
                'Kcal': nutri.get('energy-kcal_100g', 0),
                'Protein': nutri.get('proteins_100g', 0),
                'Kolhydrater': nutri.get('carbohydrates_100g', 0),
                'Fett': nutri.get('fat_100g', 0)
            }
    except:
        return None
    return None

# --- APPENS UTSEENDE ---
st.title("🍎 Min Kalorikoll")

# Inmatningsfält
kod = st.text_input("Skriv in streckkod:")

if kod:
    vara = hamta_matdata(kod)
    
    if vara:
        st.success(f"Hittade: {vara['Namn']}")
        
        # Visa data snyggt i kolumner
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Kcal", vara['Kcal'])
        col2.metric("Protein", vara['Protein'])
        col3.metric("Kolhydrater", vara['Kolhydrater'])
        col4.metric("Fett", vara['Fett'])
        
        # Spara-knapp
        if st.button("Spara till Databasen"):
            sheet = get_sheet()
            rad = [vara['Namn'], vara['Kcal'], vara['Protein'], vara['Kolhydrater'], vara['Fett']]
            sheet.append_row(rad)
            st.balloons() # 🎉 Lite festligt när man sparar
            st.write("Sparat! ✅")
            
    else:
        st.error("Kunde inte hitta varan.")