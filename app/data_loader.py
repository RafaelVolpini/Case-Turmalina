"""Carrega e consolida os 4 CSVs da Rede Turmalina Café, sem editar os originais.
Entrada: nenhuma (lê os CSVs de DATA_DIR).
Retorno: módulo expõe funções load_* que devolvem pandas.DataFrame já tipado e normalizado."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y")


def parse_date_flex(series: pd.Series) -> pd.Series:
    """Converte uma coluna de datas testando múltiplos formatos até encontrar um que funcione.
    Entrada: series (pd.Series) de strings de data em formatos variados.
    Retorno: pd.Series de datas (datetime64[ns]); NaT onde nenhum formato bateu."""
    result = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    remaining = series.astype(str).str.strip()
    for fmt in DATE_FORMATS:
        mask = result.isna() & remaining.notna()
        parsed = pd.to_datetime(remaining[mask], format=fmt, errors="coerce")
        result.loc[parsed.index] = parsed
    return result


def parse_brl_currency(series: pd.Series) -> pd.Series:
    """Converte texto de moeda em formato brasileiro para número.
    Entrada: series (pd.Series) de strings tipo "R$ 168.000,00".
    Retorno: pd.Series de float; NaN onde não converteu."""
    cleaned = (
        series.astype(str)
        .str.replace("R$", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def parse_decimal_comma(series: pd.Series) -> pd.Series:
    """Converte texto numérico com vírgula ou ponto decimal para float.
    Entrada: series (pd.Series) de strings numéricas.
    Retorno: pd.Series de float; NaN onde não converteu."""
    cleaned = series.astype(str).str.strip().str.replace(",", ".", regex=False)
    return pd.to_numeric(cleaned, errors="coerce")


def extract_leading_int(series: pd.Series) -> pd.Series:
    """Extrai o primeiro número de um texto com sufixo ou observação.
    Entrada: series (pd.Series) de strings tipo "12 (sendo 2 PJ)" ou "58m2".
    Retorno: pd.Series de float; NaN onde não achou número."""
    extracted = series.astype(str).str.extract(r"(\d+(?:[.,]\d+)?)")[0]
    return parse_decimal_comma(extracted)


def normalize_text(series: pd.Series) -> pd.Series:
    """Normaliza texto para minúsculo, sem espaços nas pontas.
    Entrada: series (pd.Series) de strings.
    Retorno: pd.Series de strings."""
    return series.astype(str).str.strip().str.lower()


def normalize_id_loja(series: pd.Series) -> pd.Series:
    """Normaliza id_loja para maiúsculo, sem espaços ou hífen, padrão usado nos outros CSVs.
    Entrada: series (pd.Series) de strings de id_loja.
    Retorno: pd.Series de strings em maiúsculo (ex.: "lj-13" e "LJ-13" viram "LJ13", igual a "LJ13")."""
    return series.astype(str).str.strip().str.upper().str.replace("-", "", regex=False)


_NUMEROS_POR_EXTENSO = {
    "um": 1, "uma": 1,
    "dois": 2, "duas": 2,
    "tres": 3, "três": 3,
    "quatro": 4,
    "cinco": 5,
}


def parse_nota(series: pd.Series) -> pd.Series:
    """Converte nota de avaliação (número, decimal, sufixo ou por extenso) para float.
    Entrada: series (pd.Series) de strings de nota em formatos variados.
    Retorno: pd.Series de float; NaN onde não converteu."""
    texto = series.astype(str).str.strip().str.lower()
    numerico = (
        texto.str.replace("estrelas", "", regex=False)
        .str.replace("estrela", "", regex=False)
        .str.strip()
        .str.replace(",", ".", regex=False)
    )
    numerico = pd.to_numeric(numerico, errors="coerce")
    por_extenso = texto.map(_NUMEROS_POR_EXTENSO)
    return numerico.fillna(por_extenso)


_CANAIS_CANONICOS = {
    "app": "App",
    "google": "Google",
    "google maps": "Google",
    "totem na loja": "Totem na loja",
}


def normalize_canal(series: pd.Series) -> pd.Series:
    """Normaliza canal de avaliação pra um rótulo canônico por dicionário de apelidos.
    Entrada: series (pd.Series) de strings de canal.
    Retorno: pd.Series de strings com o rótulo canônico."""
    texto = series.astype(str).str.strip().str.lower()
    return texto.map(lambda v: _CANAIS_CANONICOS.get(v, v.title()))


_PALAVRAS_FORMATO = {
    "quiosque": "Quiosque", "quiosk": "Quiosque", "kiosk": "Quiosque",
    "shopping": "Shopping",
    "rua": "Rua",
}


def _classificar_formato(texto: str) -> str:
    """Classifica o formato de loja por palavra-chave num texto normalizado.
    Entrada: texto (str) já normalizado (minúsculo, sem espaços nas pontas).
    Retorno: str com o formato padronizado, ou o texto original em title case."""
    for palavra, formato in _PALAVRAS_FORMATO.items():
        if palavra in texto:
            return formato
    return texto.title()  # não reconhecido: mantém visível, não mascara como "Rua"


@lru_cache(maxsize=1)
def load_lojas() -> pd.DataFrame:
    """Lê e normaliza turmalina_lojas.csv.
    Entrada: nenhuma (lê DATA_DIR/turmalina_lojas.csv).
    Retorno: pd.DataFrame com colunas tipadas e normalizadas."""
    df = pd.read_csv(DATA_DIR / "turmalina_lojas.csv")
    df["data_abertura"] = parse_date_flex(df["data_abertura"])
    df["area_m2"] = extract_leading_int(df["area_m2"])
    df["num_funcionarios"] = extract_leading_int(df["num_funcionarios"])
    df["meta_faturamento_mensal"] = parse_brl_currency(df["meta_faturamento_mensal"])

    formato_norm = normalize_text(df["formato"])
    df["formato_norm"] = formato_norm.map(_classificar_formato)

    modelo_norm = normalize_text(df["modelo"])
    df["modelo_norm"] = modelo_norm.map(lambda v: "Franquia" if "franq" in v else "Própria")

    status_norm = normalize_text(df["status"])
    df["ativa"] = status_norm.isin(["ativa", "1", "true", "ativo"])

    df["nome_loja"] = df["nome_loja"].astype(str).str.strip()
    df["id_loja"] = normalize_id_loja(df["id_loja"])
    return df


@lru_cache(maxsize=1)
def load_vendas() -> pd.DataFrame:
    """Lê e normaliza turmalina_vendas_diarias.csv.
    Entrada: nenhuma (lê DATA_DIR/turmalina_vendas_diarias.csv).
    Retorno: pd.DataFrame com colunas numéricas tipadas; linhas sem data/id_loja válidos removidas."""
    df = pd.read_csv(DATA_DIR / "turmalina_vendas_diarias.csv")
    df["data"] = parse_date_flex(df["data"])
    df["id_loja"] = normalize_id_loja(df["id_loja"])
    numeric_cols = [
        "faturamento_bruto", "descontos", "num_tickets",
        "horas_trabalhadas_equipe", "custo_insumos", "valor_desperdicio",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["data", "id_loja"])
    return df


@lru_cache(maxsize=1)
def load_avaliacoes() -> pd.DataFrame:
    """Lê e normaliza turmalina_avaliacoes.csv.
    Entrada: nenhuma (lê DATA_DIR/turmalina_avaliacoes.csv).
    Retorno: pd.DataFrame com nota, canal e tempo_espera_min tipados e validados."""
    df = pd.read_csv(DATA_DIR / "turmalina_avaliacoes.csv")
    df["data"] = parse_date_flex(df["data"])
    df["id_loja"] = normalize_id_loja(df["id_loja"])
    df["canal"] = normalize_canal(df["canal"])
    df["nota"] = parse_nota(df["nota"])
    df.loc[~df["nota"].between(1, 5), "nota"] = pd.NA
    df["tempo_espera_min"] = pd.to_numeric(df["tempo_espera_min"], errors="coerce")
    df.loc[df["tempo_espera_min"] >= 120, "tempo_espera_min"] = pd.NA
    return df


@lru_cache(maxsize=1)
def load_itens() -> pd.DataFrame:
    """Lê e normaliza turmalina_itens.csv.
    Entrada: nenhuma (lê DATA_DIR/turmalina_itens.csv).
    Retorno: pd.DataFrame com categoria, preco_medio, custo_unitario e quantidade_vendida tipados."""
    df = pd.read_csv(DATA_DIR / "turmalina_itens.csv")
    df["id_loja"] = normalize_id_loja(df["id_loja"])  # csv tem variante minúscula (lj05), como nos outros arquivos
    df["categoria"] = df["categoria"].astype(str).str.strip().str.title()
    df["preco_medio"] = parse_brl_currency(df["preco_medio"])
    df["custo_unitario"] = pd.to_numeric(df["custo_unitario"], errors="coerce")
    df["quantidade_vendida"] = pd.to_numeric(df["quantidade_vendida"], errors="coerce")
    return df


def pior_categoria_margem(id_loja: str) -> dict | None:
    """Acha a categoria com pior margem de produto de uma loja no mês mais recente disponível em turmalina_itens.csv.
    Margem de produto agregada por categoria = (receita - custo) / receita, com receita/custo ponderados pela
    quantidade vendida de cada produto (não a média simples das margens unitárias).
    Entrada: id_loja (str).
    Retorno: dict com categoria, margem_pct e competencia; None se a loja não tem registro em turmalina_itens.csv."""
    itens_loja = load_itens()[load_itens()["id_loja"] == id_loja]
    if itens_loja.empty:
        return None

    competencia_recente = itens_loja["competencia"].max()
    itens_mes = itens_loja[itens_loja["competencia"] == competencia_recente].copy()
    itens_mes["receita"] = itens_mes["preco_medio"] * itens_mes["quantidade_vendida"]
    itens_mes["custo"] = itens_mes["custo_unitario"] * itens_mes["quantidade_vendida"]

    por_categoria = itens_mes.groupby("categoria").agg(
        receita=("receita", "sum"), custo=("custo", "sum"),
    ).reset_index()
    por_categoria = por_categoria[por_categoria["receita"] > 0]  # receita <= 0 não dá margem definida
    if por_categoria.empty:
        return None

    por_categoria["margem_pct"] = (por_categoria["receita"] - por_categoria["custo"]) / por_categoria["receita"] * 100
    pior = por_categoria.sort_values("margem_pct").iloc[0]
    return {
        "categoria": pior["categoria"],
        "margem_pct": round(pior["margem_pct"], 1),
        "competencia": competencia_recente,
    }


def eficiencia_equipe(id_loja: str) -> dict | None:
    """Calcula faturamento por hora trabalhada da equipe nos últimos 30 dias vs. média histórica da loja.
    Contexto auxiliar -- não gera percentil nem entra no Índice de Prioridade.
    Entrada: id_loja (str).
    Retorno: dict com eficiencia_30d, eficiencia_historica e variacao_pct (R$/hora); None sem horas registradas."""
    vendas_loja = load_vendas()[load_vendas()["id_loja"] == id_loja].sort_values("data")
    if vendas_loja.empty:
        return None

    fim = vendas_loja["data"].max()
    inicio = fim - pd.Timedelta(days=29)
    janela = vendas_loja[(vendas_loja["data"] >= inicio) & (vendas_loja["data"] <= fim)]

    horas_30d = janela["horas_trabalhadas_equipe"].sum()
    horas_historico = vendas_loja["horas_trabalhadas_equipe"].sum()
    if not horas_30d or pd.isna(horas_30d) or not horas_historico or pd.isna(horas_historico):
        return None

    eficiencia_30d = janela["faturamento_bruto"].sum() / horas_30d
    eficiencia_historica = vendas_loja["faturamento_bruto"].sum() / horas_historico
    variacao_pct = (
        (eficiencia_30d - eficiencia_historica) / eficiencia_historica * 100
        if eficiencia_historica else None
    )
    return {
        "eficiencia_30d": round(eficiencia_30d, 2),
        "eficiencia_historica": round(eficiencia_historica, 2),
        "variacao_pct": round(variacao_pct, 1) if variacao_pct is not None else None,
    }


MARGEM_QUEDA_CRITICA_PP = 3.0  # queda >= 3 p.p. entre janelas de 30 dias, ou margem negativa
N_SEMANAS_TENDENCIA = 8


def _margem_operacional_pct(faturamento: float, descontos: float, custo: float, desperdicio: float) -> float:
    """Calcula a margem operacional: (faturamento líquido - custo_insumos - valor_desperdicio) / faturamento líquido.
    Entrada: faturamento, descontos, custo, desperdicio (float, valores agregados em R$).
    Retorno: float em %; NaN se faturamento líquido <= 0 (margem indefinida)."""
    liquido = faturamento - descontos
    if liquido <= 0:  # sem receita líquida positiva, margem é indefinida, não zero
        return float("nan")
    return (liquido - custo - desperdicio) / liquido * 100


def _margem_historica(vendas_loja: pd.DataFrame) -> float:
    """Calcula a margem operacional agregada de toda a série histórica da loja.
    Entrada: vendas_loja (pd.DataFrame) com as vendas de uma loja.
    Retorno: float em %; pode ser NaN (ver _margem_operacional_pct)."""
    faturamento = vendas_loja["faturamento_bruto"].sum()
    descontos = vendas_loja["descontos"].sum()
    custo = vendas_loja["custo_insumos"].sum()
    desperdicio = vendas_loja["valor_desperdicio"].sum()
    return _margem_operacional_pct(faturamento, descontos, custo, desperdicio)


def _janela_metrics(vendas_loja: pd.DataFrame, fim: pd.Timestamp, dias: int = 30) -> dict:
    """Agrega faturamento e margem operacional numa janela de dias terminando em `fim`.
    Entrada: vendas_loja (pd.DataFrame), fim (pd.Timestamp), dias (int, tamanho da janela).
    Retorno: dict com faturamento (float), margem (float, pode ser NaN) e dias_com_venda (int)."""
    inicio = fim - pd.Timedelta(days=dias - 1)
    janela = vendas_loja[(vendas_loja["data"] >= inicio) & (vendas_loja["data"] <= fim)]
    faturamento = janela["faturamento_bruto"].sum()
    descontos = janela["descontos"].sum()
    custo = janela["custo_insumos"].sum()
    desperdicio = janela["valor_desperdicio"].sum()
    margem = _margem_operacional_pct(faturamento, descontos, custo, desperdicio)
    return {"faturamento": faturamento, "margem": margem, "dias_com_venda": len(janela)}


def _add_rotulos(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona rótulos posicionais (S-N...S-1, Atual) às linhas de uma série temporal.
    Entrada: df (pd.DataFrame) ordenado cronologicamente.
    Retorno: o mesmo pd.DataFrame com a coluna rotulo adicionada."""
    n = len(df)
    df["rotulo"] = [f"S-{n - 1 - i}" if i < n - 1 else "Atual" for i in range(n)]
    return df


def weekly_desvio_faturamento(id_loja: str, n_semanas: int = N_SEMANAS_TENDENCIA) -> tuple[pd.DataFrame, float]:
    """Calcula o desvio (%) do faturamento semanal vs. média histórica da loja. Não usada por nenhuma rota hoje.
    Entrada: id_loja (str), n_semanas (int).
    Retorno: tuple (pd.DataFrame semanal com desvio_pct, float da média histórica)."""
    vendas_loja = load_vendas()[load_vendas()["id_loja"] == id_loja].sort_values("data").copy()
    media_historica = vendas_loja["faturamento_bruto"].mean()
    vendas_loja["semana"] = vendas_loja["data"].dt.to_period("W").apply(lambda p: p.start_time)
    semanal = vendas_loja.groupby("semana").agg(faturamento_medio=("faturamento_bruto", "mean")).reset_index()
    semanal["desvio_pct"] = (semanal["faturamento_medio"] - media_historica) / media_historica * 100
    semanal = semanal.sort_values("semana").tail(n_semanas).reset_index(drop=True)
    return _add_rotulos(semanal), media_historica


def _semanas_margem_loja(id_loja: str) -> tuple[pd.DataFrame, float]:
    """Calcula margem operacional e desvio (p.p.) por semana civil completa, para toda a série da loja.
    Entrada: id_loja (str).
    Retorno: tuple (pd.DataFrame semanal com margem_pct e desvio_pp, float da média histórica)."""
    vendas_loja = load_vendas()[load_vendas()["id_loja"] == id_loja].sort_values("data").copy()
    media_historica_margem = _margem_historica(vendas_loja)

    vendas_loja["semana"] = vendas_loja["data"].dt.to_period("W").apply(lambda p: p.start_time)
    dias_por_semana = vendas_loja.groupby("semana")["data"].nunique()
    semanas_completas = dias_por_semana[dias_por_semana == 7].index  # semana com <7 dias é descartada, nunca completada
    vendas_loja = vendas_loja[vendas_loja["semana"].isin(semanas_completas)]

    semanal = vendas_loja.groupby("semana").agg(
        faturamento=("faturamento_bruto", "sum"),
        descontos=("descontos", "sum"),
        custo=("custo_insumos", "sum"),
        desperdicio=("valor_desperdicio", "sum"),
    ).reset_index()
    semanal["margem_pct"] = semanal.apply(
        lambda r: _margem_operacional_pct(r["faturamento"], r["descontos"], r["custo"], r["desperdicio"]),
        axis=1,
    )
    semanal["desvio_pp"] = semanal["margem_pct"] - media_historica_margem
    return semanal.sort_values("semana").reset_index(drop=True), media_historica_margem


def weekly_desvio_margem(id_loja: str, n_semanas: int = N_SEMANAS_TENDENCIA) -> tuple[pd.DataFrame, float]:
    """Calcula o desvio (p.p.) da margem operacional semanal vs. média histórica, para uma loja.
    Entrada: id_loja (str), n_semanas (int, quantas semanas civis completas mais recentes retornar).
    Retorno: tuple (pd.DataFrame semanal com desvio_pp, float da média histórica). Pode devolver menos de n_semanas linhas."""
    semanal, media_historica_margem = _semanas_margem_loja(id_loja)
    semanal = semanal.tail(n_semanas).reset_index(drop=True)
    return _add_rotulos(semanal), media_historica_margem


def weekly_desvio_margem_comparativo(
    loja_a: str, loja_b: str, n_semanas: int = N_SEMANAS_TENDENCIA
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula o desvio (p.p.) da margem operacional semanal de duas lojas, alinhado num eixo de semanas civis compartilhado.
    Entrada: loja_a (str), loja_b (str), n_semanas (int).
    Retorno: tuple (pd.DataFrame de A, pd.DataFrame de B), mesma coluna semana; NaN onde a loja não tem semana completa."""
    semanal_a, _ = _semanas_margem_loja(loja_a)
    semanal_b, _ = _semanas_margem_loja(loja_b)

    vendas = load_vendas()
    fim_a = vendas.loc[vendas["id_loja"] == loja_a, "data"].max()
    fim_b = vendas.loc[vendas["id_loja"] == loja_b, "data"].max()
    fim_comum = min(fim_a, fim_b)
    semana_atual = fim_comum.to_period("W").start_time

    eixo = pd.DataFrame({
        "semana": [semana_atual - pd.Timedelta(weeks=k) for k in range(n_semanas - 1, -1, -1)]
    })

    resultado_a = eixo.merge(semanal_a, on="semana", how="left")
    resultado_b = eixo.merge(semanal_b, on="semana", how="left")
    return _add_rotulos(resultado_a), _add_rotulos(resultado_b)


DIAS_FALTANTES_TOLERADOS_MES = 3  # ruído de sincronização do PDV visto na base (0-3 dias/mês); acima disso é mês parcial (abertura/outage)


def _meses_margem_loja(id_loja: str) -> tuple[pd.DataFrame, float]:
    """Calcula margem operacional e desvio (p.p.) por mês calendário quase completo, para toda a série da loja.
    Entrada: id_loja (str).
    Retorno: tuple (pd.DataFrame mensal com margem_pct e desvio_pp, float da média histórica)."""
    vendas_loja = load_vendas()[load_vendas()["id_loja"] == id_loja].sort_values("data").copy()
    media_historica_margem = _margem_historica(vendas_loja)

    vendas_loja["periodo_mes"] = vendas_loja["data"].dt.to_period("M")
    dias_por_mes = vendas_loja.groupby("periodo_mes")["data"].nunique()
    dias_faltantes = dias_por_mes.index.days_in_month - dias_por_mes
    meses_completos = dias_por_mes[dias_faltantes <= DIAS_FALTANTES_TOLERADOS_MES].index
    vendas_loja = vendas_loja[vendas_loja["periodo_mes"].isin(meses_completos)]
    vendas_loja["mes"] = vendas_loja["periodo_mes"].dt.to_timestamp()

    mensal = vendas_loja.groupby("mes").agg(
        faturamento=("faturamento_bruto", "sum"),
        descontos=("descontos", "sum"),
        custo=("custo_insumos", "sum"),
        desperdicio=("valor_desperdicio", "sum"),
    ).reset_index()
    mensal["margem_pct"] = mensal.apply(
        lambda r: _margem_operacional_pct(r["faturamento"], r["descontos"], r["custo"], r["desperdicio"]),
        axis=1,
    )
    mensal["desvio_pp"] = mensal["margem_pct"] - media_historica_margem
    return mensal.sort_values("mes").reset_index(drop=True), media_historica_margem


def monthly_desvio_margem_comparativo(loja_a: str, loja_b: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula o desvio (p.p.) da margem operacional mensal de duas lojas, alinhado num eixo de meses compartilhado.
    Entrada: loja_a (str), loja_b (str).
    Retorno: tuple (pd.DataFrame de A, pd.DataFrame de B), mesma coluna mes; NaN no mês incompleto ou sem venda."""
    mensal_a, _ = _meses_margem_loja(loja_a)
    mensal_b, _ = _meses_margem_loja(loja_b)

    # eixo = meses de operação das duas lojas (mesma união de monthly_faturamento_comparativo)
    meses_operacao = pd.concat([
        monthly_faturamento(loja_a)["mes"], monthly_faturamento(loja_b)["mes"],
    ]).drop_duplicates().sort_values()
    eixo = pd.DataFrame({"mes": meses_operacao.reset_index(drop=True)})

    resultado_a = eixo.merge(mensal_a, on="mes", how="left")
    resultado_b = eixo.merge(mensal_b, on="mes", how="left")
    return resultado_a, resultado_b


def _semanas_avaliacoes_loja(id_loja: str, fim_referencia: pd.Timestamp) -> pd.DataFrame:
    """Calcula nota média e volume de avaliações por semana civil, para toda a série da loja.
    Entrada: id_loja (str), fim_referencia (pd.Timestamp, até quando considerar a semana civil decorrida).
    Retorno: pd.DataFrame com nota_media e volume por semana; semana sem avaliação não aparece."""
    aval_loja = load_avaliacoes()
    aval_loja = aval_loja[aval_loja["id_loja"] == id_loja].dropna(subset=["data"]).copy()
    aval_loja["semana"] = aval_loja["data"].dt.to_period("W").apply(lambda p: p.start_time)
    # completude = semana civil decorrida até fim_referencia, não "7 dias com avaliação" (evento esparso)
    aval_loja = aval_loja[aval_loja["semana"] + pd.Timedelta(days=6) <= fim_referencia]
    semanal = aval_loja.groupby("semana").agg(
        nota_media=("nota", "mean"), volume=("nota", "count"),
    ).reset_index()
    return semanal.sort_values("semana").reset_index(drop=True)


def weekly_avaliacoes(id_loja: str, n_semanas: int = N_SEMANAS_TENDENCIA) -> pd.DataFrame:
    """Calcula nota média e volume de avaliações por semana, para uma loja.
    Entrada: id_loja (str), n_semanas (int, quantas semanas mais recentes com avaliação retornar).
    Retorno: pd.DataFrame semanal com nota_media, volume e rotulo."""
    fim_rede = load_vendas()["data"].max()
    semanal = _semanas_avaliacoes_loja(id_loja, fim_rede)
    semanal = semanal.tail(n_semanas).reset_index(drop=True)
    return _add_rotulos(semanal)


N_SEMANAS_AVALIACOES_COMPARATIVO = 16  # avaliação é esparsa; janela maior que a de margem (8) pra ter dado real


def weekly_avaliacoes_comparativo(
    loja_a: str, loja_b: str, n_semanas: int = N_SEMANAS_AVALIACOES_COMPARATIVO
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula nota média e volume de avaliações de duas lojas, alinhado num eixo de semanas civis compartilhado.
    Entrada: loja_a (str), loja_b (str), n_semanas (int).
    Retorno: tuple (pd.DataFrame de A, pd.DataFrame de B), mesma coluna semana; NaN onde a loja não tem avaliação naquela semana."""
    fim_rede = load_vendas()["data"].max()
    semanal_a = _semanas_avaliacoes_loja(loja_a, fim_rede)
    semanal_b = _semanas_avaliacoes_loja(loja_b, fim_rede)

    # eixo = união das semanas com avaliação em qualquer uma das duas lojas, não semanas civis em branco
    todas_semanas = pd.concat([semanal_a["semana"], semanal_b["semana"]]).drop_duplicates().sort_values()
    eixo = pd.DataFrame({"semana": todas_semanas.tail(n_semanas).reset_index(drop=True)})

    resultado_a = eixo.merge(semanal_a, on="semana", how="left")
    resultado_b = eixo.merge(semanal_b, on="semana", how="left")
    return _add_rotulos(resultado_a), _add_rotulos(resultado_b)


def monthly_faturamento(id_loja: str) -> pd.DataFrame:
    """Soma o faturamento bruto por mês, para uma loja.
    Entrada: id_loja (str).
    Retorno: pd.DataFrame com mes e faturamento."""
    vendas_loja = load_vendas()[load_vendas()["id_loja"] == id_loja].copy()
    vendas_loja["mes"] = vendas_loja["data"].dt.to_period("M").dt.to_timestamp()
    mensal = vendas_loja.groupby("mes").agg(faturamento=("faturamento_bruto", "sum")).reset_index()
    return mensal.sort_values("mes").reset_index(drop=True)


def monthly_faturamento_comparativo(loja_a: str, loja_b: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Soma o faturamento bruto por mês de duas lojas, alinhado num eixo de meses compartilhado.
    Entrada: loja_a (str), loja_b (str).
    Retorno: tuple (pd.DataFrame de A, pd.DataFrame de B), mesma coluna mes (união dos dois períodos); NaN no mês sem venda."""
    mensal_a = monthly_faturamento(loja_a)
    mensal_b = monthly_faturamento(loja_b)

    todos_meses = pd.concat([mensal_a["mes"], mensal_b["mes"]]).drop_duplicates().sort_values()
    eixo = pd.DataFrame({"mes": todos_meses.reset_index(drop=True)})

    resultado_a = eixo.merge(mensal_a, on="mes", how="left")
    resultado_b = eixo.merge(mensal_b, on="mes", how="left")
    return resultado_a, resultado_b


def _mensal_avaliacoes_loja(id_loja: str) -> pd.DataFrame:
    """Calcula nota média e volume de avaliações por mês, para uma loja.
    Entrada: id_loja (str).
    Retorno: pd.DataFrame com mes, nota_media e volume; mês sem avaliação não aparece."""
    aval_loja = load_avaliacoes()
    aval_loja = aval_loja[aval_loja["id_loja"] == id_loja].dropna(subset=["data"]).copy()
    aval_loja["mes"] = aval_loja["data"].dt.to_period("M").dt.to_timestamp()
    mensal = aval_loja.groupby("mes").agg(
        nota_media=("nota", "mean"), volume=("nota", "count"),
    ).reset_index()
    return mensal.sort_values("mes").reset_index(drop=True)


def monthly_avaliacoes_comparativo(loja_a: str, loja_b: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula nota média e volume de avaliações de duas lojas, por mês, alinhado num eixo de meses compartilhado.
    Entrada: loja_a (str), loja_b (str).
    Retorno: tuple (pd.DataFrame de A, pd.DataFrame de B), mesma coluna mes; NaN no mês sem avaliação."""
    mensal_a = _mensal_avaliacoes_loja(loja_a)
    mensal_b = _mensal_avaliacoes_loja(loja_b)

    # eixo = meses de operação das duas lojas (mesma união de monthly_faturamento_comparativo), não só meses com avaliação
    meses_operacao = pd.concat([
        monthly_faturamento(loja_a)["mes"], monthly_faturamento(loja_b)["mes"],
    ]).drop_duplicates().sort_values()
    eixo = pd.DataFrame({"mes": meses_operacao.reset_index(drop=True)})

    resultado_a = eixo.merge(mensal_a, on="mes", how="left")
    resultado_b = eixo.merge(mensal_b, on="mes", how="left")
    return resultado_a, resultado_b


# palavra-chave -> ícone; ordem importa (negativas primeiro, pega "não gostei" antes de "gostei")
_PALAVRAS_ATENCAO = {
    "não gostei": "alert", "nao gostei": "alert",
    "não recomendo": "alert", "nao recomendo": "alert",
    "lotado": "person", "lotada": "person", "fila": "person", "cheio demais": "person", "cheia demais": "person",
    "faltava": "alert", "poderia ter mais": "alert",
    "demorou": "clock", "demora": "clock", "demorado": "clock", "lento": "clock", "lenta": "clock",
    "ruim": "alert", "péssimo": "alert", "pessimo": "alert", "péssima": "alert", "pessima": "alert",
    "frio": "thermometer", "fria": "thermometer", "morno": "thermometer", "morna": "thermometer",
    "sujo": "sparkle", "suja": "sparkle",
    "caro": "currency", "cara": "currency",
    "grosso": "person", "grossa": "person", "mal educado": "person", "mal educada": "person",
    "totem": "alert", "travou": "alert", "travando": "alert", "trava": "alert",
    "quebrado": "alert", "quebrada": "alert", "fora do ar": "alert",
    "não funcionava": "alert", "nao funcionava": "alert", "não funcionou": "alert", "nao funcionou": "alert",
    "timeout": "alert",
}

_PALAVRAS_FORTE = {
    "gostei": "heart", "adorei": "heart", "recomendo": "heart",
    "ótimo": "check", "otimo": "check", "ótima": "check", "otima": "check",
    "excelente": "check", "excelentes": "check",
    "bom": "check", "boa": "check", "boas": "check", "bons": "check",
    "rápido": "clock", "rapido": "clock", "rápida": "clock", "rapida": "clock",
    "atencioso": "person", "atenciosa": "person", "educado": "person", "educada": "person",
    "limpo": "sparkle", "limpa": "sparkle", "aconchegante": "sparkle", "agradável": "sparkle", "agradavel": "sparkle",
    "fresco": "food", "fresquinho": "food", "quente": "food", "saboroso": "food", "saborosa": "food",
    "wi-fi": "wifi", "wifi": "wifi",
    "justo": "currency",
}

_ICONE_FALLBACK = {"forte": "check", "atencao": "alert"}


def _classificar_comentario(texto: str, nota: float) -> tuple[str, str]:
    """Categoriza um comentário em "atencao" ou "forte" por palavra-chave, com fallback pela nota.
    Entrada: texto (str) do comentário, nota (float).
    Retorno: tuple (categoria: str, icone: str)."""
    texto_norm = texto.lower()
    for palavra, icone in _PALAVRAS_ATENCAO.items():
        if palavra in texto_norm:
            return "atencao", icone
    for palavra, icone in _PALAVRAS_FORTE.items():
        if palavra in texto_norm:
            return "forte", icone

    categoria = "forte" if pd.notna(nota) and nota >= 4 else "atencao"
    return categoria, _ICONE_FALLBACK[categoria]


def comentarios_destaque(id_loja: str, limit: int = 5) -> dict:
    """Lista os comentários mais repetidos de uma loja, separados em pontos fortes e de atenção.
    Entrada: id_loja (str), limit (int, quantos itens por categoria).
    Retorno: dict com pontos_fortes e pontos_atencao (list[dict])."""
    aval = load_avaliacoes()
    aval_loja = aval[
        (aval["id_loja"] == id_loja)
        & aval["comentario"].notna()
        & (aval["comentario"].astype(str).str.strip() != "")
    ].sort_values("data", ascending=False)

    # agrupa por texto idêntico -- mesma frase repetida não deve listar 5x
    agrupado: dict[tuple[str, str], dict] = {}
    for _, row in aval_loja.iterrows():
        comentario = str(row["comentario"]).strip()
        categoria, icone = _classificar_comentario(comentario, row["nota"])
        chave = (categoria, comentario.lower())
        if chave not in agrupado:
            agrupado[chave] = {
                "data": row["data"],
                "nota": row["nota"],
                "canal": row["canal"],
                "comentario": comentario,
                "icone": icone,
                "categoria": categoria,
                "ocorrencias": 0,
            }
        agrupado[chave]["ocorrencias"] += 1

    def _chave_ordenacao(item: dict):
        # mais repetido primeiro; empate desfeito pelo mais recente (NaT vai por último)
        data_valor = item["data"].value if pd.notna(item["data"]) else -1
        return (-item["ocorrencias"], -data_valor)

    fortes = sorted((v for v in agrupado.values() if v["categoria"] == "forte"), key=_chave_ordenacao)
    atencao = sorted((v for v in agrupado.values() if v["categoria"] == "atencao"), key=_chave_ordenacao)

    return {
        "pontos_fortes": fortes[:limit],
        "pontos_atencao": atencao[:limit],
    }


def _tendencia_avaliacao(semanal: pd.DataFrame) -> str:
    """Classifica a tendência da nota média comparando a metade mais recente das semanas com a mais antiga.
    Entrada: semanal (pd.DataFrame) com a coluna nota_media.
    Retorno: str, um de "Tendência de queda", "Tendência de alta", "Estável" ou "Sem dados suficientes"."""
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
    """Classifica o status da margem a partir do valor atual e da variação vs. histórico.
    Entrada: margem_atual (float, pode ser NaN), variacao_pp (float, pode ser NaN).
    Retorno: str, um de "Margem indefinida", "Desvio crítico", "Em queda", "Em alta" ou "Estável"."""
    if pd.isna(margem_atual):  # checa antes dos outros ramos -- NaN em comparação nunca é True
        return "Margem indefinida"
    if margem_atual < 0 or (pd.notna(variacao_pp) and variacao_pp <= -MARGEM_QUEDA_CRITICA_PP):
        return "Desvio crítico"
    if pd.notna(variacao_pp) and variacao_pp < 0:
        return "Em queda"
    if pd.notna(variacao_pp) and variacao_pp > MARGEM_QUEDA_CRITICA_PP:
        return "Em alta"
    return "Estável"


def list_stores_summary() -> list[dict]:
    """Lista faturamento e margem dos últimos 30 dias de todas as lojas, ordenado da pior margem pra melhor.
    Entrada: nenhuma.
    Retorno: list[dict], um item por loja com id_loja, nome_loja, faturamento_30d, margem_30d e risco_critico."""
    lojas = load_lojas()
    vendas = load_vendas()
    fim = vendas["data"].max()

    resumo = []
    for _, loja in lojas.iterrows():
        vendas_loja = vendas[vendas["id_loja"] == loja["id_loja"]].sort_values("data")
        if vendas_loja.empty:
            continue
        atual = _janela_metrics(vendas_loja, fim)
        margem_indefinida = pd.isna(atual["margem"])
        resumo.append({
            "id_loja": loja["id_loja"],
            "nome_loja": loja["nome_loja"],
            "faturamento_30d": round(atual["faturamento"], 2),
            "margem_30d": round(atual["margem"], 1) if not margem_indefinida else None,
            "risco_critico": (not margem_indefinida) and atual["margem"] < 0,
        })
    # margem indefinida ordena primeiro -- caso mais anômalo, merece atenção antes de margem negativa "normal"
    return sorted(resumo, key=lambda x: x["margem_30d"] if x["margem_30d"] is not None else float("-inf"))


# Limiar de referência pra tempo de espera de balcão em cafeteria: não há benchmark oficial do
# projeto (igual à nota, ver NOTA_QUEDA_CRITICA_PONTOS), então 8 minutos foi escolhido como o ponto
# em que a espera passa de "aceitável" pra "perceptível como demora" numa operação de balcão/quiosque,
# valor documentável mas é premissa nova, não um número já validado em outra parte do sistema.
TEMPO_ESPERA_LIMIAR_MIN = 8.0


def store_metrics(id_loja: str) -> dict:
    """Calcula as métricas de uma loja: faturamento, margem, avaliação e variações vs. histórico.
    Entrada: id_loja (str).
    Retorno: dict com faturamento_30d, margem_30d, variacao_margem_pp, avaliacao_media, variacao_nota, entre outros."""
    lojas = load_lojas()
    vendas = load_vendas()
    avaliacoes = load_avaliacoes()

    loja_row = lojas[lojas["id_loja"] == id_loja].iloc[0]
    vendas_loja = vendas[vendas["id_loja"] == id_loja].sort_values("data")
    fim = vendas_loja["data"].max()

    atual = _janela_metrics(vendas_loja, fim, 30)
    margem_historica = _margem_historica(vendas_loja)

    # variação = 30 dias vs. média histórica completa (não vs. 30 dias anteriores)
    variacao_margem_pp = atual["margem"] - margem_historica
    risco_critico = atual["margem"] < 0 or variacao_margem_pp <= -MARGEM_QUEDA_CRITICA_PP

    meta_mensal = loja_row["meta_faturamento_mensal"]
    variacao_faturamento_vs_meta_pct = (
        (atual["faturamento"] - meta_mensal) / meta_mensal * 100
        if pd.notna(meta_mensal) and meta_mensal else None
    )

    aval_loja = avaliacoes[avaliacoes["id_loja"] == id_loja]
    aval_janela = aval_loja[aval_loja["data"] >= (fim - pd.Timedelta(days=90))]
    avaliacao_media = aval_janela["nota"].mean()
    nota_historica = aval_loja["nota"].mean()
    # variação de nota em pontos da escala 1-5, não p.p.
    variacao_nota = (
        avaliacao_media - nota_historica
        if pd.notna(avaliacao_media) and pd.notna(nota_historica) else float("nan")
    )
    tempo_espera_medio = aval_janela["tempo_espera_min"].mean()
    tendencia_avaliacao = _tendencia_avaliacao(weekly_avaliacoes(id_loja))
    tempo_espera_acima_limiar = (
        tempo_espera_medio > TEMPO_ESPERA_LIMIAR_MIN if pd.notna(tempo_espera_medio) else None
    )

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
        "margem_30d": round(atual["margem"], 1) if pd.notna(atual["margem"]) else None,
        "margem_historica": round(margem_historica, 1) if pd.notna(margem_historica) else None,
        # arredondado pra exibição na tela
        "variacao_margem_pp": round(variacao_margem_pp, 1) if pd.notna(variacao_margem_pp) else None,
        "variacao_margem_pp_raw": variacao_margem_pp,  # não arredondado -- usado internamente por list_prioridades()
        "status_margem": _status_margem(atual["margem"], variacao_margem_pp),
        "risco_critico": risco_critico,
        "avaliacao_media": round(avaliacao_media, 1) if pd.notna(avaliacao_media) else None,
        "nota_historica": round(nota_historica, 1) if pd.notna(nota_historica) else None,
        "variacao_nota": variacao_nota,  # não arredondado -- usado internamente por list_prioridades()
        "avaliacao_count": int(aval_janela["nota"].notna().sum()),
        "tempo_espera_medio": round(tempo_espera_medio, 1) if pd.notna(tempo_espera_medio) else None,
        "tempo_espera_limiar_min": TEMPO_ESPERA_LIMIAR_MIN,
        "tempo_espera_acima_limiar": tempo_espera_acima_limiar,
        "tendencia_avaliacao": tendencia_avaliacao,
        "periodo_fim": fim,
        "periodo_inicio": fim - pd.Timedelta(days=29),
    }


def list_lojas_options() -> list[dict]:
    """Lista id e nome de todas as lojas.
    Entrada: nenhuma.
    Retorno: list[dict] com id_loja e nome_loja."""
    lojas = load_lojas()
    return lojas[["id_loja", "nome_loja"]].to_dict("records")


N_LOJAS_INTERVENCAO = 2  # "a estrutura atual sustenta ação efetiva em, no máximo, duas lojas por semana"


PESO_PERCENTIL_MARGEM = 0.6
PESO_PERCENTIL_NOTA = 0.4

# Limiar de magnitude que equivale a percentil 100 na dimensão de nota. Não
# existe um limiar oficial de queda crítica de nota no projeto (diferente da
# margem, que já tinha MARGEM_QUEDA_CRITICA_PP); 0,5 ponto foi escolhido por
# ser meia "estrela" cheia na escala 1-5, um valor documentável e defensável
# de severidade, mas é uma premissa nova, não um número já validado em outra
# parte do sistema.
NOTA_QUEDA_CRITICA_PONTOS = 0.5


def _percentil_por_magnitude(variacao: float, limiar_critico: float) -> float:
    """Converte uma variação em percentil 0-100 pela magnitude da queda, não pela posição entre as lojas.
    Entrada: variacao (float, p.p. ou pontos; pode ser NaN), limiar_critico (float > 0, magnitude que já vale percentil 100).
    Retorno: float 0-100; 0 se variacao >= 0 ou NaN (sem queda confirmada, sem urgência); escala linear até o limiar, saturando em 100."""
    if pd.isna(variacao) or variacao >= 0:
        return 0.0
    return min(100.0, -variacao / limiar_critico * 100)


def _motivo_prioridade(percentil_margem: float, percentil_nota: float,
                        variacao_margem_pp: float, variacao_nota: float) -> str:
    """Monta o texto do motivo de prioridade a partir da dimensão (margem ou nota) com maior percentil.
    Entrada: percentil_margem, percentil_nota, variacao_margem_pp, variacao_nota (float).
    Retorno: str descrevendo a variação da dimensão que mais pesou."""
    if percentil_margem >= percentil_nota:
        if variacao_margem_pp is None or pd.isna(variacao_margem_pp):
            return "Margem indefinida no período (desconto maior que faturamento bruto) vs. histórico da loja"
        direcao = "caiu" if variacao_margem_pp < 0 else "subiu"
        return f"Margem {direcao} {abs(variacao_margem_pp):.1f} p.p. vs. histórico da loja"
    direcao = "caiu" if variacao_nota < 0 else "subiu"
    unidade = "ponto" if round(abs(variacao_nota), 1) == 1.0 else "pontos"
    return f"Nota {direcao} {abs(variacao_nota):.1f} {unidade} vs. histórico da loja"


def _indice_prioridade(percentil_margem: float, percentil_nota: float) -> float:
    """Calcula o Índice de Prioridade combinando os percentis de margem e nota.
    Entrada: percentil_margem, percentil_nota (float, 0-100).
    Retorno: float, 0.6 x percentil_margem + 0.4 x percentil_nota. Equipe não entra na conta."""
    return round(PESO_PERCENTIL_MARGEM * percentil_margem + PESO_PERCENTIL_NOTA * percentil_nota, 1)


def list_prioridades() -> dict:
    """Rankeia as 14 lojas por Índice de Prioridade.
    Entrada: nenhuma.
    Retorno: dict com "criticas" (as N_LOJAS_INTERVENCAO primeiras) e "outras" (list[dict]). Loja com margem e nota estáveis/melhorando fica com índice 0."""
    metricas = [store_metrics(opt["id_loja"]) for opt in list_lojas_options()]

    ranking = []
    for m in metricas:
        pm = _percentil_por_magnitude(m["variacao_margem_pp_raw"], MARGEM_QUEDA_CRITICA_PP)
        pn = _percentil_por_magnitude(m["variacao_nota"], NOTA_QUEDA_CRITICA_PONTOS)
        indice = _indice_prioridade(pm, pn)
        motivo = _motivo_prioridade(pm, pn, m["variacao_margem_pp"], m["variacao_nota"])
        ranking.append({
            **m,
            "indice_prioridade": indice,
            "percentil_margem": round(pm, 1),
            "percentil_nota": round(pn, 1),
            "motivos": [motivo],
        })

    ranking.sort(key=lambda r: -r["indice_prioridade"])
    criticas = ranking[:N_LOJAS_INTERVENCAO]

    # dados de contexto abaixo são só pros cards críticos exibidos na tela -- não entram no ranking,
    # no índice nem em nenhum percentil (ver pior_categoria_margem e eficiencia_equipe).
    for c in criticas:
        motivo_margem = c["percentil_margem"] >= c["percentil_nota"]
        c["motivo_dimensao"] = "margem" if motivo_margem else "nota"
        c["mix_pior_categoria"] = pior_categoria_margem(c["id_loja"]) if motivo_margem else None
        c["eficiencia_equipe"] = eficiencia_equipe(c["id_loja"])

    return {
        "criticas": criticas,
        "outras": ranking[N_LOJAS_INTERVENCAO:],
    }


PERIODOS_REDE = {
    "6m": "Últimos 6 meses",
    "12m": "Últimos 12 meses",
    "fundacao": "Desde a fundação",
}


def _intervalo_periodo(periodo: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Calcula o intervalo de datas de um período selecionável.
    Entrada: periodo (str), um de "6m", "12m" ou "fundacao".
    Retorno: tuple (inicio, fim) de pd.Timestamp."""
    vendas = load_vendas()
    fim = vendas["data"].max()
    if periodo == "6m":
        inicio = fim - pd.DateOffset(months=6)
    elif periodo == "fundacao":
        inicio = vendas["data"].min()
    else:  # "12m" -- padrão
        inicio = fim - pd.DateOffset(months=12)
    return inicio, fim


def _inicio_semestre(data: pd.Timestamp) -> pd.Timestamp:
    """Calcula o início do semestre calendário que contém uma data.
    Entrada: data (pd.Timestamp).
    Retorno: pd.Timestamp do dia 1º de janeiro ou 1º de julho."""
    mes_inicio = 1 if data.month <= 6 else 7
    return pd.Timestamp(year=data.year, month=mes_inicio, day=1)


def rede_kpis(periodo: str = "12m") -> dict:
    """Calcula os KPIs de rede (faturamento, crescimento, margem, ticket médio) pro período selecionado.
    Entrada: periodo (str), um de "6m", "12m" ou "fundacao".
    Retorno: dict com faturamento_total, crescimento_pct, margem_pct, ticket_medio, entre outros."""
    inicio, fim = _intervalo_periodo(periodo)
    vendas = load_vendas()
    janela = vendas[(vendas["data"] >= inicio) & (vendas["data"] <= fim)]

    faturamento_total = janela["faturamento_bruto"].sum()
    descontos_total = janela["descontos"].sum()
    custo_total = janela["custo_insumos"].sum()
    desperdicio_total = janela["valor_desperdicio"].sum()
    tickets_total = janela["num_tickets"].sum()

    # corte por semestre calendário (não por tempo decorrido) pra período de ano cheio -- bate com o relatório oficial
    meio = _inicio_semestre(fim) if periodo in ("12m", "fundacao") else inicio + (fim - inicio) / 2
    primeira_metade = janela[janela["data"] < meio]["faturamento_bruto"].sum()
    segunda_metade = janela[janela["data"] >= meio]["faturamento_bruto"].sum()
    crescimento_pct = (
        (segunda_metade - primeira_metade) / primeira_metade * 100 if primeira_metade else None
    )
    margem_pct = _margem_operacional_pct(faturamento_total, descontos_total, custo_total, desperdicio_total)
    ticket_medio = faturamento_total / tickets_total if tickets_total else None

    return {
        "periodo": periodo,
        "periodo_label": PERIODOS_REDE[periodo],
        "inicio": inicio,
        "fim": fim,
        "faturamento_total": round(faturamento_total, 2),
        "crescimento_pct": round(crescimento_pct, 1) if crescimento_pct is not None else None,
        "margem_pct": round(margem_pct, 1) if pd.notna(margem_pct) else None,
        "ticket_medio": round(ticket_medio, 2) if ticket_medio is not None else None,
    }


_MESES_PT_EXTENSO = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril", 5: "maio", 6: "junho",
    7: "julho", 8: "agosto", 9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}


def retrato_atual(mensal_expansao: pd.DataFrame) -> dict:
    """Calcula o retrato de "agora" (mês mais recente) e a média do período de lojas indo bem/mal.
    Entrada: mensal_expansao (pd.DataFrame) de tendencia_expansao.
    Retorno: dict com agora_acima, agora_abaixo, media_acima, media_abaixo, entre outros. "Agora" não varia com o período selecionado; a média varia."""
    if mensal_expansao.empty:
        return {
            "agora_acima": 0, "agora_abaixo": 0, "agora_total": 0,
            "agora_mes": None, "agora_mes_label": None,
            "agora_pct_acima": 0, "agora_pct_abaixo": 0,
            "media_acima": 0.0, "media_abaixo": 0.0, "media_total": 0.0,
            "media_pct_acima": 0, "media_pct_abaixo": 0, "n_meses": 0,
        }

    ultimo_mes = mensal_expansao.iloc[-1]
    agora_acima, agora_abaixo = int(ultimo_mes["positivas"]), int(ultimo_mes["negativas"])
    agora_total = agora_acima + agora_abaixo
    agora_mes_label = f"{_MESES_PT_EXTENSO[ultimo_mes['mes'].month]}/{ultimo_mes['mes'].year}"

    media_acima = mensal_expansao["positivas"].mean()
    media_abaixo = mensal_expansao["negativas"].mean()
    media_total = media_acima + media_abaixo

    return {
        "agora_acima": agora_acima,
        "agora_abaixo": agora_abaixo,
        "agora_total": agora_total,
        "agora_mes": ultimo_mes["mes"],
        "agora_mes_label": agora_mes_label,
        "agora_pct_acima": round(agora_acima / agora_total * 100, 1) if agora_total else 0,
        "agora_pct_abaixo": round(agora_abaixo / agora_total * 100, 1) if agora_total else 0,
        "media_acima": round(media_acima, 1),
        "media_abaixo": round(media_abaixo, 1),
        "media_total": round(media_total, 1),
        "media_pct_acima": round(media_acima / media_total * 100, 1) if media_total else 0,
        "media_pct_abaixo": round(media_abaixo / media_total * 100, 1) if media_total else 0,
        "n_meses": len(mensal_expansao),
    }


def tendencia_expansao(periodo: str = "12m") -> pd.DataFrame:
    """Calcula quantas lojas faturaram mais ou menos que no mês anterior (nunca vs. média histórica), por mês, dentro do período.
    Entrada: periodo (str), um de "6m", "12m" ou "fundacao".
    Retorno: pd.DataFrame com mes, positivas, negativas e lojas_ativas."""
    inicio, fim = _intervalo_periodo(periodo)
    vendas = load_vendas()

    # sem filtro de início: precisa dos meses anteriores ao período pra já ter "mês anterior" no primeiro mês
    vendas_ate_fim = vendas[vendas["data"] <= fim].copy()
    vendas_ate_fim["mes"] = vendas_ate_fim["data"].dt.to_period("M").dt.to_timestamp()

    mensal_por_loja = (
        vendas_ate_fim.groupby(["id_loja", "mes"])["faturamento_bruto"]
        .sum()
        .reset_index()
        .sort_values(["id_loja", "mes"])
    )
    mensal_por_loja["mes_anterior"] = mensal_por_loja.groupby("id_loja")["faturamento_bruto"].shift(1)

    inicio_mes = inicio.to_period("M").to_timestamp()
    periodo_df = mensal_por_loja[mensal_por_loja["mes"] >= inicio_mes]

    linhas = []
    for mes, grupo in periodo_df.groupby("mes"):
        comparaveis = grupo.dropna(subset=["mes_anterior"])
        linhas.append({
            "mes": mes,
            "positivas": int((comparaveis["faturamento_bruto"] > comparaveis["mes_anterior"]).sum()),
            "negativas": int((comparaveis["faturamento_bruto"] < comparaveis["mes_anterior"]).sum()),
            "lojas_ativas": len(grupo),
        })

    return pd.DataFrame(linhas).sort_values("mes").reset_index(drop=True)
