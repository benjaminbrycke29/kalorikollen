import streamlit as st
import gspread
import requests
from datetime import datetime
from pyzbar.pyzbar import decode
from PIL import Image, ImageEnhance

# --- INSTÄLLNINGAR ---
SHEET_NAME = "kalorikollen"

# --- KOPPLING MOT GOOGLE ---
@st.cache_resource
def get_client():
    try:
        credentials = dict(st.secrets["gcp_service_account"])
        return gspread.service_account_from_dict(credentials)
    except:
        return gspread.service_account(filename='service_account.json')

def get_sheet(tab_name):
    client = get_client()
    return client.open(SHEET_NAME).worksheet(tab_name)

# Hämta alla matvaror vi redan sparat (för sökfunktionen)
def hamta_sparade_varor():
    try:
        sheet = get_sheet("Databas")
        # Hämtar alla namn (kolumn A) och deras data
        data = sheet.get_all_records()
        return data # Returnerar en lista med lexikon
    except:
        return []

def hamta_fran_api(streckkod):
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
                'Fett': nutri.get('fat_100g', 0),
                'Pris': 0 # API vet inte pris
            }
    except:
        return None
    return None

# --- APPENS UTSEENDE ---
st.title("🍎 Min Matdagbok")

# Sidomeny för navigation
sida = st.sidebar.radio("Meny", ["Logga Mat", "Statistik (Kommer snart)"])

if sida == "Logga Mat":
    
    # 1. Välj hur vi hittar maten
    metod = st.radio("Hitta vara:", ["🔍 Sök i min lista", "📷 Kamera", "✍️ Skriv kod"], horizontal=True)
    
    vald_vara = None
    
    # --- METOD 1: Sök i listan (Det du sparat tidigare) ---
    if metod == "🔍 Sök i min lista":
        sparade = hamta_sparade_varor()
        if sparade:
            # Skapa en lista med namn för dropdown-menyn
            namn_lista = [rad['Livsmedel'] for rad in sparade if 'Livsmedel' in rad] # Anpassa nyckel om du döpt kolumn A till 'Namn' eller 'Livsmedel' i Databas-fliken
            
            # OBS: Koden antar att Kolumn A heter "Livsmedel" i din Databas. 
            # Om den heter "Namn", ändra 'Livsmedel' till 'Namn' på raden ovan.
            
            val = st.selectbox("Välj vara:", ["- Välj -"] + namn_lista)
            
            if val != "- Välj -":
                # Hitta rätt rad i datan
                for rad in sparade:
                    if rad.get('Livsmedel') == val or rad.get('Namn') == val:
                        vald_vara = rad
                        # Fixa så nycklarna stämmer med API-formatet
                        vald_vara['Namn'] = val
                        break
        else:
            st.warning("Din databas är tom. Scanna något först!")

    # --- METOD 2: Kamera ---
    elif metod == "📷 Kamera":
        img_file = st.camera_input("Fota streckkoden")
        if img_file:
            img = Image.open(img_file)
            # (Här kör vi din bild-magi för bättre scanning)
            gray = img.convert('L')
            enhancer = ImageEnhance.Contrast(gray)
            high_contrast = enhancer.enhance(3.0)
            
            # Testa läsa
            decoded = decode(high_contrast)
            if not decoded:
                decoded = decode(img) # Testa originalbilden också
                
            if decoded:
                kod = decoded[0].data.decode("utf-8")
                st.success(f"Kod: {kod}")
                vald_vara = hamta_fran_api(kod)
            else:
                st.warning("Hittade ingen kod.")

    # --- METOD 3: Manuell Kod ---
    elif metod == "✍️ Skriv kod":
        kod = st.text_input("Streckkod:")
        if kod:
            vald_vara = hamta_fran_api(kod)

    # --- OM VI HITTAT EN VARA (Oavsett metod) ---
    if vald_vara:
        st.divider()
        st.subheader(f"Mat: {vald_vara['Namn']}")
        
        # Visa per 100g
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Kcal/100g", vald_vara['Kcal'])
        c2.metric("Protein", vald_vara['Protein'])
        c3.metric("Kolh", vald_vara['Kolhydrater'])
        c4.metric("Fett", vald_vara['Fett'])
        
        # --- LOGGA TILL DAGBOK ---
        st.info("🍽 Lägg till i dagboken")
        
        col_a, col_b = st.columns(2)
        with col_a:
            mangd = st.number_input("Mängd (gram):", value=100, step=10)
        with col_b:
            maltid = st.selectbox("Måltid:", ["Frukost", "Lunch", "Middag", "Mellanmål"])
            
        # Räkna ut totalen för portionen
        faktor = mangd / 100
        tot_kcal = round(vald_vara['Kcal'] * faktor)
        tot_prot = round(vald_vara['Protein'] * faktor, 1)
        tot_kolh = round(vald_vara['Kolhydrater'] * faktor, 1)
        tot_fett = round(vald_vara['Fett'] * faktor, 1)
        
        # Prisräknare (om pris finns i databasen)
        pris_per_kg = vald_vara.get('Pris', 0) # Om du sparat pris i databasen
        # Om API användes är priset 0, låt användaren fylla i
        tot_pris = 0
        if pris_per_kg:
             # Om priset är sparat som kr/st eller kr/paket blir detta lite skevt, 
             # men vi antar kr/förpackning och låter användaren justera nedan.
             pass 
        
        tot_kostnad = st.number_input("Kostnad för denna portion (kr):", min_value=0.0, step=1.0)

        # Visa vad som kommer loggas
        st.write(f"📊 **Totalt för {mangd}g:** {tot_kcal} kcal | {tot_prot}g Protein")
        
        if st.button("Logga i Dagboken ✅"):
            datum = datetime.now().strftime("%Y-%m-%d")
            
            # Förbered raden för Dagbok-fliken
            rad_dagbok = [
                datum, maltid, vald_vara['Namn'], mangd, 
                tot_kcal, tot_prot, tot_kolh, tot_fett, tot_kostnad
            ]
            
            sheet_dagbok = get_sheet("Dagbok")
            sheet_dagbok.append_row(rad_dagbok)
            
            # Om varan kom från API (inte fanns i listan), spara den till Databasen också!
            # Så vi slipper scanna den nästa gång.
            if metod != "🔍 Sök i min lista":
                try:
                    sheet_db = get_sheet("Databas")
                    # Kolla så vi inte dubbelsparar (enkelt check) kan läggas till sen
                    rad_db = [
                        vald_vara['Namn'], vald_vara['Kcal'], vald_vara['Protein'], 
                        vald_vara['Kolhydrater'], vald_vara['Fett'], 0 # Pris noll tills vidare
                    ]
                    sheet_db.append_row(rad_db)
                    st.toast("Sparade även varan i din snabblista!")
                except:
                    pass

            st.balloons()
            st.success("Måltiden loggad!")

elif sida == "Statistik (Kommer snart)":
    st.write("Här ska vi bygga grafer sen! 📈")