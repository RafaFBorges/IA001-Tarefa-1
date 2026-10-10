import re
from pathlib import Path
import pandas as pd
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

    /* Barra lateral compacta: o conteúdo todo cabe sem rolagem. */
    [data-testid="stSidebarHeader"] {
        height: 2.5rem;
        padding-top: 0.5rem;
        padding-bottom: 0;
    }
    [data-testid="stSidebarUserContent"] {
        padding-top: 0;
        padding-bottom: 0.5rem;
    }
    [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] {
        gap: 0.4rem;
    }
    [data-testid="stSidebarUserContent"] h2 {
        padding: 0 0 0.5rem;
    }
    [data-testid="stSidebarUserContent"] [data-testid="stCaptionContainer"] p {
        line-height: 1.3;
    }
    [class*="st-key-ir_pergunta_"] button {
        min-height: 1.6rem;
        padding-top: 0;
        padding-bottom: 0;
    }

    /* Botões dos anos: o nome completo precisa caber na barra lateral. */
    .st-key-botoes_anos button {
        padding-left: 0.25rem;
        padding-right: 0.25rem;
        white-space: nowrap;
    }
    .st-key-botoes_anos button p {
        font-size: 0.8rem;
        white-space: nowrap;
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


# Com o raio de 1 em 1 m há até 301 resultados possíveis: o limite de entradas
# evita que a memória cresça se o usuário percorrer muitos valores.
@st.cache_data(max_entries=20)
def calcular_relacao(_acidentes, _sinalizacao, raio):
    # Os dados são fixos na sessão: só o raio entra na chave do cache.
    return relacao.calcular_relacao(_acidentes, _sinalizacao, raio)


@st.cache_data(max_entries=200)
def calcular_antes_depois(_acidentes, _sinalizacao, categoria, raio, meses):
    return relacao.antes_depois(_acidentes, _sinalizacao, categoria, raio, meses)


@st.cache_data(max_entries=5)
def dados_mapa_graves(_graves, _grupos, raio, anos):
    return mapas.dados_mapa_graves(_graves, _grupos, raio)


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

ABA_SINALIZACAO = "Sinalização × Acidentes"
SUBABAS = {
    1: "Tipos e conjuntos",
    2: "Zonas e distância",
    3: "Densidade",
    4: "Horário",
    5: "Vítimas",
}


def ir_para_pergunta(numero):
    """Atalho da barra lateral: abre a aba Sinalização × Acidentes na subaba
    da pergunta. Roda como callback, antes de as abas serem desenhadas."""
    st.session_state["aba_principal"] = ABA_SINALIZACAO
    st.session_state["aba_perguntas"] = SUBABAS[numero]


# Uma aba fechada não é desenhada e o Streamlit esqueceria qual subaba estava
# aberta; reatribuir o valor a cada execução a mantém.
if "aba_perguntas" in st.session_state:
    st.session_state["aba_perguntas"] = st.session_state["aba_perguntas"]

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

def marcar_anos(valor):
    """Callback dos botões: marca ou desmarca todos os anos de uma vez."""
    for ano in anos:
        st.session_state[f"ano_{ano}"] = valor


# Uma caixa por ano, em no máximo duas linhas, da esquerda para a direita e
# de cima para baixo. Todos começam marcados.
for ano in anos:
    st.session_state.setdefault(f"ano_{ano}", True)

st.sidebar.markdown("Ano")
colunas_por_linha = -(-len(anos) // 2)
for inicio in range(0, len(anos), colunas_por_linha):
    colunas_anos = st.sidebar.columns(colunas_por_linha)
    for coluna, ano in zip(colunas_anos, anos[inicio:inicio + colunas_por_linha]):
        coluna.checkbox(str(ano), key=f"ano_{ano}")

anos_selecionados = [ano for ano in anos if st.session_state[f"ano_{ano}"]]

with st.sidebar.container(key="botoes_anos"):
    botao_todos, botao_nenhum = st.columns(2, gap="xsmall")
    botao_todos.button(
        "Selecionar tudo", on_click=marcar_anos, args=(True,), width="stretch"
    )
    botao_nenhum.button(
        "Desmarcar tudo", on_click=marcar_anos, args=(False,), width="stretch"
    )

RAIOS_SINALIZACAO = [1, 3, 5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100]

raio_sinalizacao = st.sidebar.select_slider(
    "Raio da sinalização (m)",
    options=RAIOS_SINALIZACAO,
    value=15,
    help=(
        "Distância em volta de cada acidente usada para contar os sinais "
        "próximos. Vale só para a aba Sinalização × Acidentes."
    ),
)

with st.sidebar:
    # Escala visual do raio: o círculo tem o tamanho real em metros. O centro
    # e o zoom mudam com o raio para o componente reposicionar o mapa.
    st_folium(
        mapas.mapa_referencia_raio(raio_sinalizacao),
        width=None,
        height=150,
        key="mapa_raio",
        center=mapas.MERCADO_PUBLICO,
        zoom=mapas.zoom_para_raio(raio_sinalizacao),
        returned_objects=[],
    )
    st.caption(
        "Escala do raio, em volta do Mercado Público de Porto Alegre."
    )

apenas_graves = st.sidebar.checkbox(
    "Mostrar somente acidentes graves"
)

st.sidebar.markdown("**Ir para a pergunta**")
for numero, nome in SUBABAS.items():
    st.sidebar.button(
        f"Pergunta {numero}: {nome}",
        key=f"ir_pergunta_{numero}",
        on_click=ir_para_pergunta,
        args=(numero,),
        type="tertiary",
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
def mostrar_frequencia(dados, coluna, chave, titulo=None, titulo_grande=False):
    """Gráfico de frequência horizontal com um toggle de escala logarítmica
    (desligado por padrão) ao lado do título e um aviso quando há categorias
    muito pequenas. É um fragmento: ligar o toggle reexecuta só este gráfico."""
    chave = re.sub(r"\W+", "_", chave)
    with st.container(
        horizontal=True,
        vertical_alignment="center",
        gap=None,
        key=f"linha_radio_log_{chave}",
    ):
        if titulo:
            if titulo_grande:
                st.subheader(titulo, width="content")
            else:
                st.markdown(f"**{titulo}**", width="content")
        escala_log = st.toggle("Escala logarítmica", key=f"log_{chave}")
        if graficos.tem_categorias_muito_pequenas(dados, coluna):
            st.caption(
                "Há categorias muito pequenas; a escala logarítmica ajuda a "
                "vê-las, mas as barras deixam de ser proporcionais."
            )
    mostrar_grafico(
        graficos.grafico_frequencia(
            dados,
            coluna,
            cor_texto=cor_do_texto(),
            mostrar_titulo=False,
            horizontal=True,
            escala_log=escala_log,
        )
    )


@st.fragment
def mostrar_heatmap_dia_hora(dados):
    st.subheader("Dias e horários com mais acidentes")
    st.caption(
        "Quanto mais escura a célula, mais acidentes naquele dia da semana e "
        "horário."
    )

    # Filtros do heatmap: valem só para este gráfico e reexecutam só este bloco.
    coluna_tipo, coluna_vitimas = st.columns([3, 2], vertical_alignment="bottom")
    tipos = list(dados["tipo_acid"].dropna().value_counts().index)
    tipo_heatmap = coluna_tipo.selectbox(
        "Tipo de acidente",
        [graficos.ROTULO_TODOS_TIPOS] + tipos,
        key="heatmap_tipo",
    )
    so_com_vitimas = coluna_vitimas.checkbox(
        "Só acidentes com vítimas",
        key="heatmap_vitimas",
        help="Acidentes com pelo menos um ferido ou morto.",
    )
    if tipo_heatmap != graficos.ROTULO_TODOS_TIPOS:
        dados = dados[dados["tipo_acid"].eq(tipo_heatmap)]
    if so_com_vitimas:
        dados = dados[(dados["feridos"].fillna(0) + dados["mortes"].fillna(0)) > 0]

    if dados.empty:
        st.info("Nenhum acidente para o tipo e os filtros selecionados.")
        return

    dados_heatmap = graficos.dados_heatmap_dia_hora(dados)
    maximo_heatmap = int(dados_heatmap["quantidade"].max())

    piso_heatmap = 0
    if maximo_heatmap > 1:
        piso_heatmap = st.slider(
            "Realçar só as células com mais acidentes que:",
            min_value=0,
            max_value=maximo_heatmap - 1,
            value=0,
            help=(
                "Células com esse número de acidentes ou menos ficam na cor "
                "mais clara, para destacar os horários de pico. Ao passar o "
                "mouse, o número real continua aparecendo."
            ),
        )
        if piso_heatmap:
            st.caption(
                f"Células com até {piso_heatmap} acidentes aparecem na cor "
                "mais clara."
            )
        else:
            st.caption(
                "As cores vão de 0 até o maior número de acidentes."
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
                larga = graficos.precisa_largura_total(
                    dados, coluna, horizontal=True
                )
                sufixo = "larga" if larga else "normal"
                with st.container(key=f"categoria_{sufixo}_{indice}"):
                    mostrar_frequencia(
                        dados, coluna, f"{nome}_{coluna}", titulo=coluna
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
    ["Visão geral", "Mapas", ABA_SINALIZACAO, "Análise de dados", "Dados"],
    key="aba_principal",
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

    if filtrado.empty:
        st.subheader("Acidentes por tipo")
        st.info("Nenhum acidente para os filtros selecionados.")
    elif "tipo_acid" in filtrado.columns:
        mostrar_frequencia(
            filtrado,
            "tipo_acid",
            "visao_tipo_acid",
            titulo="Acidentes por tipo",
            titulo_grande=True,
        )

    if not filtrado.empty:
        esquerda, direita = st.columns(2)

        with esquerda:
            mostrar_grafico(graficos.grafico_barras_mes(filtrado))

        with direita:
            mostrar_grafico(
                graficos.grafico_dias_uteis_fim_de_semana(filtrado)
            )

@st.fragment
def secao_regiao(dados, raio):
    st.subheader("É só efeito da região?")
    st.caption(
        "Cada região tem um nível diferente de sinalização e de gravidade, o "
        "que pode criar uma associação falsa. Aqui a comparação é feita dentro "
        "de cada região, com os mesmos grupos de sinais. A linha em cada barra "
        f"é a margem de erro (95%). Grupos com menos de {relacao.MINIMO_REGISTROS} "
        "acidentes ficam de fora, o que acontece quando a região quase não "
        "tem locais com aquela quantidade de sinais."
    )

    tipos = [graficos.ROTULO_TODOS_TIPOS] + [
        t.capitalize() for t in graficos.TIPOS_COMPARADOS
    ]
    tipo = st.selectbox(
        "Tipo de acidente",
        tipos,
        key="regiao_tipo",
        help="Atropelamentos são bem mais graves; escolher o tipo separa esse efeito.",
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
    mostrar_grafico(
        graficos.grafico_graves_por_densidade_agrupado(
            dados_regiao, raio, legenda="Região"
        )
    )


def padrao_do_widget(chave, valor):
    """Valor inicial de um widget só na primeira vez: depois dela o valor vem
    do estado da sessão, e passar os dois faz o Streamlit avisar."""
    return {} if chave in st.session_state else {"value": valor}


def bloco_pareamento(dados, raio, pares, unidade, chave, titulo):
    st.subheader(titulo)
    nome_par = st.selectbox("Par de análise", list(pares), key=chave)
    par = pares[nome_par]
    categoria = par["categoria"]

    dados_par = graficos.dados_pareamento(
        dados, par["selecao"](dados), categoria
    )
    st.caption(
        f"Compara {par['ocorrencia']} com e sem sinais de \"{categoria}\" por "
        f"perto (até {raio} m). Os locais são agrupados pela quantidade total "
        "de sinais, para a comparação ser justa: assim vemos o efeito do sinal "
        "específico, e não o de haver muita sinalização em geral. A linha em "
        "cada barra é a margem de erro (95%). Grupos com menos de "
        f"{relacao.MINIMO_REGISTROS} {unidade} ficam de fora."
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
        "Ter o sinal certo por perto ajuda?",
    )


@st.fragment
def secao_horario(dados, raio):
    st.subheader("Complemento: dia, noite e sinalização")
    dados = dados.assign(
        periodo=dados["noite_dia"].astype("string").str.strip().str.upper()
    )
    dados = dados[dados["periodo"].isin(["DIA", "NOITE"])]
    if dados.empty:
        st.info("Nenhum acidente com horário informado para os filtros selecionados.")
        return

    noite = dados["periodo"].eq("NOITE")
    colunas = st.columns(3)
    colunas[0].metric(
        "Acidentes à noite",
        graficos.formatar_percentual(noite.mean() * 100),
        border=True,
    )
    colunas[1].metric(
        "Graves de dia (%)",
        graficos.formatar_percentual(dados.loc[~noite, "acidente_grave"].mean() * 100),
        border=True,
    )
    colunas[2].metric(
        "Graves à noite (%)",
        graficos.formatar_percentual(dados.loc[noite, "acidente_grave"].mean() * 100),
        border=True,
    )

    st.subheader("Os sinais têm o mesmo efeito de dia e de noite?")
    st.caption(
        "Cada barra mostra a porcentagem de acidentes graves, do grupo com "
        "poucos sinais por perto ao grupo com muitos (sinais de todos os "
        "tipos), de dia e de noite. Se o efeito fosse o mesmo, as barras dos "
        "dois períodos cairiam na mesma proporção. A linha em cada barra é a "
        f"margem de erro (95%). Grupos com menos de {relacao.MINIMO_REGISTROS} "
        "acidentes ficam de fora."
    )
    mostrar_grafico(
        graficos.grafico_graves_horario(graficos.dados_graves_horario(dados), raio)
    )


@st.fragment
def secao_antes_depois(raio):
    st.subheader("Um sinal novo surte efeito?")
    st.caption(
        "Para cada sinal instalado, compara os acidentes num raio de "
        f"{raio} m nos meses antes e depois da instalação. Entram só locais "
        "sem outra instalação por perto nesse período. O controle são locais "
        "com sinais antigos do mesmo tipo, com datas sorteadas entre as dos "
        "sinais novos: ele mostra a tendência geral dos acidentes no período. "
        "Usa todos os acidentes, sem os filtros de ano e de gravidade."
    )

    categorias = list(bases["sinalizacao"]["categoria"].value_counts().index)
    coluna_categoria, coluna_janela = st.columns(2)
    categoria = coluna_categoria.selectbox(
        "Tipo de sinal", categorias, key="antes_depois_categoria"
    )
    meses = coluna_janela.select_slider(
        "Janela antes e depois (meses)",
        options=[6, 12, 18, 24],
        key="antes_depois_meses",
        **padrao_do_widget("antes_depois_meses", 12),
        help="Janelas maiores têm menos locais elegíveis: precisam de dados "
        "nos dois lados da implantação.",
    )

    with st.spinner("Comparando antes e depois..."):
        locais, info = calcular_antes_depois(
            df, bases["sinalizacao"], categoria, raio, meses
        )

    st.caption(
        f"{graficos.formatar_inteiro(info['implantacoes_na_janela'])} "
        f"implantações na janela, em {graficos.formatar_inteiro(info['locais_unicos'])} "
        f"locais distintos; {graficos.formatar_inteiro(info['locais_tratados'])} "
        "ficaram sem outra implantação por perto e entram na análise. "
        f"Controle: {graficos.formatar_inteiro(info['locais_controle'])} locais."
    )

    if info["locais_tratados"] < relacao.MINIMO_REGISTROS:
        st.info(
            "Poucos locais com essa categoria para a janela e o raio "
            "escolhidos. Tente uma janela menor ou outro raio."
        )
        return

    resumo = relacao.resumir_antes_depois(locais)
    efeito = relacao.efeito_relativo(resumo)

    esquerda, direita = st.columns(2)
    with esquerda:
        mostrar_grafico(graficos.grafico_media_antes_depois(resumo, meses))
    with direita:
        mostrar_grafico(graficos.grafico_razao_antes_depois(resumo, efeito))

    if efeito is not None:
        faixa = f"{efeito['inferior']:.2f} a {efeito['superior']:.2f}".replace(".", ",")
        razao = f"{efeito['razao']:.2f}".replace(".", ",")
        if efeito["inferior"] <= 1 <= efeito["superior"]:
            leitura = "a margem de erro inclui 1: não há diferença clara em relação ao controle."
        elif efeito["superior"] < 1:
            leitura = "os acidentes caíram mais (ou subiram menos) onde entrou o sinal."
        else:
            leitura = "os acidentes subiram mais onde entrou o sinal."
        st.markdown(
            f"**Efeito relativo: {razao}** (margem de erro de 95%: {faixa}); {leitura} "
            "As margens tendem a ser estreitas demais, porque o mesmo "
            "acidente pode contar em mais de um local próximo."
        )

    st.subheader("Gravidade antes e depois")
    st.caption(
        "Porcentagem de acidentes graves nos mesmos locais, antes e depois. "
        "A linha em cada barra é a margem de erro (95%)."
    )
    mostrar_grafico(graficos.grafico_graves_antes_depois(resumo))


@st.fragment
def secao_vitimas(dados, raio):
    st.subheader("Vítimas e sinalização")
    st.caption(
        "A tabela de vítimas não diz se cada pessoa se feriu gravemente. Por "
        "isso, cada vítima recebe a gravidade do acidente: \"grave\" quer dizer "
        "que houve ferido grave ou morte. Se o acidente teve só uma vítima, "
        "essa é a gravidade dela mesma."
    )
    so_uma_vitima = st.checkbox(
        "Só acidentes com uma vítima (gravidade exata da pessoa)",
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

    st.subheader("Entre condutor, ocupante e pedestre, quem corre mais risco com baixa sinalização?")
    st.caption(
        "Cada barra mostra a porcentagem de vítimas que estavam em acidentes "
        "graves, do grupo com poucos sinais por perto ao grupo com muitos. "
        "Condutor é quem dirige e ocupante é o passageiro. A linha em cada "
        "barra é a margem de erro (intervalo de confiança de 95%). Grupos com "
        f"menos de {relacao.MINIMO_REGISTROS} vítimas ficam de fora."
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
        mostrar_grafico(
            graficos.grafico_graves_por_densidade_agrupado(
                dados_papel, raio, "vítimas", legenda="Papel da vítima"
            )
        )

    bloco_pareamento(
        dados,
        raio,
        relacao.PARES_VITIMAS,
        "vítimas",
        "par_vitimas",
        "Ter o sinal certo por perto ajuda pedestres e ciclistas?",
    )


MESES_RESUMO = 12


def leitura_razao(efeito):
    """Lê uma razão de graves pelo intervalo de confiança."""
    if efeito is None or pd.isna(efeito["razao"]) or pd.isna(efeito["inferior"]):
        return "sem dados suficientes"
    if efeito["superior"] < 1:
        return "menos graves"
    if efeito["inferior"] > 1:
        return "mais graves"
    return "sem diferença clara"


def texto_intervalo(efeito):
    if efeito is None or pd.isna(efeito["inferior"]):
        return ""
    return f"{efeito['inferior']:.2f} a {efeito['superior']:.2f}".replace(".", ",")


def secao_resumo_categorias(dados, raio):
    st.subheader("Quais tipos de sinal estão ligados a menos acidentes graves?")
    st.caption(
        "Duas leituras para cada tipo de sinal. **Entre locais:** compara a "
        "porcentagem de acidentes graves com e sem o tipo de sinal por perto "
        f"(até {raio} m), sempre entre locais parecidos: com a mesma "
        "quantidade de sinais, o mesmo tipo de acidente e a mesma região. "
        "**Antes e depois:** conta os acidentes graves em volta de sinais "
        f"novos, {MESES_RESUMO} meses antes e depois, e compara com locais de "
        "controle (usa todos os acidentes, sem os filtros). Abaixo de 1 quer "
        "dizer menos graves. É associação: sinais costumam ser instalados "
        "onde já havia problema."
    )

    categorias = list(bases["sinalizacao"]["categoria"].value_counts().index)
    entre = relacao.razoes_por_categoria(dados, categorias).set_index("categoria")

    linhas_tabela, linhas_grafico = [], []
    for categoria in categorias:
        linha = entre.loc[categoria] if categoria in entre.index else None
        antes_depois_acidentes = antes_depois_graves = None
        locais, info = calcular_antes_depois(
            df, bases["sinalizacao"], categoria, raio, MESES_RESUMO
        )
        if info["locais_tratados"] >= relacao.MINIMO_REGISTROS:
            resumo_ad = relacao.resumir_antes_depois(locais)
            antes_depois_acidentes = relacao.efeito_relativo(resumo_ad)
            antes_depois_graves = relacao.efeito_relativo(resumo_ad, graves=True)

        if linha is not None:
            linhas_tabela.append({
                "Categoria": categoria,
                "Acidentes com a categoria por perto": int(linha["n_expostos"]),
                "Graves com (%)": linha["pct_expostos"],
                "Graves sem (%)": linha["pct_nao_expostos"],
                "Razão sem controle": linha["razao_bruta"],
                "Razão com controle": linha["razao"],
                "Margem de erro (95%)": texto_intervalo(linha),
                "Entre locais": leitura_razao(linha),
                "Antes e depois (acidentes)": (
                    antes_depois_acidentes["razao"] if antes_depois_acidentes else None
                ),
                "Antes e depois: leitura": leitura_razao(antes_depois_acidentes),
            })
            if not pd.isna(linha["razao"]):
                linhas_grafico.append({
                    "categoria": categoria,
                    "serie": graficos.SERIE_ENTRE_LOCAIS,
                    "razao": linha["razao"],
                    "inferior": linha["inferior"],
                    "superior": linha["superior"],
                })
        if antes_depois_graves is not None:
            linhas_grafico.append({
                "categoria": categoria,
                "serie": graficos.SERIE_ANTES_DEPOIS,
                **antes_depois_graves,
            })

    if not linhas_grafico:
        st.info("Poucos acidentes para os filtros selecionados.")
        return

    tabela = pd.DataFrame(linhas_tabela)
    menos = list(tabela.loc[tabela["Entre locais"] == "menos graves", "Categoria"])
    mais = list(tabela.loc[tabela["Entre locais"] == "mais graves", "Categoria"])
    st.markdown(
        "**Entre locais, tipos ligados a menos graves:** "
        + (", ".join(menos) if menos else "nenhum")
        + ". **Ligados a mais graves:** "
        + (", ".join(mais) if mais else "nenhuma")
        + "."
    )
    mostrar_grafico(
        graficos.grafico_razao_por_categoria(pd.DataFrame(linhas_grafico))
    )
    st.dataframe(
        tabela,
        hide_index=True,
        column_config={
            "Graves com (%)": st.column_config.NumberColumn(format="%.1f"),
            "Graves sem (%)": st.column_config.NumberColumn(format="%.1f"),
            "Razão sem controle": st.column_config.NumberColumn(format="%.2f"),
            "Razão com controle": st.column_config.NumberColumn(format="%.2f"),
            "Antes e depois (acidentes)": st.column_config.NumberColumn(format="%.2f"),
        },
        width="stretch",
    )


@st.fragment
def secao_pontos_criticos(dados, raio):
    st.subheader("Zonas mais críticas")
    st.caption(
        "A cidade é dividida em áreas quadradas, e cada linha é uma área com "
        "acidentes graves. **Prioridade**: quanto mais acidentes graves e "
        f"menos sinais por perto (até {raio} m), maior. O nome da área é a "
        "rua e a transversal mais comuns entre os acidentes graves dela. "
        "Segue o filtro de ano."
    )

    c1, c2, c3, c4 = st.columns(4)
    tamanho = c1.select_slider(
        "Tamanho da área (m)", options=relacao.TAMANHOS_CELULA,
        key="criticos_tamanho", **padrao_do_widget("criticos_tamanho", 200),
    )
    ordem = c2.selectbox(
        "Ordenar por",
        [
            "Prioridade (graves com pouca sinalização)",
            "Mais acidentes graves",
            "Maior % de graves (mín. 10 acidentes)",
        ],
        key="criticos_ordem",
    )
    minimo = c3.slider(
        "Mínimo de graves na área", 1, 10,
        key="criticos_minimo", **padrao_do_widget("criticos_minimo", 3),
    )
    quantidade = c4.selectbox(
        "Quantos mostrar", [10, 20, 50], key="criticos_quantidade"
    )

    ranking = relacao.ranking_pontos_criticos(dados, tamanho)
    ranking = ranking[ranking["graves"] >= minimo]
    if ordem.startswith("Maior %"):
        ranking = ranking[ranking["acidentes"] >= 10].sort_values(
            ["graves_pct", "graves"], ascending=False
        )
    elif ordem.startswith("Mais acidentes"):
        ranking = ranking.sort_values(["graves", "prioridade"], ascending=False)
    else:
        ranking = ranking.sort_values(["prioridade", "graves"], ascending=False)
    ranking = ranking.head(quantidade)

    if ranking.empty:
        st.info("Nenhuma área com esse mínimo de acidentes graves.")
        return

    tabela = ranking[[
        "local", "graves", "acidentes", "graves_pct", "mortes",
        "sinais_mediana", "categorias_mediana", "distancia_mediana", "prioridade",
    ]].rename(columns={
        "local": "Local",
        "graves": "Graves",
        "acidentes": "Acidentes",
        "graves_pct": "Graves (%)",
        "mortes": "Fatais",
        "sinais_mediana": f"Sinais em {raio} m (mediana)",
        "categorias_mediana": "Categorias de sinal (mediana)",
        "distancia_mediana": "Distância ao sinal (m, mediana)",
        "prioridade": "Prioridade",
    })
    tabela.index = pd.RangeIndex(1, len(tabela) + 1, name="Posição")

    st.caption("Clique em qualquer célula de uma linha para destacá-la em azul no mapa.")
    escolha = st.dataframe(
        tabela,
        column_config={
            "Graves (%)": st.column_config.NumberColumn(format="%.1f"),
            "Fatais": st.column_config.NumberColumn(format="%d"),
            f"Sinais em {raio} m (mediana)": st.column_config.NumberColumn(format="%.0f"),
            "Categorias de sinal (mediana)": st.column_config.NumberColumn(format="%.0f"),
            "Distância ao sinal (m, mediana)": st.column_config.NumberColumn(format="%.0f"),
            "Prioridade": st.column_config.NumberColumn(format="%.1f"),
        },
        width="stretch",
        on_select="rerun",
        selection_mode="single-cell",
        key="criticos_tabela",
    )
    celulas = escolha.selection.cells
    selecionado = celulas[0][0] + 1 if celulas else None
    st.download_button(
        "Baixar ranking (CSV)",
        tabela.to_csv(sep=";", decimal=",").encode("utf-8-sig"),
        file_name="pontos_criticos.csv",
        mime="text/csv",
    )
    mapa_base, camada = mapas.mapa_pontos_criticos(ranking, raio, selecionado)
    centro, zoom = mapas.enquadrar(ranking)
    st_folium(
        mapa_base,
        feature_group_to_add=camada,
        center=centro,
        zoom=zoom,
        width=None,
        height=450,
        key="mapa_pontos_criticos",
        returned_objects=[],
    )


@st.fragment
def secao_combinacoes(dados, raio):
    st.subheader("Quais combinações de sinais são mais comuns?")
    siglas = "; ".join(f"{sigla} = {nome}" for nome, sigla in relacao.SIGLAS.items())
    st.caption(
        "Cada acidente tem uma combinação: o conjunto de tipos de sinal que "
        f"existem por perto (até {raio} m). Cada barra do gráfico é a "
        "porcentagem de acidentes graves daquela combinação. As linhas estão "
        "em ordem de quantidade de acidentes (o número ao lado do nome), das "
        "mais comuns para as menos. A linha tracejada é a média de todos os "
        "acidentes, e barras à esquerda dela "
        f"têm menos graves que o normal. Siglas: {siglas}. Segue o filtro de "
        "ano."
    )

    quantidade = st.select_slider(
        "Combinações mostradas",
        options=[10, 15, 20, 30],
        key="combinacoes_quantidade",
        **padrao_do_widget("combinacoes_quantidade", 15),
    )
    tabela, cobertura, total = graficos.dados_combinacoes(dados, quantidade)
    if tabela.empty:
        st.info("Poucos acidentes para formar combinações.")
        return

    coluna_cobertura, coluna_combinacoes = st.columns(2)
    coluna_cobertura.metric(
        "Cobertura",
        f"{cobertura:.0%}",
        help=(
            f"Parte dos acidentes que as {len(tabela)} combinações mostradas "
            "cobrem."
        ),
        border=True,
    )
    coluna_combinacoes.metric(
        "Combinações",
        graficos.formatar_inteiro(total),
        help=(
            f"Combinações de sinais com pelo menos {relacao.MINIMO_REGISTROS} "
            "acidentes."
        ),
        border=True,
    )
    mostrar_grafico(graficos.grafico_combinacoes(tabela))

    st.subheader("Variedade de sinalização diminui a severidade?")
    st.caption(
        "Cada barra é a porcentagem de acidentes graves conforme quantos tipos "
        "diferentes de sinal existem por perto (de 0 a 9). A linha em cada "
        f"barra é a margem de erro (95%). Grupos com menos de "
        f"{relacao.MINIMO_REGISTROS} acidentes ficam de fora."
    )
    mostrar_grafico(
        graficos.grafico_graves_por_n_categorias(
            graficos.dados_por_n_categorias(dados), raio
        )
    )


PERGUNTAS = {
    1: "Quais tipos de sinal estão ligados a menos acidentes graves?",
    2: "Onde ficam as zonas de acidentes graves e a que distância está o sinal mais próximo de cada uma?",
    3: "A quantidade de sinais por perto reduz a severidade dos acidentes?",
    4: "Em quais dias e horários acontecem mais acidentes com vítimas?",
    5: "As vítimas são mais graves onde há menos sinais? Depende do tipo de vítima?",
}

# Widgets das subabas. Uma subaba fechada não desenha seus widgets, e o
# Streamlit esqueceria a escolha; reatribuir o valor a cada execução a mantém.
CHAVES_SUBABAS = [
    "regiao_tipo", "par_acidentes", "combinacoes_quantidade",
    "criticos_tamanho", "criticos_ordem", "criticos_minimo",
    "criticos_quantidade", "antes_depois_categoria", "antes_depois_meses",
    "vitimas_uma", "par_vitimas", "heatmap_tipo", "heatmap_vitimas",
]


def cabecalho_pergunta(numero, onde):
    st.markdown(f"#### Pergunta {numero}")
    st.markdown(f"**{PERGUNTAS[numero]}**")
    st.caption(onde)
    st.divider()


def secao_densidade(dados, raio):
    st.subheader("A porcentagem de graves cai quando há mais sinais?")
    st.caption(
        "Cada barra mostra a porcentagem de acidentes graves, do grupo com "
        "poucos sinais por perto ao grupo com muitos, no total e por tipo de "
        "acidente. Separamos por tipo porque ele pesa muito: atropelamentos "
        "são bem mais graves. Isso mostra uma associação, não prova que o "
        "sinal causa a queda: áreas centrais têm mais sinais e velocidade "
        "menor, e a sinalização costuma ser instalada onde já houve problema."
    )
    dados_densidade = graficos.dados_graves_por_densidade(dados)
    if dados_densidade.empty:
        st.info("Poucos acidentes para formar os grupos de densidade.")
        return
    mostrar_grafico(
        graficos.grafico_graves_por_densidade_agrupado(
            dados_densidade, raio, legenda="Tipo de acidente"
        )
    )


def secao_mapa_graves(dados, raio, anos):
    st.subheader("Onde estão os acidentes graves")
    graves = dados[dados["acidente_grave"]]
    if graves.empty:
        st.info("Nenhum acidente grave para os anos selecionados.")
        return
    st.caption(
        "Cada ponto é um acidente grave. A cor mostra quantos sinais há por "
        f"perto (até {raio} m). Passe o mouse sobre um ponto para ver os "
        "detalhes; pontos próximos são agrupados, e o zoom os separa."
    )
    st_folium(
        mapas.mapa_graves_sinalizacao(
            dados_mapa_graves(
                graves,
                relacao.grupos_densidade(dados["n_sinais"]),
                raio,
                tuple(sorted(anos)),
            ),
        ),
        width=None,
        height=550,
        key="mapa_graves_sinalizacao",
        returned_objects=[],
    )


def secao_distancia(dados):
    st.subheader("A que distância fica o sinal mais próximo?")
    st.caption(
        "O primeiro gráfico mostra quantos acidentes há em cada faixa de "
        "distância ao sinal mais próximo. A escala é de raiz quadrada, para as "
        "faixas mais distantes (poucos acidentes) continuarem visíveis. O "
        "segundo mostra a porcentagem de graves em cada faixa; faixas com "
        f"menos de {relacao.MINIMO_REGISTROS} acidentes ficam de fora. Esta "
        "análise não depende do raio."
    )
    contagem, graves = graficos.dados_distancia(dados)
    esquerda, direita = st.columns(2)
    with esquerda:
        mostrar_grafico(graficos.grafico_histograma_distancia(contagem))
    with direita:
        mostrar_grafico(graficos.grafico_graves_por_distancia(graves))


@st.fragment
def abas_perguntas(dados, raio, anos):
    """Uma subaba por pergunta do projeto, cada uma com os gráficos que a
    respondem. Trocar de subaba reexecuta só este bloco, e cada subaba só é
    montada quando aberta (os mapas precisam disso)."""
    for chave in CHAVES_SUBABAS:
        if chave in st.session_state:
            st.session_state[chave] = st.session_state[chave]

    aba1, aba2, aba3, aba4, aba5 = st.tabs(
        list(SUBABAS.values()),
        key="aba_perguntas",
        on_change="rerun",
    )

    with aba1:
        if aba1.open:
            cabecalho_pergunta(
                1,
                "Respondida por: a comparação por tipo de sinal, as combinações "
                "de sinais, o sinal certo por perto e o antes e depois da "
                "instalação.",
            )
            secao_resumo_categorias(dados, raio)
            st.divider()
            secao_combinacoes(dados, raio)
            st.divider()
            secao_pareamento(dados, raio)
            st.divider()
            secao_antes_depois(raio)

    with aba2:
        if aba2.open:
            cabecalho_pergunta(
                2,
                "Respondida por: o mapa dos acidentes graves, o ranking das zonas "
                "mais críticas e a distância ao sinal mais próximo.",
            )
            secao_mapa_graves(dados, raio, anos)
            st.divider()
            secao_pontos_criticos(dados, raio)
            st.divider()
            secao_distancia(dados)

    with aba3:
        if aba3.open:
            cabecalho_pergunta(
                3,
                "Respondida por: a porcentagem de graves por quantidade de sinais "
                "e a checagem por região.",
            )
            secao_densidade(dados, raio)
            st.divider()
            secao_regiao(dados, raio)

    with aba4:
        if aba4.open:
            cabecalho_pergunta(
                4,
                "Respondida pelo mapa de calor abaixo. A parte de dia, noite e "
                "sinalização é um complemento.",
            )
            mostrar_heatmap_dia_hora(dados)
            st.divider()
            secao_horario(dados, raio)

    with aba5:
        if aba5.open:
            cabecalho_pergunta(
                5,
                "Mostrado aqui: vítimas por papel e quantidade de sinais, e dois "
                "casos específicos (pedestre com travessia, ciclista com "
                "sinalização de bicicletas).",
            )
            secao_vitimas(relacao.ligar_vitimas(bases["vitimas"], dados), raio)


with aba_relacao:
    # O mapa só é criado com a aba aberta (mesmo motivo da aba Mapas).
    if aba_relacao.open:
        st.subheader("Sinalização × Acidentes")
        st.caption(
            f"Cada acidente é ligado aos sinais num raio de {raio_sinalizacao} m "
            "(ajuste na barra lateral). Entram só os sinais já implantados no "
            "ano do acidente, mas o cadastro traz apenas os sinais em vigor "
            "hoje. Esta aba segue o filtro de ano; o filtro de acidentes graves "
            "não se aplica, porque a análise compara graves com os demais. "
            "Cada subaba abaixo responde a uma pergunta do projeto."
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

            abas_perguntas(dados_relacao, raio_sinalizacao, anos_selecionados)


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
