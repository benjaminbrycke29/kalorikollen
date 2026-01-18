import streamlit as st
import gspread
import requests
from pyzbar.pyzbar import decode
from PIL import Image, ImageEnhance

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

metod = st.radio("Metod:", ["📷 Kamera", "✍️ Manuell Kod"], horizontal=True)
kod = ""

if metod == "📷 Kamera":
    img_file = st.camera_input("Fota streckkoden")
    
    if img_file:
        # Öppna bilden
        original_image = Image.open(img_file)
        
        # --- BILD-MAGI (Förbättra bilden så datorn ser koden) ---
        bilder_att_testa = [original_image]
        
        # 1. Gör svartvit
        gray_img = original_image.convert('L')
        bilder_att_testa.append(gray_img)
        
        # 2. Öka kontrasten rejält (Hjälper oftast mest)
        enhancer = ImageEnhance.Contrast(gray_img)
        high_contrast_img = enhancer.enhance(3.0)
        bilder_att_testa.append(high_contrast_img)
        
        # 3. Zooma in mitten (Crop)
        w, h = gray_img.size
        cropped_img = high_contrast_img.crop((w*0.25, h*0.25, w*0.75, h*0.75))
        bilder_att_testa.append(cropped_img)

        # Testa att läsa alla varianter
        for img in bilder_att_testa:
            decodade = decode(img)
            if decodade:
                kod = decodade[0].data.decode("utf-8")
                st.success(f"Lyckades läsa: {kod}")
                break 
        
        if not kod:
            st.warning("Kunde inte läsa koden. Försök hålla stilla & ha bra ljus!")

else:
    kod = st.text_input("Skriv kod:")

# --- VISA RESULTAT ---
if kod:
    vara = hamta_matdata(kod)
    
    if vara:
        st.info(f"Hittade: **{vara['Namn']}**")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Kcal", vara['Kcal'])
        c2.metric("Prot", vara['Protein'])
        c3.metric("Kolh", vara['Kolhydrater'])
        c4.metric("Fett", vara['Fett'])
        
        st.divider()
        pris = st.number_input("Pris (kr):", min_value=0.0, step=1.0)
        
        if st.button("Spara 💾"):
            sheet = get_sheet()
            rad = [
                vara['Namn'], vara['Kcal'], vara['Protein'], 
                vara['Kolhydrater'], vara['Fett'], pris
            ]
            sheet.append_row(rad)
            st.balloons()
            st.toast("Sparat i molnet!")
            
    else:
        st.error("Kunde inte hitta varan.")