"""Gera os gráficos Plotly do dashboard, como fragmentos HTML prontos pro template.
Entrada: nenhuma (módulo). Cada função recebe DataFrames já calculados por app/data_loader.py.
Retorno: cada função de gráfico devolve str (HTML do gráfico, sem o bundle do Plotly.js)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Tokens (docs/DESIGN.md) -- única fonte de verdade para cor/tipografia aqui.
# ---------------------------------------------------------------------------

INTER = "Inter, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

COLOR_PRIMARY = "#00413C"              # primary -- identidade "loja A" / série principal
COLOR_PRIMARY_CONTAINER = "#005A54"    # primary-container -- verde-petróleo, pontos positivos
COLOR_SECONDARY = "#725A42"            # secondary -- marrom-café, identidade "loja B"
COLOR_ERROR = "#BA1A1A"                # error -- ÚNICO uso: alerta / variação negativa forte
COLOR_SUCCESS = "#10B981"              # nota boa (>= 4)
COLOR_WARNING = "#D97706"              # nota média (3-4)
COLOR_NEUTRAL_LINE = "#6F7977"         # outline -- linha de referência (média histórica)

SURFACE_CONTAINER_LOWEST = "#FFFFFF"   # fundo do card / tooltip
ON_SURFACE = "#121C2A"
ON_SURFACE_VARIANT = "#3F4947"
GRID_COLOR = "#E6EEFF"                 # surface-container, grade discreta

LIMIAR_QUEDA_FORTE_PP = -8.0  # abaixo disso (p.p.), o ponto vira vermelho (alerta), não a série toda

_MESES_PT = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}


def _rotulo_semana(data: pd.Timestamp) -> str:
    """Formata uma data como rótulo de semana no eixo X.
    Entrada: data (pd.Timestamp), início da semana.
    Retorno: str no formato "dd/Mmm/aa"."""
    return f"{data.day:02d}/{_MESES_PT[data.month]}/{data.strftime('%y')}"


def _rotulo_mes(data: pd.Timestamp) -> str:
    """Formata uma data como rótulo de mês no eixo X, em pt-BR.
    Entrada: data (pd.Timestamp), início do mês.
    Retorno: str no formato "Mmm/aa"."""
    return f"{_MESES_PT[data.month]}/{data.strftime('%y')}"


def _cor_por_nota(nota: float) -> str:
    """Escolhe a cor da faixa de uma nota de avaliação.
    Entrada: nota (float), pode ser NaN.
    Retorno: str, código de cor hex."""
    if pd.isna(nota):
        return ON_SURFACE_VARIANT
    if nota < 3:
        return COLOR_ERROR
    if nota < 4:
        return COLOR_WARNING
    return COLOR_SUCCESS


def _texto_nota(nota: float) -> str:
    """Formata uma nota de avaliação como texto de hover.
    Entrada: nota (float), pode ser NaN.
    Retorno: str, ex. "4.5 de 5" ou "sem nota registrada"."""
    return f"{nota:.1f} de 5" if pd.notna(nota) else "sem nota registrada"


def _fmt_moeda(valor: float) -> str:
    """Formata um valor em reais sem casas decimais e com separador de milhar.
    Entrada: valor (float).
    Retorno: str."""
    return "{:,.0f}".format(valor).replace(",", ".")


def _hoverlabel() -> dict:
    """Monta o estilo do tooltip do Plotly, alinhado ao design system.
    Entrada: nenhuma.
    Retorno: dict de configuração de hoverlabel."""
    return dict(
        bgcolor=SURFACE_CONTAINER_LOWEST,
        bordercolor=COLOR_PRIMARY,
        font=dict(family=INTER, size=14, color=ON_SURFACE),  # body-md
    )


def _legend_horizontal_abaixo(ncol_hint: int = 2) -> dict:
    """Monta a legenda horizontal fixa abaixo da área de plotagem.
    Entrada: ncol_hint (int, não usado).
    Retorno: dict de configuração de legend."""
    return dict(
        orientation="h",
        yanchor="top",
        y=-0.22,
        xanchor="center",
        x=0.5,
        font=dict(family=INTER, size=12, color=ON_SURFACE),  # label-md
        bgcolor="rgba(0,0,0,0)",
    )


def _apply_layout(
    fig: go.Figure, y_title: str, height: int = 360, top_margin: int = 16,
    y_range: list | None = None, x_categoryarray: list | None = None,
) -> go.Figure:
    """Aplica fonte, cores, legenda, hover e eixos padrão do design system a um gráfico.
    Entrada: fig (go.Figure), y_title (str), height/top_margin (int), y_range (list | None), x_categoryarray (list | None).
    Retorno: go.Figure, o mesmo objeto recebido."""
    fig.update_layout(
        autosize=True,
        font=dict(family=INTER, size=13, color=ON_SURFACE),
        plot_bgcolor=SURFACE_CONTAINER_LOWEST,
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=_hoverlabel(),
        hovermode="x unified",  # caixa única no topo do gráfico, nunca sobre o ponto/linha
        legend=_legend_horizontal_abaixo(),
        margin=dict(l=56, r=16, t=top_margin, b=72),
        height=height,
        bargap=0.35,
    )
    xaxis_kwargs = dict(
        showgrid=False,
        linecolor=GRID_COLOR,
        tickfont=dict(family=INTER, size=12, color=ON_SURFACE_VARIANT),
    )
    if x_categoryarray is not None:
        xaxis_kwargs.update(categoryorder="array", categoryarray=x_categoryarray)  # ordem cronológica explícita, não ordem de inserção
    fig.update_xaxes(**xaxis_kwargs)
    fig.update_yaxes(
        showgrid=True,
        gridcolor=GRID_COLOR,
        zeroline=False,
        range=y_range,
        tickfont=dict(family=INTER, size=12, color=ON_SURFACE_VARIANT),
        title=dict(text=y_title, font=dict(family=INTER, size=12, color=ON_SURFACE_VARIANT)),
    )
    return fig


def _headroom(*volumes: pd.Series, factor: float = 1.28) -> list:
    """Amplia o teto do eixo Y pra o rótulo de texto acima da barra não ser cortado.
    Entrada: volumes (pd.Series, um ou mais), factor (float, multiplicador do máximo).
    Retorno: list [0, topo] pro range do eixo Y."""
    maximo = max((v.max() for v in volumes if len(v)), default=0)
    topo = maximo * factor if maximo > 0 else 1
    return [0, topo]


def _to_html(fig: go.Figure) -> str:
    """Serializa uma figura Plotly como fragmento HTML, sem o bundle do Plotly.js.
    Entrada: fig (go.Figure).
    Retorno: str."""
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False, "responsive": True},
    )


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------

def desvio_margem(semanal: pd.DataFrame) -> str:
    """Desenha a linha de desvio semanal de margem operacional de uma loja.
    Entrada: semanal (pd.DataFrame) com as colunas semana e desvio_pp.
    Retorno: str (HTML do gráfico)."""
    x = semanal["semana"].apply(_rotulo_semana)
    cores_pontos = [
        COLOR_ERROR if v <= LIMIAR_QUEDA_FORTE_PP else COLOR_PRIMARY_CONTAINER
        for v in semanal["desvio_pp"]
    ]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=[0] * len(semanal),
        mode="lines", name="Média histórica (referência)",
        line=dict(color=COLOR_NEUTRAL_LINE, width=1.5, dash="dash"),
        hoverinfo="skip",  # hover unificado repetiria este texto em todo x; legenda já identifica a linha
    ))
    fig.add_trace(go.Scatter(
        x=x, y=semanal["desvio_pp"],
        mode="lines+markers", name="Desvio semanal de margem",
        line=dict(color=COLOR_PRIMARY, width=2.5),
        marker=dict(size=10, color=cores_pontos, line=dict(color="#FFFFFF", width=1)),
        hovertemplate="Desvio de margem: %{y:.1f} p.p. vs. média histórica da loja<extra></extra>",
    ))
    _apply_layout(fig, y_title="Desvio vs. média histórica (p.p.)")
    return _to_html(fig)


def avaliacoes_volume_nota(semanal: pd.DataFrame) -> str:
    """Desenha as barras de volume e nota média de avaliações por semana de uma loja.
    Entrada: semanal (pd.DataFrame) com as colunas semana, nota_media e volume.
    Retorno: str (HTML do gráfico)."""
    x = semanal["semana"].apply(_rotulo_semana)
    cores = [_cor_por_nota(n) for n in semanal["nota_media"]]
    texto_barra = [f"{n:.1f}" if pd.notna(n) else "s/ nota" for n in semanal["nota_media"]]
    texto_hover = [_texto_nota(n) for n in semanal["nota_media"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=x, y=semanal["volume"],
        marker_color=cores, showlegend=False,
        text=texto_barra, textposition="outside",
        textfont=dict(family=INTER, size=11, color=ON_SURFACE),
        customdata=texto_hover,
        hovertemplate="Volume de avaliações: %{y}<br>Nota média: %{customdata}<extra></extra>",
    ))

    # traços fantasma (x/y=[None]) só pra expor a legenda de faixa de cor
    for rotulo, cor in [
        ("Nota média abaixo de 3 (alerta)", COLOR_ERROR),
        ("Nota média entre 3 e 4", COLOR_WARNING),
        ("Nota média acima de 4", COLOR_SUCCESS),
    ]:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers", marker=dict(symbol="square", size=12, color=cor),
            name=rotulo, hoverinfo="skip",
        ))

    _apply_layout(
        fig, y_title="Volume de avaliações",
        top_margin=36, y_range=_headroom(semanal["volume"]),
    )
    return _to_html(fig)


def comparativo_faturamento_mensal(mensal_a: pd.DataFrame, mensal_b: pd.DataFrame, nome_a: str, nome_b: str) -> str:
    """Desenha o faturamento mensal de duas lojas, com linha de média de cada uma.
    Entrada: mensal_a, mensal_b (pd.DataFrame, mesmo eixo de meses, ver data_loader.monthly_faturamento_comparativo), nome_a, nome_b (str).
    Retorno: str (HTML do gráfico)."""
    x = mensal_a["mes"].apply(_rotulo_mes)  # eixo compartilhado -- x_a e x_b são idênticos
    fmt_a = [_fmt_moeda(v) if pd.notna(v) else "N/D" for v in mensal_a["faturamento"]]
    fmt_b = [_fmt_moeda(v) if pd.notna(v) else "N/D" for v in mensal_b["faturamento"]]
    media_a = mensal_a["faturamento"].mean()
    media_b = mensal_b["faturamento"].mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=mensal_a["faturamento"], mode="lines+markers", name=nome_a,
        line=dict(color=COLOR_PRIMARY, width=2.5), marker=dict(size=8, color=COLOR_PRIMARY),
        connectgaps=False, customdata=fmt_a,
        hovertemplate=f"Faturamento de {nome_a}: R$ %{{customdata}}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=[media_a] * len(mensal_a), mode="lines", name=f"Média de {nome_a}",
        line=dict(color=COLOR_PRIMARY, width=1.3, dash="dot"),
        hovertemplate=f"Média mensal de {nome_a} no período: R$ {_fmt_moeda(media_a)}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=mensal_b["faturamento"], mode="lines+markers", name=nome_b,
        line=dict(color=COLOR_SECONDARY, width=2.5), marker=dict(size=8, color=COLOR_SECONDARY),
        connectgaps=False, customdata=fmt_b,
        hovertemplate=f"Faturamento de {nome_b}: R$ %{{customdata}}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=[media_b] * len(mensal_b), mode="lines", name=f"Média de {nome_b}",
        line=dict(color=COLOR_SECONDARY, width=1.3, dash="dot"),
        hovertemplate=f"Média mensal de {nome_b} no período: R$ {_fmt_moeda(media_b)}<extra></extra>",
    ))
    _apply_layout(fig, y_title="Faturamento (R$)", x_categoryarray=list(x))
    return _to_html(fig)


def comparativo_desvio_margem(mensal_a: pd.DataFrame, mensal_b: pd.DataFrame, nome_a: str, nome_b: str) -> str:
    """Desenha o desvio mensal de margem operacional de duas lojas no mesmo eixo.
    Entrada: mensal_a, mensal_b (pd.DataFrame, mesmo eixo de meses, ver data_loader.monthly_desvio_margem_comparativo), nome_a, nome_b (str).
    Retorno: str (HTML do gráfico)."""
    x = mensal_a["mes"].apply(_rotulo_mes)  # eixo compartilhado -- x_a e x_b são idênticos
    # NaN em desvio_pp = loja sem mês completo/com venda; connectgaps=False deixa o buraco visível
    cores_a = [COLOR_ERROR if pd.notna(v) and v <= LIMIAR_QUEDA_FORTE_PP else COLOR_PRIMARY for v in mensal_a["desvio_pp"]]
    cores_b = [COLOR_ERROR if pd.notna(v) and v <= LIMIAR_QUEDA_FORTE_PP else COLOR_SECONDARY for v in mensal_b["desvio_pp"]]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=[0] * len(mensal_a),
        mode="lines", name="0 p.p. = média histórica de cada loja",
        line=dict(color=COLOR_NEUTRAL_LINE, width=1.5, dash="dash"),
        hoverinfo="skip",  # ver nota em desvio_margem() sobre ruído em hover unificado
    ))
    fig.add_trace(go.Scatter(
        x=x, y=mensal_a["desvio_pp"], mode="lines+markers", name=nome_a,
        line=dict(color=COLOR_PRIMARY, width=2.5), connectgaps=False,
        marker=dict(size=9, color=cores_a, line=dict(color="#FFFFFF", width=1)),
        hovertemplate=f"{nome_a}: %{{y:.1f}} p.p. vs. média histórica da própria loja<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=mensal_b["desvio_pp"], mode="lines+markers", name=nome_b,
        line=dict(color=COLOR_SECONDARY, width=2.5), connectgaps=False,
        marker=dict(size=9, color=cores_b, line=dict(color="#FFFFFF", width=1)),
        hovertemplate=f"{nome_b}: %{{y:.1f}} p.p. vs. média histórica da própria loja<extra></extra>",
    ))
    _apply_layout(fig, y_title="Desvio de margem (p.p.)", x_categoryarray=list(x))
    return _to_html(fig)


def comparativo_avaliacoes(mensal_a: pd.DataFrame, mensal_b: pd.DataFrame, nome_a: str, nome_b: str) -> str:
    """Desenha volume e nota média de avaliações de duas lojas, em barras agrupadas por mês.
    Entrada: mensal_a, mensal_b (pd.DataFrame, mesmo eixo de meses, ver data_loader.monthly_avaliacoes_comparativo), nome_a, nome_b (str).
    Retorno: str (HTML do gráfico)."""
    x = mensal_a["mes"].apply(_rotulo_mes)  # eixo compartilhado -- x_a e x_b são idênticos
    # loja A sólida, loja B com textura diagonal -- cor já é usada pra faixa de nota
    cores_a = [_cor_por_nota(n) for n in mensal_a["nota_media"]]
    cores_b = [_cor_por_nota(n) for n in mensal_b["nota_media"]]
    texto_a = [f"{n:.1f}" if pd.notna(n) else "s/ nota" for n in mensal_a["nota_media"]]
    texto_b = [f"{n:.1f}" if pd.notna(n) else "s/ nota" for n in mensal_b["nota_media"]]
    hover_nota_a = [_texto_nota(n) for n in mensal_a["nota_media"]]
    hover_nota_b = [_texto_nota(n) for n in mensal_b["nota_media"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=x, y=mensal_a["volume"], name=nome_a, showlegend=False,
        marker=dict(color=cores_a, pattern=dict(shape=""), line=dict(color="#FFFFFF", width=1)),
        text=texto_a, textposition="outside", textfont=dict(family=INTER, size=10.5, color=ON_SURFACE),
        customdata=hover_nota_a,
        hovertemplate=f"{nome_a} · volume de avaliações: %{{y}}<br>Nota média: %{{customdata}}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=x, y=mensal_b["volume"], name=nome_b, showlegend=False,
        marker=dict(color=cores_b, pattern=dict(shape="/", fgcolor="#FFFFFF", size=6, solidity=0.35), line=dict(color="#FFFFFF", width=1)),
        text=texto_b, textposition="outside", textfont=dict(family=INTER, size=10.5, color=ON_SURFACE),
        customdata=hover_nota_b,
        hovertemplate=f"{nome_b} · volume de avaliações: %{{y}}<br>Nota média: %{{customdata}}<extra></extra>",
    ))

    # traços fantasma: cor explica a nota, textura explica qual loja é qual
    for rotulo, cor in [
        ("Nota média abaixo de 3 (alerta)", COLOR_ERROR),
        ("Nota média entre 3 e 4", COLOR_WARNING),
        ("Nota média acima de 4", COLOR_SUCCESS),
    ]:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers", marker=dict(symbol="square", size=12, color=cor),
            name=rotulo, hoverinfo="skip",
        ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="markers", name=f"{nome_a} (sólido)", hoverinfo="skip",
        marker=dict(symbol="square", size=12, color=ON_SURFACE_VARIANT),
    ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="markers", name=f"{nome_b} (textura)", hoverinfo="skip",
        marker=dict(symbol="square-open", size=12, color=ON_SURFACE_VARIANT, line=dict(width=2)),
    ))

    fig.update_layout(barmode="group")
    _apply_layout(
        fig, y_title="Volume de avaliações",
        top_margin=36, y_range=_headroom(mensal_a["volume"], mensal_b["volume"]),
        x_categoryarray=list(x),
    )
    return _to_html(fig)


def tendencia_expansao(mensal: pd.DataFrame) -> str:
    """Desenha barras divergentes de lojas faturando mais ou menos que no mês anterior.
    Entrada: mensal (pd.DataFrame) com as colunas mes, positivas, negativas e lojas_ativas (ver data_loader.tendencia_expansao).
    Retorno: str (HTML do gráfico)."""
    x = mensal["mes"].apply(_rotulo_mes)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=x, y=mensal["positivas"], name="Lojas crescendo vs. mês anterior",
        marker_color=COLOR_SUCCESS,
        customdata=mensal["lojas_ativas"],
        hovertemplate="%{y} loja(s) faturaram mais que no mês anterior<br>Lojas ativas no mês: %{customdata}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=x, y=-mensal["negativas"], name="Lojas encolhendo vs. mês anterior",
        marker_color=COLOR_ERROR,
        customdata=list(zip(mensal["negativas"], mensal["lojas_ativas"])),
        hovertemplate="%{customdata[0]} loja(s) faturaram menos que no mês anterior<br>Lojas ativas no mês: %{customdata[1]}<extra></extra>",
    ))
    fig.add_hline(y=0, line_width=1.5, line_color=COLOR_NEUTRAL_LINE)

    _apply_layout(fig, y_title="Nº de lojas vs. mês anterior", top_margin=16)
    fig.update_yaxes(tickformat="d")
    return _to_html(fig)
