import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import folium
from streamlit_folium import st_folium
import airportsdata

# --- CONNEXION GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data
def charger_base_aeroports():
    return airportsdata.load('ICAO')

def charger_donnees():
    return conn.read(worksheet="vols", ttl="0")

# --- GÉNÉRATION DU RAPPORT PDF ---
def generer_pdf_logbook_final(df_total, date_affichage):
    df_filtre = df_total[df_total['Date'] >= date_affichage].sort_values(by='Date')
    
    if df_total.empty: return None

    df_total['DateDT'] = pd.to_datetime(df_total['Date'])
    auj = datetime.now()

    # --- CALCULS ---
    cols_hdv = ['SEP Dual', 'SEP Pilot', 'SEP Dual Night', 'SEP Pilot Night', 'MEP Dual', 'MEP Pilot', 'MEP Dual Night', 'MEP Pilot Night']
    t_hdv = df_total[cols_hdv].sum().sum()
    t_mep_glob = df_total[['MEP Dual', 'MEP Pilot', 'MEP Dual Night', 'MEP Pilot Night']].sum().sum()
    t_ir_glob = df_total[['IFR Dual', 'IFR Pilote']].sum().sum()
    t_night_glob = df_total[['SEP Dual Night', 'SEP Pilot Night', 'MEP Dual Night', 'MEP Pilot Night']].sum().sum()

    t_solo_glob = df_total[['SEP Pilot', 'SEP Pilot Night', 'MEP Pilot', 'MEP Pilot Night']].sum().sum()
    t_solo_mep = df_total[['MEP Pilot', 'MEP Pilot Night']].sum().sum()
    t_solo_ir = df_total['IFR Pilote'].sum()
    t_solo_night = df_total[['SEP Pilot Night', 'MEP Pilot Night']].sum().sum()

    n_app_6m = df_total[df_total['DateDT'] >= (auj - timedelta(days=180))]['Approach'].sum()
    n_land_3m = df_total[df_total['DateDT'] >= (auj - timedelta(days=90))][['Landing Day', 'Landing Night']].sum().sum()
    h_tot_12m = df_total[df_total['DateDT'] >= (auj - timedelta(days=365))][cols_hdv].sum().sum()
    h_ir_12m = df_total[df_total['DateDT'] >= (auj - timedelta(days=365))][['IFR Dual', 'IFR Pilote']].sum().sum()

    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "BILAN D'EXPERIENCE ET CARNET DE VOL", align="C", border='B', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.ln(5); pdf.set_fill_color(230, 230, 230); pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 8, " SYNTHESE GLOBALE", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "", 9)
    pdf.cell(65, 7, f" HDV Totales (SEP+MEP): {t_hdv:.2f} h", border='L')
    pdf.cell(65, 7, f" MEP Totale (Dual+Solo): {t_mep_glob:.2f} h", border='0')
    pdf.cell(65, 7, f" IR Global: {t_ir_glob:.2f} h", border='0')
    pdf.cell(0, 7, f" Nuit Totale: {t_night_glob:.2f} h", border='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 8, " EXPERIENCE SOLO (PIC)", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(65, 7, f" Solo Global: {t_solo_glob:.2f} h", border='LB')
    pdf.cell(65, 7, f" Solo MEP: {t_solo_mep:.2f} h", border='B')
    pdf.cell(65, 7, f" Solo IR: {t_solo_ir:.2f} h", border='B')
    pdf.cell(0, 7, f" Solo Nuit: {t_solo_night:.2f} h", border='RB', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(3); pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 8, " MAINTIEN DE COMPETENCES (RECENCY)", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "", 9)
    pdf.cell(65, 7, f" Approches (6 mois): {int(n_app_6m)}", border='LB')
    pdf.cell(65, 7, f" Atterrissages (3 mois): {int(n_land_3m)}", border='B')
    pdf.cell(65, 7, f" HDV Totales (12 mois): {h_tot_12m:.2f} h", border='B')
    pdf.cell(0, 7, f" HDV IR (12 mois): {h_ir_12m:.2f} h", border='RB', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.ln(8)
    pdf.set_font("helvetica", "B", 8); pdf.set_fill_color(240, 240, 240)
    headers = [("Date", 22), ("Type", 18), ("Immat", 18), ("De/A", 35), ("SEP", 15), ("MEP", 15), ("IFR", 15), ("Remarques", 130)]
    for h, w in headers: pdf.cell(w, 8, h, border=1, align="C", fill=True)
    pdf.ln()
    
    pdf.set_font("helvetica", "", 7)
    for idx, r in df_filtre.iterrows():
        rem = str(r['Remarks']) if r['Remarks'] and str(r['Remarks']).strip() not in ["0", "0.0", "None", "nan"] else ""
        v_sep = sum([r[c] for c in ['SEP Dual', 'SEP Pilot', 'SEP Dual Night', 'SEP Pilot Night'] if pd.notnull(r[c])])
        v_mep = sum([r[c] for c in ['MEP Dual', 'MEP Pilot', 'MEP Dual Night', 'MEP Pilot Night'] if pd.notnull(r[c])])
        v_ifr = (r['IFR Dual'] or 0) + (r['IFR Pilote'] or 0)
        pdf.cell(22, 6, str(r['Date'])[:10], border=1, align="C")
        pdf.cell(18, 6, str(r['Type']), border=1, align="C")
        pdf.cell(18, 6, str(r['Registration']), border=1, align="C")
        pdf.cell(35, 6, f"{r['From']} - {r['To']}", border=1, align="C")
        pdf.cell(15, 6, f"{v_sep:.2f}", border=1, align="C")
        pdf.cell(15, 6, f"{v_mep:.2f}", border=1, align="C")
        pdf.cell(15, 6, f"{v_ifr:.2f}", border=1, align="C")
        pdf.cell(130, 6, rem[:110], border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())

# --- INTERFACE ---
st.set_page_config(page_title="Logbook Christophe Cloud", layout="wide")
st.title("✈️ Pilot Logbook Manager (Cloud)")

df_vols = charger_donnees()
t_saisie, t_hist, t_print, t_map = st.tabs(["📝 Saisie", "📊 Historique", "🖨️ Rapports", "🗺️ Carte & Stats"])

with t_saisie:
    st.header("Enregistrer un vol")
    with st.form("f_v3", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Date", datetime.now()); typ = st.text_input("Type Avion"); reg = st.text_input("Immat")
        with c2:
            f_fr = st.text_input("Départ"); f_to = st.text_input("Arrivée"); s_p = st.number_input("SEP Pilot", 0.0); m_p = st.number_input("MEP Pilot", 0.0)
        with c3:
            i_p = st.number_input("IFR Pilot", 0.0); app = st.number_input("Approches", 0); lnd = st.number_input("Atterrissages", 0); rem = st.text_area("Remarques")
        
        if st.form_submit_button("Sauvegarder"):
            nouveau_vol = pd.DataFrame([{
                "Date": d.strftime('%Y-%m-%d'), "Type": typ, "Registration": reg, "From": f_fr, "To": f_to,
                "SEP Pilot": s_p, "MEP Pilot": m_p, "IFR Pilote": i_p, "Approach": app, "Landing Day": lnd, "Remarks": rem
            }])
            df_maj = pd.concat([df_vols, nouveau_vol], ignore_index=True)
            conn.update(worksheet="vols", data=df_maj)
            st.cache_data.clear()
            st.success("Vol enregistré sur Google Sheets !")
            st.rerun()

with t_hist:
    if not df_vols.empty:
        st.dataframe(df_vols.sort_values(by="Date", ascending=False), use_container_width=True)

with t_print:
    date_c = st.date_input("Détail dès le :", datetime(2024, 1, 1))
    if st.button("📥 Générer le PDF"):
        pdf_bytes = generer_pdf_logbook_final(df_vols, date_c.strftime('%Y-%m-%d'))
        if pdf_bytes:
            st.download_button("Télécharger le PDF", pdf_bytes, "Logbook_Christophe.pdf", "application/pdf")

with t_map:
    c1, c2 = st.columns(2)
    with c1: d1 = st.date_input("Du", datetime(2024, 1, 1), key="d1")
    with c2: d2 = st.date_input("Au", datetime.now(), key="d2")
    if st.button("Afficher la carte"):
        df_m = df_vols[(df_vols['Date'] >= d1.strftime('%Y-%m-%d')) & (df_vols['Date'] <= d2.strftime('%Y-%m-%d'))]
        if not df_m.empty:
            airports = charger_base_aeroports()
            m = folium.Map(location=[45, 5], zoom_start=5)
            for _, row in df_m.iterrows():
                dep, arr = str(row['From']).upper().strip(), str(row['To']).upper().strip()
                if dep in airports and arr in airports:
                    folium.PolyLine([[airports[dep]['lat'], airports[dep]['lon']], [airports[arr]['lat'], airports[arr]['lon']]], color="blue", weight=2).add_to(m)
            st_folium(m, width=1100, height=500)
