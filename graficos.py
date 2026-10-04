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

LIMITES_LATITUDE = (-30.30, -29.90)
LIMITES_LONGITUDE = (-51.30, -51.00)

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

    return (linha + rotulos).properties(title=titulo, height=320)


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


def grafico_heatmap_dia_hora(df):
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
                scale=alt.Scale(scheme="yelloworangered"),
                legend=alt.Legend(title="Acidentes"),
            ),
            tooltip=[
                alt.Tooltip("dia_sem_normalizado:N", title="Dia"),
                alt.Tooltip("hora_num:O", title="Hora"),
                alt.Tooltip("quantidade:Q", title="Acidentes", format=".0f"),
            ],
        )
        .properties(
            title="Distribuição de acidentes por dia da semana e horário",
            height=320,
        )
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
):
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

    estilo_valor = {
        "color": cor_texto,
        "fontSize": 12,
        "fontWeight": "bold",
    }
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

    titulo = alt.TitleParams(coluna)
    if nulos:
        titulo = alt.TitleParams(
            coluna,
            subtitle=(
                f"Fora do gráfico: {formatar_inteiro(nulos)} nulos / não "
                f"informados ({formatar_percentual(nulos / len(df) * 100)} "
                "dos registros). Percentuais sobre os preenchidos."
            ),
            subtitleColor="gray",
        )

    return alt.layer(barras, valores, simbolos, nomes).properties(
        title=titulo,
        height=altura,
        padding={"left": 5, "top": 5, "bottom": 5, "right": largura_legenda},
    )


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
                legend=alt.Legend(title=None, orient="top"),
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


def grafico_espacial(df, coluna_gravidade=None, limite_pontos=10000):
    dados = df.dropna(subset=["latitude", "longitude"])
    dados = dados[
        dados["latitude"].between(*LIMITES_LATITUDE)
        & dados["longitude"].between(*LIMITES_LONGITUDE)
    ]
    total = len(dados)

    if total > limite_pontos:
        dados = dados.sample(limite_pontos, random_state=0)

    colunas = ["latitude", "longitude"]
    if coluna_gravidade is not None:
        colunas.append(coluna_gravidade)
    dados = dados[colunas].copy()

    codificacao = {
        "x": alt.X(
            "longitude:Q",
            title="Longitude",
            scale=alt.Scale(domain=list(LIMITES_LONGITUDE), zero=False),
        ),
        "y": alt.Y(
            "latitude:Q",
            title="Latitude",
            scale=alt.Scale(domain=list(LIMITES_LATITUDE), zero=False),
        ),
        "tooltip": [
            alt.Tooltip("latitude:Q", format=".5f"),
            alt.Tooltip("longitude:Q", format=".5f"),
        ],
    }

    if coluna_gravidade is None:
        grafico = (
            alt.Chart(dados)
            .mark_circle(size=25)
            .encode(
                color=alt.value("#756bb1"),
                opacity=alt.value(0.5),
                **codificacao,
            )
        )
    else:
        dados["situacao"] = dados[coluna_gravidade].map({
            True: "Grave",
            False: "Não grave",
        })
        selecao = alt.selection_point(fields=["situacao"], bind="legend")
        grafico = (
            alt.Chart(dados)
            .mark_circle(size=25)
            .encode(
                color=alt.Color(
                    "situacao:N",
                    scale=alt.Scale(
                        domain=["Não grave", "Grave"],
                        range=["#74add1", "#d73027"],
                    ),
                    legend=alt.Legend(title="Acidente"),
                ),
                opacity=alt.when(selecao).then(alt.value(0.6)).otherwise(alt.value(0.05)),
                **codificacao,
            )
            .add_params(selecao)
        )

    return grafico.properties(height=600).interactive(), total, len(dados)
