"""Relação espacial entre os acidentes e a sinalização gráfica.

Cada acidente é ligado aos sinais próximos usando coordenadas projetadas em
metros. Só entram os sinais já implantados no ano do acidente (o cadastro tem
apenas os sinais em vigor, então sinais mais novos não existiam na época).
"""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

RAIO_TERRA = 6_371_000
LATITUDE_REFERENCIA = -30.05
PREFIXO_PERTO = "perto: "
MINIMO_REGISTROS = 30

# Cada par liga um tipo de ocorrência ao sinal que deveria protegê-lo.
PARES = {
    "Atropelamento × Travessia de pedestres": {
        "categoria": "Travessia de pedestres",
        "ocorrencia": "atropelamentos",
        "selecao": lambda a: a["tipo_acid"].eq("ATROPELAMENTO"),
    },
    "Bicicleta envolvida × Sinalização de bicicletas": {
        "categoria": "Bicicletas",
        "ocorrencia": "acidentes com bicicleta",
        "selecao": lambda a: a["bicicleta"].gt(0),
    },
    "Ônibus ou lotação envolvido × Transporte coletivo": {
        "categoria": "Transporte coletivo",
        "ocorrencia": "acidentes com ônibus ou lotação",
        "selecao": lambda a: (
            a[["onibus_urb", "onibus_met", "onibus_int", "lotacao"]]
            .sum(axis=1)
            .gt(0)
        ),
    },
}

# Mesma ideia para as vítimas: perfil da vítima × sinal que deveria protegê-la.
PARES_VITIMAS = {
    "Pedestre × Travessia de pedestres": {
        "categoria": "Travessia de pedestres",
        "ocorrencia": "vítimas pedestres",
        "selecao": lambda v: v["papel"].eq("Pedestre"),
    },
    "Ciclista × Sinalização de bicicletas": {
        "categoria": "Bicicletas",
        "ocorrencia": "vítimas ciclistas",
        "selecao": lambda v: v["tipo_veic"].eq("BICICLETA"),
    },
}

PAPEIS_VITIMA = {
    "CONDUTOR": "Condutor",
    "OCUPANTE": "Ocupante",
    "PEDESTRE": "Pedestre",
}
ROTULO_PAPEL_NAO_INFORMADO = "Não informado"

REGIOES = ["CENTRO", "LESTE", "NORTE", "SUL"]

# O cadastro não diz se o sinal é horizontal ou vertical, mas o local de
# instalação separa bem: marcações no pavimento ficam no leito da via; placas,
# abrigos e gradis ficam na calçada, no canteiro ou sobre a rua.
LOCAIS_HORIZONTAIS = ["LEITO DA VIA"]
LOCAIS_VERTICAIS = ["CALCADA", "CANTEIRO CENTRAL", "SOBRE A RUA (AÉREA)"]
ROTULO_HORIZONTAL = "Marcações no leito da via (horizontais)"
ROTULO_VERTICAL = "Placas e equipamentos na calçada ou canteiro (verticais)"

FAIXAS_DISTANCIA = [0, 5, 10, 25, 50, 100, 200, 500, np.inf]
ROTULOS_DISTANCIA = [
    "< 5", "5–10", "10–25", "25–50", "50–100", "100–200", "200–500", "> 500",
]


def projetar(df):
    """Latitude e longitude em metros (projeção plana local, suficiente
    para a escala de Porto Alegre)."""
    latitude = np.radians(df["latitude"].to_numpy(dtype=float))
    longitude = np.radians(df["longitude"].to_numpy(dtype=float))
    fator = np.cos(np.radians(LATITUDE_REFERENCIA))
    return np.column_stack([
        RAIO_TERRA * longitude * fator,
        RAIO_TERRA * latitude,
    ])


def _contar(arvore, pontos, raio):
    if arvore is None:
        return np.zeros(len(pontos), dtype=int)
    return arvore.query_ball_point(pontos, raio, return_length=True)


def calcular_relacao(acidentes, sinalizacao, raio):
    """Para cada acidente: distância ao sinal mais próximo, quantidade de
    sinais e de categorias distintas em até `raio` metros e, por categoria,
    se há ao menos um sinal desse tipo nesse raio."""
    acidentes = acidentes.dropna(subset=["latitude", "longitude", "ano"])
    sinais = sinalizacao.dropna(subset=["latitude", "longitude"])

    pontos_sinais = projetar(sinais)
    # Sem data de implantação, o sinal é tratado como antigo.
    ano_sinais = sinais["implantacao"].dt.year.fillna(0).to_numpy()
    categorias_sinais = sinais["categoria"].to_numpy()
    categorias = sorted(set(categorias_sinais))
    local_sinais = sinais["local_de_instal"].to_numpy()
    do_tipo = {
        "n_horizontal": np.isin(local_sinais, LOCAIS_HORIZONTAIS),
        "n_vertical": np.isin(local_sinais, LOCAIS_VERTICAIS),
    }

    pontos_acidentes = projetar(acidentes)
    ano_acidentes = acidentes["ano"].to_numpy()

    total = len(acidentes)
    distancia = np.full(total, np.nan)
    quantidade = np.zeros(total, dtype=int)
    perto = {c: np.zeros(total, dtype=bool) for c in categorias}
    por_tipo = {nome: np.zeros(total, dtype=int) for nome in do_tipo}

    for ano in np.unique(ano_acidentes):
        do_ano = ano_acidentes == ano
        vigentes = ano_sinais <= ano
        pontos = pontos_acidentes[do_ano]

        if vigentes.any():
            arvore = cKDTree(pontos_sinais[vigentes])
            distancia[do_ano] = arvore.query(pontos)[0]
            quantidade[do_ano] = _contar(arvore, pontos, raio)

        for nome, do_local in do_tipo.items():
            membros = vigentes & do_local
            arvore = cKDTree(pontos_sinais[membros]) if membros.any() else None
            por_tipo[nome][do_ano] = _contar(arvore, pontos, raio)

        for categoria in categorias:
            membros = vigentes & (categorias_sinais == categoria)
            arvore = cKDTree(pontos_sinais[membros]) if membros.any() else None
            perto[categoria][do_ano] = _contar(arvore, pontos, raio) > 0

    resultado = pd.DataFrame(
        {
            "dist_sinal": distancia,
            "n_sinais": quantidade,
            **por_tipo,
            **{PREFIXO_PERTO + c: v for c, v in perto.items()},
        },
        index=acidentes.index,
    )
    resultado["n_categorias"] = resultado[
        [PREFIXO_PERTO + c for c in categorias]
    ].sum(axis=1)
    return resultado


def grupos_densidade(contagens, n_grupos=5):
    """Divide as contagens em grupos de tamanho parecido e rotula cada um
    com a faixa de sinais que cobre (ex.: "6–15")."""
    cortes = pd.qcut(contagens, n_grupos, duplicates="drop")
    rotulos = []
    anterior = None
    for indice, intervalo in enumerate(cortes.cat.categories):
        alto = int(np.floor(intervalo.right))
        baixo = int(contagens.min()) if indice == 0 else anterior + 1
        rotulos.append(f"{baixo}" if baixo == alto else f"{baixo}–{alto}")
        anterior = alto
    return cortes.cat.rename_categories(rotulos)


def faixas_distancia(distancias):
    return pd.cut(
        distancias,
        bins=FAIXAS_DISTANCIA,
        labels=ROTULOS_DISTANCIA,
        right=False,
    )


def intervalo_wilson(sucessos, total, z=1.96):
    """Intervalo de confiança de 95% (Wilson) para uma proporção, em %."""
    sucessos = np.asarray(sucessos, dtype=float)
    total = np.asarray(total, dtype=float)
    proporcao = sucessos / total
    denominador = 1 + z**2 / total
    centro = (proporcao + z**2 / (2 * total)) / denominador
    margem = z * np.sqrt(
        proporcao * (1 - proporcao) / total + z**2 / (4 * total**2)
    ) / denominador
    return (centro - margem) * 100, (centro + margem) * 100


def proporcao_graves(df, por):
    """Quantidade e proporção de acidentes graves por grupo, com intervalo
    de confiança. Grupos com poucos registros são descartados."""
    tabela = (
        df.groupby(por, observed=True)["acidente_grave"]
        .agg(n="size", graves="sum")
        .reset_index()
    )
    tabela = tabela[tabela["n"] >= MINIMO_REGISTROS].copy()
    tabela["pct"] = tabela["graves"] / tabela["n"] * 100
    tabela["inferior"], tabela["superior"] = intervalo_wilson(
        tabela["graves"], tabela["n"]
    )
    return tabela


def ligar_vitimas(vitimas, dados_relacao):
    """Liga cada vítima ao acidente por `idacidente`.

    A vítima herda do acidente a gravidade e a relação com a sinalização
    (a tabela de vítimas não tem gravidade individual). `n_vitimas` é o
    número de vítimas do acidente: com uma só vítima, a gravidade do
    acidente é a da própria pessoa.
    """
    colunas = [
        "idacidente", "acidente_grave", "acidente_fatal", "n_sinais",
        "dist_sinal", "n_categorias",
        *[c for c in dados_relacao.columns if c.startswith(PREFIXO_PERTO)],
    ]
    acidentes = dados_relacao[colunas].drop_duplicates("idacidente")

    ligadas = vitimas.merge(acidentes, on="idacidente", how="inner")
    ligadas["n_vitimas"] = ligadas.groupby("idacidente")["idacidente"].transform("size")
    ligadas["papel"] = (
        ligadas["sit_vitima"]
        .astype("string")
        .str.strip()
        .str.upper()
        .map(PAPEIS_VITIMA)
        .fillna(ROTULO_PAPEL_NAO_INFORMADO)
    )
    return ligadas


def resumo_regioes(df):
    """Acidentes, densidade mediana de sinais e proporção de graves por
    região da cidade."""
    resumo = (
        df.groupby("regiao")
        .agg(
            acidentes=("acidente_grave", "size"),
            sinais_mediana=("n_sinais", "median"),
            graves_pct=("acidente_grave", lambda s: s.mean() * 100),
        )
        .reindex([r for r in REGIOES if r in set(df["regiao"])])
    )
    resumo.index = resumo.index.str.capitalize()
    return resumo.rename_axis("Região")


# ---------- antes e depois de uma implantação ----------

CELULA_METROS = 25
DIAS_POR_MES = 30.44
GRUPO_TRATADO = "Com sinal novo"
GRUPO_CONTROLE = "Sem sinal novo (controle)"
MAXIMO_CONTROLES = 5000


def _dias(datas):
    return datas.to_numpy().astype("datetime64[D]").astype("int64")


def _um_por_celula(pontos, dias):
    """Mantém um local por célula de CELULA_METROS, o de implantação mais
    antiga, para não contar duas vezes o mesmo ponto."""
    ordem = np.argsort(dias, kind="stable")
    celulas = np.floor(pontos[ordem] / CELULA_METROS).astype(int)
    _, primeiros = np.unique(celulas, axis=0, return_index=True)
    return ordem[np.sort(primeiros)]


def antes_depois(acidentes, sinalizacao, categoria, raio, meses, semente=0):
    """Compara os acidentes em volta de sinais implantados antes e depois da
    data de implantação, com um grupo de controle.

    Tratados: locais onde um sinal da `categoria` foi implantado com `meses`
    de dados antes e depois, sem outra implantação (de qualquer tipo) nas
    redondezas dentro da janela. Controle: locais de sinais antigos da mesma
    categoria, com datas de referência sorteadas entre as dos tratados e a
    mesma exigência de não haver implantação por perto. O controle mostra a
    tendência geral dos acidentes no período.

    Devolve (locais, info): uma linha por local com os acidentes e os graves
    antes e depois, e as contagens de cada etapa da seleção.
    """
    acidentes = acidentes.dropna(subset=["latitude", "longitude", "data"])
    sinais = sinalizacao.dropna(subset=["latitude", "longitude", "implantacao"])
    janela = int(round(meses * DIAS_POR_MES))

    pontos_acidentes = projetar(acidentes)
    dias_acidentes = _dias(acidentes["data"])
    graves = acidentes["acidente_grave"].to_numpy()
    primeiro, ultimo = dias_acidentes.min(), dias_acidentes.max()

    pontos_sinais = projetar(sinais)
    dias_sinais = _dias(sinais["implantacao"])
    do_tipo = sinais["categoria"].to_numpy() == categoria
    arvore_sinais = cKDTree(pontos_sinais)
    arvore_acidentes = cKDTree(pontos_acidentes)

    def sem_outra_implantacao(pontos, dias):
        vizinhos = arvore_sinais.query_ball_point(pontos, raio)
        limpos = np.zeros(len(pontos), dtype=bool)
        for i, (vizinhos_do_ponto, dia) in enumerate(zip(vizinhos, dias)):
            diferenca = np.abs(dias_sinais[vizinhos_do_ponto] - dia)
            # Diferença zero é a própria obra (vários sinais no mesmo dia).
            limpos[i] = not ((diferenca > 0) & (diferenca <= janela)).any()
        return limpos

    def contar(pontos, dias):
        vizinhos = arvore_acidentes.query_ball_point(pontos, raio)
        contagens = np.zeros((len(pontos), 4), dtype=int)
        for i, (vizinhos_do_ponto, dia) in enumerate(zip(vizinhos, dias)):
            posicao = np.asarray(vizinhos_do_ponto, dtype=int)
            desvio = dias_acidentes[posicao] - dia
            antes = (desvio >= -janela) & (desvio < 0)
            depois = (desvio >= 0) & (desvio < janela)
            grave = graves[posicao]
            contagens[i] = (
                antes.sum(), depois.sum(),
                (antes & grave).sum(), (depois & grave).sum(),
            )
        return contagens

    # Tratados
    elegivel = (
        do_tipo
        & (dias_sinais >= primeiro + janela)
        & (dias_sinais <= ultimo - janela)
    )
    posicoes = np.flatnonzero(elegivel)
    escolhidos = posicoes[_um_por_celula(
        pontos_sinais[posicoes], dias_sinais[posicoes]
    )] if len(posicoes) else posicoes
    pontos_tratados = pontos_sinais[escolhidos]
    dias_tratados = dias_sinais[escolhidos]
    limpos = (
        sem_outra_implantacao(pontos_tratados, dias_tratados)
        if len(escolhidos) else np.zeros(0, dtype=bool)
    )
    pontos_tratados, dias_tratados = pontos_tratados[limpos], dias_tratados[limpos]

    # Controle
    antigos = np.flatnonzero(do_tipo & (dias_sinais < primeiro))
    escolhidos_controle = antigos[_um_por_celula(
        pontos_sinais[antigos], dias_sinais[antigos]
    )] if len(antigos) else antigos
    sorteador = np.random.default_rng(semente)
    if len(escolhidos_controle) > MAXIMO_CONTROLES:
        escolhidos_controle = sorteador.choice(
            escolhidos_controle, MAXIMO_CONTROLES, replace=False
        )
    pontos_controle = pontos_sinais[escolhidos_controle]
    if len(dias_tratados) and len(escolhidos_controle):
        dias_controle = sorteador.choice(dias_tratados, len(escolhidos_controle))
        limpos_controle = sem_outra_implantacao(pontos_controle, dias_controle)
        pontos_controle = pontos_controle[limpos_controle]
        dias_controle = dias_controle[limpos_controle]
    else:
        pontos_controle = pontos_controle[:0]
        dias_controle = np.zeros(0, dtype="int64")

    info = {
        "implantacoes_na_janela": int(len(posicoes)),
        "locais_unicos": int(len(escolhidos)),
        "locais_tratados": int(len(dias_tratados)),
        "locais_controle": int(len(dias_controle)),
    }

    quadros = []
    for rotulo, pontos, dias in (
        (GRUPO_TRATADO, pontos_tratados, dias_tratados),
        (GRUPO_CONTROLE, pontos_controle, dias_controle),
    ):
        if len(dias) == 0:
            continue
        quadro = pd.DataFrame(
            contar(pontos, dias),
            columns=["antes", "depois", "graves_antes", "graves_depois"],
        )
        quadro["grupo"] = rotulo
        quadros.append(quadro)

    locais = (
        pd.concat(quadros, ignore_index=True)
        if quadros
        else pd.DataFrame(
            columns=["antes", "depois", "graves_antes", "graves_depois", "grupo"]
        )
    )
    return locais, info


def resumir_antes_depois(locais):
    """Totais por grupo, razão depois/antes e proporção de graves, cada um
    com intervalo de confiança de 95%."""
    linhas = []
    for grupo, parte in locais.groupby("grupo", sort=False):
        antes, depois = int(parte["antes"].sum()), int(parte["depois"].sum())
        graves_antes = int(parte["graves_antes"].sum())
        graves_depois = int(parte["graves_depois"].sum())
        razao = depois / antes if antes else np.nan
        # Erro-padrão do log da razão, tratando as contagens como Poisson.
        erro = np.sqrt(1 / antes + 1 / depois) if antes and depois else np.nan
        pct_antes_inf, pct_antes_sup = (
            intervalo_wilson(graves_antes, antes) if antes else (np.nan, np.nan)
        )
        pct_depois_inf, pct_depois_sup = (
            intervalo_wilson(graves_depois, depois) if depois else (np.nan, np.nan)
        )
        linhas.append({
            "grupo": grupo,
            "locais": len(parte),
            "antes": antes,
            "depois": depois,
            "media_antes": antes / len(parte),
            "media_depois": depois / len(parte),
            "razao": razao,
            "log_erro": erro,
            "razao_inferior": razao * np.exp(-1.96 * erro),
            "razao_superior": razao * np.exp(1.96 * erro),
            "graves_antes": graves_antes,
            "graves_depois": graves_depois,
            "pct_graves_antes": graves_antes / antes * 100 if antes else np.nan,
            "pct_graves_antes_inf": pct_antes_inf,
            "pct_graves_antes_sup": pct_antes_sup,
            "pct_graves_depois": graves_depois / depois * 100 if depois else np.nan,
            "pct_graves_depois_inf": pct_depois_inf,
            "pct_graves_depois_sup": pct_depois_sup,
        })
    return pd.DataFrame(linhas)


def efeito_relativo(resumo):
    """Razão depois/antes dos tratados dividida pela do controle, com
    intervalo de 95%. Abaixo de 1: os acidentes caíram mais (ou subiram
    menos) onde entrou o sinal. Devolve None sem os dois grupos."""
    por_grupo = resumo.set_index("grupo")
    if not {GRUPO_TRATADO, GRUPO_CONTROLE} <= set(por_grupo.index):
        return None
    tratado, controle = por_grupo.loc[GRUPO_TRATADO], por_grupo.loc[GRUPO_CONTROLE]
    razao = tratado["razao"] / controle["razao"]
    erro = np.sqrt(tratado["log_erro"] ** 2 + controle["log_erro"] ** 2)
    return {
        "razao": razao,
        "inferior": razao * np.exp(-1.96 * erro),
        "superior": razao * np.exp(1.96 * erro),
    }
