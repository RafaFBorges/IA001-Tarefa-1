# Dashboard de Acidentes de Trânsito — Porto Alegre

Dashboard interativo desenvolvido com Streamlit para explorar acidentes de trânsito registrados em Porto Alegre.

## Objetivo

A aplicação permite analisar:

- quantidade de acidentes por ano;
- acidentes graves;
- quantidade de feridos e mortes;
- distribuição dos acidentes por tipo;
- concentração espacial das ocorrências;
- dados filtrados por período e gravidade.

## Estrutura do projeto

```text
IA001.1/
├── app.py
├── atividade01_proposta_analise_visual.ipynb
├── requirements.txt
├── dados/
│   └── cat_acidentes.csv
└── maps/
```

## Requisitos

- Python 3.10 ou superior
- pip

## Instalação

No terminal, execute:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Execução

Rodar todas as células na sequencia.

ou 

Com o ambiente virtual ativado:

```bash
streamlit run app.py
```

Depois, acesse no navegador:

```text
http://localhost:8501
```

## Interações disponíveis

O dashboard possui filtros para:

- selecionar o ano;
- visualizar todos os acidentes ou somente acidentes graves.

Quando uma combinação de filtros não possui registros, a aplicação informa o usuário.

## Dados utilizados

Os dados são provenientes da Empresa Pública de Transporte e Circulação (EPTC) e da Prefeitura Municipal de Porto Alegre.

Fonte dos acidentes:

https://dadosabertos.poa.br/dataset/acidentes-de-transito-acidentes

Fonte das vítimas:

https://dadosabertos.poa.br/dataset/acidentes-de-transito-vitimas

Fonte da sinalização gráfica:

https://dadosabertos.poa.br/dataset/sinalizacao-grafica

Os arquivos CSV foram baixados em 21 de setembro de 2026.

## Tratamento dos dados

Foram realizadas as seguintes etapas:

- conversão e validação das datas;
- remoção de registros posteriores à data de extração;
- classificação de acidentes graves;
- tratamento das coordenadas geográficas;
- remoção de duplicatas completas;
- criação de indicadores de feridos e mortes.

Um acidente foi considerado grave quando possuía pelo menos um ferido grave ou uma morte registrada.

## Limitações

A aplicação utiliza principalmente a tabela de acidentes. Apesar de as bases de vítimas e sinalização gráfica terem sido analisadas no notebook, elas ainda não são cruzadas diretamente no dashboard.

Portanto, a aplicação não permite concluir que determinado tipo de sinalização causa ou evita acidentes. Os resultados são exploratórios e dependem da qualidade e da cobertura dos registros disponibilizados pela EPTC.

## Tecnologias utilizadas

- Python
- Pandas
- Streamlit
- Folium
- Streamlit-Folium

## Autoria

Rafael Fernandes Borges