import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pdfplumber
import re

# --- DATA CATCHER LOGIK ---
def parse_note(x):
    if pd.isna(x):
        return 0.0
    x = str(x).strip().replace(",", ".")
    x = re.sub(r"[^0-9.\-]", "", x)
    try:
        return float(x) if x else 0.0
    except ValueError:
        return 0.0

def sort_key(sem_string):
    jahre = re.findall(r'\d{4}', sem_string)
    jahr = int(jahre[0]) if jahre else 0
    prio = 0.5 if "WiSe" in sem_string else 0.0
    return jahr + prio

def get_data_from_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        erste_seite = pdf.pages[0].extract_table()
        if not erste_seite:
            return pd.DataFrame(), pd.DataFrame(), 0.0
        header = erste_seite[0]
        daten = erste_seite[2:]

        for page in pdf.pages[1:]:
            table = page.extract_table()
            if table:
                daten.extend(table[1:]) 

    df = pd.DataFrame(daten, columns=header)
    df['Endnote'] = df['Endnote'].apply(parse_note)
    df['ECTS'] = df['ECTS'].apply(parse_note)

    total_ects = sum(df['ECTS'])
    nc = (sum(df['Endnote'] * df['ECTS']) / total_ects) if total_ects > 0 else 0.0

    df['Weighted_Note'] = df['Endnote'] * df['ECTS']
    df_sem = df.groupby('Sem.', as_index=False).agg({'Weighted_Note': 'sum', 'ECTS': 'sum'})
    
    df_sem['NC'] = (df_sem['Weighted_Note'] / df_sem['ECTS']).round(2)
    df_sem = df_sem[['Sem.', 'NC']]
    df_sem['Sem.'] = df_sem['Sem.'].str.replace('\n', ' ', regex=False)
    df_sem.rename(columns={'Sem.': 'Semester'}, inplace=True)
    df_sem = df_sem.sort_values('Semester', key=lambda col: col.map(sort_key)).reset_index(drop=True)

    if len(df_sem) > 1:
        df_sem = df_sem.iloc[1:]

    return df, df_sem, nc

# --- VISUALIZER LOGIK ---
def visualize_dashboard(df, df_sem, nc, total_ects_required=210):
    total_ects_done = df["ECTS"].sum()
    percent_done = (total_ects_done / total_ects_required) * 100
    remaining_ects = max(total_ects_required - total_ects_done, 0)

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle(f"Studienübersicht | Gesamtnote (NC): {nc:.2f}", fontsize=16)
    ax1, ax2, ax3, ax4 = axes.flatten()

    # 1) NC pro Semester
    ax1.plot(df_sem["Semester"], df_sem["NC"], marker="o", linewidth=2)
    ax1.set_title("NC pro Semester")
    ax1.set_xlabel("Semester")
    ax1.set_ylabel("NC")
    ax1.tick_params(axis="x", rotation=45)
    ax1.grid(True, alpha=0.3)

    # 2) ECTS pro Semester
    ects_per_sem = df.groupby("Sem.")["ECTS"].sum().reset_index()
    ects_per_sem["Sem."] = ects_per_sem["Sem."].str.replace("\n", " ", regex=False)
    ax2.bar(ects_per_sem["Sem."], ects_per_sem["ECTS"])
    ax2.set_title("ECTS pro Semester")
    ax2.set_xlabel("Semester")
    ax2.set_ylabel("ECTS")
    ax2.tick_params(axis="x", rotation=45)
    ax2.grid(True, axis="y", alpha=0.3)

    # 3) Notenverteilung
    bins = np.arange(1.0, 4.5, 0.3)
    ax3.hist(df["Endnote"], bins=bins, edgecolor="black")
    ax3.set_title("Notenverteilung")
    ax3.set_xlabel("Note")
    ax3.set_ylabel("Anzahl")
    ax3.grid(True, axis="y", alpha=0.3)

    # 4) Studienfortschritt als Donut
    sizes = [total_ects_done, remaining_ects]
    labels = [f"Geschafft: {total_ects_done:.0f} ECTS", f"Offen: {remaining_ects:.0f} ECTS"]
    ax4.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90, wedgeprops=dict(width=0.35))
    ax4.set_title("Studienfortschritt")
    ax4.text(0, 0, f"{percent_done:.1f}%", ha="center", va="center", fontsize=16, fontweight="bold")

    plt.tight_layout()
    return fig

# --- STREAMLIT OBERFLÄCHE (Navigation via Tabs) ---
st.set_page_config(page_title="Studienmanager", page_icon="🎓", layout="wide")

# Navigation simulieren mit Tabs statt echten Unterseiten (perfekt für GitHub Pages)
tab1, tab2 = st.tabs(["🏠 Home", "📊 Dashboard & Analyse"])

with tab1:
    st.title("Willkommen bei deinem persönlichen Studienmanager! 🎓")
    st.write("---")
    st.markdown("""
    ### Was kann diese Website?
    Mit dieser App kannst du dein offizielles Notenblatt analysieren lassen und visuelle Einblicke in deinen Studienfortschritt gewinnen.
    
    ### Datenschutz-Hinweis
    Da diese App komplett in deinem Browser läuft, werden deine Noten und PDFs **niemals auf einen Server hochgeladen**. Alles bleibt privat auf deinem PC!
    """)

with tab2:
    st.title("📊 Dein Noten- & ECTS-Dashboard")
    st.write("Lade dein PDF-Notenblatt hoch, um die Auswertung zu starten.")
    
    uploaded_file = st.file_uploader("Wähle deine Notenblatt-PDF-Datei aus", type=["pdf"])
    
    if uploaded_file is not None:
        try:
            df, df_sem, nc = get_data_from_pdf(uploaded_file)
            
            col1, col2, col3 = st.columns(3)
            col1.metric(label="Gesamtnote (NC)", value=f"{nc:.2f}")
            col2.metric(label="Erreichte ECTS", value=f"{df['ECTS'].sum():.0f} / 210")
            col3.metric(label="Absolvierte Module", value=len(df))
            
            st.write("---")
            st.pyplot(visualize_dashboard(df, df_sem, nc))
            st.write("---")
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Fehler bei der PDF-Verarbeitung: {e}")
