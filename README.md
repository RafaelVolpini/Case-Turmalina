# Turmalina Café -- Dashboard de Análise de Lojas

Stack: **FastAPI** (backend + rotas) + **Jinja2** (SSR) + **HTMX** (interatividade sem reload) +
**CSS puro** (`styles/main.css`, sem build step). Gráficos renderizados no servidor com
**matplotlib** (sem lib de gráficos em JS). Dados lidos diretamente dos 4 CSVs em `data/`, sem
edição manual.

## Rodar o projeto
Só precisa de Python -- não há passo de front-end (sem npm, sem build de CSS/JS).
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Acesse **http://127.0.0.1:8000**.

## Estrutura
- `app/` -- FastAPI (`main.py`), rotas + fragmentos HTMX (`routes.py`), limpeza dos CSVs
  (`data_loader.py`) e geração dos gráficos (`charts.py`).
- `templates/` -- Jinja2 (`base.html` + `pages/` + `components/`).
- `styles/main.css` -- todo o CSS do projeto, servido como estático em `/styles/main.css`.
- `data/` -- os 4 CSVs originais, sem edição.

## O que já funciona
- Sidebar com as 14 lojas ordenadas por margem (30 dias); clique carrega a análise via HTMX.
- Tela "Análise Individual": KPIs de faturamento (vs. meta da loja), margem (com rótulo de
  status: Estável / Em queda / Desvio crítico) e avaliação média (com tendência), badge de
  "Risco Crítico" quando a margem é negativa ou cai >= 3 p.p. frente aos 30 dias anteriores, e
  dois gráficos: desvio semanal de faturamento vs. média histórica, e volume/nota de avaliações.
- Tela "Comparativo de Lojas": dois seletores atualizados via HTMX, KPIs lado a lado com ponto
  colorido por loja, e dois gráficos comparando desvio de margem e nota média entre as lojas.
- Botão "Generate Report" no header abre um modal (`<dialog>` nativo) com uma tabela-resumo das
  14 lojas e as que estão em risco crítico, carregado via HTMX.
- Tooltips (ex.: aba "Prioridades", ícones do header) são CSS puro via `data-tooltip`, sem JS.

## Limitações conhecidas / premissas
Ver comentário no topo de `app/data_loader.py` para as regras de limpeza aplicadas aos CSVs
(datas em três formatos, moeda em `R$ 1.234,56`, texto livre no campo de nota, sentinela de
totem travado em `tempo_espera_min`). O limite de "risco crítico" (margem negativa ou queda de
3 p.p.) é uma premissa de projeto, não um valor fornecido pela Turmalina.
