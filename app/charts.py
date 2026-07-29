"""
Gráficos renderizados no servidor com matplotlib, devolvidos como PNG em
base64. Escolha deliberada: evita depender de uma lib JS de gráficos no
cliente, mantendo a interatividade inteira no HTMX + Python -- o efeito
colateral é que não há tooltip ao passar o mouse sobre um ponto (é uma
imagem estática); por isso os valores relevantes são anotados diretamente
no gráfico.

Paleta segue os protótipos: vermelho (#BA1A1A) para a série em risco / Loja
A, verde-petróleo (#005A54) para a série de referência / Loja B, linha
tracejada cinza para a média histórica.
"""

from __future__ import annotations

import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import pandas as pd

VERMELHO = "#BA1A1A"
VERDE_PETROLEO = "#005A54"
CINZA = "#9AA1A9"
NOTA_RUIM = "#BA1A1A"
NOTA_MEDIA = "#D97706"
NOTA_BOA = "#10B981"

plt.rcParams.update({
    "font.size": 11,
    "axes.edgecolor": "#D5D8DC",
    "axes.labelcolor": "#4B5563",
    "axes.grid": True,
    "grid.color": "#EEF0F2",
    "grid.linewidth": 0.8,
    "text.color": "#374151",
    "xtick.color": "#6B7280",
    "ytick.color": "#6B7280",
    "legend.fontsize": 9.5,
})


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=160, transparent=True)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _clean_axes(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_axisbelow(True)


def _legend_abaixo(ax, ncol=2):
    """Legenda fora da área de plotagem -- em cima das linhas ela dificultava a leitura."""
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=ncol)


def _cor_por_nota(nota: float) -> str:
    if pd.isna(nota):
        return CINZA
    if nota < 3:
        return NOTA_RUIM
    if nota < 4:
        return NOTA_MEDIA
    return NOTA_BOA


def desvio_faturamento(semanal: pd.DataFrame) -> str:
    """Linha única do desvio (%) do faturamento semanal vs. média histórica da própria loja."""
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.axhline(0, color=CINZA, linewidth=1.4, linestyle="--", label="Média histórica")
    ax.plot(semanal["rotulo"], semanal["desvio_pct"], color=VERMELHO, linewidth=2.5,
            marker="o", markersize=6, label="Desvio semanal")
    for x, y in zip(semanal["rotulo"], semanal["desvio_pct"]):
        offset = 10 if y >= 0 else -14
        ax.annotate(f"{y:.0f}%", (x, y), textcoords="offset points", xytext=(0, offset),
                    ha="center", fontsize=8.5, color="#4B5563")
    ax.set_ylabel("Desvio vs. média histórica (%)")
    _clean_axes(ax)
    _legend_abaixo(ax)
    fig.tight_layout()
    return _fig_to_base64(fig)


def avaliacoes_volume_nota(semanal: pd.DataFrame) -> str:
    """
    Barras: altura = volume de avaliações na semana, cor = faixa da nota média
    (vermelho < 3, dourado 3-4, verde >= 4). Junta quantidade e qualidade num
    único gráfico de barras, em vez do combo linha+barra anterior.
    """
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    cores = [_cor_por_nota(n) for n in semanal["nota_media"]]
    barras = ax.bar(semanal["rotulo"], semanal["volume"], color=cores)

    for barra, nota in zip(barras, semanal["nota_media"]):
        rotulo_nota = f"{nota:.1f}" if pd.notna(nota) else "s/ nota"
        ax.annotate(rotulo_nota, (barra.get_x() + barra.get_width() / 2, barra.get_height()),
                    textcoords="offset points", xytext=(0, 5), ha="center",
                    fontsize=9, fontweight="bold", color="#374151")

    ax.set_ylabel("Volume de avaliações")
    _clean_axes(ax)

    legenda = [
        Patch(facecolor=NOTA_RUIM, label="Nota média < 3"),
        Patch(facecolor=NOTA_MEDIA, label="Nota média 3-4"),
        Patch(facecolor=NOTA_BOA, label="Nota média >= 4"),
    ]
    ax.legend(handles=legenda, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3)
    fig.tight_layout()
    return _fig_to_base64(fig)


def comparativo_faturamento_mensal(mensal_a: pd.DataFrame, mensal_b: pd.DataFrame, nome_a: str, nome_b: str) -> str:
    """Faturamento absoluto (R$) por mês, uma linha por loja."""
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    ax.plot(mensal_a["mes"].dt.strftime("%b/%y"), mensal_a["faturamento"], color=VERMELHO,
            linewidth=2.5, marker="o", markersize=6, label=nome_a)
    ax.plot(mensal_b["mes"].dt.strftime("%b/%y"), mensal_b["faturamento"], color=VERDE_PETROLEO,
            linewidth=2.5, marker="o", markersize=6, label=nome_b)
    ax.set_ylabel("Faturamento (R$)")
    ax.tick_params(axis="x", rotation=30)
    _clean_axes(ax)
    _legend_abaixo(ax, ncol=2)
    fig.tight_layout()
    return _fig_to_base64(fig)


def comparativo_desvio_faturamento(semanal_a: pd.DataFrame, semanal_b: pd.DataFrame, nome_a: str, nome_b: str) -> str:
    """
    Duas linhas do desvio (%) do faturamento semanal vs. a própria média
    histórica de cada loja -- mesma leitura da tela individual, mas com as
    duas lojas na mesma escala percentual (substitui a escala em p.p. de
    margem, que ficava difícil de comparar entre lojas de porte diferente).
    """
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    ax.axhline(0, color=CINZA, linewidth=1.4, linestyle="--", label="Média histórica")
    ax.plot(semanal_a["rotulo"], semanal_a["desvio_pct"], color=VERMELHO, linewidth=2.5,
            marker="o", markersize=6, label=nome_a)
    ax.plot(semanal_b["rotulo"], semanal_b["desvio_pct"], color=VERDE_PETROLEO, linewidth=2.5,
            marker="o", markersize=6, label=nome_b)
    ax.set_ylabel("Desvio de faturamento (%)")
    _clean_axes(ax)
    _legend_abaixo(ax, ncol=3)
    fig.tight_layout()
    return _fig_to_base64(fig)


def comparativo_avaliacoes(semanal_a: pd.DataFrame, semanal_b: pd.DataFrame, nome_a: str, nome_b: str) -> str:
    """
    Barras agrupadas (uma por loja, por semana): altura = volume de avaliações,
    cor = identidade da loja (vermelho/verde-petróleo), opacidade = nota média
    (mais clara = nota mais baixa). Anota a nota exata acima de cada barra.
    """
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    width = 0.32
    offset = 0.24
    x = range(len(semanal_a))

    def _alpha(nota):
        return 0.35 if pd.isna(nota) else max(0.35, min(1.0, 0.28 + 0.16 * nota))

    for i, (nota, volume) in enumerate(zip(semanal_a["nota_media"], semanal_a["volume"])):
        ax.bar(i - offset, volume, width=width, color=VERMELHO, alpha=_alpha(nota))
        if pd.notna(nota):
            ax.annotate(f"{nota:.1f}", (i - offset, volume), textcoords="offset points",
                        xytext=(0, 6), ha="center", fontsize=7.5, color="#374151")

    for i, (nota, volume) in enumerate(zip(semanal_b["nota_media"], semanal_b["volume"])):
        ax.bar(i + offset, volume, width=width, color=VERDE_PETROLEO, alpha=_alpha(nota))
        if pd.notna(nota):
            ax.annotate(f"{nota:.1f}", (i + offset, volume), textcoords="offset points",
                        xytext=(0, 6), ha="center", fontsize=7.5, color="#374151")

    ax.set_xticks(list(x))
    ax.set_xticklabels(semanal_a["rotulo"])
    ax.set_ylabel("Volume de avaliações")
    _clean_axes(ax)

    legenda = [
        Patch(facecolor=VERMELHO, label=f"{nome_a} (nota acima da barra)"),
        Patch(facecolor=VERDE_PETROLEO, label=f"{nome_b} (nota acima da barra)"),
    ]
    ax.legend(handles=legenda, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    fig.tight_layout()
    return _fig_to_base64(fig)
