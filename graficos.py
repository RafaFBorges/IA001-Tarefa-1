import colorsys

import altair as alt
import numpy as np
import pandas as pd

ORDEM_DIAS = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]

NOMES_MESES = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]

COR_MEDIA = "#d62728"
COR_MEDIANA = "#2ca02c"
COR_NEUTRA = "#4c78a8"
COR_NULO = "#8c8c8c"
COR_DESTAQUE = "#9e9e9e"
COR_VALOR = "#868e96"
LIMITE_NOME_LEGENDA = 30
LARGURA_COLUNA_GRADE = 600
ALTURA_LINHA_LEGENDA = 24
ROTULO_NULO = "Nulo / Não informado"
PALETA_BASE = [
    "#4c78a8", "#f58518", "#e45756", "#54a24b", "#b279a2",
    "#eeca3b", "#72b7b2", "#9d755d", "#ff9da6", "#439894",
]


def paleta_categorias(categorias):
    cores = []
    for indice, categoria in enumerate(categorias):
        if categoria == ROTULO_NULO:
            cores.append(COR_NULO)
        elif len(categorias) <= len(PALETA_BASE):
            cores.append(PALETA_BASE[indice])
        else:
            matiz = (indice * 0.381966) % 1
            luminosidade = 0.40 if indice % 2 == 0 else 0.58
            r, g, b = colorsys.hls_to_rgb(matiz, luminosidade, 0.70)
            cores.append(f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}")
    return cores


def formatar_inteiro(valor):
    return f"{int(valor):,}".replace(",", ".")


def formatar_percentual(valor):
    return f"{valor:.1f}".replace(".", ",") + "%"


def grafico_linha_por_ano(serie, titulo, rotulo_y, cor):
    dados = serie.rename("valor").rename_axis("ano").reset_index()
    dados["ano"] = dados["ano"].astype(int)

    base = alt.Chart(dados).encode(
        x=alt.X("ano:O", title="Ano", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("valor:Q", title=rotulo_y),
        tooltip=[
            alt.Tooltip("ano:O", title="Ano"),
            alt.Tooltip("valor:Q", title=rotulo_y, format=".0f"),
        ],
    )

    linha = base.mark_line(
        color=cor,
        point=alt.OverlayMarkDef(color=cor, size=70),
    )
    rotulos = base.mark_text(dy=-14, color=cor).encode(
        text=alt.Text("valor:Q", format=".0f"),
    )

    grafico = (linha + rotulos).properties(height=320)
    return grafico.properties(title=titulo) if titulo else grafico


def grafico_barras_mes(df):
    meses = df["mes"].dropna().astype(int)
    por_mes = meses.value_counts().reindex(range(1, 13), fill_value=0)
    dados = pd.DataFrame({
        "mes": NOMES_MESES,
        "quantidade": por_mes.sort_index().values,
    })

    return (
        alt.Chart(dados)
        .mark_bar(color="#7570b3")
        .encode(
            x=alt.X(
                "mes:N",
                sort=NOMES_MESES,
                title="Mês",
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y("quantidade:Q", title="Quantidade de acidentes"),
            tooltip=[
                alt.Tooltip("mes:N", title="Mês"),
                alt.Tooltip("quantidade:Q", title="Acidentes", format=".0f"),
            ],
        )
        .properties(title="Quantidade de acidentes por mês", height=320)
    )


def grafico_dias_uteis_fim_de_semana(df):
    validos = df.dropna(subset=["dia_sem_normalizado"])
    rotulos = validos["fim_de_semana"].map({
        False: "Dias úteis",
        True: "Fim de semana",
    })
    ordem = ["Dias úteis", "Fim de semana"]
    dados = (
        rotulos.value_counts()
        .reindex(ordem, fill_value=0)
        .rename_axis("periodo")
        .reset_index(name="quantidade")
    )

    return (
        alt.Chart(dados)
        .mark_bar(color="#66c2a5")
        .encode(
            x=alt.X(
                "periodo:N",
                sort=ordem,
                title=None,
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y("quantidade:Q", title="Quantidade de acidentes"),
            tooltip=[
                alt.Tooltip("periodo:N", title="Período"),
                alt.Tooltip("quantidade:Q", title="Acidentes", format=".0f"),
            ],
        )
        .properties(
            title="Acidentes em dias úteis e fins de semana",
            height=320,
        )
    )


def dados_heatmap_dia_hora(df):
    hora = pd.to_numeric(
        df["hora"].astype("string").str.extract(r"(\d{1,2})")[0],
        errors="coerce",
    )
    validos = df.assign(hora_num=hora)
    validos = validos[validos["hora_num"].between(0, 23)].dropna(
        subset=["dia_sem_normalizado"]
    )
    validos["hora_num"] = validos["hora_num"].astype(int)

    contagem = (
        validos.groupby(["dia_sem_normalizado", "hora_num"])
        .size()
        .rename("quantidade")
        .reset_index()
    )
    grade = pd.MultiIndex.from_product(
        [ORDEM_DIAS, range(24)],
        names=["dia_sem_normalizado", "hora_num"],
    ).to_frame(index=False)
    dados = grade.merge(
        contagem,
        on=["dia_sem_normalizado", "hora_num"],
        how="left",
    ).fillna({"quantidade": 0})

    return dados


def grafico_heatmap_dia_hora(dados, piso=0):
    maximo = dados["quantidade"].max()

    return (
        alt.Chart(dados)
        .mark_rect()
        .encode(
            x=alt.X(
                "hora_num:O",
                title="Hora do dia",
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y("dia_sem_normalizado:O", sort=ORDEM_DIAS, title=None),
            color=alt.Color(
                "quantidade:Q",
                scale=alt.Scale(
                    scheme="yelloworangered",
                    domain=[piso, max(maximo, piso + 1)],
                    clamp=True,
                ),
                legend=alt.Legend(title="Acidentes"),
            ),
            tooltip=[
                alt.Tooltip("dia_sem_normalizado:N", title="Dia"),
                alt.Tooltip("hora_num:O", title="Hora"),
                alt.Tooltip("quantidade:Q", title="Acidentes", format=".0f"),
            ],
        )
        .properties(height=320)
    )


def colunas_categoricas(df, limite=20, ignorar=()):
    return [
        coluna
        for coluna in df.select_dtypes(
            include=["object", "string", "category"]
        ).columns
        if coluna not in ignorar and df[coluna].nunique(dropna=True) <= limite
    ]


def grafico_frequencia(
    df,
    coluna,
    max_categorias_rotulo_horizontal=6,
    cor_texto=COR_VALOR,
    mostrar_titulo=True,
    horizontal=False,
    escala_log=False,
):
    """Frequência de cada categoria. Com `horizontal=True`, as barras ficam
    na horizontal, com os nomes retos à esquerda e ocupando a largura
    inteira (não há legenda lateral: os nomes já estão no eixo). Com
    `escala_log=True` (só na versão horizontal), o eixo usa escala symlog:
    comprime as barras grandes e mantém o zero como base, mas as barras
    deixam de ser proporcionais à quantidade."""
    contagem = (
        df[coluna]
        .astype("string")
        .fillna(ROTULO_NULO)
        .value_counts()
        .rename_axis("categoria")
        .reset_index(name="quantidade")
    )

    nulos = int(
        contagem.loc[contagem["categoria"] == ROTULO_NULO, "quantidade"].sum()
    )
    preenchidos = contagem[contagem["categoria"] != ROTULO_NULO]
    if not preenchidos.empty:
        contagem = preenchidos.copy()

    total = contagem["quantidade"].sum()
    contagem["percentual"] = contagem["quantidade"] / total * 100
    contagem["rotulo"] = [
        f"{formatar_inteiro(quantidade)} ({formatar_percentual(percentual)})"
        for quantidade, percentual in zip(
            contagem["quantidade"],
            contagem["percentual"],
        )
    ]

    categorias = contagem["categoria"].tolist()
    quantidade_categorias = len(categorias)
    rotulos_na_horizontal = (
        quantidade_categorias <= max_categorias_rotulo_horizontal
    )
    escala_cor = alt.Scale(
        domain=categorias,
        range=paleta_categorias(categorias),
    )

    # A legenda nativa do Altair só reage a clique, então ela é desenhada
    # como camadas do próprio gráfico, para barras e opções compartilharem
    # a mesma seleção de hover.
    legenda = contagem[["categoria", "quantidade", "percentual"]].copy()
    legenda["nome"] = [
        categoria if len(categoria) <= LIMITE_NOME_LEGENDA
        else categoria[:LIMITE_NOME_LEGENDA - 1] + "…"
        for categoria in categorias
    ]
    legenda["posicao_y"] = [
        ALTURA_LINHA_LEGENDA * indice + ALTURA_LINHA_LEGENDA / 2
        for indice in range(quantidade_categorias)
    ]
    largura_legenda = int(
        44 + 7 * legenda["nome"].str.len().max()
    )

    destaque = alt.selection_point(
        fields=["categoria"],
        on="pointerover",
        clear="pointerout",
    )
    opacidade = (
        alt.when(destaque).then(alt.value(1)).otherwise(alt.value(0.35))
    )

    tooltip = [
        alt.Tooltip("categoria:N", title="Categoria"),
        alt.Tooltip("quantidade:Q", title="Registros", format=".0f"),
        alt.Tooltip("percentual:Q", title="Percentual (%)", format=".2f"),
    ]

    estilo_valor = {
        "color": cor_texto,
        "fontSize": 12,
        "fontWeight": "bold",
    }
    texto_titulo = coluna if mostrar_titulo else ""
    titulo = alt.TitleParams(texto_titulo) if mostrar_titulo else None
    if nulos:
        titulo = alt.TitleParams(
            texto_titulo,
            subtitle=(
                f"Fora do gráfico: {formatar_inteiro(nulos)} nulos / não "
                f"informados ({formatar_percentual(nulos / len(df) * 100)} "
                "dos registros). Percentuais sobre os preenchidos."
            ),
            subtitleColor="gray",
        )

    if horizontal:
        maximo = float(contagem["quantidade"].max())
        if escala_log:
            # Na escala symlog a posição cresce com log(1 + valor): o limite
            # é calculado para sobrar cerca de 14% da largura para os rótulos.
            limite = (1 + maximo) ** 1.14 - 1
            escala_x = alt.Scale(type="symlog", constant=1, domain=[0, limite])
            marcas = [0] + [10**k for k in range(8) if 10**k <= limite]
            eixo_x = alt.Axis(values=marcas, format=",.0f")
            titulo_x = "Quantidade de registros (escala logarítmica)"
        else:
            escala_x = alt.Scale(domain=[0, maximo * 1.22])
            eixo_x = alt.Axis()
            titulo_x = "Quantidade de registros"
        base_h = alt.Chart(contagem).encode(
            y=alt.Y(
                "categoria:N",
                sort=categorias,
                title=None,
                axis=alt.Axis(
                    labelAngle=0,
                    labelLimit=min(280, 12 + 7 * max(len(c) for c in categorias)),
                    labelOverlap=False,
                ),
            ),
            x=alt.X(
                "quantidade:Q",
                title=titulo_x,
                scale=escala_x,
                axis=eixo_x,
            ),
            tooltip=tooltip,
        )
        barras_h = (
            base_h.mark_bar(
                stroke=COR_DESTAQUE,
                cornerRadiusTopRight=2,
                cornerRadiusBottomRight=2,
            )
            .encode(
                color=alt.Color("categoria:N", scale=escala_cor, legend=None),
                opacity=opacidade,
                strokeWidth=alt.when(destaque, empty=False)
                .then(alt.value(3))
                .otherwise(alt.value(0)),
            )
            .add_params(destaque)
        )
        valores_h = base_h.mark_text(
            align="left", baseline="middle", dx=6, **estilo_valor
        ).encode(text="rotulo:N", opacity=opacidade)
        grafico_h = alt.layer(barras_h, valores_h).properties(
            height=max(170, 36 * quantidade_categorias + 110),
            padding={"left": 5, "top": 5, "bottom": 5, "right": 5},
        )
        return (
            grafico_h.properties(title=titulo) if titulo is not None else grafico_h
        )

    base = alt.Chart(contagem).encode(
        x=alt.X(
            "categoria:N",
            sort=categorias,
            title=None,
            axis=alt.Axis(
                labels=True,
                labelAngle=-45,
                labelLimit=110,
                labelOverlap=False,
            ),
        ),
        y=alt.Y(
            "quantidade:Q",
            title="Quantidade de registros",
            scale=alt.Scale(
                domain=[
                    0,
                    contagem["quantidade"].max()
                    * (1.15 if rotulos_na_horizontal else 1.5),
                ]
            ),
        ),
        tooltip=tooltip,
    )

    barras = (
        base.mark_bar(
            stroke=COR_DESTAQUE,
            cornerRadiusTopLeft=2,
            cornerRadiusTopRight=2,
        )
        .encode(
            color=alt.Color("categoria:N", scale=escala_cor, legend=None),
            opacity=opacidade,
            strokeWidth=alt.when(destaque, empty=False)
            .then(alt.value(3))
            .otherwise(alt.value(0)),
        )
        .add_params(destaque)
    )

    if rotulos_na_horizontal:
        valores = base.mark_text(dy=-8, **estilo_valor)
    else:
        valores = base.mark_text(
            angle=270,
            align="left",
            baseline="middle",
            dy=-9,
            **estilo_valor,
        )
    valores = valores.encode(text="rotulo:N", opacity=opacidade)

    posicao_legenda = alt.Y("posicao_y:Q", scale=None, axis=None)
    base_legenda = alt.Chart(legenda).encode(
        y=posicao_legenda,
        tooltip=tooltip,
        opacity=opacidade,
    )
    simbolos = base_legenda.mark_square(size=170).encode(
        x=alt.XValue(alt.expr("width + 18")),
        color=alt.Color("categoria:N", scale=escala_cor, legend=None),
    )
    nomes = base_legenda.mark_text(
        align="left",
        baseline="middle",
        fontSize=12,
        color=cor_texto,
    ).encode(
        x=alt.XValue(alt.expr("width + 34")),
        text="nome:N",
    )

    # No Streamlit a altura inclui eixos e rótulos, então cresce com o
    # número de categorias para o gráfico não ficar espremido.
    altura = 420 if quantidade_categorias <= 6 else 560
    if quantidade_categorias > 14:
        altura = 640

    grafico = alt.layer(barras, valores, simbolos, nomes).properties(
        height=altura,
        padding={"left": 5, "top": 5, "bottom": 5, "right": largura_legenda},
    )
    return grafico.properties(title=titulo) if titulo is not None else grafico


def tem_categorias_muito_pequenas(df, coluna, limite=0.01):
    """Verdadeiro quando a menor categoria tem menos de `limite` (1%) da
    maior: nesse caso a escala logarítmica ajuda a enxergá-la."""
    contagem = df[coluna].astype("string").dropna().value_counts()
    if len(contagem) < 2:
        return False
    return contagem.min() < limite * contagem.max()


def precisa_largura_total(df, coluna, horizontal=False):
    categorias = (
        df[coluna]
        .astype("string")
        .dropna()
        .unique()
        .tolist()
    )
    if not categorias:
        return False

    maior_nome = min(max(len(c) for c in categorias), LIMITE_NOME_LEGENDA)
    if horizontal:
        # Barras horizontais crescem na altura com o número de categorias; a
        # largura só importa para o espaço dos nomes à esquerda.
        return 300 + 7 * maior_nome > LARGURA_COLUNA_GRADE
    largura_legenda = 44 + 7 * maior_nome
    largura_estimada = 70 + largura_legenda + 26 * len(categorias)
    return largura_estimada > LARGURA_COLUNA_GRADE


def estatisticas_descritivas(serie):
    q25, q75 = serie.quantile(0.25), serie.quantile(0.75)
    return {
        "Registros válidos": len(serie),
        "Média": serie.mean(),
        "Mediana": serie.median(),
        "Desvio padrão": serie.std(),
        "IQR": q75 - q25,
        "Mínimo": serie.min(),
        "Máximo": serie.max(),
        "Assimetria": serie.skew(),
    }


def _linhas_referencia(serie):
    return pd.DataFrame({
        "medida": ["Média", "Mediana"],
        "valor": [serie.mean(), serie.median()],
    })


def _camada_referencia(serie):
    return (
        alt.Chart(_linhas_referencia(serie))
        .mark_rule(strokeWidth=2)
        .encode(
            x="valor:Q",
            color=alt.Color(
                "medida:N",
                scale=alt.Scale(
                    domain=["Média", "Mediana"],
                    range=[COR_MEDIA, COR_MEDIANA],
                ),
                legend=_legenda(orient="top"),
            ),
            strokeDash=alt.StrokeDash(
                "medida:N",
                scale=alt.Scale(
                    domain=["Média", "Mediana"],
                    range=[[6, 4], [1, 0]],
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("medida:N", title="Medida"),
                alt.Tooltip("valor:Q", title="Valor", format=".2f"),
            ],
        )
    )


def _intervalos_histograma(serie, max_discretos=20, bins=20):
    if serie.nunique() <= max_discretos:
        contagem = serie.value_counts().sort_index()
        return pd.DataFrame({
            "inicio": contagem.index.astype(float) - 0.5,
            "fim": contagem.index.astype(float) + 0.5,
            "quantidade": contagem.values,
        })

    quantidades, limites = np.histogram(serie, bins=bins)
    return pd.DataFrame({
        "inicio": limites[:-1],
        "fim": limites[1:],
        "quantidade": quantidades,
    })


def grafico_histograma(serie, rotulo_x, cor=COR_NEUTRA):
    dados = _intervalos_histograma(serie)

    barras = (
        alt.Chart(dados)
        .mark_bar(color=cor, stroke="white", strokeWidth=0.5)
        .encode(
            x=alt.X("inicio:Q", title=rotulo_x),
            x2="fim:Q",
            y=alt.Y("quantidade:Q", title="Quantidade de registros"),
            tooltip=[
                alt.Tooltip("inicio:Q", title="De", format=".2f"),
                alt.Tooltip("fim:Q", title="Até", format=".2f"),
                alt.Tooltip("quantidade:Q", title="Registros", format=".0f"),
            ],
        )
    )

    return (barras + _camada_referencia(serie)).properties(
        title=f"Histograma: {rotulo_x}",
        height=280,
    )


def grafico_boxplot(serie, rotulo_x):
    q1, mediana, q3 = serie.quantile([0.25, 0.5, 0.75])
    iqr = q3 - q1
    limite_inferior = q1 - 1.5 * iqr
    limite_superior = q3 + 1.5 * iqr

    dentro = serie[serie.between(limite_inferior, limite_superior)]
    resumo = pd.DataFrame({
        "grupo": [rotulo_x],
        "inferior": [dentro.min()],
        "q1": [q1],
        "mediana": [mediana],
        "q3": [q3],
        "superior": [dentro.max()],
    })
    outliers = (
        serie[~serie.between(limite_inferior, limite_superior)]
        .value_counts()
        .rename_axis("valor")
        .reset_index(name="quantidade")
        .assign(grupo=rotulo_x)
    )

    eixo_y = alt.Y("grupo:N", title=None, axis=alt.Axis(labels=False, ticks=False))

    bigodes = (
        alt.Chart(resumo)
        .mark_rule(color="#555")
        .encode(x=alt.X("inferior:Q", title=rotulo_x), x2="superior:Q", y=eixo_y)
    )
    caixa = (
        alt.Chart(resumo)
        .mark_bar(color="lightgreen", stroke="#555", size=28)
        .encode(
            x="q1:Q",
            x2="q3:Q",
            y=eixo_y,
            tooltip=[
                alt.Tooltip("inferior:Q", title="Limite inferior", format=".2f"),
                alt.Tooltip("q1:Q", title="Q1", format=".2f"),
                alt.Tooltip("mediana:Q", title="Mediana", format=".2f"),
                alt.Tooltip("q3:Q", title="Q3", format=".2f"),
                alt.Tooltip("superior:Q", title="Limite superior", format=".2f"),
            ],
        )
    )
    marca_mediana = (
        alt.Chart(resumo)
        .mark_tick(color=COR_MEDIANA, thickness=3, size=28)
        .encode(x="mediana:Q", y=eixo_y)
    )
    pontos = (
        alt.Chart(outliers)
        .mark_point(color="#555", size=30, filled=True, opacity=0.6)
        .encode(
            x="valor:Q",
            y=eixo_y,
            tooltip=[
                alt.Tooltip("valor:Q", title="Valor", format=".2f"),
                alt.Tooltip("quantidade:Q", title="Ocorrências", format=".0f"),
            ],
        )
    )

    camadas = bigodes + caixa + marca_mediana
    if not outliers.empty:
        camadas = camadas + pontos

    return (camadas + _camada_referencia(serie)).properties(
        title=f"Boxplot: {rotulo_x}",
        height=110,
    )


def grafico_distribuicao(serie, rotulo_x, cor=COR_NEUTRA):
    return alt.vconcat(
        grafico_histograma(serie, rotulo_x, cor),
        grafico_boxplot(serie, rotulo_x),
    ).resolve_scale(x="shared")


# ---------- sinalização × acidentes ----------

TIPOS_COMPARADOS = ["COLISÃO", "ABALROAMENTO", "CHOQUE", "ATROPELAMENTO"]
ROTULO_TODOS_TIPOS = "Todos os tipos"
COR_COM_SINAL = "#2ca25f"
COR_SEM_SINAL = "#e45756"


def _barras_com_erro(base, y_titulo, cor):
    """Barras de percentual com a barra de erro do intervalo de confiança.
    `cor` é uma cor fixa ou um encoding de cor do Altair."""
    if isinstance(cor, str):
        barras = base.mark_bar(color=cor)
    else:
        barras = base.mark_bar().encode(color=cor)
    barras = barras.encode(
        y=alt.Y("pct:Q", title=y_titulo, scale=alt.Scale(domainMin=0)),
    )
    erros = base.mark_rule(color=COR_VALOR).encode(
        y="inferior:Q", y2="superior:Q"
    )
    return barras, erros


# Rótulos conforme a unidade contada. Para vítimas, "grave" é o acidente em
# que ela estava (a tabela de vítimas não traz gravidade individual).
UNIDADES = {
    "acidentes": {
        "plural": "Acidentes",
        "graves": "Graves",
        "pct": "Acidentes graves (%)",
    },
    "vítimas": {
        "plural": "Vítimas",
        "graves": "Em acidentes graves",
        "pct": "Vítimas em acidentes graves (%)",
    },
}


def _tooltip_metricas(unidade="acidentes"):
    rotulos = UNIDADES[unidade]
    return [
        alt.Tooltip("n:Q", title=rotulos["plural"], format=",.0f"),
        alt.Tooltip("graves:Q", title=rotulos["graves"], format=",.0f"),
        alt.Tooltip("pct:Q", title=rotulos["pct"], format=".1f"),
        alt.Tooltip("inferior:Q", title="IC 95% inferior (%)", format=".1f"),
        alt.Tooltip("superior:Q", title="IC 95% superior (%)", format=".1f"),
    ]


def dados_graves_por_densidade(
    df, coluna="tipo_acid", valores=TIPOS_COMPARADOS, rotulo_todos=ROTULO_TODOS_TIPOS
):
    """Proporção de graves por grupo de densidade de sinais, para todos os
    registros juntos e para cada valor de `coluna` (por padrão, o tipo de
    acidente). Os grupos são definidos uma vez com todos os registros, para
    ficarem comparáveis entre as facetas."""
    import relacao_espacial as relacao

    df = df.assign(grupo=relacao.grupos_densidade(df["n_sinais"]))
    conjuntos = {rotulo_todos: df}
    for valor in valores:
        conjuntos[valor.capitalize()] = df[df[coluna].eq(valor)]

    tabelas = []
    for nome, conjunto in conjuntos.items():
        if conjunto.empty:
            continue
        tabela = relacao.proporcao_graves(conjunto, "grupo")
        tabela["tipo"] = nome
        tabelas.append(tabela)

    if not tabelas:
        return pd.DataFrame()
    dados = pd.concat(tabelas, ignore_index=True)
    dados["grupo"] = dados["grupo"].astype(str)
    return dados


def grafico_graves_por_densidade_agrupado(
    dados, raio, unidade="acidentes", legenda="Grupo"
):
    """Mesma proporção de graves por grupo de densidade, mas com as séries
    (por exemplo, as regiões) lado a lado em um único gráfico que ocupa a
    largura da página, e não em facetas. A primeira série é o total e fica
    em cinza.

    Ao passar o mouse sobre uma barra ou sobre a legenda, todas as barras da
    série ficam em destaque e as demais esmaecem. A legenda é desenhada
    dentro do gráfico (a nativa do Altair só reage ao clique) para barras e
    legenda compartilharem a mesma seleção."""
    ordem_grupos = list(dict.fromkeys(dados["grupo"]))
    ordem_series = list(dict.fromkeys(dados["tipo"]))
    cores = [COR_VALOR] + PALETA_BASE[: len(ordem_series) - 1]

    # Uma seleção para as barras e outra para a legenda (cada camada só
    # escuta os eventos das próprias marcas). Sem nenhuma ativa, tudo fica
    # opaco; com uma ativa, só a série escolhida.
    sobre_barra = alt.selection_point(
        name="destaque_barra", fields=["tipo"], on="pointerover",
        clear="pointerout", empty=False,
    )
    sobre_legenda = alt.selection_point(
        name="destaque_legenda", fields=["tipo"], on="pointerover",
        clear="pointerout", empty=False,
    )
    opacidade = (
        alt.when(
            "length(data('destaque_barra_store')) == 0"
            " && length(data('destaque_legenda_store')) == 0"
        )
        .then(alt.value(1))
        .when(sobre_barra | sobre_legenda)
        .then(alt.value(1))
        .otherwise(alt.value(0.22))
    )
    cor = alt.Color(
        "tipo:N",
        sort=ordem_series,
        scale=alt.Scale(domain=ordem_series, range=cores),
        legend=None,
    )

    base = alt.Chart(dados).encode(
        x=alt.X(
            "grupo:N",
            sort=ordem_grupos,
            title=f"Sinais em até {raio} m do acidente",
            axis=alt.Axis(labelAngle=0),
        ),
        xOffset=alt.XOffset("tipo:N", sort=ordem_series),
        opacity=opacidade,
        tooltip=[
            alt.Tooltip("tipo:N", title=legenda),
            alt.Tooltip("grupo:N", title="Sinais no raio"),
            *_tooltip_metricas(unidade),
        ],
    )
    barras, erros = _barras_com_erro(base, UNIDADES[unidade]["pct"], cor)

    # Legenda no alto do gráfico, em pixels, cada item após o anterior. Cada
    # item é um só texto ("■ nome") na cor da série, fácil de apontar.
    posicao, itens = 0, []
    for nome in ordem_series:
        itens.append({"tipo": nome, "px": posicao, "item": f"■ {nome}"})
        posicao += 30 + 7.2 * len(nome)
    legenda_itens = (
        alt.Chart(pd.DataFrame(itens))
        .mark_text(align="left", baseline="middle", fontSize=13, fontWeight="bold")
        .encode(
            x=alt.X("px:Q", scale=None, axis=None),
            y=alt.value(-18),
            text="item:N",
            color=cor,
            opacity=opacidade,
        )
    )

    return (
        alt.layer(
            barras.add_params(sobre_barra),
            erros,
            legenda_itens.add_params(sobre_legenda),
        )
        .properties(height=360, padding={"top": 34, "left": 5, "right": 12, "bottom": 5})
    )


def dados_pareamento(df, selecao, categoria):
    """Proporção de graves com e sem sinais da categoria no raio, no total
    e dentro de cada grupo de densidade (para separar o efeito da
    quantidade geral de sinais)."""
    import relacao_espacial as relacao

    df = df[selecao].copy()
    if df.empty:
        return pd.DataFrame()

    df["grupo"] = relacao.grupos_densidade(df["n_sinais"]).astype(str)
    df["situacao"] = df[relacao.PREFIXO_PERTO + categoria].map(
        {True: "Com sinal por perto", False: "Sem sinal por perto"}
    )

    tabelas = []
    todos = relacao.proporcao_graves(df, "situacao")
    todos["grupo"] = "Todos"
    tabelas.append(todos)
    for grupo, conjunto in df.groupby("grupo", sort=False):
        tabela = relacao.proporcao_graves(conjunto, "situacao")
        tabela["grupo"] = grupo
        tabelas.append(tabela)

    dados = pd.concat(tabelas, ignore_index=True)
    ordem = ["Todos"] + sorted(
        (g for g in dados["grupo"].unique() if g != "Todos"),
        key=lambda g: int(g.split("–")[0]),
    )
    dados["grupo"] = pd.Categorical(dados["grupo"], categories=ordem, ordered=True)
    return dados.sort_values("grupo").reset_index(drop=True)


def grafico_pareamento(dados, categoria, raio, unidade="acidentes"):
    ordem_grupos = list(dados["grupo"].cat.categories)
    cor = alt.Color(
        "situacao:N",
        title=None,
        scale=alt.Scale(
            domain=["Com sinal por perto", "Sem sinal por perto"],
            range=[COR_COM_SINAL, COR_SEM_SINAL],
        ),
        legend=_legenda(orient="top"),
    )
    base = alt.Chart(dados).encode(
        x=alt.X(
            "grupo:N",
            sort=ordem_grupos,
            title=f"Sinais de qualquer tipo em até {raio} m (grupos de densidade)",
            axis=alt.Axis(labelAngle=0),
        ),
        xOffset=alt.XOffset("situacao:N", sort=["Com sinal por perto", "Sem sinal por perto"]),
        tooltip=[
            alt.Tooltip("situacao:N", title=f"{categoria} em {raio} m"),
            alt.Tooltip("grupo:N", title="Sinais no raio"),
            *_tooltip_metricas(unidade),
        ],
    )
    barras, erros = _barras_com_erro(base, UNIDADES[unidade]["pct"], cor)
    return alt.layer(barras, erros).properties(height=300)


def dados_distancia(df):
    import relacao_espacial as relacao

    df = df.assign(faixa=relacao.faixas_distancia(df["dist_sinal"]))
    contagem = (
        df.groupby("faixa", observed=False)
        .size()
        .rename("n")
        .reset_index()
    )
    contagem["faixa"] = contagem["faixa"].astype(str)
    proporcao = relacao.proporcao_graves(df, "faixa")
    proporcao["faixa"] = proporcao["faixa"].astype(str)
    return contagem, proporcao


def grafico_histograma_distancia(contagem):
    return (
        alt.Chart(contagem)
        .mark_bar(color=COR_NEUTRA)
        .encode(
            x=alt.X(
                "faixa:N",
                sort=list(contagem["faixa"]),
                title="Distância ao sinal mais próximo (m)",
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y("n:Q", title="Acidentes", scale=alt.Scale(type="sqrt")),
            tooltip=[
                alt.Tooltip("faixa:N", title="Distância (m)"),
                alt.Tooltip("n:Q", title="Acidentes", format=",.0f"),
            ],
        )
        .properties(height=300)
    )


def grafico_graves_por_distancia(proporcao):
    ordem = list(proporcao["faixa"])
    base = alt.Chart(proporcao).encode(
        x=alt.X(
            "faixa:N",
            sort=ordem,
            title="Distância ao sinal mais próximo (m)",
            axis=alt.Axis(labelAngle=0),
        ),
        tooltip=[alt.Tooltip("faixa:N", title="Distância (m)"), *_tooltip_metricas()],
    )
    barras, erros = _barras_com_erro(base, "Acidentes graves (%)", COR_NEUTRA)
    return alt.layer(barras, erros).properties(height=300)


# ---------- antes e depois de uma implantação ----------

COR_ANTES = "#9e9e9e"
COR_DEPOIS = "#4c78a8"
COR_EFEITO = "#f58518"
ROTULO_EFEITO = "Efeito relativo (novo ÷ controle)"


def _cor_periodo():
    return alt.Color(
        "periodo:N",
        title=None,
        sort=["Antes", "Depois"],
        scale=alt.Scale(domain=["Antes", "Depois"], range=[COR_ANTES, COR_DEPOIS]),
        legend=_legenda(orient="top"),
    )


def grafico_media_antes_depois(resumo, meses):
    dados = pd.DataFrame([
        {
            "grupo": linha["grupo"],
            "periodo": periodo,
            "media": linha[f"media_{campo}"],
            "total": linha[campo],
            "locais": linha["locais"],
        }
        for _, linha in resumo.iterrows()
        for periodo, campo in (("Antes", "antes"), ("Depois", "depois"))
    ])
    return (
        alt.Chart(dados)
        .mark_bar()
        .encode(
            x=alt.X(
                "grupo:N",
                title=None,
                sort=list(resumo["grupo"]),
                axis=alt.Axis(labelAngle=0, labelLimit=170),
            ),
            xOffset=alt.XOffset("periodo:N", sort=["Antes", "Depois"]),
            y=alt.Y("media:Q", title=f"Acidentes por local em {meses} meses"),
            color=_cor_periodo(),
            tooltip=[
                alt.Tooltip("grupo:N", title="Grupo"),
                alt.Tooltip("periodo:N", title="Período"),
                alt.Tooltip("media:Q", title="Acidentes por local", format=".2f"),
                alt.Tooltip("total:Q", title="Acidentes", format=",.0f"),
                alt.Tooltip("locais:Q", title="Locais", format=",.0f"),
            ],
        )
        .properties(height=300)
    )


def grafico_razao_antes_depois(resumo, efeito):
    linhas = [
        {
            "grupo": linha["grupo"],
            "razao": linha["razao"],
            "inferior": linha["razao_inferior"],
            "superior": linha["razao_superior"],
            "detalhe": f"{int(linha['antes'])} antes, {int(linha['depois'])} depois",
        }
        for _, linha in resumo.iterrows()
    ]
    if efeito is not None:
        linhas.append({
            "grupo": ROTULO_EFEITO,
            "razao": efeito["razao"],
            "inferior": efeito["inferior"],
            "superior": efeito["superior"],
            "detalhe": "razão do grupo com sinal novo ÷ razão do controle",
        })
    dados = pd.DataFrame(linhas)
    ordem = list(dados["grupo"])

    base = alt.Chart(dados).encode(
        y=alt.Y("grupo:N", sort=ordem, title=None, axis=alt.Axis(labelLimit=230)),
        color=alt.Color(
            "grupo:N",
            legend=None,
            scale=alt.Scale(
                domain=ordem,
                range=[COR_DEPOIS, COR_ANTES, COR_EFEITO][: len(ordem)],
            ),
        ),
        tooltip=[
            alt.Tooltip("grupo:N", title="Grupo"),
            alt.Tooltip("razao:Q", title="Razão", format=".2f"),
            alt.Tooltip("inferior:Q", title="IC 95% inferior", format=".2f"),
            alt.Tooltip("superior:Q", title="IC 95% superior", format=".2f"),
            alt.Tooltip("detalhe:N", title="Detalhe"),
        ],
    )
    pontos = base.mark_point(filled=True, size=110).encode(
        x=alt.X("razao:Q", title="Acidentes depois ÷ antes (1 = sem mudança)",
                scale=alt.Scale(zero=False)),
    )
    intervalos = base.mark_rule(strokeWidth=2).encode(x="inferior:Q", x2="superior:Q")
    referencia = (
        alt.Chart(pd.DataFrame({"x": [1]}))
        .mark_rule(strokeDash=[4, 4], color=COR_VALOR)
        .encode(x="x:Q")
    )
    return alt.layer(referencia, intervalos, pontos).properties(height=200)


def grafico_graves_antes_depois(resumo):
    dados = pd.DataFrame([
        {
            "grupo": linha["grupo"],
            "periodo": periodo,
            "n": linha[f"{campo}"],
            "graves": linha[f"graves_{campo}"],
            "pct": linha[f"pct_graves_{campo}"],
            "inferior": linha[f"pct_graves_{campo}_inf"],
            "superior": linha[f"pct_graves_{campo}_sup"],
        }
        for _, linha in resumo.iterrows()
        for periodo, campo in (("Antes", "antes"), ("Depois", "depois"))
    ])
    base = alt.Chart(dados).encode(
        x=alt.X(
            "grupo:N",
            title=None,
            sort=list(resumo["grupo"]),
            axis=alt.Axis(labelAngle=0, labelLimit=170),
        ),
        xOffset=alt.XOffset("periodo:N", sort=["Antes", "Depois"]),
        tooltip=[
            alt.Tooltip("grupo:N", title="Grupo"),
            alt.Tooltip("periodo:N", title="Período"),
            *_tooltip_metricas(),
        ],
    )
    barras, erros = _barras_com_erro(base, "Acidentes graves (%)", _cor_periodo())
    return alt.layer(barras, erros).properties(height=300)


# ---------- horário × sinalização ----------

COR_DIA = "#f2a900"
COR_NOITE = "#3b4a8c"
PERIODOS = {"DIA": "Dia", "NOITE": "Noite"}


def _com_periodo(df):
    df = df.assign(
        periodo=df["noite_dia"].astype("string").str.strip().str.upper().map(PERIODOS)
    )
    return df.dropna(subset=["periodo"])


def _cor_dia_noite():
    return alt.Color(
        "periodo:N",
        title=None,
        sort=["Dia", "Noite"],
        scale=alt.Scale(domain=["Dia", "Noite"], range=[COR_DIA, COR_NOITE]),
        legend=_legenda(orient="top"),
    )


def dados_graves_horario(df):
    """Proporção de graves, de dia e de noite, por grupo de densidade de
    marcações horizontais e de sinais verticais (grupos de cada tipo)."""
    import relacao_espacial as relacao

    df = _com_periodo(df)
    tabelas = []
    for rotulo, coluna in (
        (relacao.ROTULO_HORIZONTAL, "n_horizontal"),
        (relacao.ROTULO_VERTICAL, "n_vertical"),
    ):
        grupos = relacao.grupos_densidade(df[coluna])
        parte = df.assign(grupo=grupos)
        tabela = relacao.proporcao_graves(parte, ["grupo", "periodo"])
        ordem = {g: i for i, g in enumerate(grupos.cat.categories)}
        tabela["ordem"] = tabela["grupo"].map(ordem).astype(int)
        tabela["grupo"] = tabela["grupo"].astype(str)
        tabela["tipo"] = rotulo
        tabelas.append(tabela)
    return pd.concat(tabelas, ignore_index=True)


def grafico_graves_horario(dados, raio):
    ordem_tipos = list(dict.fromkeys(dados["tipo"]))
    base = alt.Chart(dados).encode(
        x=alt.X(
            "grupo:N",
            sort=alt.EncodingSortField("ordem", op="min"),
            title=f"Sinais do tipo em até {raio} m do acidente",
            axis=alt.Axis(labelAngle=0),
        ),
        xOffset=alt.XOffset("periodo:N", sort=["Dia", "Noite"]),
        tooltip=[
            alt.Tooltip("periodo:N", title="Período"),
            alt.Tooltip("grupo:N", title="Sinais no raio"),
            *_tooltip_metricas(),
        ],
    )
    barras, erros = _barras_com_erro(base, "Acidentes graves (%)", _cor_dia_noite())
    return (
        alt.layer(barras, erros)
        .properties(width=240, height=260)
        .facet(
            facet=alt.Facet("tipo:N", sort=ordem_tipos, title=None),
            columns=2,
        )
        .resolve_scale(x="independent")
    )


def dados_marcacao_e_placa(df):
    """Combina marcações horizontais (muitas ou poucas) e sinais verticais
    (muitos ou poucos), cortando cada um na mediana, para separar o efeito de
    um do outro."""
    import relacao_espacial as relacao

    df = _com_periodo(df)
    muitas_marcacoes = df["n_horizontal"] > df["n_horizontal"].median()
    muitas_placas = df["n_vertical"] > df["n_vertical"].median()
    rotulos = {
        (False, False): "Poucas marcações · poucas placas",
        (True, False): "Muitas marcações · poucas placas",
        (False, True): "Poucas marcações · muitas placas",
        (True, True): "Muitas marcações · muitas placas",
    }
    df = df.assign(
        grupo=[rotulos[c] for c in zip(muitas_marcacoes, muitas_placas)]
    )
    tabela = relacao.proporcao_graves(df, ["grupo", "periodo"])
    tabela["ordem"] = tabela["grupo"].map({g: i for i, g in enumerate(rotulos.values())})
    return tabela.sort_values(["ordem", "periodo"]).reset_index(drop=True)


def grafico_marcacao_e_placa(dados):
    base = alt.Chart(dados).encode(
        y=alt.Y(
            "grupo:N",
            sort=alt.EncodingSortField("ordem", op="min"),
            title=None,
            axis=alt.Axis(labelLimit=260),
        ),
        yOffset=alt.YOffset("periodo:N", sort=["Dia", "Noite"]),
        tooltip=[
            alt.Tooltip("periodo:N", title="Período"),
            alt.Tooltip("grupo:N", title="Grupo"),
            *_tooltip_metricas(),
        ],
    )
    barras = base.mark_bar().encode(
        x=alt.X("pct:Q", title="Acidentes graves (%)", scale=alt.Scale(domainMin=0)),
        color=_cor_dia_noite(),
    )
    erros = base.mark_rule(color=COR_VALOR).encode(x="inferior:Q", x2="superior:Q")
    return alt.layer(barras, erros).properties(height=260)


# ---------- razões ajustadas ----------

COR_AJUSTADA = "#4c78a8"
LIMITE_NOME_LEGENDA = 420  # px; bem acima do maior nome de série
SERIE_ENTRE_LOCAIS = "Comparação entre locais (ajustada)"
SERIE_ANTES_DEPOIS = "Antes e depois da implantação"


def _legenda(**opcoes):
    """Legenda de séries com o nome inteiro: o limite padrão do Vega (160 px)
    cortava nomes como "Antes e depois da implantação" com "…"."""
    return alt.Legend(title=None, labelLimit=LIMITE_NOME_LEGENDA, **opcoes)


def _referencia_em_um(escala=None):
    return (
        alt.Chart(pd.DataFrame({"x": [1]}))
        .mark_rule(strokeDash=[4, 4], color=COR_VALOR)
        .encode(x=alt.X("x:Q", scale=escala if escala is not None else alt.Undefined))
    )


MARCAS_RAZAO = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, 1.2, 1.5, 2, 3, 4, 5, 8]


def _escala_logaritmica_razao(*colunas, folga=1.08):
    """Escala logarítmica para razões (comparam-se multiplicativamente: 0,5 e
    2 ficam à mesma distância de 1) ajustada aos dados, com marcas em valores
    redondos."""
    valores = pd.concat([pd.to_numeric(c, errors="coerce") for c in colunas]).dropna()
    valores = valores[valores > 0]
    minimo = min(valores.min(), 1) / folga
    maximo = max(valores.max(), 1) * folga
    marcas = [m for m in MARCAS_RAZAO if minimo <= m <= maximo]
    return alt.Scale(type="log", domain=[minimo, maximo]), marcas


def grafico_razao_por_categoria(dados):
    """Razão de graves por categoria de sinal, em duas séries: a comparação
    entre locais com e sem a categoria (ajustada) e o antes e depois."""
    ordem = list(
        dados[dados["serie"] == SERIE_ENTRE_LOCAIS]
        .sort_values("razao")["categoria"]
    )
    base = alt.Chart(dados).encode(
        y=alt.Y("categoria:N", sort=ordem, title=None, axis=alt.Axis(labelLimit=240)),
        yOffset=alt.YOffset("serie:N", sort=[SERIE_ENTRE_LOCAIS, SERIE_ANTES_DEPOIS]),
        color=alt.Color(
            "serie:N",
            title=None,
            sort=[SERIE_ENTRE_LOCAIS, SERIE_ANTES_DEPOIS],
            scale=alt.Scale(
                domain=[SERIE_ENTRE_LOCAIS, SERIE_ANTES_DEPOIS],
                range=[COR_AJUSTADA, COR_EFEITO],
            ),
            legend=_legenda(orient="top"),
        ),
        tooltip=[
            alt.Tooltip("categoria:N", title="Categoria"),
            alt.Tooltip("serie:N", title="Análise"),
            alt.Tooltip("razao:Q", title="Razão", format=".2f"),
            alt.Tooltip("inferior:Q", title="IC 95% inferior", format=".2f"),
            alt.Tooltip("superior:Q", title="IC 95% superior", format=".2f"),
        ],
    )
    escala, marcas = _escala_logaritmica_razao(
        dados["razao"], dados["inferior"], dados["superior"]
    )
    pontos = base.mark_point(filled=True, size=90).encode(
        x=alt.X(
            "razao:Q",
            title="Razão de acidentes graves (escala logarítmica; 1 = sem diferença; abaixo de 1 = menos graves)",
            scale=escala,
            axis=alt.Axis(values=marcas, format=".1f"),
        )
    )
    intervalos = base.mark_rule(strokeWidth=2).encode(
        x=alt.X("inferior:Q", scale=escala), x2="superior:Q"
    )
    return alt.layer(_referencia_em_um(escala), intervalos, pontos).properties(
        height=max(260, 46 * len(ordem))
    )


# ---------- combinações de sinalização ----------

def _rotulo_combinacao(presentes, siglas):
    """Nome curto de uma combinação: lista as siglas quando há poucas e diz
    "Todas menos ..." quando quase todas as categorias estão presentes."""
    if not presentes.any():
        return "Nenhuma"
    if presentes.all():
        return f"Todas as {len(presentes)}"
    if presentes.sum() >= len(presentes) - 3:
        return "Todas menos " + ", ".join(siglas[~presentes])
    return " + ".join(siglas[presentes])


def dados_combinacoes(df, quantidade):
    """As combinações de categorias de sinal mais frequentes, com a
    proporção de graves de cada uma. Devolve a tabela, a parte dos acidentes
    que elas cobrem e o total de combinações com amostra suficiente."""
    import relacao_espacial as relacao

    rotulos, completos = relacao.combinacoes_de_sinais(df)
    df = df.assign(combinacao=rotulos, categorias=completos)
    tabela = relacao.proporcao_graves(df, "combinacao")
    nomes = df.drop_duplicates("combinacao").set_index("combinacao")["categorias"]
    tabela["categorias"] = tabela["combinacao"].map(nomes)

    colunas = [c for c in df.columns if c.startswith(relacao.PREFIXO_PERTO)]
    siglas = np.array(
        [relacao.SIGLAS.get(c[len(relacao.PREFIXO_PERTO):], c) for c in colunas]
    )
    presentes = df.drop_duplicates("combinacao").set_index("combinacao")[colunas]
    legivel = {
        combinacao: _rotulo_combinacao(linha.to_numpy(dtype=bool), siglas)
        for combinacao, linha in presentes.iterrows()
    }
    tabela["rotulo"] = tabela["combinacao"].map(legivel)
    # A quantidade vai no nome da linha: é por ela que as barras estão em
    # ordem, e o comprimento da barra mostra outra medida (a % de graves).
    tabela["rotulo_eixo"] = [
        f"{r} · {formatar_inteiro(n)}"
        for r, n in zip(tabela["rotulo"], tabela["n"])
    ]
    tabela["rotulo_barra"] = tabela["pct"].map(formatar_percentual)
    tabela["media_geral"] = df["acidente_grave"].mean() * 100

    cobertura = tabela.nlargest(quantidade, "n")["n"].sum() / len(df)
    return tabela.nlargest(quantidade, "n").reset_index(drop=True), cobertura, len(tabela)


def grafico_combinacoes(tabela):
    """Porcentagem de graves de cada combinação, com as mais comuns no topo e
    uma linha na média de todos os acidentes: barras à esquerda dela têm menos
    graves que o normal. A quantidade de acidentes vai escrita na barra."""
    media = float(tabela["media_geral"].iloc[0])
    base = alt.Chart(tabela).encode(
        y=alt.Y(
            "rotulo_eixo:N",
            sort=alt.EncodingSortField("n", order="descending"),
            title="Combinação · acidentes",
            axis=alt.Axis(labelLimit=420, labelOverlap=False),
        ),
        tooltip=[
            alt.Tooltip("categorias:N", title="Tipos de sinal presentes"),
            *_tooltip_metricas(),
        ],
    )
    barras = base.mark_bar(color=COR_NEUTRA).encode(
        x=alt.X("pct:Q", title="Acidentes graves (%)")
    )
    rotulos = base.mark_text(align="left", dx=4, color=COR_VALOR).encode(
        x="pct:Q", text="rotulo_barra:N"
    )
    referencia = (
        alt.Chart(pd.DataFrame({"x": [media]}))
        .mark_rule(strokeDash=[4, 4], color=COR_MEDIA)
        .encode(x="x:Q")
    )
    texto_media = (
        alt.Chart(pd.DataFrame({"x": [media], "texto": [f"Média de todos os acidentes: {formatar_percentual(media)}"]}))
        .mark_text(align="left", baseline="bottom", dx=4, dy=-4, color=COR_MEDIA, y=0)
        .encode(x="x:Q", text="texto:N")
    )
    return alt.layer(barras, rotulos, referencia, texto_media).properties(
        height=max(200, 32 * len(tabela))
    )


def dados_por_n_categorias(df):
    import relacao_espacial as relacao

    tabela = relacao.proporcao_graves(df, "n_categorias")
    tabela["n_categorias"] = tabela["n_categorias"].astype(int)
    return tabela


def grafico_graves_por_n_categorias(tabela, raio):
    base = alt.Chart(tabela).encode(
        x=alt.X(
            "n_categorias:O",
            title=f"Categorias distintas de sinal em até {raio} m",
            axis=alt.Axis(labelAngle=0),
        ),
        tooltip=[
            alt.Tooltip("n_categorias:O", title="Categorias distintas"),
            *_tooltip_metricas(),
        ],
    )
    barras, erros = _barras_com_erro(base, "Acidentes graves (%)", COR_NEUTRA)
    return alt.layer(barras, erros).properties(height=300)
