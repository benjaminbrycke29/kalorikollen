import gspread
import requests
import sys

# --- INSTÄLLNINGAR ---
SHEET_NAME = "kalorikollen"  # Se till att detta stämmer exakt med ditt ark
TAB_NAME = "Databas"

def koppla_till_sheets():
    try:
        # Det moderna sättet att ansluta (kräver ingen oauth2client)
        gc = gspread.service_account(filename='service_account.json')
        sh = gc.open(SHEET_NAME)
        return sh.worksheet(TAB_NAME)
    except FileNotFoundError:
        print("FEL: Hittar inte filen 'service_account.json'.")
        print("Ligger den verkligen i samma mapp som det här skriptet?")
        sys.exit()
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"FEL: Hittar inte kalkylarket '{SHEET_NAME}'.")
        print("Har du delat arket med e-postadressen i json-filen?")
        sys.exit()

def hamta_matdata(streckkod):
    url = f"https://world.openfoodfacts.org/api/v0/product/{streckkod}.json"
    print(f"Letar efter vara...")
    
    try:
        response = requests.get(url, timeout=10).json()
    except:
        print("Kunde inte nå internet eller OpenFoodFacts.")
        return None
    
    if response.get('status') == 1:
        product = response['product']
        nutriments = product.get('nutriments', {})
        
        data = {
            'Namn': product.get('product_name', 'Okänt namn'),
            'Kcal': nutriments.get('energy-kcal_100g', 0),
            'Protein': nutriments.get('proteins_100g', 0),
            'Kolhydrater': nutriments.get('carbohydrates_100g', 0),
            'Fett': nutriments.get('fat_100g', 0)
        }
        return data
    else:
        return None

# --- HUVUDPROGRAM ---
if __name__ == "__main__":
    print("Försöker ansluta till Google...")
    sheet = koppla_till_sheets()
    print("Uppkopplad mot Google Sheets! 🚀")

    while True:
        kod = input("\nScanna/skriv streckkod (eller 'q' för att avsluta): ")
        if kod.lower() == 'q':
            break
            
        vara = hamta_matdata(kod)
        
        if vara:
            print(f"Hittade: {vara['Namn']}")
            print(f"Kcal: {vara['Kcal']} | P: {vara['Protein']} | K: {vara['Kolhydrater']} | F: {vara['Fett']}")
            
            spara = input("Vill du spara till databasen? (j/n): ")
            if spara.lower() == 'j':
                rad = [vara['Namn'], vara['Kcal'], vara['Protein'], vara['Kolhydrater'], vara['Fett']]
                sheet.append_row(rad)
                print("Sparat i molnet! ✅")
        else:
            print("Kunde inte hitta varan. Är streckkoden rätt?")