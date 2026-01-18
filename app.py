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
                    # Byt komma mot punkt och gör till siffra
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
    
    # --- INSTÄLLNINGAR FÖR MÅL ---
    with st.sidebar.expander("🎯 Dina Mål & Macros", expanded=True):
        mal_kcal = st.slider("Kalorimål:", 1500, 4000, 2500)
        st.write("---")
        st.write("**Fördelning (%)**")
        mal_prot_proc = st.slider("Protein %", 10, 60, 30)
        mal_fett_proc = st.slider("Fett %", 10, 60, 35)
        # Kolhydrater blir det som blir över (så det alltid blir 100%)
        mal_kolh_proc = 100 - (mal_prot_proc + mal_fett_proc)
        st.info(f"Kolhydrater: {mal_kolh_proc}% (Automatiskt)")
        
        if mal_kolh_proc < 0:
            st.error("Oj! Protein + Fett är mer än 100%!")

    # --- RÄKNA UT MÅL I GRAM ---
    # Protein/Kolh = 4 kcal/g. Fett = 9 kcal/g.
    target_prot_g = round((mal_kcal * (mal_prot_proc / 100)) / 4)
    target_fett_g = round((mal_kcal * (mal_fett_proc / 100)) / 9)
    target_kolh_g = round((mal_kcal * (mal_kolh_proc / 100)) / 4)

    # 2. Hämta datan
    df = hamta_dagbok()
    
    if not df.empty:
        # Filtrera fram dagens mat
        if 'Datum' in df.columns:
             dagens_mat = df[df['Datum'] == DAGENS_DATUM]
        else:
             st.error("Hittar ingen kolumn som heter 'Datum' i din Excel-fil.")
             dagens_mat = pd.DataFrame() # Tom
        
        if not dagens_mat.empty:
            # Summera allt
            tot_kcal = int(dagens_mat['Kcal'].sum())
            tot_prot = int(dagens_mat['Protein'].sum())
            tot_kolh = int(dagens_mat['Kolh'].sum())
            tot_fett = int(dagens_mat['Fett'].sum())
            tot_kostnad = int(dagens_mat['Kostnad'].sum())
            
            # --- KPI:er (Stora siffror) ---
            # Vi räknar ut "kvar" (delta)
            kvar_kcal = mal_kcal - tot_kcal
            kvar_prot = target_prot_g - tot_prot
            kvar_kolh = target_kolh_g - tot_kolh
            kvar_fett = target_fett_g - tot_fett

            # Rad 1: Kalorier & Kostnad
            c1, c2 = st.columns(2)
            c1.metric("🔥 Kalorier", f"{tot_kcal}", f"{kvar_kcal} kvar")
            c2.metric("💰 Kostnad", f"{tot_kostnad} kr")
            
            st.progress(min(tot_kcal / mal_kcal, 1.0))
            
            st.divider()

            # Rad 2: Makronutrienter (Med jämförelse!)
            m1, m2, m3 = st.columns(3)
            
            # Helper för att visa färg om man gått över
            def show_macro(label, current, target, left):
                color = "normal"
                if left < 0: 
                    label += " (Över!)"
                    color = "inverse"
                st.metric(label, f"{current}g", f"{left}g kvar", delta_color=color)

            with m1:
                show_macro("Protein", tot_prot, target_prot_g, kvar_prot)
                st.caption(f"Mål: {target_prot_g}g")
                st.progress(min(tot_prot / target_prot_g, 1.0) if target_prot_g > 0 else 0)

            with m2:
                show_macro("Kolhydrater", tot_kolh, target_kolh_g, kvar_kolh)
                st.caption(f"Mål: {target_kolh_g}g")
                st.progress(min(tot_kolh / target_kolh_g, 1.0) if target_kolh_g > 0 else 0)

            with m3:
                show_macro("Fett", tot_fett, target_fett_g, kvar_fett)
                st.caption(f"Mål: {target_fett_g}g")
                st.progress(min(tot_fett / target_fett_g, 1.0) if target_fett_g > 0 else 0)
            
            st.divider()
            
            # --- CIRKELDIAGRAM ---
            c_chart, c_list = st.columns([1, 1])
            
            with c_chart:
                st.subheader("Fördelning")
                macro_data = pd.DataFrame({
                    'Macro': ['Protein', 'Kolhydrater', 'Fett'],
                    'Gram': [tot_prot, tot_kolh, tot_fett]
                })
                # Om man inte ätit något än kraschar diagrammet, så vi kollar:
                if tot_prot + tot_kolh + tot_fett > 0:
                    fig = px.pie(macro_data, values='Gram', names='Macro', hole=0.5, 
                                 color_discrete_sequence=['#ff4b4b', '#1f77b4', '#ff7f0e'])
                    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=250)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.write("Ät något för att se diagrammet! 🍕")

            with c_list:
                st.subheader("Dagens måltider")
                st.dataframe(dagens_mat[['Måltid', 'Vara', 'Mängd', 'Kcal']], hide_index=True, height=250)
                
        else:
            st.info(f"Ingen mat loggad för {DAGENS_DATUM}. Gå till 'Logga Mat'!")
    else:
        st.warning("Kunde inte läsa dagboken. Kolla att fliken heter 'Dagbok' och har rätt rubriker.")

# ---------------------------------------------------------
# SIDA 2: LOGGA MAT
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
        c3.metric("Pris (ca)", f"{vald_vara.get('Pris', 0)} kr")

        with st.form("log_form"):
            col_a, col_b = st.columns(2)
            mangd = col_a.number_input("Mängd (g):", value=100)
            maltid = col_b.selectbox("Måltid:", ["Frukost", "Lunch", "Middag", "Mellanmål"])
            
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
                
                sheet_dagbok = get_sheet("Dagbok")
                sheet_dagbok.append_row(rad_dagbok)
                
                if metod != "🔍 Sök i min lista":
                    try:
                        sheet_db = get_sheet("Databas")
                        rad_db = [vald_vara['Namn'], vald_vara['Kcal'], vald_vara['Protein'], vald_vara['Kolhydrater'], vald_vara['Fett'], 0]
                        sheet_db.append_row(rad_db)
                    except:
                        pass
                
                st.balloons()
                st.success("Sparat!")