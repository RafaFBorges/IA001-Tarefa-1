from pathlib import Path
import streamlit as st
from streamlit_folium import st_folium

import graficos
import mapas
import relacao_espacial as relacao
from pipeline_dados import DATA_EXTRACAO, ler_dados_brutos, preparar_bases

BASE = Path(__file__).parent

st.set_page_config(
    page_title="Acidentes de trânsito em Porto Alegre",
    page_icon="🚦",
    layout="wide"
)

ESTILO = """
    <style>
    .st-key-metricas_visao [data-testid="stMetricLabel"],
    .st-key-metricas_visao [data-testid="stMetricLabel"] *,
    [class*="st-key-metricas_dados"] [data-testid="stMetricLabel"],
    [class*="st-key-metricas_dados"] [data-testid="stMetricLabel"] * {
        font-size: 1.1rem !important;
        font-weight: 700 !important;
    }

    /* Título seguido de radio: 12 px entre o título e as opções. */
    [class*="st-key-linha_radio"] {
        gap: 12px !important;
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


@st.cache_data
def calcular_relacao(_acidentes, _sinalizacao, raio):
    # Os dados são fixos na sessão: só o raio entra na chave do cache.
    return relacao.calcular_relacao(_acidentes, _sinalizacao, raio)


@st.cache_resource
def montar_mapa_graves(_graves, _grupos, raio, anos):
    return mapas.mapa_graves_sinalizacao(_graves, _grupos, raio)


@st.cache_resource
def carregar_brutos():
    # CSVs inteiros, sem tratamento. Só são lidos ao abrir a aba Dados e
    # ficam compartilhados em memória (somente leitura).
    return ler_dados_brutos(BASE)


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

raio_sinalizacao = st.sidebar.slider(
    "Raio da sinalização (m)",
    min_value=25,
    max_value=300,
    value=100,
    step=25,
    help=(
        "Distância em volta de cada acidente usada para contar os sinais "
        "próximos. Vale só para a aba Sinalização × Acidentes."
    ),
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


def linha_com_radio(titulo, opcoes, chave, subtitulo=False):
    """Título e radio horizontal na mesma linha, com 12 px entre eles."""
    with st.container(
        horizontal=True,
        vertical_alignment="center",
        gap=None,
        key=f"linha_radio_{chave}",
    ):
        if subtitulo:
            st.subheader(titulo, width="content")
        else:
            st.markdown(f"**{titulo}**", width="content")
        return st.radio(
            titulo,
            opcoes,
            horizontal=True,
            key=chave,
            label_visibility="collapsed",
        )


def selecionar_base(conjuntos, chave):
    return linha_com_radio("Base de dados", list(conjuntos), chave)


def cor_do_texto():
    tema = st.context.theme.type
    return {"dark": "#fafafa", "light": "#262730"}.get(
        tema,
        graficos.COR_VALOR,
    )


def mostrar_grafico(grafico):
    st.altair_chart(grafico, width="stretch")


@st.fragment
def mostrar_heatmap_dia_hora(dados_heatmap):
    maximo_heatmap = int(dados_heatmap["quantidade"].max())

    st.subheader("Distribuição de acidentes por dia da semana e horário")

    piso_heatmap = 0
    if maximo_heatmap > 1:
        piso_heatmap = st.slider(
            "Piso da escala de cores (acidentes)",
            min_value=0,
            max_value=maximo_heatmap - 1,
            value=0,
            help=(
                "Células com acidentes até este valor ficam com a cor "
                "mais clara. O tooltip continua mostrando a contagem real."
            ),
        )
        if piso_heatmap:
            st.caption(
                f"Cores a partir de {piso_heatmap} acidentes: células "
                "abaixo disso aparecem na cor mais clara."
            )
        else:
            st.caption(
                "Escala completa: as cores cobrem de 0 ao máximo de "
                "acidentes."
            )

    mostrar_grafico(
        graficos.grafico_heatmap_dia_hora(dados_heatmap, piso_heatmap)
    )


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

    aba_categorias, aba_distribuicao = st.tabs(["Categorias", "Distribuição"])

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


aba_visao, aba_mapa, aba_relacao, aba_analise, aba_dados = st.tabs(
    ["Visão geral", "Mapas", "Sinalização × Acidentes", "Análise de dados", "Dados"],
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

    if not filtrado.empty:
        mostrar_heatmap_dia_hora(
            graficos.dados_heatmap_dia_hora(filtrado)
        )

        esquerda, direita = st.columns(2)

        with esquerda:
            mostrar_grafico(graficos.grafico_barras_mes(filtrado))

        with direita:
            mostrar_grafico(
                graficos.grafico_dias_uteis_fim_de_semana(filtrado)
            )

@st.fragment
def secao_regiao(dados, raio):
    st.subheader("A região explica o padrão?")
    st.caption(
        "Cada região tem um nível diferente de sinalização e de gravidade, e "
        "isso pode criar uma associação aparente. Aqui a densidade é separada "
        "por região, com os mesmos grupos de densidade em todas elas. Barras "
        "de erro: intervalo de confiança de 95%. Grupos com menos de "
        f"{relacao.MINIMO_REGISTROS} acidentes são omitidos, o que acontece "
        "quando uma região quase não tem locais com aquela densidade."
    )

    tipos = [graficos.ROTULO_TODOS_TIPOS] + [
        t.capitalize() for t in graficos.TIPOS_COMPARADOS
    ]
    tipo = st.selectbox(
        "Tipo de acidente",
        tipos,
        key="regiao_tipo",
        help="Atropelamentos são muito mais graves; fixar o tipo separa esse efeito.",
    )
    if tipo != graficos.ROTULO_TODOS_TIPOS:
        dados = dados[dados["tipo_acid"].eq(tipo.upper())]

    dados = dados.dropna(subset=["regiao"])
    if dados.empty:
        st.info("Nenhum acidente para os filtros selecionados.")
        return

    st.dataframe(
        relacao.resumo_regioes(dados),
        column_config={
            "acidentes": st.column_config.NumberColumn("Acidentes", format="%d"),
            "sinais_mediana": st.column_config.NumberColumn(
                f"Sinais em {raio} m (mediana)", format="%.0f"
            ),
            "graves_pct": st.column_config.NumberColumn(
                "Acidentes graves (%)", format="%.1f"
            ),
        },
        width="stretch",
    )

    dados_regiao = graficos.dados_graves_por_densidade(
        dados,
        coluna="regiao",
        valores=relacao.REGIOES,
        rotulo_todos="Todas as regiões",
    )
    if dados_regiao.empty:
        st.info("Poucos acidentes para formar os grupos de densidade.")
        return
    st.altair_chart(
        graficos.grafico_graves_por_densidade(dados_regiao, raio),
        width="content",
    )


def bloco_pareamento(dados, raio, pares, unidade, chave, titulo):
    st.subheader(titulo)
    nome_par = st.selectbox("Par de análise", list(pares), key=chave)
    par = pares[nome_par]
    categoria = par["categoria"]

    dados_par = graficos.dados_pareamento(
        dados, par["selecao"](dados), categoria
    )
    st.caption(
        f"Compara {par['ocorrencia']} com e sem sinais de \"{categoria}\" em "
        f"até {raio} m. Cada grupo de densidade reúne locais com quantidade "
        "parecida de sinais de qualquer tipo, para não confundir o efeito do "
        "sinal específico com o de haver muita sinalização. Barras de erro: "
        f"intervalo de confiança de 95%. Grupos com menos de "
        f"{relacao.MINIMO_REGISTROS} {unidade} são omitidos."
    )

    if dados_par.empty:
        st.info("Nenhum registro desse tipo para os filtros selecionados.")
        return
    mostrar_grafico(
        graficos.grafico_pareamento(dados_par, categoria, raio, unidade)
    )


@st.fragment
def secao_pareamento(dados, raio):
    bloco_pareamento(
        dados,
        raio,
        relacao.PARES,
        "acidentes",
        "par_acidentes",
        "O sinal certo perto do acidente muda a gravidade?",
    )


@st.fragment
def secao_vitimas(dados, raio):
    st.divider()
    st.subheader("Vítimas e sinalização")
    st.caption(
        "A tabela de vítimas não traz a gravidade de cada pessoa. Cada vítima "
        "herda a do acidente: \"grave\" quer dizer que ela estava num acidente "
        "com ferido grave ou morte. Com uma só vítima, isso é a gravidade da "
        "própria pessoa; com várias, não se sabe qual delas foi a grave."
    )
    so_uma_vitima = st.checkbox(
        "Somente acidentes com uma vítima (gravidade exata da pessoa)",
        key="vitimas_uma",
    )
    if so_uma_vitima:
        dados = dados[dados["n_vitimas"] == 1]

    if dados.empty:
        st.info("Nenhuma vítima para os filtros selecionados.")
        return

    coluna_total, coluna_graves = st.columns(2)
    coluna_total.metric(
        "Vítimas analisadas",
        graficos.formatar_inteiro(len(dados)),
        border=True,
    )
    coluna_graves.metric(
        "Em acidentes graves (%)",
        graficos.formatar_percentual(dados["acidente_grave"].mean() * 100),
        border=True,
    )

    st.subheader("Quem está mais exposto onde há menos sinais?")
    st.caption(
        "Proporção de vítimas em acidentes graves por grupo de densidade de "
        "sinais, no total e por papel da vítima. Barras de erro: intervalo de "
        f"confiança de 95%. Grupos com menos de {relacao.MINIMO_REGISTROS} "
        "vítimas são omitidos."
    )
    dados_papel = graficos.dados_graves_por_densidade(
        dados,
        coluna="papel",
        valores=["Condutor", "Ocupante", "Pedestre"],
        rotulo_todos="Todas as vítimas",
    )
    if dados_papel.empty:
        st.info("Poucas vítimas para formar os grupos de densidade.")
    else:
        st.altair_chart(
            graficos.grafico_graves_por_densidade(dados_papel, raio, "vítimas"),
            width="content",
        )

    bloco_pareamento(
        dados,
        raio,
        relacao.PARES_VITIMAS,
        "vítimas",
        "par_vitimas",
        "O sinal certo perto muda a gravidade para pedestres e ciclistas?",
    )


with aba_relacao:
    # O mapa só é criado com a aba aberta (mesmo motivo da aba Mapas).
    if aba_relacao.open:
        st.subheader("Sinalização × Acidentes")
        st.caption(
            f"Cada acidente é ligado aos sinais num raio de {raio_sinalizacao} m "
            "(ajuste na barra lateral). Entram só os sinais já implantados no "
            "ano do acidente, mas o cadastro traz apenas os sinais em vigor "
            "hoje. Esta aba segue o filtro de ano; o filtro de acidentes graves "
            "não se aplica, porque a análise compara graves com os demais."
        )

        with st.spinner("Calculando a relação espacial..."):
            relacao_acidentes = calcular_relacao(
                df, bases["sinalizacao"], raio_sinalizacao
            )
        dados_relacao = df.join(relacao_acidentes, how="inner")
        dados_relacao = dados_relacao[
            dados_relacao["ano"].isin(anos_selecionados)
        ]

        if dados_relacao.empty:
            st.info("Nenhum acidente com coordenadas para os anos selecionados.")
        else:
            colunas_resumo = st.columns(4)
            colunas_resumo[0].metric(
                "Acidentes analisados",
                graficos.formatar_inteiro(len(dados_relacao)),
                border=True,
            )
            colunas_resumo[1].metric(
                "Acidentes graves (%)",
                graficos.formatar_percentual(
                    dados_relacao["acidente_grave"].mean() * 100
                ),
                border=True,
            )
            colunas_resumo[2].metric(
                "Distância mediana ao sinal",
                f"{dados_relacao['dist_sinal'].median():.0f} m",
                border=True,
            )
            colunas_resumo[3].metric(
                f"Sinais em {raio_sinalizacao} m (mediana)",
                f"{dados_relacao['n_sinais'].median():.0f}",
                border=True,
            )

            st.subheader("Mais sinais ao redor, menos acidentes graves?")
            st.caption(
                "Proporção de acidentes graves por grupo de densidade de sinais, "
                "no total e por tipo de acidente. O tipo pesa muito na "
                "gravidade (atropelamentos são bem mais graves), por isso a "
                "separação. É uma associação: áreas centrais têm mais sinais e "
                "menor velocidade, e a sinalização costuma ser instalada onde "
                "já houve problema."
            )
            dados_densidade = graficos.dados_graves_por_densidade(dados_relacao)
            if dados_densidade.empty:
                st.info("Poucos acidentes para formar os grupos de densidade.")
            else:
                st.altair_chart(
                    graficos.grafico_graves_por_densidade(
                        dados_densidade, raio_sinalizacao
                    ),
                    width="content",
                )

            secao_regiao(dados_relacao, raio_sinalizacao)

            secao_pareamento(dados_relacao, raio_sinalizacao)

            st.subheader("Onde estão os acidentes graves")
            graves_relacao = dados_relacao[dados_relacao["acidente_grave"]]
            if graves_relacao.empty:
                st.info("Nenhum acidente grave para os anos selecionados.")
            else:
                st.caption(
                    "Cada ponto é um acidente grave, colorido pela quantidade "
                    f"de sinais em até {raio_sinalizacao} m. Passe o mouse para "
                    "ver os detalhes."
                )
                grupos_mapa = relacao.grupos_densidade(
                    dados_relacao["n_sinais"]
                )
                st_folium(
                    montar_mapa_graves(
                        graves_relacao,
                        grupos_mapa,
                        raio_sinalizacao,
                        tuple(sorted(anos_selecionados)),
                    ),
                    width=None,
                    height=550,
                    key="mapa_graves_sinalizacao",
                    returned_objects=[],
                )

            st.subheader("Distância ao sinal mais próximo")
            st.caption(
                "A escala do primeiro gráfico é de raiz quadrada, para as faixas "
                "mais distantes (poucos acidentes) continuarem visíveis. Esta "
                "análise não depende do raio. No segundo gráfico, faixas com "
                f"menos de {relacao.MINIMO_REGISTROS} acidentes são omitidas."
            )
            contagem_distancia, graves_distancia = graficos.dados_distancia(
                dados_relacao
            )
            esquerda, direita = st.columns(2)
            with esquerda:
                mostrar_grafico(
                    graficos.grafico_histograma_distancia(contagem_distancia)
                )
            with direita:
                mostrar_grafico(
                    graficos.grafico_graves_por_distancia(graves_distancia)
                )

            secao_vitimas(
                relacao.ligar_vitimas(bases["vitimas"], dados_relacao),
                raio_sinalizacao,
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
    # nasce com largura zero e as camadas falham ao desenhar.
    if aba_mapa.open:
        titulo_mapa, botao_mapa = st.columns([6, 1], vertical_alignment="center")
        titulo_mapa.subheader("Mapas dos acidentes e da sinalização")

        if "cliques_centralizar" not in st.session_state:
            st.session_state["cliques_centralizar"] = 0

        if botao_mapa.button("Centralizar mapa", width="stretch"):
            st.session_state["cliques_centralizar"] += 1

        # O componente só reposiciona o mapa quando center/zoom diferem do último
        # valor enviado. Por isso cada clique alterna uma diferença imperceptível
        # (cerca de 10 cm e 0,001 de zoom, que o Leaflet arredonda): o mapa volta
        # à posição inicial sem ser recriado.
        alternar = st.session_state["cliques_centralizar"] % 2
        centro_enviado = [mapas.CENTRO_MAPA[0] + alternar * 1e-6, mapas.CENTRO_MAPA[1]]
        zoom_enviado = mapas.ZOOM_MAPA + alternar * 0.001

        st.caption(
            "Use o painel \"Visualização\" no mapa para alternar entre os pontos "
            "dos acidentes, o mapa de calor e a sinalização. Os acidentes seguem "
            "os filtros da barra lateral; a sinalização é o cadastro atual da "
            "EPTC e não é filtrada. Passe o mouse sobre um ponto para ver os "
            "detalhes."
        )

        if filtrado.empty:
            st.info(
                "Nenhum acidente para os filtros selecionados; só a "
                "sinalização é exibida."
            )

        st_folium(
            mapas.mapa_vistas(filtrado, bases["sinalizacao"]),
            width=None,
            height=650,
            key="mapa_acidentes",
            center=centro_enviado,
            zoom=zoom_enviado,
            returned_objects=[],
        )

def mostrar_tabela(nome, visao, bruta, filtrada, aviso=None):
    # Completo: o CSV inteiro, como foi lido. Filtrado: a base já tratada
    # (duplicatas, coordenadas inválidas, datas após a extração) e filtrada.
    exibida = filtrada if visao == "Filtrado" else bruta

    # A legenda existe nas duas visões para a altura não mudar na troca.
    st.caption(
        aviso if visao == "Filtrado"
        else "CSV inteiro, como foi lido, sem tratamento."
    )

    with st.container(key=f"metricas_dados_{nome}"):
        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Linhas exibidas",
            f"{len(exibida):,}".replace(",", "."),
            border=True
        )

        col2.metric(
            "Linhas na base",
            f"{len(bruta):,}".replace(",", "."),
            border=True
        )

        col3.metric(
            "Percentual da base",
            f"{len(exibida) / len(bruta) * 100:.1f}%".replace(".", ","),
            border=True
        )

    st.dataframe(exibida, width="stretch")


@st.fragment
def secao_dados():
    # Fragmento: trocar de visão ou de tabela reexecuta só esta seção, sem
    # recarregar o restante da página.
    visao = linha_com_radio(
        "Dados", ["Filtrado", "Completo"], "dados_visao", subtitulo=True
    )

    brutos = carregar_brutos()

    aba_acidentes, aba_sinalizacao, aba_vitimas = st.tabs(
        ["Acidentes", "Sinalização", "Vítimas"],
        on_change="rerun",
    )

    # Filtrado usa as bases tratadas: o filtro de ano vale para acidentes e
    # vítimas, o de graves só para acidentes e a sinalização não é filtrada.
    with aba_acidentes:
        if aba_acidentes.open:
            mostrar_tabela(
                "acidentes",
                visao,
                brutos["acidentes"],
                filtrado,
                aviso="Base tratada, com os filtros de ano e de acidentes graves."
            )

    with aba_sinalizacao:
        if aba_sinalizacao.open:
            mostrar_tabela(
                "sinalizacao",
                visao,
                brutos["sinalizacao"],
                bases["sinalizacao"],
                aviso="Base tratada. A sinalização não é afetada pelos filtros."
            )

    with aba_vitimas:
        if aba_vitimas.open:
            vitimas = bases["vitimas"]
            mostrar_tabela(
                "vitimas",
                visao,
                brutos["vitimas"],
                vitimas[vitimas["data"].dt.year.isin(anos_selecionados)],
                aviso="Base tratada, com o filtro de ano."
            )


with aba_dados:
    # A tabela só é enviada ao navegador com a aba aberta.
    if aba_dados.open:
        secao_dados()
