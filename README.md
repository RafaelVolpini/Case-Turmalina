# Turmalina Café Dashboard de Análise de Lojas

Dashboard desenvolvido para apoiar a priorização semanal das lojas da rede **Turmalina Café**, utilizando os dados fornecidos pelos 4 csv na pasta Data.

## Requisitos

- Python >= **3.12.3**

## Tecnologias

- FastAPI
- Uvicorn
- Jinja2
- Pandas
- Plotly
- HTML5
- CSS3

## Estrutura do Projeto

```text
Case-Turmalina/
├── app/                # Aplicação FastAPI
├── data/               # Arquivos CSV
├── docs/               # Documentação
├── prototipos/         # Protótipos
├── styles/             # Arquivos CSS
├── templates/          # Templates Jinja2
├── README.md
├── requirements.txt
└── .gitignore
```

## Como executar

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt

uvicorn app.main:app --reload
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

uvicorn app.main:app --reload
```

Acesse a aplicação em:

```text
http://127.0.0.1:8000
```

## Funcionalidades

- Priorização semanal das lojas.
- Análise individual das unidades.
- Comparativo entre lojas.
- Visualização de indicadores e gráficos.
- Leitura automática dos arquivos CSV localizados em `data/`.
