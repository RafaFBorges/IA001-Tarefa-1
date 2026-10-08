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

    pontos_acidentes = projetar(acidentes)
    ano_acidentes = acidentes["ano"].to_numpy()

    total = len(acidentes)
    distancia = np.full(total, np.nan)
    quantidade = np.zeros(total, dtype=int)
    perto = {c: np.zeros(total, dtype=bool) for c in categorias}

    for ano in np.unique(ano_acidentes):
        do_ano = ano_acidentes == ano
        vigentes = ano_sinais <= ano
        pontos = pontos_acidentes[do_ano]

        if vigentes.any():
            arvore = cKDTree(pontos_sinais[vigentes])
            distancia[do_ano] = arvore.query(pontos)[0]
            quantidade[do_ano] = _contar(arvore, pontos, raio)

        for categoria in categorias:
            membros = vigentes & (categorias_sinais == categoria)
            arvore = cKDTree(pontos_sinais[membros]) if membros.any() else None
            perto[categoria][do_ano] = _contar(arvore, pontos, raio) > 0

    resultado = pd.DataFrame(
        {
            "dist_sinal": distancia,
            "n_sinais": quantidade,
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
