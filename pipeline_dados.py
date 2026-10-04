from pathlib import Path

import pandas as pd

DATA_EXTRACAO = pd.Timestamp("2026-09-21")

COLUNAS_NUMERICAS_ACIDENTES = [
    "latitude",
    "longitude",
    "feridos",
    "feridos_gr",
    "mortes",
    "morte_post",
    "fatais",
    "cont_vit",
    "ups",
]

COLUNAS_NUMERICAS_VITIMAS = [
    "latitude",
    "longitude",
    "idade",
    "auto",
    "taxi",
    "onibus_urb",
    "onibus_met",
    "onibus_int",
    "caminhao",
    "moto",
    "carroca",
    "bicicleta",
    "outro",
    "lotacao",
]

COLUNAS_NUMERICAS_SINALIZACAO = [
    "latitude",
    "longitude",
    "num_inicial",
    "num_final",
]

MARCADORES_NULOS = ["", " ", "null", "none", "nan", "n/a", "na", "-", "--"]


def _padronizar_colunas(dataframe):
    dataframe = dataframe.copy()
    dataframe.columns = (
        dataframe.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
    )
    return dataframe


def _converter_numeros(dataframe, colunas):
    dataframe = dataframe.copy()
    for coluna in colunas:
        if coluna in dataframe.columns:
            dataframe[coluna] = pd.to_numeric(
                dataframe[coluna]
                .astype(str)
                .str.replace(",", ".", regex=False),
                errors="coerce",
            )
    return dataframe


def _padronizar_nulos(dataframe):
    dataframe = dataframe.copy()
    return dataframe.replace(MARCADORES_NULOS, pd.NA)


def _filtrar_coordenadas(dataframe):
    dataframe = dataframe.copy()
    if {"latitude", "longitude"}.issubset(dataframe.columns):
        dataframe = dataframe[
            dataframe["latitude"].between(-90, 90)
            & dataframe["longitude"].between(-180, 180)
        ].copy()
    return dataframe


def _preparar_base(dataframe):
    dataframe = _padronizar_colunas(dataframe)
    dataframe = _padronizar_nulos(dataframe)
    for coluna in ["data", "data_extracao", "implantacao"]:
        if coluna in dataframe.columns:
            dataframe[coluna] = pd.to_datetime(
                dataframe[coluna],
                errors="coerce",
            )
    dataframe = dataframe.drop_duplicates().copy()
    return dataframe


def ler_dados_brutos(base_dir):
    base_dir = Path(base_dir)
    dados_dir = base_dir / "dados"
    leitura = {
        "acidentes": "cat_acidentes.csv",
        "vitimas": "cat_vitimas.csv",
        "sinalizacao": "websin.csv",
    }

    return {
        nome: pd.read_csv(
            dados_dir / arquivo,
            sep=";",
            encoding="utf-8",
        )
        for nome, arquivo in leitura.items()
    }


def preparar_acidentes(dataframe):
    acidentes = _preparar_base(dataframe)
    acidentes["data"] = pd.to_datetime(
        acidentes["data"],
        errors="coerce",
    )

    acidentes = acidentes[
        acidentes["data"].isna()
        | acidentes["data"].le(DATA_EXTRACAO)
    ].copy()

    acidentes = _filtrar_coordenadas(acidentes)

    acidentes = _converter_numeros(
        acidentes,
        COLUNAS_NUMERICAS_ACIDENTES,
    )
    acidentes["ano"] = acidentes["data"].dt.year
    acidentes["mes"] = acidentes["data"].dt.month
    acidentes["dia_mes"] = acidentes["data"].dt.day
    acidentes["dia_sem_normalizado"] = (
        acidentes["dia_sem"]
        .astype("string")
        .str.strip()
        .str.lower()
    )
    acidentes["fim_de_semana"] = acidentes["dia_sem_normalizado"].isin(
        ["sábado", "sabado", "domingo"]
    )
    acidentes["acidente_grave"] = (
        acidentes["feridos_gr"].fillna(0).gt(0)
        | acidentes["mortes"].fillna(0).gt(0)
    )
    acidentes["acidente_fatal"] = acidentes["mortes"].fillna(0).gt(0)
    return acidentes


def preparar_vitimas(dataframe):
    vitimas = _preparar_base(dataframe)
    vitimas["data"] = pd.to_datetime(
        vitimas["data"],
        errors="coerce",
    )
    vitimas = vitimas[
        vitimas["data"].isna()
        | vitimas["data"].le(DATA_EXTRACAO)
    ].copy()
    vitimas = _filtrar_coordenadas(vitimas)
    return _converter_numeros(vitimas, COLUNAS_NUMERICAS_VITIMAS)


def preparar_sinalizacao(dataframe):
    sinalizacao = _preparar_base(dataframe)
    sinalizacao = _filtrar_coordenadas(sinalizacao)
    return _converter_numeros(sinalizacao, COLUNAS_NUMERICAS_SINALIZACAO)


def preparar_bases(base_dir):
    brutos = ler_dados_brutos(base_dir)
    tratados = {
        "acidentes": preparar_acidentes(brutos["acidentes"]),
        "vitimas": preparar_vitimas(brutos["vitimas"]),
        "sinalizacao": preparar_sinalizacao(brutos["sinalizacao"]),
    }
    return brutos, tratados
