from pathlib import Path
import streamlit as st
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium

import graficos
from pipeline_dados import DATA_EXTRACAO, preparar_bases

BASE = Path(__file__).parent
CENTRO_MAPA = [-30.0346, -51.2177]
ZOOM_MAPA = 12

st.set_page_config(
    page_title="Acidentes de trânsito em Porto Alegre",
    page_icon="🚦",
    layout="wide"
)

ESTILO = """
    <style>
    .st-key-metricas_visao [data-testid="stMetricLabel"],
    .st-key-metricas_visao [data-testid="stMetricLabel"] *,
    .st-key-metricas_dados [data-testid="stMetricLabel"],
    .st-key-metricas_dados [data-testid="stMetricLabel"] * {
        font-size: 1.1rem !important;
        font-weight: 700 !important;
    }

    /* Grade das categorias: 1 ou 2 colunas conforme a largura disponível.
       Cada coluna tem no mínimo {LARGURA} px; gráficos largos ocupam a linha. */
    .st-key-grade_categorias {
        display: grid !important;
        grid-template-columns: repeat(
            auto-fit,
            minmax(min(100%, max({LARGURA}px, calc(50% - 0.5rem))), 1fr)
        );
        gap: 1rem;
    }
    .st-key-grade_categorias > * {
        min-width: 0;
    }
    .st-key-grade_categorias > *:has([class*="st-key-categoria_larga"]) {
        grid-column: 1 / -1;
    }
    </style>
    """.replace("{LARGURA}", str(graficos.LARGURA_COLUNA_GRADE))

st.markdown(ESTILO, unsafe_allow_html=True)


@st.cache_data
def carregar_dados():
    _, tratados = preparar_bases(BASE)
    return tratados


st.title("🚦 Acidentes de trânsito em Porto Alegre")
st.caption("Análise exploratória dos dados abertos da EPTC")

try:
    bases = carregar_dados()
    df = bases["acidentes"]
except Exception as erro:
    st.error(f"Não foi possível carregar os dados: {erro}")
    st.stop()

st.sidebar.header("Filtros")

anos = sorted(
    df["ano"]
    .dropna()
    .astype(int)
    .unique()
)

if not anos:
    st.warning("Não há anos válidos disponíveis para exibição.")
    st.stop()

anos_selecionados = st.sidebar.multiselect(
    "Ano",
    options=anos,
    default=anos
)

apenas_graves = st.sidebar.checkbox(
    "Mostrar somente acidentes graves"
)

filtrado = df[
    df["ano"].isin(anos_selecionados)
].copy()

if apenas_graves:
    filtrado = filtrado[
        filtrado["acidente_grave"]
    ]

VARIAVEIS_NUMERICAS = {
    "Acidentes": {
        "feridos": "Feridos",
        "feridos_gr": "Feridos graves",
        "mortes": "Mortes",
        "fatais": "Vítimas fatais",
        "ups": "UPS",
    },
    "Vítimas": {"idade": "Idade"},
    "Sinalização gráfica": {
        "num_inicial": "Número inicial",
        "num_final": "Número final",
    },
}


def selecionar_base(conjuntos, chave):
    titulo, opcoes = st.columns([1, 6], vertical_alignment="center")
    titulo.markdown("**Base de dados**")
    return opcoes.radio(
        "Base de dados",
        list(conjuntos),
        horizontal=True,
        key=chave,
        label_visibility="collapsed",
    )


def cor_do_texto():
    tema = st.context.theme.type
    return {"dark": "#fafafa", "light": "#262730"}.get(
        tema,
        graficos.COR_VALOR,
    )


def mostrar_grafico(grafico):
    st.altair_chart(grafico, width="stretch")


def renderizar_analise(conjuntos):
    acidentes = conjuntos["Acidentes"]

    if acidentes.empty:
        st.info("Nenhum acidente para os filtros selecionados.")
        return

    st.caption(
        "O filtro de ano vale para acidentes e vítimas, o filtro de acidentes "
        "graves vale só para acidentes e a sinalização gráfica não é filtrada. "
        f"Dados até {DATA_EXTRACAO.strftime('%d/%m/%Y')}, então o último ano é parcial."
    )

    aba_temporal, aba_categorias, aba_distribuicao = st.tabs(
        ["Temporal", "Categorias", "Distribuição"]
    )

    with aba_temporal:
        esquerda, direita = st.columns(2)

        with esquerda:
            mostrar_grafico(
                graficos.grafico_linha_por_ano(
                    acidentes.groupby("ano").size(),
                    "Quantidade de acidentes por ano",
                    "Quantidade de acidentes",
                    "#d95f02",
                )
            )

        with direita:
            mostrar_grafico(
                graficos.grafico_linha_por_ano(
                    acidentes.groupby("ano")["fatais"].sum(),
                    "Quantidade de vítimas fatais por ano",
                    "Quantidade de vítimas fatais",
                    "#e7298a",
                )
            )

        mostrar_grafico(graficos.grafico_heatmap_dia_hora(acidentes))

        esquerda, direita = st.columns(2)

        with esquerda:
            mostrar_grafico(graficos.grafico_barras_mes(acidentes))

        with direita:
            mostrar_grafico(
                graficos.grafico_dias_uteis_fim_de_semana(acidentes)
            )

    with aba_categorias:
        nome = selecionar_base(conjuntos, "base_categorias")
        dados = conjuntos[nome]
        colunas = graficos.colunas_categoricas(
            dados,
            ignorar=("dia_sem_normalizado",),
        )

        with st.container(key="grade_categorias"):
            for indice, coluna in enumerate(colunas):
                larga = graficos.precisa_largura_total(dados, coluna)
                sufixo = "larga" if larga else "normal"
                with st.container(key=f"categoria_{sufixo}_{indice}"):
                    mostrar_grafico(
                        graficos.grafico_frequencia(
                            dados,
                            coluna,
                            cor_texto=cor_do_texto(),
                        )
                    )

    with aba_distribuicao:
        nome = selecionar_base(conjuntos, "base_distribuicao")
        variaveis = VARIAVEIS_NUMERICAS[nome]
        rotulo = st.selectbox(
            "Variável",
            list(variaveis.values()),
            key=f"coluna_distribuicao_{nome}",
        )
        coluna = next(c for c, r in variaveis.items() if r == rotulo)
        serie = conjuntos[nome][coluna].dropna()

        if coluna == "idade":
            fora_do_intervalo = int((~serie.between(0, 120)).sum())
            serie = serie[serie.between(0, 120)]
            if fora_do_intervalo:
                st.caption(
                    f"{fora_do_intervalo} valores de idade fora de 0 a 120 "
                    "foram ignorados nos gráficos."
                )

        if serie.empty:
            st.info("Não há valores válidos para esta variável.")
        else:
            estatisticas = graficos.estatisticas_descritivas(serie)
            colunas_metricas = st.columns(len(estatisticas))
            for coluna_metrica, (medida, valor) in zip(
                colunas_metricas,
                estatisticas.items(),
            ):
                coluna_metrica.metric(
                    medida,
                    graficos.formatar_inteiro(valor)
                    if medida == "Registros válidos"
                    else f"{valor:.2f}".replace(".", ","),
                )
            mostrar_grafico(
                graficos.grafico_distribuicao(serie, rotulo)
            )


aba_visao, aba_mapa, aba_analise, aba_dados = st.tabs(
    ["Visão geral", "Mapa de calor", "Análise de dados", "Dados"],
    on_change="rerun",
)

with aba_visao:
    with st.container(key="metricas_visao"):
        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Acidentes",
            f"{len(filtrado):,}".replace(",", "."),
            border=True
        )

        col2.metric(
            "Acidentes graves",
            f"{filtrado['acidente_grave'].sum():,}".replace(",", "."),
            border=True
        )

        col3.metric(
            "Feridos",
            f"{filtrado['feridos'].sum():,.0f}".replace(",", "."),
            border=True
        )

        col4.metric(
            "Mortes",
            f"{filtrado['mortes'].sum():,.0f}".replace(",", "."),
            border=True
        )

    st.divider()

    esquerda, direita = st.columns(2)

    with esquerda:
        st.subheader("Acidentes por ano")

        por_ano = filtrado.groupby("ano").size()

        if por_ano.empty:
            st.info("Nenhum acidente para os filtros selecionados.")
        else:
            mostrar_grafico(
                graficos.grafico_linha_por_ano(
                    por_ano,
                    None,
                    "Quantidade de acidentes",
                    "#d95f02",
                )
            )

    with direita:
        st.subheader("Vítimas fatais por ano")

        fatais_por_ano = filtrado.groupby("ano")["fatais"].sum()

        if fatais_por_ano.empty:
            st.info("Nenhum acidente para os filtros selecionados.")
        else:
            mostrar_grafico(
                graficos.grafico_linha_por_ano(
                    fatais_por_ano,
                    None,
                    "Quantidade de vítimas fatais",
                    "#e7298a",
                )
            )

    st.subheader("Acidentes por tipo")

    if filtrado.empty:
        st.info("Nenhum acidente para os filtros selecionados.")
    elif "tipo_acid" in filtrado.columns:
        mostrar_grafico(
            graficos.grafico_frequencia(
                filtrado,
                "tipo_acid",
                cor_texto=cor_do_texto(),
                mostrar_titulo=False,
            )
        )

with aba_analise:
    vitimas = bases["vitimas"]
    renderizar_analise({
        "Acidentes": filtrado,
        "Vítimas": vitimas[
            vitimas["data"].dt.year.isin(anos_selecionados)
        ],
        "Sinalização gráfica": bases["sinalizacao"],
    })

with aba_mapa:
    # O mapa só é criado com a aba aberta: dentro de uma aba escondida ele
    # nasce com largura zero e o heat layer falha ao desenhar.
    if aba_mapa.open:
        titulo_mapa, botao_mapa = st.columns([6, 1], vertical_alignment="center")
        titulo_mapa.subheader("Mapa de calor dos acidentes")

        if "cliques_centralizar" not in st.session_state:
            st.session_state["cliques_centralizar"] = 0

        if botao_mapa.button("Centralizar mapa", width="stretch"):
            st.session_state["cliques_centralizar"] += 1

        # O componente só reposiciona o mapa quando center/zoom diferem do último
        # valor enviado. Por isso cada clique alterna uma diferença imperceptível
        # (cerca de 10 cm e 0,001 de zoom, que o Leaflet arredonda): o mapa volta
        # à posição inicial sem ser recriado.
        alternar = st.session_state["cliques_centralizar"] % 2
        centro_enviado = [CENTRO_MAPA[0] + alternar * 1e-6, CENTRO_MAPA[1]]
        zoom_enviado = ZOOM_MAPA + alternar * 0.001

        mapa_dados = filtrado.dropna(
            subset=["latitude", "longitude"]
        ).copy()

        mapa_dados = mapa_dados[
            mapa_dados["latitude"].between(-30.30, -29.90)
            & mapa_dados["longitude"].between(-51.30, -51.00)
        ]

        mapa = folium.Map(
            location=CENTRO_MAPA,
            zoom_start=ZOOM_MAPA,
            tiles="OpenStreetMap"
        )

        if not mapa_dados.empty:
            HeatMap(
                mapa_dados[["latitude", "longitude"]].values.tolist(),
                radius=12,
                blur=18,
                min_opacity=0.4
            ).add_to(mapa)

        st_folium(
            mapa,
            width=None,
            height=600,
            key="mapa_calor",
            center=centro_enviado,
            zoom=zoom_enviado,
            returned_objects=[],
        )

with aba_dados:
    # A tabela só é enviada ao navegador com a aba aberta.
    if aba_dados.open:
        st.subheader("Dados filtrados")

        with st.container(key="metricas_dados"):
            col1, col2, col3 = st.columns(3)

            col1.metric(
                "Linhas exibidas",
                f"{len(filtrado):,}".replace(",", "."),
                border=True
            )

            col2.metric(
                "Linhas na base",
                f"{len(df):,}".replace(",", "."),
                border=True
            )

            col3.metric(
                "Percentual da base",
                f"{len(filtrado) / len(df) * 100:.1f}%".replace(".", ","),
                border=True
            )

        st.dataframe(filtrado, width="stretch")
