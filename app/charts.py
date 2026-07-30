"""
Gráficos renderizados no servidor com Plotly, devolvidos como fragmento HTML
(<div> + <script>) para embutir direto no template via `{{ ... | safe }}`.

Escolha deliberada: mantém tudo em Python (pip install plotly, sem passo de
build, sem npm/npx) -- o único JavaScript envolvido é o bundle do Plotly.js
carregado uma única vez via <script> no <head> de base.html; cada função
aqui só gera o HTML do gráfico (`fig.to_html(include_plotlyjs=False, ...)`),
reaproveitando esse bundle já carregado na página.

Paleta, tipografia, raio e hoverlabel seguem os tokens de docs/DESIGN.md:
vermelho (#BA1A1A) é usado *só* como sinal de alerta -- ponto/nota/loja em
variação negativa forte --, nunca como identidade fixa de série. As duas
lojas comparadas usam verde-petróleo (#00413C, primary) e marrom-café
(#725A42, secondary) como identidade neutra.
"""

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

LIMIAR_QUEDA_FORTE_PCT = -8.0  # abaixo disso, o ponto vira vermelho (alerta), não a série toda

_MESES_PT = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}


def _rotulo_semana(data: pd.Timestamp) -> str:
    """dd/Mmm/aa (ex.: '12/Mai/25') -- em vez do rótulo posicional 'S-7'/'Atual',
    que não dizia a que semana do calendário cada ponto correspondia."""
    return f"{data.day:02d}/{_MESES_PT[data.month]}/{data.strftime('%y')}"


def _rotulo_mes(data: pd.Timestamp) -> str:
    """Mmm/aa (ex.: 'Mai/25'), nomes de mês em pt-BR -- strftime('%b') sai em inglês."""
    return f"{_MESES_PT[data.month]}/{data.strftime('%y')}"


def _cor_por_nota(nota: float) -> str:
    if pd.isna(nota):
        return ON_SURFACE_VARIANT
    if nota < 3:
        return COLOR_ERROR
    if nota < 4:
        return COLOR_WARNING
    return COLOR_SUCCESS


def _texto_nota(nota: float) -> str:
    return f"{nota:.1f} de 5" if pd.notna(nota) else "sem nota registrada"


def _fmt_moeda(valor: float) -> str:
    return "{:,.0f}".format(valor).replace(",", ".")


def _hoverlabel() -> dict:
    """Tooltip totalmente adaptado ao design system -- nunca o cinza padrão do Plotly."""
    return dict(
        bgcolor=SURFACE_CONTAINER_LOWEST,
        bordercolor=COLOR_PRIMARY,
        font=dict(family=INTER, size=14, color=ON_SURFACE),  # body-md
    )


def _legend_horizontal_abaixo(ncol_hint: int = 2) -> dict:
    """Legenda sempre visível, horizontal, abaixo da área de plotagem -- nunca por cima dos dados."""
    return dict(
        orientation="h",
        yanchor="top",
        y=-0.22,
        xanchor="center",
        x=0.5,
        font=dict(family=INTER, size=12, color=ON_SURFACE),  # label-md
        bgcolor="rgba(0,0,0,0)",
    )


def _apply_layout(fig: go.Figure, y_title: str, height: int = 360, top_margin: int = 16, y_range: list | None = None) -> go.Figure:
    fig.update_layout(
        autosize=True,
        font=dict(family=INTER, size=13, color=ON_SURFACE),
        plot_bgcolor=SURFACE_CONTAINER_LOWEST,
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=_hoverlabel(),
        legend=_legend_horizontal_abaixo(),
        margin=dict(l=56, r=16, t=top_margin, b=72),
        height=height,
        bargap=0.35,
    )
    fig.update_xaxes(
        showgrid=False,
        linecolor=GRID_COLOR,
        tickfont=dict(family=INTER, size=12, color=ON_SURFACE_VARIANT),
    )
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
    """Amplia o teto do eixo Y pra o rótulo 'outside' (nota acima da barra) não
    ser cortado pela borda do gráfico -- o auto-range do Plotly não reserva
    espaço pra texto fora da barra."""
    maximo = max((v.max() for v in volumes if len(v)), default=0)
    topo = maximo * factor if maximo > 0 else 1
    return [0, topo]


def _to_html(fig: go.Figure) -> str:
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False, "responsive": True},
    )


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------

def desvio_faturamento(semanal: pd.DataFrame) -> str:
    """Linha única do desvio (%) do faturamento semanal vs. média histórica da própria loja."""
    x = semanal["semana"].apply(_rotulo_semana)
    cores_pontos = [
        COLOR_ERROR if v <= LIMIAR_QUEDA_FORTE_PCT else COLOR_PRIMARY_CONTAINER
        for v in semanal["desvio_pct"]
    ]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=[0] * len(semanal),
        mode="lines", name="Média histórica (referência)",
        line=dict(color=COLOR_NEUTRAL_LINE, width=1.5, dash="dash"),
        hovertemplate="Referência: média histórica de faturamento da loja (0%)<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=semanal["desvio_pct"],
        mode="lines+markers", name="Desvio semanal de faturamento",
        line=dict(color=COLOR_PRIMARY, width=2.5),
        marker=dict(size=10, color=cores_pontos, line=dict(color="#FFFFFF", width=1)),
        hovertemplate="<b>%{x}</b><br>Desvio de faturamento: %{y:.1f}% vs. média histórica da loja<extra></extra>",
    ))
    _apply_layout(fig, y_title="Desvio vs. média histórica (%)")
    return _to_html(fig)


def avaliacoes_volume_nota(semanal: pd.DataFrame) -> str:
    """
    Barras: altura = volume de avaliações na semana, cor = faixa da nota média
    (vermelho < 3 = alerta, âmbar 3-4, verde >= 4). Sempre em barras -- nunca
    linha -- para deixar claro que cada barra é uma contagem discreta por semana.
    """
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
        hovertemplate="<b>%{x}</b><br>Volume de avaliações: %{y}<br>Nota média: %{customdata}<extra></extra>",
    ))

    # Entradas de legenda "fantasma" (sem dado real) só para expor a faixa de cor,
    # já que a barra real varia de cor por ponto e não teria legenda própria.
    # Scatter (não Bar): um traço Bar a mais aqui dividiria a largura das
    # barras reais no barmode, deixando-as finas sem necessidade.
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
    """
    Faturamento absoluto (R$) por mês, uma linha por loja -- identidade neutra,
    sem vermelho. Cada loja ganha também uma linha pontilhada com a própria
    média mensal no período mostrado, pra dar uma referência de "acima ou
    abaixo do normal" (sem isso, só dava pra comparar mês a mês entre as duas
    lojas, nunca cada loja contra o próprio histórico).
    """
    x_a = mensal_a["mes"].apply(_rotulo_mes)
    x_b = mensal_b["mes"].apply(_rotulo_mes)
    fmt_a = [_fmt_moeda(v) for v in mensal_a["faturamento"]]
    fmt_b = [_fmt_moeda(v) for v in mensal_b["faturamento"]]
    media_a = mensal_a["faturamento"].mean()
    media_b = mensal_b["faturamento"].mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_a, y=mensal_a["faturamento"], mode="lines+markers", name=nome_a,
        line=dict(color=COLOR_PRIMARY, width=2.5), marker=dict(size=8, color=COLOR_PRIMARY),
        customdata=fmt_a,
        hovertemplate=f"<b>%{{x}}</b><br>Faturamento de {nome_a}: R$ %{{customdata}}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x_a, y=[media_a] * len(mensal_a), mode="lines", name=f"Média de {nome_a}",
        line=dict(color=COLOR_PRIMARY, width=1.3, dash="dot"),
        hovertemplate=f"Média mensal de {nome_a} no período: R$ {_fmt_moeda(media_a)}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x_b, y=mensal_b["faturamento"], mode="lines+markers", name=nome_b,
        line=dict(color=COLOR_SECONDARY, width=2.5), marker=dict(size=8, color=COLOR_SECONDARY),
        customdata=fmt_b,
        hovertemplate=f"<b>%{{x}}</b><br>Faturamento de {nome_b}: R$ %{{customdata}}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x_b, y=[media_b] * len(mensal_b), mode="lines", name=f"Média de {nome_b}",
        line=dict(color=COLOR_SECONDARY, width=1.3, dash="dot"),
        hovertemplate=f"Média mensal de {nome_b} no período: R$ {_fmt_moeda(media_b)}<extra></extra>",
    ))
    _apply_layout(fig, y_title="Faturamento (R$)")
    return _to_html(fig)


def comparativo_desvio_faturamento(semanal_a: pd.DataFrame, semanal_b: pd.DataFrame, nome_a: str, nome_b: str) -> str:
    """
    Duas linhas do desvio (%) do faturamento semanal vs. a própria média
    histórica de cada loja. Identidade de série é sempre verde-petróleo (loja A)
    e marrom-café (loja B) -- o vermelho só aparece nos pontos de queda forte
    (<= -8%), independente de qual loja é "A" ou "B" na comparação.
    """
    x_a = semanal_a["semana"].apply(_rotulo_semana)
    x_b = semanal_b["semana"].apply(_rotulo_semana)
    cores_a = [COLOR_ERROR if v <= LIMIAR_QUEDA_FORTE_PCT else COLOR_PRIMARY for v in semanal_a["desvio_pct"]]
    cores_b = [COLOR_ERROR if v <= LIMIAR_QUEDA_FORTE_PCT else COLOR_SECONDARY for v in semanal_b["desvio_pct"]]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_a, y=[0] * len(semanal_a),
        mode="lines", name="0% = média histórica de cada loja",
        line=dict(color=COLOR_NEUTRAL_LINE, width=1.5, dash="dash"),
        hovertemplate=(
            "0% é o ponto de referência de cada loja contra a própria média "
            "histórica, não é um valor único: a média de "
            f"{nome_a} e a de {nome_b} são diferentes, ambas caem em 0% aqui "
            "porque o gráfico mostra desvio relativo, não R$ absoluto.<extra></extra>"
        ),
    ))
    fig.add_trace(go.Scatter(
        x=x_a, y=semanal_a["desvio_pct"], mode="lines+markers", name=nome_a,
        line=dict(color=COLOR_PRIMARY, width=2.5),
        marker=dict(size=9, color=cores_a, line=dict(color="#FFFFFF", width=1)),
        hovertemplate=f"<b>%{{x}}</b><br>Desvio de faturamento de {nome_a}: %{{y:.1f}}% vs. média histórica da própria loja<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x_b, y=semanal_b["desvio_pct"], mode="lines+markers", name=nome_b,
        line=dict(color=COLOR_SECONDARY, width=2.5),
        marker=dict(size=9, color=cores_b, line=dict(color="#FFFFFF", width=1)),
        hovertemplate=f"<b>%{{x}}</b><br>Desvio de faturamento de {nome_b}: %{{y:.1f}}% vs. média histórica da própria loja<extra></extra>",
    ))
    _apply_layout(fig, y_title="Desvio de faturamento (%)")
    return _to_html(fig)


def comparativo_avaliacoes(semanal_a: pd.DataFrame, semanal_b: pd.DataFrame, nome_a: str, nome_b: str) -> str:
    """
    Barras agrupadas (uma por loja, por semana): altura = volume de avaliações,
    cor = faixa da nota média (vermelho < 3, âmbar 3-4, verde >= 4) -- mesmo
    padrão do gráfico de Avaliações da Análise Individual. Como a cor já é
    ocupada pela nota, loja A e loja B se diferenciam por textura (A sólida,
    B com textura diagonal), não por cor.
    """
    x_a = semanal_a["semana"].apply(_rotulo_semana)
    x_b = semanal_b["semana"].apply(_rotulo_semana)
    cores_a = [_cor_por_nota(n) for n in semanal_a["nota_media"]]
    cores_b = [_cor_por_nota(n) for n in semanal_b["nota_media"]]
    texto_a = [f"{n:.1f}" if pd.notna(n) else "s/ nota" for n in semanal_a["nota_media"]]
    texto_b = [f"{n:.1f}" if pd.notna(n) else "s/ nota" for n in semanal_b["nota_media"]]
    hover_nota_a = [_texto_nota(n) for n in semanal_a["nota_media"]]
    hover_nota_b = [_texto_nota(n) for n in semanal_b["nota_media"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=x_a, y=semanal_a["volume"], name=nome_a, showlegend=False,
        marker=dict(color=cores_a, pattern=dict(shape=""), line=dict(color="#FFFFFF", width=1)),
        text=texto_a, textposition="outside", textfont=dict(family=INTER, size=10.5, color=ON_SURFACE),
        customdata=hover_nota_a,
        hovertemplate=f"<b>%{{x}}</b><br>{nome_a} · volume de avaliações: %{{y}}<br>Nota média: %{{customdata}}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=x_b, y=semanal_b["volume"], name=nome_b, showlegend=False,
        marker=dict(color=cores_b, pattern=dict(shape="/", fgcolor="#FFFFFF", size=6, solidity=0.35), line=dict(color="#FFFFFF", width=1)),
        text=texto_b, textposition="outside", textfont=dict(family=INTER, size=10.5, color=ON_SURFACE),
        customdata=hover_nota_b,
        hovertemplate=f"<b>%{{x}}</b><br>{nome_b} · volume de avaliações: %{{y}}<br>Nota média: %{{customdata}}<extra></extra>",
    ))

    # Legenda "fantasma": cor explica a nota, textura explica qual loja é qual.
    # Scatter (não Bar): um traço Bar a mais aqui dividiria a largura das
    # barras reais no barmode, deixando-as finas sem necessidade.
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
        top_margin=36, y_range=_headroom(semanal_a["volume"], semanal_b["volume"]),
    )
    return _to_html(fig)


def tendencia_expansao(mensal: pd.DataFrame) -> str:
    """
    Barras divergentes por mês: quantas lojas faturaram mais (verde, acima de
    zero) ou menos (vermelho, abaixo de zero) que no mês IMEDIATAMENTE
    ANTERIOR -- nunca contra uma média histórica completa (ver
    data_loader.tendencia_expansao). `mensal` já vem calculado de lá, com
    colunas mes/positivas/negativas/lojas_ativas.
    """
    x = mensal["mes"].apply(_rotulo_mes)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=x, y=mensal["positivas"], name="Lojas crescendo vs. mês anterior",
        marker_color=COLOR_SUCCESS,
        customdata=mensal["lojas_ativas"],
        hovertemplate="<b>%{x}</b><br>%{y} loja(s) faturaram mais que no mês anterior<br>Lojas ativas no mês: %{customdata}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=x, y=-mensal["negativas"], name="Lojas encolhendo vs. mês anterior",
        marker_color=COLOR_ERROR,
        customdata=list(zip(mensal["negativas"], mensal["lojas_ativas"])),
        hovertemplate="<b>%{x}</b><br>%{customdata[0]} loja(s) faturaram menos que no mês anterior<br>Lojas ativas no mês: %{customdata[1]}<extra></extra>",
    ))
    fig.add_hline(y=0, line_width=1.5, line_color=COLOR_NEUTRAL_LINE)

    _apply_layout(fig, y_title="Nº de lojas vs. mês anterior", top_margin=16)
    fig.update_yaxes(tickformat="d")
    return _to_html(fig)
