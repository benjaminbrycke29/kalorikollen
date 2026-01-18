import streamlit as st
import gspread
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime
from pyzbar.pyzbar import decode
from PIL import Image, ImageEnhance

# --- INSTÄLLNINGAR ---
SHEET_NAME = "kalorikollen"
DAGENS_DATUM = datetime.now().strftime("%Y-%m-%d")

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

def hamta_dagbok():
    try:
        sheet = get_sheet("Dagbok")
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # --- FIX: Tvätta siffrorna så 25,2 och 25.2 funkar ---
        if not df.empty:
            cols_to_fix = ['Kcal', 'Protein', 'Kolh', 'Fett', 'Kostnad']
            
            for col in cols_to_fix:
                if col in df.columns:
                    # 1. Gör om allt till text först
                    # 2. Byt ut komma mot punkt
                    # 3. Tvinga till siffra (kraschar det så sätts 0)
                    df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    
        return df
    except:
        return pd.DataFrame()

def hamta_sparade_varor():
    try:
        sheet = get_sheet("Databas")
        data = sheet.get_all_records()
        return data
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
                'Pris': 0
            }
    except:
        return None
    return None

# --- APPENS UTSEENDE ---
st.title("🍎 Min Mat-App")

# Sidomeny
sida = st.sidebar.radio("Meny", ["📊 Statistik & Översikt", "🍽 Logga Mat"])

# ---------------------------------------------------------
# SIDA 1: STATISTIK (DASHBOARD)
# ---------------------------------------------------------
if sida == "📊 Statistik & Översikt":
    st.header(f"Dagens status ({DAGENS_DATUM})")
    
    # 1. Sätt ditt mål (du kan ändra detta med en slider)
    mal_kcal = st.sidebar.slider("Ditt Kalorimål:", 1500, 4000, 2500)
    
    # 2. Hämta datan
    df = hamta_dagbok()
    
    if not df.empty:
        # Filtrera så vi bara ser DAGENS mat
        # (Förutsätter att kolumn A heter 'Datum')
        dagens_mat = df[df['Datum'] == DAGENS_DATUM]
        
        if not dagens_mat.empty:
            # Summera allt
            tot_kcal = dagens_mat['Kcal'].sum()
            tot_prot = dagens_mat['Protein'].sum()
            tot_kolh = dagens_mat['Kolh'].sum() # Kolla att din kolumn heter Kolh
            tot_fett = dagens_mat['Fett'].sum()
            tot_kostnad = dagens_mat['Kostnad'].sum() # Kolla att din kolumn heter Kostnad
            
            # --- KPI:er (Stora siffror) ---
            kvar = mal_kcal - tot_kcal
            col1, col2, col3 = st.columns(3)
            col1.metric("Ätet idag", f"{tot_kcal} kcal", delta=f"{kvar} kvar")
            col2.metric("Protein", f"{tot_prot} g")
            col3.metric("Dagens Kostnad", f"{tot_kostnad} kr")
            
            # --- PROGRESS BAR ---
            st.write(f"Du har ätit **{int((tot_kcal/mal_kcal)*100)}%** av ditt mål.")
            st.progress(min(tot_kcal / mal_kcal, 1.0))
            
            st.divider()
            
            # --- CIRKELDIAGRAM (Macros) ---
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("Makrofördelning")
                # Skapa data för diagrammet
                macro_data = pd.DataFrame({
                    'Macro': ['Protein', 'Kolhydrater', 'Fett'],
                    'Gram': [tot_prot, tot_kolh, tot_fett]
                })
                fig = px.pie(macro_data, values='Gram', names='Macro', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                st.plotly_chart(fig, use_container_width=True)
                
            with c2:
                st.subheader("Vad har du ätit?")
                # Visa en enkel lista på dagens mat
                st.dataframe(dagens_mat[['Måltid', 'Vara', 'Mängd', 'Kcal']], hide_index=True)
                
        else:
            st.info("Du har inte loggat något idag än. Gå till 'Logga Mat'!")
    else:
        st.warning("Dagboken är tom eller kunde inte läsas.")

# ---------------------------------------------------------
# SIDA 2: LOGGA MAT (Samma som förut men uppstädad)
# ---------------------------------------------------------
elif sida == "🍽 Logga Mat":
    st.header("Lägg till måltid")
    
    metod = st.radio("Metod:", ["🔍 Sök i min lista", "📷 Kamera", "✍️ Skriv kod"], horizontal=True)
    vald_vara = None
    
    if metod == "🔍 Sök i min lista":
        sparade = hamta_sparade_varor()
        if sparade:
            namn_lista = [rad['Livsmedel'] for rad in sparade if 'Livsmedel' in rad]
            val = st.selectbox("Välj vara:", ["-"] + namn_lista)
            if val != "-":
                for rad in sparade:
                    if rad.get('Livsmedel') == val:
                        vald_vara = rad
                        vald_vara['Namn'] = val
                        break

    elif metod == "📷 Kamera":
        img_file = st.camera_input("Fota streckkoden")
        if img_file:
            img = Image.open(img_file)
            gray = img.convert('L')
            enhancer = ImageEnhance.Contrast(gray)
            high_contrast = enhancer.enhance(3.0)
            decoded = decode(high_contrast)
            if not decoded:
                decoded = decode(img)
            
            if decoded:
                kod = decoded[0].data.decode("utf-8")
                st.success(f"Kod: {kod}")
                vald_vara = hamta_fran_api(kod)
            else:
                st.warning("Ingen kod hittad.")

    elif metod == "✍️ Skriv kod":
        kod = st.text_input("Streckkod:")
        if kod:
            vald_vara = hamta_fran_api(kod)

    if vald_vara:
        st.divider()
        st.subheader(f"{vald_vara['Namn']}")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Kcal/100g", vald_vara['Kcal'])
        c2.metric("Protein", vald_vara['Protein'])
        c3.metric("Pris (Databas)", f"{vald_vara.get('Pris', 0)} kr")

        with st.form("log_form"):
            col_a, col_b = st.columns(2)
            mangd = col_a.number_input("Mängd (g):", value=100)
            maltid = col_b.selectbox("Måltid:", ["Frukost", "Lunch", "Middag", "Mellanmål"])
            
            # Räkna ut kostnad
            pris_forslag = 0.0
            # Om vi har sparat pris i databasen kan vi försöka gissa kostnaden för portionen
            if vald_vara.get('Pris'):
                # En enkel gissning: Vi antar att priset i databasen är per 100g (eller paket). 
                # Låt oss hålla det manuellt tills vidare för att inte krångla till det.
                pass

            kostnad = st.number_input("Kostnad för denna portion (kr):", min_value=0.0, step=1.0)
            
            submitted = st.form_submit_button("Spara till Dagboken ✅")
            
            if submitted:
                faktor = mangd / 100
                rad_dagbok = [
                    DAGENS_DATUM, 
                    maltid, 
                    vald_vara['Namn'], 
                    mangd, 
                    round(vald_vara['Kcal'] * faktor), 
                    round(vald_vara['Protein'] * faktor, 1), 
                    round(vald_vara['Kolhydrater'] * faktor, 1), 
                    round(vald_vara['Fett'] * faktor, 1),
                    kostnad
                ]
                
                # Spara till dagbok
                sheet_dagbok = get_sheet("Dagbok")
                sheet_dagbok.append_row(rad_dagbok)
                
                # Om ny vara, spara till snabblista
                if metod != "🔍 Sök i min lista":
                    try:
                        sheet_db = get_sheet("Databas")
                        rad_db = [vald_vara['Namn'], vald_vara['Kcal'], vald_vara['Protein'], vald_vara['Kolhydrater'], vald_vara['Fett'], 0]
                        sheet_db.append_row(rad_db)
                    except:
                        pass
                
                st.balloons()
                st.success("Sparat!")