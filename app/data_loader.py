"""
Carrega e consolida os 4 CSVs da Rede Turmalina Café.

Os arquivos são exportações reais de sistemas distintos (franquias, PDV,
estoque, avaliações) e chegam sem qualquer tratamento -- formatos de data,
moeda e texto livre inconsistentes dentro do mesmo arquivo. Este módulo
concentra toda a limpeza para que as rotas só lidem com dados já tipados.

Premissas de tratamento (documentadas por serem decisões de projeto, não
"a verdade" dos dados):
- Datas mistas (ISO, DD/MM/YYYY, DD.MM.YYYY) são resolvidas tentando os
  três formatos nessa ordem; o que não parsear em nenhum vira NaT.
- `status` de loja com valor "1" é tratado como "ativa" (falha de digitação
  no cadastro manual, conforme nota de exportação).
- `nota` de avaliação aceita separador decimal "," ou "."; valores fora de
  [1, 5] após conversão são descartados (herança do campo livre da versão
  antiga do app).
- `tempo_espera_min` >= 120 é tratado como falha de leitura do totem e
  descartado da média (o enunciado cita explicitamente que o totem trava).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y")


def parse_date_flex(series: pd.Series) -> pd.Series:
    """Tenta múltiplos formatos de data conhecidos nos exports da Turmalina."""
    result = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    remaining = series.astype(str).str.strip()
    for fmt in DATE_FORMATS:
        mask = result.isna() & remaining.notna()
        parsed = pd.to_datetime(remaining[mask], format=fmt, errors="coerce")
        result.loc[parsed.index] = parsed
    return result


def parse_brl_currency(series: pd.Series) -> pd.Series:
    """'R$ 168.000,00' -> 168000.00"""
    cleaned = (
        series.astype(str)
        .str.replace("R$", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def parse_decimal_comma(series: pd.Series) -> pd.Series:
    """Números que podem vir com vírgula decimal ('4,0') ou ponto (4.0)."""
    cleaned = series.astype(str).str.strip().str.replace(",", ".", regex=False)
    return pd.to_numeric(cleaned, errors="coerce")


def extract_leading_int(series: pd.Series) -> pd.Series:
    """'12 (sendo 2 PJ)' -> 12 ; '58m2' -> 58 ; '74,0' -> 74"""
    extracted = series.astype(str).str.extract(r"(\d+(?:[.,]\d+)?)")[0]
    return parse_decimal_comma(extracted)


def normalize_text(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower()


@lru_cache(maxsize=1)
def load_lojas() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "turmalina_lojas.csv")
    df["data_abertura"] = parse_date_flex(df["data_abertura"])
    df["area_m2"] = extract_leading_int(df["area_m2"])
    df["num_funcionarios"] = extract_leading_int(df["num_funcionarios"])
    df["meta_faturamento_mensal"] = parse_brl_currency(df["meta_faturamento_mensal"])

    formato_norm = normalize_text(df["formato"])
    df["formato_norm"] = formato_norm.map(
        lambda v: "Quiosque" if "quiosk" in v or "quiosque" in v or "kiosk" in v
        else "Shopping" if "shopping" in v
        else "Rua"
    )

    modelo_norm = normalize_text(df["modelo"])
    df["modelo_norm"] = modelo_norm.map(lambda v: "Franquia" if "franq" in v else "Própria")

    status_norm = normalize_text(df["status"])
    df["ativa"] = status_norm.isin(["ativa", "1", "true", "ativo"])

    df["nome_loja"] = df["nome_loja"].astype(str).str.strip()
    return df


@lru_cache(maxsize=1)
def load_vendas() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "turmalina_vendas_diarias.csv")
    df["data"] = parse_date_flex(df["data"])
    numeric_cols = [
        "faturamento_bruto", "descontos", "num_tickets",
        "horas_trabalhadas_equipe", "custo_insumos", "valor_desperdicio",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["data", "id_loja"])
    df["margem_pct"] = (
        (df["faturamento_bruto"] - df["custo_insumos"]) / df["faturamento_bruto"] * 100
    )
    return df


@lru_cache(maxsize=1)
def load_avaliacoes() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "turmalina_avaliacoes.csv")
    df["data"] = parse_date_flex(df["data"])
    df["nota"] = parse_decimal_comma(df["nota"])
    df.loc[~df["nota"].between(1, 5), "nota"] = pd.NA
    df["tempo_espera_min"] = pd.to_numeric(df["tempo_espera_min"], errors="coerce")
    df.loc[df["tempo_espera_min"] >= 120, "tempo_espera_min"] = pd.NA
    return df


@lru_cache(maxsize=1)
def load_itens() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "turmalina_itens.csv")
    df["categoria"] = df["categoria"].astype(str).str.strip().str.title()
    df["preco_medio"] = parse_brl_currency(df["preco_medio"])
    df["custo_unitario"] = pd.to_numeric(df["custo_unitario"], errors="coerce")
    df["quantidade_vendida"] = pd.to_numeric(df["quantidade_vendida"], errors="coerce")
    return df


MARGEM_QUEDA_CRITICA_PP = 3.0  # queda >= 3 p.p. entre janelas de 30 dias, ou margem negativa
N_SEMANAS_TENDENCIA = 8


def _janela_metrics(vendas_loja: pd.DataFrame, fim: pd.Timestamp, dias: int = 30) -> dict:
    inicio = fim - pd.Timedelta(days=dias - 1)
    janela = vendas_loja[(vendas_loja["data"] >= inicio) & (vendas_loja["data"] <= fim)]
    faturamento = janela["faturamento_bruto"].sum()
    custo = janela["custo_insumos"].sum()
    margem = (faturamento - custo) / faturamento * 100 if faturamento else 0.0
    return {"faturamento": faturamento, "margem": margem, "dias_com_venda": len(janela)}


def _add_rotulos(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)
    df["rotulo"] = [f"S-{n - 1 - i}" if i < n - 1 else "Atual" for i in range(n)]
    return df


def weekly_desvio_faturamento(id_loja: str, n_semanas: int = N_SEMANAS_TENDENCIA) -> tuple[pd.DataFrame, float]:
    """Desvio (%) do faturamento médio diário de cada semana vs. a média histórica da própria loja."""
    vendas_loja = load_vendas()[load_vendas()["id_loja"] == id_loja].sort_values("data").copy()
    media_historica = vendas_loja["faturamento_bruto"].mean()
    vendas_loja["semana"] = vendas_loja["data"].dt.to_period("W").apply(lambda p: p.start_time)
    semanal = vendas_loja.groupby("semana").agg(faturamento_medio=("faturamento_bruto", "mean")).reset_index()
    semanal["desvio_pct"] = (semanal["faturamento_medio"] - media_historica) / media_historica * 100
    semanal = semanal.sort_values("semana").tail(n_semanas).reset_index(drop=True)
    return _add_rotulos(semanal), media_historica


def weekly_desvio_margem(id_loja: str, n_semanas: int = N_SEMANAS_TENDENCIA) -> tuple[pd.DataFrame, float]:
    """Desvio (p.p.) da margem semanal sobre insumos vs. a média histórica da própria loja."""
    vendas_loja = load_vendas()[load_vendas()["id_loja"] == id_loja].sort_values("data").copy()
    media_historica_margem = (
        (vendas_loja["faturamento_bruto"].sum() - vendas_loja["custo_insumos"].sum())
        / vendas_loja["faturamento_bruto"].sum() * 100
    )
    vendas_loja["semana"] = vendas_loja["data"].dt.to_period("W").apply(lambda p: p.start_time)
    semanal = vendas_loja.groupby("semana").agg(
        faturamento=("faturamento_bruto", "sum"), custo=("custo_insumos", "sum"),
    ).reset_index()
    semanal["margem_pct"] = (semanal["faturamento"] - semanal["custo"]) / semanal["faturamento"] * 100
    semanal["desvio_pp"] = semanal["margem_pct"] - media_historica_margem
    semanal = semanal.sort_values("semana").tail(n_semanas).reset_index(drop=True)
    return _add_rotulos(semanal), media_historica_margem


def weekly_avaliacoes(id_loja: str, n_semanas: int = N_SEMANAS_TENDENCIA) -> pd.DataFrame:
    """Nota média e volume de avaliações por semana."""
    aval_loja = load_avaliacoes()
    aval_loja = aval_loja[aval_loja["id_loja"] == id_loja].dropna(subset=["data"]).copy()
    aval_loja["semana"] = aval_loja["data"].dt.to_period("W").apply(lambda p: p.start_time)
    semanal = aval_loja.groupby("semana").agg(
        nota_media=("nota", "mean"), volume=("nota", "count"),
    ).reset_index()
    semanal = semanal.sort_values("semana").tail(n_semanas).reset_index(drop=True)
    return _add_rotulos(semanal)


def monthly_faturamento(id_loja: str) -> pd.DataFrame:
    """Faturamento somado por mês -- para o gráfico 'faturamento por mês' do comparativo."""
    vendas_loja = load_vendas()[load_vendas()["id_loja"] == id_loja].copy()
    vendas_loja["mes"] = vendas_loja["data"].dt.to_period("M").dt.to_timestamp()
    mensal = vendas_loja.groupby("mes").agg(faturamento=("faturamento_bruto", "sum")).reset_index()
    return mensal.sort_values("mes").reset_index(drop=True)


NOTA_CRITICA = 3.0  # abaixo disso, o comentário entra na lista de "avaliações críticas"


def comentarios_criticos(id_loja: str, limit: int = 5) -> list[dict]:
    """
    Comentários de avaliações com nota baixa (< 3) e texto preenchido -- ajuda a
    entender O PORQUÊ da nota, não só o número. Muitas avaliações vêm sem
    comentário (campo de texto livre, nem sempre preenchido); essas são
    descartadas aqui por não agregarem contexto.
    """
    aval = load_avaliacoes()
    aval_loja = aval[
        (aval["id_loja"] == id_loja)
        & (aval["nota"] < NOTA_CRITICA)
        & aval["comentario"].notna()
        & (aval["comentario"].astype(str).str.strip() != "")
    ].sort_values("data", ascending=False)

    return [
        {
            "data": row["data"],
            "nota": row["nota"],
            "canal": row["canal"],
            "comentario": row["comentario"],
        }
        for _, row in aval_loja.head(limit).iterrows()
    ]


def _tendencia_avaliacao(semanal: pd.DataFrame) -> str:
    """Compara a metade mais recente das semanas com a metade anterior."""
    notas = semanal["nota_media"].dropna()
    if len(notas) < 2:
        return "Sem dados suficientes"
    metade = len(notas) // 2 or 1
    recente = notas.tail(metade).mean()
    anterior = notas.head(len(notas) - metade).mean()
    delta = recente - anterior
    if delta <= -0.2:
        return "Tendência de queda"
    if delta >= 0.2:
        return "Tendência de alta"
    return "Estável"


def _status_margem(margem_atual: float, variacao_pp: float) -> str:
    if margem_atual < 0 or variacao_pp <= -MARGEM_QUEDA_CRITICA_PP:
        return "Desvio crítico"
    if variacao_pp < 0:
        return "Em queda"
    if variacao_pp > MARGEM_QUEDA_CRITICA_PP:
        return "Em alta"
    return "Estável"


def list_stores_summary() -> list[dict]:
    lojas = load_lojas()
    vendas = load_vendas()
    fim = vendas["data"].max()

    resumo = []
    for _, loja in lojas.iterrows():
        vendas_loja = vendas[vendas["id_loja"] == loja["id_loja"]].sort_values("data")
        if vendas_loja.empty:
            continue
        atual = _janela_metrics(vendas_loja, fim)
        resumo.append({
            "id_loja": loja["id_loja"],
            "nome_loja": loja["nome_loja"],
            "faturamento_30d": round(atual["faturamento"], 2),
            "margem_30d": round(atual["margem"], 1),
            "risco_critico": atual["margem"] < 0,
        })
    return sorted(resumo, key=lambda x: x["margem_30d"])


def store_metrics(id_loja: str) -> dict:
    lojas = load_lojas()
    vendas = load_vendas()
    avaliacoes = load_avaliacoes()

    loja_row = lojas[lojas["id_loja"] == id_loja].iloc[0]
    vendas_loja = vendas[vendas["id_loja"] == id_loja].sort_values("data")
    fim = vendas_loja["data"].max()
    inicio_anterior_fim = fim - pd.Timedelta(days=30)

    atual = _janela_metrics(vendas_loja, fim, 30)
    anterior = _janela_metrics(vendas_loja, inicio_anterior_fim, 30)

    variacao_margem_pp = atual["margem"] - anterior["margem"]
    risco_critico = atual["margem"] < 0 or variacao_margem_pp <= -MARGEM_QUEDA_CRITICA_PP

    meta_mensal = loja_row["meta_faturamento_mensal"]
    variacao_faturamento_vs_meta_pct = (
        (atual["faturamento"] - meta_mensal) / meta_mensal * 100
        if pd.notna(meta_mensal) and meta_mensal else None
    )

    aval_loja = avaliacoes[avaliacoes["id_loja"] == id_loja]
    aval_janela = aval_loja[aval_loja["data"] >= (fim - pd.Timedelta(days=90))]
    avaliacao_media = aval_janela["nota"].mean()
    tempo_espera_medio = aval_janela["tempo_espera_min"].mean()
    tendencia_avaliacao = _tendencia_avaliacao(weekly_avaliacoes(id_loja))

    return {
        "id_loja": id_loja,
        "nome_loja": loja_row["nome_loja"],
        "cidade_uf": loja_row["cidade_uf"],
        "formato": loja_row["formato_norm"],
        "modelo": loja_row["modelo_norm"],
        "meta_faturamento_mensal": meta_mensal,
        "faturamento_30d": round(atual["faturamento"], 2),
        "variacao_faturamento_vs_meta_pct": (
            round(variacao_faturamento_vs_meta_pct, 1) if variacao_faturamento_vs_meta_pct is not None else None
        ),
        "margem_30d": round(atual["margem"], 1),
        "variacao_margem_pp": round(variacao_margem_pp, 1),
        "status_margem": _status_margem(atual["margem"], variacao_margem_pp),
        "risco_critico": risco_critico,
        "avaliacao_media": round(avaliacao_media, 1) if pd.notna(avaliacao_media) else None,
        "avaliacao_count": int(aval_janela["nota"].notna().sum()),
        "tempo_espera_medio": round(tempo_espera_medio, 1) if pd.notna(tempo_espera_medio) else None,
        "tendencia_avaliacao": tendencia_avaliacao,
        "periodo_fim": fim,
        "periodo_inicio": fim - pd.Timedelta(days=29),
    }


def list_lojas_options() -> list[dict]:
    lojas = load_lojas()
    return lojas[["id_loja", "nome_loja"]].to_dict("records")


N_LOJAS_INTERVENCAO = 2  # "a estrutura atual sustenta ação efetiva em, no máximo, duas lojas por semana"


def _indice_prioridade(m: dict) -> tuple[float, list[str]]:
    """
    Combina os sinais que os 4 CSVs sustentam num único índice de priorização,
    para ordenar as 14 lojas por urgência de intervenção. Pesos e limites são
    premissa de projeto (não fornecidos pela Turmalina) e ficam documentados aqui:
    - margem negativa nos últimos 30 dias pesa mais que qualquer outro sinal;
    - queda de margem (p.p.) e desvio de faturamento vs. meta contam proporcionalmente;
    - nota média abaixo de 3,5 e tendência de queda nas avaliações somam pontos fixos.
    """
    score = 0.0
    motivos: list[tuple[float, str]] = []

    if m["margem_30d"] < 0:
        score += 40
        motivos.append((40, "Margem negativa nos últimos 30 dias"))
    elif m["variacao_margem_pp"] <= -MARGEM_QUEDA_CRITICA_PP:
        peso = min(30, abs(m["variacao_margem_pp"]) * 3)
        score += peso
        motivos.append((peso, f"Queda de {abs(m['variacao_margem_pp']):.1f} p.p. na margem"))
    elif m["variacao_margem_pp"] < 0:
        score += abs(m["variacao_margem_pp"])

    if m["variacao_faturamento_vs_meta_pct"] is not None and m["variacao_faturamento_vs_meta_pct"] < -10:
        peso = min(20, abs(m["variacao_faturamento_vs_meta_pct"]) * 0.6)
        score += peso
        motivos.append((peso, f"Faturamento {abs(m['variacao_faturamento_vs_meta_pct']):.0f}% abaixo da meta"))

    if m["avaliacao_media"] is not None and m["avaliacao_media"] < 3.5:
        peso = (3.5 - m["avaliacao_media"]) * 10
        score += peso
        motivos.append((peso, f"Avaliação média baixa ({m['avaliacao_media']:.1f}/5)"))

    if m["tendencia_avaliacao"] == "Tendência de queda":
        score += 8
        motivos.append((8, "Avaliações em tendência de queda"))

    motivos.sort(key=lambda t: -t[0])
    return round(score, 1), [texto for _, texto in motivos[:2]] or ["Sem sinais críticos no período"]


def list_prioridades() -> dict:
    """Ranking das 14 lojas por índice de prioridade -- tela 'Prioridades'."""
    ranking = []
    for opt in list_lojas_options():
        m = store_metrics(opt["id_loja"])
        score, motivos = _indice_prioridade(m)
        ranking.append({**m, "indice_prioridade": score, "motivos": motivos})

    ranking.sort(key=lambda r: -r["indice_prioridade"])
    return {
        "criticas": ranking[:N_LOJAS_INTERVENCAO],
        "outras": ranking[N_LOJAS_INTERVENCAO:],
    }
