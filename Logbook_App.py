import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import folium
from streamlit_folium import st_folium
import airportsdata

DATABASE_NAME = "Pilot_Logbook_Christophe.db"

# --- INITIALISATION DE LA BASE ---
def initialiser_db():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.execute("""CREATE TABLE IF NOT EXISTS vols (
        "Flight Number" INTEGER PRIMARY KEY AUTOINCREMENT, "Date" TEXT, "From" TEXT, "To" TEXT, "Route" TEXT,
        "Type" TEXT, "Registration" TEXT, "SEP Dual" REAL, "SEP Pilot" REAL, 
        "SEP Dual Night" REAL, "SEP Pilot Night" REAL, "MEP Dual" REAL, "MEP Pilot" REAL,
        "MEP Dual Night" REAL, "MEP Pilot Night" REAL, "IFR Dual" REAL, "IFR Pilote" REAL,
        "Approach" INTEGER, "T/O Day" INTEGER, "T/O Night" INTEGER, 
        "Landing Day" INTEGER, "Landing Night" INTEGER, "Remarks" TEXT
    )""")
    conn.close()

@st.cache_data
def charger_base_aeroports():
    return airportsdata.load('ICAO')

# --- GÉNÉRATION DU RAPPORT PDF ---
def generer_pdf_logbook_final(date_affichage):
    conn = sqlite3.connect(DATABASE_NAME)
    df_total = pd.read_sql("SELECT * FROM vols", conn)
    df_filtre = pd.read_sql("SELECT * FROM vols WHERE Date >= ? ORDER BY Date ASC", conn, params=(date_affichage,))
    conn.close()
    
    if df_total.empty: return None

    df_total['DateDT'] = pd.to_datetime(df_total['Date'])
    auj = datetime.now()

    # --- CALCULS ---
    t_hdv = df_total[['SEP Dual', 'SEP Pilot', 'SEP Dual Night', 'SEP Pilot Night', 'MEP Dual', 'MEP Pilot', 'MEP Dual Night', 'MEP Pilot Night']].sum().sum()
    t_mep_glob = df_total[['MEP Dual', 'MEP Pilot', 'MEP Dual Night', 'MEP Pilot Night']].sum().sum()
    t_ir_glob = df_total[['IFR Dual', 'IFR Pilote']].sum().sum()
    t_night_glob = df_total[['SEP Dual Night', 'SEP Pilot Night', 'MEP Dual Night', 'MEP Pilot Night']].sum().sum()

    t_solo_glob = df_total[['SEP Pilot', 'SEP Pilot Night', 'MEP Pilot', 'MEP Pilot Night']].sum().sum()
    t_solo_mep = df_total[['MEP Pilot', 'MEP Pilot Night']].sum().sum()
    t_solo_ir = df_total['IFR Pilote'].sum()
    t_solo_night = df_total[['SEP Pilot Night', 'MEP Pilot Night']].sum().sum()

    n_app_6m = df_total[df_total['DateDT'] >= (auj - timedelta(days=180))]['Approach'].sum()
    n_land_3m = df_total[df_total['DateDT'] >= (auj - timedelta(days=90))][['Landing Day', 'Landing Night']].sum().sum()
    h_tot_12m = df_total[df_total['DateDT'] >= (auj - timedelta(days=365))][['SEP Dual', 'SEP Pilot', 'SEP Dual Night', 'SEP Pilot Night', 'MEP Dual', 'MEP Pilot', 'MEP Dual Night', 'MEP Pilot Night']].sum().sum()
    h_ir_12m = df_total[df_total['DateDT'] >= (auj - timedelta(days=365))][['IFR Dual', 'IFR Pilote']].sum().sum()

    # --- CONSTRUCTION DU PDF ---
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "BILAN D'EXPERIENCE ET CARNET DE VOL", align="C", border='B', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # Synthèse Globale
    pdf.ln(5); pdf.set_fill_color(230, 230, 230); pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 8, " SYNTHESE GLOBALE", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "", 9)
    pdf.cell(65, 7, f" HDV Totales (SEP+MEP): {t_hdv:.2f} h", border='L')
    pdf.cell(65, 7, f" MEP Totale (Dual+Solo): {t_mep_glob:.2f} h", border='0')
    pdf.cell(65, 7, f" IR Global: {t_ir_glob:.2f} h", border='0')
    pdf.cell(0, 7, f" Nuit Totale: {t_night_glob:.2f} h", border='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # Solo Regroupé
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 8, " EXPERIENCE SOLO (PIC)", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(65, 7, f" Solo Global: {t_solo_glob:.2f} h", border='LB')
    pdf.cell(65, 7, f" Solo MEP: {t_solo_mep:.2f} h", border='B')
    pdf.cell(65, 7, f" Solo IR: {t_solo_ir:.2f} h", border='B')
    pdf.cell(0, 7, f" Solo Nuit: {t_solo_night:.2f} h", border='RB', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Recency
    pdf.ln(3); pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 8, " MAINTIEN DE COMPETENCES (RECENCY)", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "", 9)
    pdf.cell(65, 7, f" Approches (6 mois): {int(n_app_6m)}", border='LB')
    pdf.cell(65, 7, f" Atterrissages (3 mois): {int(n_land_3m)}", border='B')
    pdf.cell(65, 7, f" HDV Totales (12 mois): {h_tot_12m:.2f} h", border='B')
    pdf.cell(0, 7, f" HDV IR (12 mois): {h_ir_12m:.2f} h", border='RB', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.ln(8)
    # Tableau
    pdf.set_font("helvetica", "B", 8); pdf.set_fill_color(240, 240, 240)
    headers = [("Date", 22), ("Type", 18), ("Immat", 18), ("De/A", 35), ("SEP", 15), ("MEP", 15), ("IFR", 15), ("Remarques", 130)]
    for h, w in headers: pdf.cell(w, 8, h, border=1, align="C", fill=True)
    pdf.ln()
    
    pdf.set_font("helvetica", "", 7)
    for idx, r in df_filtre.iterrows():
        rem = str(r['Remarks']) if r['Remarks'] and str(r['Remarks']).strip() not in ["0", "0.0", "None", "nan"] else ""
        v_sep = df_filtre.loc[[idx], ['SEP Dual', 'SEP Pilot', 'SEP Dual Night', 'SEP Pilot Night']].sum().sum()
        v_mep = df_filtre.loc[[idx], ['MEP Dual', 'MEP Pilot', 'MEP Dual Night', 'MEP Pilot Night']].sum().sum()
        v_ifr = (r['IFR Dual'] or 0) + (r['IFR Pilote'] or 0)
        pdf.cell(22, 6, str(r['Date'])[:10], border=1, align="C")
        pdf.cell(18, 6, str(r['Type']), border=1, align="C")
        pdf.cell(18, 6, str(r['Registration']), border=1, align="C")
        pdf.cell(35, 6, f"{r['From']} - {r['To']}", border=1, align="C")
        pdf.cell(15, 6, f"{v_sep:.2f}", border=1, align="C")
        pdf.cell(15, 6, f"{v_mep:.2f}", border=1, align="C")
        pdf.cell(15, 6, f"{v_ifr:.2f}", border=1, align="C")
        pdf.cell(130, 6, rem[:110], border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # LA CORRECTION EST ICI : conversion forcée en bytes
    return bytes(pdf.output())

# --- INTERFACE ---
st.set_page_config(page_title="Logbook Christophe", layout="wide")
initialiser_db()
st.title("✈️ Pilot Logbook Manager")

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
            conn = sqlite3.connect(DATABASE_NAME)
            conn.execute("INSERT INTO vols (Date, Type, Registration, 'From', 'To', 'SEP Pilot', 'MEP Pilot', 'IFR Pilote', Approach, 'Landing Day', Remarks) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (d.strftime('%Y-%m-%d'), typ, reg, f_fr, f_to, s_p, m_p, i_p, app, lnd, rem))
            conn.commit(); conn.close(); st.success("Enregistré !")

with t_hist:
    conn = sqlite3.connect(DATABASE_NAME)
    df_h = pd.read_sql("SELECT Date, Type, Registration, 'From', 'To', 'SEP Pilot', 'MEP Pilot', Remarks FROM vols ORDER BY Date DESC", conn)
    conn.close()
    if not df_h.empty:
        df_h['Date'] = df_h['Date'].str.slice(0, 10)
        df_h['Remarks'] = df_h['Remarks'].apply(lambda x: "" if str(x).strip() in ["0", "0.0", "None", "nan"] or not x else x)
        st.dataframe(df_h, use_container_width=True)

with t_print:
    st.header("Rapport PDF")
    date_c = st.date_input("Détail à partir de :", datetime(2024, 1, 1))
    if st.button("📥 Générer le PDF"):
        pdf_bytes = generer_pdf_logbook_final(date_c.strftime('%Y-%m-%d'))
        if pdf_bytes:
            # Streamlit accepte maintenant les données car elles sont typées 'bytes'
            st.download_button(label="Télécharger le PDF", data=pdf_bytes, file_name="Logbook_Christophe.pdf", mime="application/pdf")

with t_map:
    c1, c2 = st.columns(2)
    with c1: d1 = st.date_input("Du", datetime(2024, 1, 1), key="d1")
    with c2: d2 = st.date_input("Au", datetime.now(), key="d2")
    if "m_on" not in st.session_state: st.session_state.m_on = False
    if st.button("Afficher la carte"): st.session_state.m_on = True
    if st.session_state.m_on:
        conn = sqlite3.connect(DATABASE_NAME); df_m = pd.read_sql("SELECT * FROM vols WHERE Date BETWEEN ? AND ?", conn, params=(d1.strftime('%Y-%m-%d'), d2.strftime('%Y-%m-%d'))); conn.close()
        if not df_m.empty:
            st.metric("Total Période (Pilot)", f"{df_m[['SEP Pilot','MEP Pilot']].sum().sum():.2f} h")
            airports = charger_base_aeroports(); m = folium.Map(location=[45, 5], zoom_start=5)
            for _, row in df_m.iterrows():
                dep, arr = str(row['From']).upper().strip(), str(row['To']).upper().strip()
                if dep in airports and arr in airports:
                    folium.PolyLine([[airports[dep]['lat'], airports[dep]['lon']], [airports[arr]['lat'], airports[arr]['lon']]], color="blue", weight=2).add_to(m)
            st_folium(m, width=1100, height=500, key="map_final")