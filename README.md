# Dashboard de Acidentes de Trânsito — Porto Alegre

Dashboard interativo desenvolvido com Streamlit para explorar acidentes de trânsito registrados em Porto Alegre.

## Objetivo

A aplicação permite analisar:

- quantidade de acidentes por ano, tipo, mês, dia da semana e horário;
- acidentes graves, feridos e mortes;
- concentração espacial das ocorrências (pontos, mapa de calor e sinalização);
- dados das três bases (acidentes, sinalização gráfica e vítimas), filtrados ou completos;
- relação entre os acidentes e a sinalização gráfica próxima (aba "Sinalização × Acidentes"): densidade e combinações de sinais, razões ajustadas, distância ao sinal mais próximo, horário, antes e depois de uma implantação, vítimas e ranking de pontos críticos para priorização.

## Estrutura do projeto

```text
IA001.1/
├── app.py                      # aplicação Streamlit (abas, filtros e textos)
├── pipeline_dados.py           # leitura e tratamento das três bases
├── graficos.py                 # gráficos (Altair)
├── mapas.py                    # mapas (Folium)
├── relacao_espacial.py         # relação espacial acidentes × sinalização e estatísticas
├── atividade01_proposta_analise_visual.ipynb
├── requirements.txt
├── .streamlit/config.toml      # configuração do Streamlit
├── dados/
│   ├── cat_acidentes.csv       # acidentes de trânsito
│   ├── cat_vitimas.csv         # vítimas de acidentes
│   └── websin.csv              # sinalização gráfica
├── doc/                        # dicionários de dados (PDF) das três bases
└── maps/                       # mapa exportado pelo notebook
```

## Requisitos

- Python 3.10 ou superior (testado com Python 3.10)
- pip
- Em Debian e Ubuntu, o pacote `python3-venv` (para criar o ambiente virtual)

## Instalação

No terminal, execute:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Se o primeiro comando falhar com a mensagem "ensurepip is not available", instale o pacote do sistema e repita:

```bash
sudo apt install python3-venv
```

O `requirements.txt` fixa as versões das bibliotecas com as quais o dashboard e o notebook foram testados do início ao fim em uma instalação limpa. Versões mais novas costumam funcionar, mas não foram testadas.

## Execução

Pelo notebook: executar todas as células em sequência. A célula da seção 5.7 inicia o Streamlit e, se já houver um rodando na porta 8501, encerra e inicia de novo para exibir a versão mais recente do código.

Ou, com o ambiente virtual ativado:

```bash
streamlit run app.py
```

Depois, acesse no navegador:

```text
http://localhost:8501
```

## Interações disponíveis

**Barra lateral** (vale para o dashboard inteiro, salvo indicação):

- **Ano:** uma caixa de seleção por ano, em duas linhas (da esquerda para a direita e de cima para baixo), todas marcadas no início, com os botões "Selecionar tudo" e "Desmarcar tudo";
- **Mostrar somente acidentes graves:** não se aplica à aba "Sinalização × Acidentes", que compara graves com os demais;
- **Ir para a pergunta:** cinco atalhos, logo abaixo desse filtro, que abrem a aba "Sinalização × Acidentes" na subaba da pergunta escolhida;
- **Raio da sinalização (m):** de 0 a 300 m, de 1 em 1, usado para contar os sinais próximos de cada acidente. Vale só para a aba "Sinalização × Acidentes". Um mapa pequeno mostra o círculo do raio, em escala, em volta do Mercado Público de Porto Alegre.

**Abas:**

- **Visão geral:** indicadores, acidentes por ano, vítimas fatais por ano, acidentes por tipo, mês e dias úteis × fim de semana.
- **Mapas:** painel "Visualização" no mapa para alternar entre os pontos dos acidentes, o mapa de calor e a sinalização (agrupada por categoria e por zoom), e botão para centralizar o mapa.
- **Sinalização × Acidentes:** cinco subabas, uma para cada pergunta do projeto, cada uma com o texto da pergunta e os gráficos que a respondem.
  - **Tipos e conjuntos** (pergunta 1): resumo por categoria de sinal, combinações de sinalização (com seletor de quantas mostrar), pares de sinal e ocorrência e antes e depois da implantação (categoria e janela de 6 a 24 meses).
  - **Zonas e distância** (pergunta 2): mapa dos acidentes graves, ranking das zonas mais críticas (tamanho da área, ordenação, mínimo de graves, quantidade e download em CSV) e distância ao sinal mais próximo.
  - **Densidade** (pergunta 3): porcentagem de graves por quantidade de sinais, por tipo de acidente e por região (com seletor de tipo), e comparação entre acidentes parecidos (razão ajustada).
  - **Horário** (pergunta 4): mapa de calor por dia da semana e horário, com filtros de **tipo de acidente** e **só acidentes com vítimas** e realce das células com mais acidentes; como complemento, comparação entre dia e noite e entre marcações e placas.
  - **Vítimas** (pergunta 5): vítimas por papel e densidade, pares de vítima e sinal e a opção de considerar só acidentes com uma vítima.
- **Análise de dados:** frequências por categoria e distribuições das variáveis numéricas, com escolha da base (acidentes, vítimas ou sinalização).
- **Dados:** tabelas de acidentes, sinalização e vítimas, em duas visões: **Filtrado** (base tratada, com os filtros da barra lateral) e **Completo** (CSV original, sem tratamento).

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

As vítimas são ligadas aos acidentes por `idacidente` e herdam a gravidade do acidente (a tabela de vítimas não traz gravidade individual). A sinalização é cruzada com os acidentes por proximidade (coordenadas), mas o cadastro traz apenas os sinais em vigor na data da extração e não há dados de fluxo e velocidade das vias.

Portanto, a aplicação não permite concluir que determinado tipo de sinalização causa ou evita acidentes: as comparações são associações. Os resultados são exploratórios e dependem da qualidade e da cobertura dos registros disponibilizados pela EPTC.

## Tecnologias utilizadas

- Python
- Pandas e NumPy
- Streamlit
- Altair (gráficos)
- Folium e Streamlit-Folium (mapas)
- SciPy (busca espacial dos sinais próximos a cada acidente)
- Matplotlib e Seaborn (análises do notebook)

## Autoria

Rafael Fernandes Borges