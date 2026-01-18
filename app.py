import streamlit as st
import gspread
import requests
from pyzbar.pyzbar import decode
from PIL import Image

# --- INSTÄLLNINGAR ---
SHEET_NAME = "kalorikollen"
TAB_NAME = "Databas"

# --- KOPPLING MOT GOOGLE ---
@st.cache_resource
def get_sheet():
    try:
        credentials = dict(st.secrets["gcp_service_account"])
        gc = gspread.service_account_from_dict(credentials)
    except:
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

# Välj metod: Kamera eller manuell?
metod = st.radio("Hur vill du mata in?", ["📷 Kamera", "✍️ Skriv kod"], horizontal=True)

kod = ""

if metod == "📷 Kamera":
    # Starta kameran
    img_file = st.camera_input("Ta en bild på streckkoden")
    
    if img_file:
        # Öppna bilden och leta efter streckkoder
        image = Image.open(img_file)
        decodade_objekt = decode(image)
        
        if decodade_objekt:
            # Vi tar den första koden vi hittar
            kod = decodade_objekt[0].data.decode("utf-8")
            st.success(f"Scannade kod: {kod}")
        else:
            st.warning("Kunde inte se någon streckkod i bilden. Försök gå närmare!")

else:
    kod = st.text_input("Skriv in streckkod manuellt:")

# --- HÄMTA DATA (Samma som förut) ---
if kod:
    vara = hamta_matdata(kod)
    
    if vara:
        st.info(f"Hittade: **{vara['Namn']}**")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Kcal", vara['Kcal'])
        col2.metric("Prot", vara['Protein'])
        col3.metric("Kolh", vara['Kolhydrater'])
        col4.metric("Fett", vara['Fett'])
        
        st.divider()
        pris = st.number_input("Pris (kr):", min_value=0.0, step=1.0)
        
        if st.button("Spara till Databasen 💾"):
            sheet = get_sheet()
            rad = [
                vara['Namn'], vara['Kcal'], vara['Protein'], 
                vara['Kolhydrater'], vara['Fett'], pris
            ]
            sheet.append_row(rad)
            st.balloons()
            st.toast("Sparat!")
            
    else:
        st.error("Kunde inte hitta varan i databasen.")