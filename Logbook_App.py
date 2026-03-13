import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
import folium
from streamlit_folium import st_folium
import airportsdata

# --- CONFIGURATION ---
st.set_page_config(page_title="Logbook Christophe Cloud", layout="wide")

GSHEET_READ_URL = "https://docs.google.com/spreadsheets/d/1ra9gSLSYh0WJbMn0tJYwBMGwQ1WEzZB1XRBH1wocRa0/export?format=csv&gid=0"
GSHEET_WRITE_URL = "https://docs.google.com/spreadsheets/d/1ra9gSLSYh0WJbMn0tJYwBMGwQ1WEzZB1XRBH1wocRa0/edit#gid=0"

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data
def charger_base_aeroports():
    return airportsdata.load('ICAO')

def charger_donnees():
    df = pd.read_csv(GSHEET_READ_URL, dayfirst=True)
    df.columns = df.columns.str.strip()
    return df

# --- GÉNÉRATION DU RAPPORT COMPLET ---
def generer_pdf_complet(df_vols, date_debut_log):
    df = df_vols.copy()
    df['DateDT'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    
    # 1. NETTOYAGE NUMÉRIQUE (Noms exacts de tes champs)
    cols_calcul = [
        'SEP Dual', 'SEP Pilot', 'SEP Dual Night', 'SEP Pilot Night',
        'MEP Dual', 'MEP Pilot', 'MEP Dual Night', 'MEP Pilot Night',
        'IFR Dual', 'IFR Pilote', 'Approach', 'Landing Day', 'Landing Night'
    ]
    
    for c in cols_calcul:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

    # 2. CALCULS DU RÉSUMÉ DE L'EXPÉRIENCE (Toute la base)
    # Totaux globaux
    hdv_total_all = df[['SEP Dual', 'SEP Pilot', 'SEP Dual Night', 'SEP Pilot Night', 
                        'MEP Dual', 'MEP Pilot', 'MEP Dual Night', 'MEP Pilot Night']].sum().sum()
    hdv_solo_all = df[['SEP Pilot', 'SEP Pilot Night', 'MEP Pilot', 'MEP Pilot Night']].sum().sum()
    
    # IFR (IR)
    hdv_ifr_total = df[['IFR Dual', 'IFR Pilote']].sum().sum()
    hdv_ifr_solo = df['IFR Pilote'].sum()
    
    # Nuit
    hdv_night_total = df[['SEP Dual Night', 'SEP Pilot Night', 'MEP Dual Night', 'MEP Pilot Night']].sum().sum()
    hdv_night_solo = df[['SEP Pilot Night', 'MEP Pilot Night']].sum().sum()
    
    # MEP
    hdv_mep_total = df[['MEP Dual', 'MEP Pilot', 'MEP Dual Night', 'MEP Pilot Night']].sum().sum()
    hdv_mep_solo = df[['MEP Pilot', 'MEP Pilot Night']].sum().sum()
    
    # Glissants
    auj = datetime.now()
    df_3m = df[df['DateDT'] >= (auj - timedelta(days=90))]
    df_6m = df[df['DateDT'] >= (auj - timedelta(days=180))]
    df_12m = df[df['DateDT'] >= (auj - timedelta(days=365))]
    
    att_3m = df_3m[['Landing Day', 'Landing Night']].sum().sum()
    app_6m = df_6m['Approach'].sum()
    ifr_12m = df_12m[['IFR Dual', 'IFR Pilote']].sum().sum()
    total_12m = df_12m[['SEP Dual', 'SEP Pilot', 'SEP Dual Night', 'SEP Pilot Night', 
                        'MEP Dual', 'MEP Pilot', 'MEP Dual Night', 'MEP Pilot Night']].sum().sum()

    # 3. CRÉATION PDF
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    
    # --- PAGE 1 : RÉSUMÉ DE L'EXPÉRIENCE ---
    pdf.set_font("helvetica", "B", 18)
    pdf.cell(0, 12, "BILAN D'EXPÉRIENCE PILOTE - RÉSUMÉ TOTAL", border='B', ln=1, align="C")
    pdf.ln(8)
    
    def write_bilan_row(label, val, unit="h"):
        pdf.set_font("helvetica", "", 11)
        pdf.cell(150, 9, label, border=1)
        pdf.set_font("helvetica", "B", 11)
        v = f"{val:.2f} {unit}" if unit == "h" else f"{int(val)} {unit}"
        pdf.cell(50, 9, v, border=1, ln=1, align="C")

    # Affichage structuré selon vos demandes
    write_bilan_row("HDV Total Dual+Solo Day+Night (SEP + MEP)", hdv_total_all)
    write_bilan_row("HDV Solo Day+Night (SEP + MEP)", hdv_solo_all)
    write_bilan_row("HDV IFR (IR) Total (MEP + SEP)", hdv_ifr_total)
    write_bilan_row("HDV IFR Pilote Solo (MEP + SEP)", hdv_ifr_solo)
    write_bilan_row("HDV Night Total Dual+Solo (MEP + SEP)", hdv_night_total)
    write_bilan_row("HDV Night Solo (MEP + SEP)", hdv_night_solo)
    write_bilan_row("HDV MEP Total Day+Night (Dual + Solo)", hdv_mep_total)
    write_bilan_row("HDV MEP Solo Day+Night", hdv_mep_solo)
    
    pdf.ln(10)
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, "Expérience Récente & Totaux Glissants", ln=1)
    write_bilan_row("Nb atterrissages Day+Night (3 derniers mois)", att_3m, "att.")
    write_bilan_row("Nb approches IFR (6 derniers mois)", app_6m, "appr.")
    write_bilan_row("HDV IFR (IR) Dual+Solo (12 derniers mois)", ifr_12m)
    write_bilan_row("HDV Total Dual+Solo (12 derniers mois)", total_12m)

    # --- PAGE 2+ : LOGBOOK DÉTAILLÉ ---
    pdf.add_page()
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, f"JOURNAL DE BORD DÉTAILLÉ (Depuis le {date_debut_log.strftime('%d/%m/%Y')})", ln=1)
    pdf.ln(2)
    
    # En-têtes du tableau Log
    pdf.set_font("helvetica", "B", 8)
    pdf.set_fill_color(240, 240, 240)
    headers = [("Date", 22), ("Type", 20), ("Immat", 20), ("De", 18), ("A", 18), ("SEP P.", 15), ("MEP P.", 15), ("IR P.", 15), ("Att.", 12), ("Remarques", 120)]
    for h, w in headers:
        pdf.cell(w, 8, h, border=1, align="C", fill=True)
    pdf.ln()
    
    # Lignes des vols
    pdf.set_font("helvetica", "", 8)
    df_log = df[df['DateDT'] >= pd.to_datetime(date_debut_log)].sort_values('DateDT')
    df_log = df_log.fillna('') # Suppression des NaN

    for _, r in df_log.iterrows():
        pdf.cell(22, 7, str(r['Date']), border=1)
        pdf.cell(20, 7, str(r['Type']), border=1)
        pdf.cell(20, 7, str(r['Registration']), border=1)
        pdf.cell(18, 7, str(r['From']), border=1)
        pdf.cell(18, 7, str(r['To']), border=1)
        pdf.cell(15, 7, str(r['SEP Pilot']), border=1, align="C")
        pdf.cell(15, 7, str(r['MEP Pilot']), border=1, align="C")
        pdf.cell(15, 7, str(r['IFR Pilote']), border=1, align="C")
        pdf.cell(12, 7, str(int(r['Landing Day'] + r['Landing Night'])), border=1, align="C")
        
        # Nettoyage final des remarques pour éviter 'nan'
        rem = str(r['Remarks'])
        if rem.lower() == 'nan' or not rem: rem = ""
        pdf.cell(120, 7, rem[:80], border=1)
        pdf.ln()

    return bytes(pdf.output())

# --- INTERFACE STREAMLIT ---
st.title("✈️ Pilot Logbook Christophe")
df_vols = charger_donnees()

t1, t2, t3, t4 = st.tabs(["📝 Saisie", "📊 Historique", "🖨️ Rapport PDF", "🗺️ Carte"])

with t1:
    with st.form("form_v"):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Date")
            ty, re = st.text_input("Type"), st.text_input("Registration")
        with c2:
            fr, to = st.text_input("From"), st.text_input("To")
            s_d, s_p = st.number_input("SEP Dual", 0.0), st.number_input("SEP Pilot", 0.0)
            sn_d, sn_p = st.number_input("SEP Dual Night", 0.0), st.number_input("SEP Pilot Night", 0.0)
        with c3:
            ir_d, ir_p = st.number_input("IFR Dual", 0.0), st.number_input("IFR Pilote", 0.0)
            m_p, m_pn = st.number_input("MEP Pilot", 0.0), st.number_input("MEP Pilot Night", 0.0)
            ap, ld = st.number_input("Approach", 0), st.number_input("Landing Day", 0)
        
        if st.form_submit_button("Enregistrer le vol"):
            nouveau = pd.DataFrame([{
                "Date": d.strftime('%d/%m/%Y'), "Type": ty, "Registration": re, 
                "From": fr, "To": to, "SEP Dual": s_d, "SEP Pilot": s_p, 
                "SEP Dual Night": sn_d, "SEP Pilot Night": sn_p, "MEP Pilot": m_p,
                "MEP Pilot Night": m_pn, "IFR Dual": ir_d, "IFR Pilote": ir_p,
                "Approach": ap, "Landing Day": ld
            }])
            df_maj = pd.concat([df_vols, nouveau], ignore_index=True)
            conn.update(spreadsheet=GSHEET_WRITE_URL, worksheet="vols", data=df_maj)
            st.cache_data.clear()
            st.success("Vol enregistré !")
            st.rerun()

with t2:
    st.dataframe(df_vols, use_container_width=True)

with t3:
    st.header("Génération du document officiel")
    date_extr = st.date_input("Détails des vols à partir du :", datetime(2024, 1, 1))
    if st.button("📊 Créer le PDF Complet"):
        pdf_bytes = generer_pdf_complet(df_vols, date_extr)
        st.download_button("📥 Télécharger le PDF (Bilan + Log)", pdf_bytes, "Logbook_Bilan.pdf")

with t4:
    airports = charger_base_aeroports()
    m = folium.Map(location=[46, 2], zoom_start=5)
    for _, r in df_vols.dropna(subset=['From', 'To']).iterrows():
        f, t = str(r['From']).upper().strip(), str(r['To']).upper().strip()
        if f in airports and t in airports:
            folium.PolyLine([[airports[f]['lat'], airports[f]['lon']], [airports[t]['lat'], airports[t]['lon']]], color="blue", weight=1).add_to(m)
    st_folium(m, width=1100, height=500, key="map_unique")
