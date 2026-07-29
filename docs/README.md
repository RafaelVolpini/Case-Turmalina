# Turmalina -- Priorização Semanal (protótipo)

## Como rodar
```
pip install flask pandas plotly
python app.py
```
Depois abra http://127.0.0.1:5000 no navegador.

## O que já funciona
- Lista as 14 lojas ordenadas pelo desvio médio de faturamento nos últimos 30 dias vs. a própria média histórica.
- Clicar em uma loja carrega, via HTMX (sem reload de página), um gráfico Plotly do desvio diário dela ao longo de todo o período.

## O que ainda falta (próximos passos)
- O cálculo de desvio aqui é um rascunho (média histórica simples) -- a fórmula final do Índice de Prioridade ainda vai ser fechada no documento de projeto.
- Falta o ranking final (top 2 lojas) e os sinais de Margem/Cliente/Equipe combinados.
