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
- `id_loja` vem ora maiúsculo ("LJ01"), ora minúsculo ("lj01") no export de
  avaliações -- normalizado pra maiúsculo em todos os CSVs, senão o filtro
  por loja perde silenciosamente as linhas minúsculas (comparação de string
  é case-sensitive; era um bug real, não só estético).
- `canal` de avaliação também varia de caixa e nome ("Google" vs "google
  maps" vs "app" vs "App") -- normalizado pra um rótulo canônico por canal
  (essencialmente o mesmo canal exportado de formas diferentes).
- `nota` de avaliação aparece em pelo menos 4 formatos: número puro ("4"),
  decimal com vírgula ("4,0"), com sufixo ("4 estrelas") e por extenso
  ("quatro") -- todos normalizados pra float antes de validar o intervalo
  [1, 5] (fora disso é descartado, herança do campo livre da versão antiga
  do app).
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


def normalize_id_loja(series: pd.Series) -> pd.Series:
    """'lj01' e 'LJ01' são a mesma loja -- maiúsculo é o padrão nos outros CSVs."""
    return series.astype(str).str.strip().str.upper()


_NUMEROS_POR_EXTENSO = {
    "um": 1, "uma": 1,
    "dois": 2, "duas": 2,
    "tres": 3, "três": 3,
    "quatro": 4,
    "cinco": 5,
}


def parse_nota(series: pd.Series) -> pd.Series:
    """
    Nota de avaliação convive em formatos bem diferentes no mesmo CSV: número
    puro ('4'), decimal com vírgula ('4,0'), com sufixo ('4 estrelas') e por
    extenso ('quatro'). Tenta o caminho numérico primeiro (cobre os 3
    primeiros formatos de uma vez, já removendo o sufixo "estrela(s)") e cai
    pro dicionário de números por extenso só no que sobrar.
    """
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
    """'Google' e 'google maps' são o mesmo canal (avaliação via Google);
    normaliza caixa e apelidos pra um rótulo canônico por canal."""
    texto = series.astype(str).str.strip().str.lower()
    return texto.map(lambda v: _CANAIS_CANONICOS.get(v, v.title()))


# 'formato' (turmalina_lojas.csv) tem variantes de caixa e de nome pro mesmo
# tipo de loja ('rua' / 'RUA' / 'Loja de rua', 'Kiosk' / 'quiosque', 'Shopping'
# / 'shopping center'). Antes o valor caía num fallback silencioso pra "Rua"
# quando não batia com quiosque/shopping -- funcionava só por coincidência
# (toda variante de rua realmente contém "rua"); trocado por checagem
# explícita de palavra-chave, igual ao canal, pra não depender de sorte se
# aparecer um valor novo.
_PALAVRAS_FORMATO = {
    "quiosque": "Quiosque", "quiosk": "Quiosque", "kiosk": "Quiosque",
    "shopping": "Shopping",
    "rua": "Rua",
}


def _classificar_formato(texto: str) -> str:
    for palavra, formato in _PALAVRAS_FORMATO.items():
        if palavra in texto:
            return formato
    return texto.title()  # formato não reconhecido -- mantém visível em vez de mascarar como "Rua"


@lru_cache(maxsize=1)
def load_lojas() -> pd.DataFrame:
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
    df["margem_pct"] = (
        (df["faturamento_bruto"] - df["custo_insumos"]) / df["faturamento_bruto"] * 100
    )
    return df


@lru_cache(maxsize=1)
def load_avaliacoes() -> pd.DataFrame:
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


# Dicionário de palavras-chave -> ícone. Cada comentário é varrido em busca
# dessas palavras pra virar "ponto forte" ou "ponto de atenção"; a ordem das
# negativas importa (checadas primeiro) pra pegar negações simples tipo "não
# gostei" antes que "gostei" bata como positivo.
_PALAVRAS_ATENCAO = {
    "não gostei": "alert", "nao gostei": "alert",
    "não recomendo": "alert", "nao recomendo": "alert",
    "lotado": "person", "lotada": "person", "fila": "person",
    "demorou": "clock", "demora": "clock", "demorado": "clock", "lento": "clock", "lenta": "clock",
    "ruim": "alert", "péssimo": "alert", "pessimo": "alert", "péssima": "alert", "pessima": "alert",
    "frio": "thermometer", "fria": "thermometer", "morno": "thermometer", "morna": "thermometer",
    "sujo": "sparkle", "suja": "sparkle",
    "caro": "currency", "cara": "currency",
    "grosso": "person", "grossa": "person", "mal educado": "person", "mal educada": "person",
    # Falha de totem/sistema -- sinal operacional, não só "demora" de atendimento
    # humano; tempo_espera_min sentinela (>=120, ver load_avaliacoes) já é
    # descartado da média, mas se o comentário falar da falha em si, é
    # importante ela aparecer aqui, não só desaparecer como dado faltante.
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
    """
    Categoriza um comentário em 'atencao' ou 'forte' buscando palavras-chave
    de sentimento (dicionário -- sem NLP). Comentário sem nenhuma palavra
    reconhecida cai no fallback pela nota (>= 4 vira ponto forte, o resto
    ponto de atenção), então nenhum comentário com texto fica de fora.
    """
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
    """
    Comentários com texto preenchido, sempre exibidos (não só os críticos),
    separados em 'pontos_fortes' e 'pontos_atencao' via busca de palavras-chave
    (ver _classificar_comentario). Muitas avaliações vêm sem comentário (campo
    de texto livre, nem sempre preenchido); essas são descartadas por não
    agregarem contexto -- não há o que classificar num campo vazio.

    O texto livre se repete muito entre clientes diferentes (poucas frases
    fixas, muita gente escrevendo a mesma coisa) -- listar a mesma frase 5x
    não ajuda em nada, então agrupa por texto idêntico (case-insensitive) e
    mostra quantas vezes cada uma apareceu; o ranking prioriza o que mais se
    repete, não só o mais recente.
    """
    aval = load_avaliacoes()
    aval_loja = aval[
        (aval["id_loja"] == id_loja)
        & aval["comentario"].notna()
        & (aval["comentario"].astype(str).str.strip() != "")
    ].sort_values("data", ascending=False)

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


PERIODOS_REDE = {
    "6m": "Últimos 6 meses",
    "12m": "Últimos 12 meses",
    "fundacao": "Desde a fundação",
}


def _intervalo_periodo(periodo: str) -> tuple[pd.Timestamp, pd.Timestamp]:
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
    """1º de janeiro ou 1º de julho do semestre calendário que contém `data`."""
    mes_inicio = 1 if data.month <= 6 else 7
    return pd.Timestamp(year=data.year, month=mes_inicio, day=1)


def rede_kpis(periodo: str = "12m") -> dict:
    """
    KPIs de rede recalculados ao vivo a partir de turmalina_vendas_diarias.csv
    pro período selecionado (tela 'Rede') -- nada travado em relatório estático.

    Crescimento compara semestre calendário atual vs. anterior (não um corte
    "metade do período" por tempo decorrido -- isso deslocava a fronteira pra
    29/12 em vez de 01/01 e distorcia o resultado por causa dos dias de maior
    faturamento do fim de ano ficarem do lado errado do corte).

    Margem é sobre a receita líquida (faturamento menos descontos) e desconta
    também o desperdício, não só o custo de insumos -- confere com o número
    que já vai pro conselho na planilha consolidada.
    """
    inicio, fim = _intervalo_periodo(periodo)
    vendas = load_vendas()
    janela = vendas[(vendas["data"] >= inicio) & (vendas["data"] <= fim)]

    faturamento_total = janela["faturamento_bruto"].sum()
    descontos_total = janela["descontos"].sum()
    custo_total = janela["custo_insumos"].sum()
    desperdicio_total = janela["valor_desperdicio"].sum()
    tickets_total = janela["num_tickets"].sum()
    faturamento_liquido = faturamento_total - descontos_total

    meio = _inicio_semestre(fim)
    primeira_metade = janela[janela["data"] < meio]["faturamento_bruto"].sum()
    segunda_metade = janela[janela["data"] >= meio]["faturamento_bruto"].sum()
    crescimento_pct = (
        (segunda_metade - primeira_metade) / primeira_metade * 100 if primeira_metade else None
    )
    margem_pct = (
        (faturamento_liquido - custo_total - desperdicio_total) / faturamento_liquido * 100
        if faturamento_liquido else None
    )
    ticket_medio = faturamento_total / tickets_total if tickets_total else None

    return {
        "periodo": periodo,
        "periodo_label": PERIODOS_REDE[periodo],
        "inicio": inicio,
        "fim": fim,
        "faturamento_total": round(faturamento_total, 2),
        "crescimento_pct": round(crescimento_pct, 1) if crescimento_pct is not None else None,
        "margem_pct": round(margem_pct, 1) if margem_pct is not None else None,
        "ticket_medio": round(ticket_medio, 2) if ticket_medio is not None else None,
    }


def retrato_atual(mensal_expansao: pd.DataFrame) -> dict:
    """
    Quantas lojas estão, AGORA, indo bem ou mal -- reaproveita o mês mais
    recente de `tendencia_expansao` (mês vs. mês anterior), a mesma conta e
    o mesmo motivo documentado lá: comparar contra a média histórica inteira
    dava sempre ~14 de 14 positivas, porque a rede inteira está crescendo e
    o histórico completo inclui os meses mais fracos do início -- não media
    nada sobre o momento atual da loja. Recebe o DataFrame já calculado (em
    vez de recalcular) pra garantir a mesma fonte pro card e pro gráfico de
    tendência, e pra herdar o filtro por período selecionado na tela.
    """
    if mensal_expansao.empty:
        return {"acima": 0, "abaixo": 0, "total": 0, "pct_acima": 0, "pct_abaixo": 0}

    ultimo_mes = mensal_expansao.iloc[-1]
    acima, abaixo = int(ultimo_mes["positivas"]), int(ultimo_mes["negativas"])
    total = acima + abaixo
    return {
        "acima": acima,
        "abaixo": abaixo,
        "total": total,
        "pct_acima": round(acima / total * 100, 1) if total else 0,
        "pct_abaixo": round(abaixo / total * 100, 1) if total else 0,
    }


def tendencia_expansao(periodo: str = "12m") -> pd.DataFrame:
    """
    Por mês (dentro do período selecionado), quantas lojas faturaram mais que
    no mês IMEDIATAMENTE ANTERIOR (positivas) vs. menos (negativas) --
    NUNCA contra uma média histórica completa: comparar contra a média inteira
    enviesava o sinal (loja nova, com poucos meses de histórico, tinha sua
    própria média dominada pelos meses recentes e o desvio ficava artificialmente
    pequeno -- por isso aqui é sempre mês vs. mês anterior, sinal local, não
    a mesma conta de weekly_desvio_faturamento).

    Loja que abriu durante o período não entra em positivas/negativas no
    primeiro mês em que aparece (não há mês anterior pra comparar), mas conta
    em 'lojas_ativas' -- por isso esse total pode ser menor que 14 nos meses
    iniciais do período.
    """
    inicio, fim = _intervalo_periodo(periodo)
    vendas = load_vendas()

    # Sem filtro de início: precisa dos meses ANTERIORES ao período pra já ter
    # "mês anterior" pra comparar logo no primeiro mês do período selecionado.
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
