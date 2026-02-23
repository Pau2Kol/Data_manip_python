import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Meteo WW2", layout="wide", initial_sidebar_state="expanded")

@st.cache_data
def load_data():
    df_weather = pd.read_csv('sumweather.csv', low_memory=False)
    df_stations = pd.read_csv('weatherstation.csv')
    df_final = pd.merge(df_weather, df_stations, left_on='STA', right_on='WBAN')
    df_final['Precip'] = pd.to_numeric(df_final['Precip'].replace('T', '0'), errors='coerce').fillna(0)
    df_final['Date'] = pd.to_datetime(df_final['Date'], errors='coerce')
    
    if 'Latitude' in df_final.columns and 'Longitude' in df_final.columns:
        df_final = df_final.rename(columns={'Latitude': 'lat', 'Longitude': 'lon'})
    
    df_final['lat'] = pd.to_numeric(df_final['lat'], errors='coerce')
    df_final['lon'] = pd.to_numeric(df_final['lon'], errors='coerce')
    return df_final

df = load_data()
df = df.assign(Temp_Amplitude=df.apply(lambda x: x['MaxTemp'] - x['MinTemp'], axis=1))

pays_disponibles = sorted(df['STATE/COUNTRY ID'].dropna().unique())

with st.sidebar:
    st.title("Filtres d'analyse")
    pays_selectionnes = st.multiselect("Selectionner un ou plusieurs pays", pays_disponibles)
    
    min_date = df['Date'].min().date()
    max_date = df['Date'].max().date()
    date_range = st.slider("Periode temporelle", min_date, max_date, (min_date, max_date))

start_date = pd.to_datetime(date_range[0])
end_date = pd.to_datetime(date_range[1])
mask_date = (df['Date'] >= start_date) & (df['Date'] <= end_date)
df_temp = df.loc[mask_date]

pays_actifs = list(pays_selectionnes)

if "map_key" in st.session_state:
    map_state = st.session_state["map_key"]
    if map_state and "selection" in map_state and map_state["selection"]["points"]:
        pays_clique = map_state["selection"]["points"][0]["customdata"][0]
        if pays_clique not in pays_actifs:
            pays_actifs.append(pays_clique)

if pays_actifs:
    df_filtre = df_temp[df_temp['STATE/COUNTRY ID'].isin(pays_actifs)]
    titre_dashboard = f"Donnees pour : {', '.join(pays_actifs)}"
else:
    df_filtre = df_temp
    titre_dashboard = "Analyse globale (Moyenne Mondiale)"

st.title("Tableau de Bord Meteorologique WW2")
st.markdown(f"**{titre_dashboard}** | Periode : {date_range[0]} au {date_range[1]}")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Temperature Moyenne", f"{df_filtre['MeanTemp'].mean():.1f} C")
with col2:
    st.metric("Precipitations Totales", f"{df_filtre['Precip'].sum():.1f} mm")
with col3:
    st.metric("Ecart Type (Temp)", f"{df_filtre['MeanTemp'].std():.2f}")
with col4:
    st.metric("Releves totaux", f"{len(df_filtre)}")

st.markdown("---")

col_map, col_line = st.columns((1, 1.5))

with col_map:
    df_map = df_temp[['lat', 'lon', 'NAME', 'STATE/COUNTRY ID']].dropna().drop_duplicates()
    if not df_map.empty:
        fig_map = px.scatter_map(
            df_map, 
            lat='lat', 
            lon='lon', 
            hover_name='NAME',
            custom_data=['STATE/COUNTRY ID'],
            color='STATE/COUNTRY ID',
            zoom=1,
            map_style="open-street-map",
            title="Localisation des stations"
        )
        fig_map.update_layout(margin=dict(l=0, r=0, t=40, b=0), showlegend=False)
        st.plotly_chart(fig_map, width="stretch", on_select="rerun", key="map_key")
    else:
        st.warning("Aucune coordonnee disponible.")

with col_line:
    if not pays_actifs:
        df_evolution = df_filtre.groupby('Date')['MeanTemp'].mean().reset_index()
        df_evolution['STATE/COUNTRY ID'] = 'Moyenne Mondiale'
    else:
        df_evolution = df_filtre.groupby(['Date', 'STATE/COUNTRY ID'])['MeanTemp'].mean().reset_index()

    fig_line = px.line(df_evolution, x='Date', y='MeanTemp', color='STATE/COUNTRY ID', title="Evolution thermique et historique")
    
    evenements = {
        '1939-09-01': 'Invasion Pologne',
        '1941-06-22': 'Op. Barbarossa',
        '1941-12-07': 'Pearl Harbor',
        '1944-06-06': 'Debarquement',
        '1945-05-08': 'Cap. Allemagne',
        '1945-09-02': 'Cap. Japon'
    }

    min_d = df_evolution['Date'].min()
    max_d = df_evolution['Date'].max()

    for date_str, event in evenements.items():
        date_evt = pd.to_datetime(date_str)
        if min_d <= date_evt <= max_d:
            timestamp_ms = date_evt.timestamp() * 1000
            fig_line.add_vline(x=timestamp_ms, line_dash="dash", line_color="red", annotation_text=event)
            
    fig_line.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_line, width="stretch")

st.markdown("---")

col_hist, col_stats = st.columns((1.5, 1))

with col_hist:
    fig_hist = px.histogram(
        df_filtre, 
        x='MeanTemp', 
        color='STATE/COUNTRY ID', 
        opacity=0.7, 
        title="Distribution des temperatures moyennes",
        nbins=40
    )
    fig_hist.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig_hist, width="stretch")

with col_stats:
    st.markdown("**Stations les plus actives**")
    st.dataframe(df_filtre['NAME'].value_counts().head(7), use_container_width=True)

st.markdown("---")

st.markdown("**Vagues de temperatures extremes (Plus de 4 jours consecutifs < 0 C ou > 35 C)**")
df_extremes = df_filtre[(df_filtre['MinTemp'] < 0) | (df_filtre['MaxTemp'] > 35)].copy()

if not df_extremes.empty:
    df_extremes = df_extremes.sort_values(by=['STA', 'Date'])
    df_extremes['Diff_Jours'] = df_extremes.groupby('STA')['Date'].diff().dt.days
    df_extremes['Nouveau_Groupe'] = (df_extremes['Diff_Jours'] > 1).cumsum()
    
    vagues_extremes = df_extremes.groupby(['STA', 'Nouveau_Groupe']).agg(
        Date_Debut=('Date', 'min'),
        Date_Fin=('Date', 'max'),
        Duree_Jours=('Date', 'count'),
        MinTemp=('MinTemp', 'min'),
        MaxTemp=('MaxTemp', 'max'),
        MeanTemp=('MeanTemp', 'mean'),
        Ville=('NAME', 'first'),
        Pays=('STATE/COUNTRY ID', 'first')
    ).reset_index()
    
    vagues_filtrees = vagues_extremes[vagues_extremes['Duree_Jours'] > 4].copy()
    
    if not vagues_filtrees.empty:
        vagues_filtrees['Date_Debut'] = vagues_filtrees['Date_Debut'].dt.strftime('%Y-%m-%d')
        vagues_filtrees['Date_Fin'] = vagues_filtrees['Date_Fin'].dt.strftime('%Y-%m-%d')
        colonnes_finales = ['Date_Debut', 'Date_Fin', 'Duree_Jours', 'MaxTemp', 'MinTemp', 'MeanTemp', 'Ville', 'Pays']
        vagues_filtrees = vagues_filtrees[colonnes_finales].sort_values(by='Date_Debut')
        st.dataframe(vagues_filtrees, use_container_width=True)
    else:
        st.info("Aucune vague prolongee enregistree sur cette selection.")
else:
    st.info("Aucun jour extreme enregistre.")