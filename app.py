# filepath: /home/rafa/Área de Trabalho/WORK/IA001.1/app.py
from pathlib import Path

import pandas as pd
import streamlit as st
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium

BASE = Path(__file__).parent
DADOS = BASE / "dados"

@st.cache_data
def carregar_dados():
    acidentes = pd.read_csv(
        DADOS / "cat_acidentes.csv",
        sep=";",
        encoding="utf-8"
    )

    acidentes.columns = acidentes.columns.str.strip().str.lower()

    acidentes["data"] = pd.to_datetime(
        acidentes["data"],
        errors="coerce"
    )

    for coluna in [
        "latitude", "longitude", "feridos",
        "feridos_gr", "mortes", "fatais"
    ]:
        if coluna in acidentes.columns:
            acidentes[coluna] = pd.to_numeric(
                acidentes[coluna]
                .astype(str)
                .str.replace(",", ".", regex=False),
                errors="coerce"
            )

    acidentes["ano"] = acidentes["data"].dt.year
    acidentes["acidente_grave"] = (
        acidentes.get("feridos_gr", 0).fillna(0).gt(0)
        | acidentes.get("mortes", 0).fillna(0).gt(0)
    )

    return acidentes


st.set_page_config(
    page_title="Acidentes de trânsito em Porto Alegre",
    page_icon="🚦",
    layout="wide"
)

st.title("🚦 Acidentes de trânsito em Porto Alegre")
st.caption("Análise exploratória dos dados abertos da EPTC")

try:
    df = carregar_dados()
except Exception as erro:
    st.error(f"Não foi possível carregar os dados: {erro}")
    st.stop()

st.sidebar.header("Filtros")

anos = sorted(df["ano"].dropna().astype(int).unique())
anos_selecionados = st.sidebar.multiselect(
    "Ano",
    anos,
    default=anos
)

apenas_graves = st.sidebar.checkbox(
    "Mostrar somente acidentes graves"
)

filtrado = df[df["ano"].isin(anos_selecionados)].copy()

if apenas_graves:
    filtrado = filtrado[filtrado["acidente_grave"]]

col1, col2, col3, col4 = st.columns(4)

col1.metric("Acidentes", f"{len(filtrado):,}".replace(",", "."))
col2.metric(
    "Acidentes graves",
    f"{filtrado['acidente_grave'].sum():,}".replace(",", ".")
)
col3.metric(
    "Feridos",
    f"{filtrado['feridos'].sum():,.0f}".replace(",", ".")
)
col4.metric(
    "Mortes",
    f"{filtrado['mortes'].sum():,.0f}".replace(",", ".")
)

st.divider()

esquerda, direita = st.columns(2)

with esquerda:
    st.subheader("Acidentes por ano")

    por_ano = (
        filtrado.groupby("ano")
        .size()
        .rename("Quantidade")
    )

    st.bar_chart(por_ano)

with direita:
    st.subheader("Acidentes por tipo")

    if "tipo_acid" in filtrado.columns:
        por_tipo = (
            filtrado["tipo_acid"]
            .fillna("Não informado")
            .value_counts()
            .head(10)
        )

        st.bar_chart(por_tipo)

st.subheader("Mapa de calor dos acidentes")

mapa_dados = filtrado.dropna(
    subset=["latitude", "longitude"]
).copy()

mapa_dados = mapa_dados[
    mapa_dados["latitude"].between(-30.30, -29.90)
    & mapa_dados["longitude"].between(-51.30, -51.00)
]

mapa = folium.Map(
    location=[-30.0346, -51.2177],
    zoom_start=12,
    tiles="OpenStreetMap"
)

if not mapa_dados.empty:
    HeatMap(
        mapa_dados[["latitude", "longitude"]].values.tolist(),
        radius=12,
        blur=18,
        min_opacity=0.4
    ).add_to(mapa)

st_folium(mapa, width=None, height=600)

st.subheader("Dados filtrados")
st.dataframe(filtrado, use_container_width=True)
