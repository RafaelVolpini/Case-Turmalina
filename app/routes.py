from fastapi import APIRouter, Query, Request
from fastapi.templating import Jinja2Templates

from app import charts, data_loader as dl

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _sidebar_ctx(active_id: str | None = None, active_tab: str = "individual") -> dict:
    return {
        "lojas_sidebar": dl.list_stores_summary(),
        "active_loja": active_id,
        "active_tab": active_tab,
        "n_criticas": dl.N_LOJAS_INTERVENCAO,
    }


def _comparativo_ctx(loja_a: str, loja_b: str) -> dict:
    # id_loja pode chegar minúsculo de URL/query digitada à mão (o CSV já é
    # normalizado em data_loader, mas a entrada externa não é garantida).
    loja_a, loja_b = loja_a.strip().upper(), loja_b.strip().upper()
    metrics_a = dl.store_metrics(loja_a)
    metrics_b = dl.store_metrics(loja_b)

    semanal_fat_a, _ = dl.weekly_desvio_faturamento(loja_a)
    semanal_fat_b, _ = dl.weekly_desvio_faturamento(loja_b)
    mensal_fat_a = dl.monthly_faturamento(loja_a)
    mensal_fat_b = dl.monthly_faturamento(loja_b)
    semanal_aval_a = dl.weekly_avaliacoes(loja_a)
    semanal_aval_b = dl.weekly_avaliacoes(loja_b)

    return {
        "opcoes": dl.list_lojas_options(),
        "loja_a": loja_a,
        "loja_b": loja_b,
        "a": metrics_a,
        "b": metrics_b,
        "grafico_faturamento_mensal": charts.comparativo_faturamento_mensal(
            mensal_fat_a, mensal_fat_b, metrics_a["nome_loja"], metrics_b["nome_loja"],
        ),
        "grafico_desvio_faturamento": charts.comparativo_desvio_faturamento(
            semanal_fat_a, semanal_fat_b, metrics_a["nome_loja"], metrics_b["nome_loja"],
        ),
        "grafico_avaliacoes": charts.comparativo_avaliacoes(
            semanal_aval_a, semanal_aval_b, metrics_a["nome_loja"], metrics_b["nome_loja"],
        ),
        # Só os pontos de atenção aqui -- na tela de comparação o que importa é
        # o que está errado em cada loja, não os elogios (esses já ficam na
        # Análise Individual de cada uma).
        "comentarios_atencao_a": dl.comentarios_destaque(loja_a)["pontos_atencao"],
        "comentarios_atencao_b": dl.comentarios_destaque(loja_b)["pontos_atencao"],
    }


@router.get("/")
def prioridades(request: Request):
    ranking = dl.list_prioridades()
    criticas = ranking["criticas"]
    loja_a = criticas[0]["id_loja"]
    loja_b = criticas[1]["id_loja"] if len(criticas) > 1 else dl.list_lojas_options()[1]["id_loja"]

    is_htmx = _is_htmx(request)
    ctx = {
        "request": request,
        "criticas": criticas,
        "is_htmx": is_htmx,
        **_comparativo_ctx(loja_a, loja_b),
        **_sidebar_ctx(None, active_tab="prioridades"),
    }
    if is_htmx:
        return templates.TemplateResponse(request, "pages/prioridades.html", ctx)
    ctx["conteudo_inicial"] = "pages/prioridades.html"
    return templates.TemplateResponse(request, "base.html", ctx)


@router.get("/rede")
def rede(request: Request, periodo: str = "12m"):
    """
    Aba 'Rede': retrato de contexto da rede inteira (não acionável como
    Prioridades/Lojas) -- KPIs recalculados ao vivo pro período selecionado,
    contagem de lojas indo bem/mal no mês mais recente e tendência de
    expansão mês a mês (mês vs. mês anterior, nunca vs. média histórica
    completa -- ver nota em tendencia_expansao). Retrato e tendência vêm do
    mesmo DataFrame pra não haver duas fontes divergentes pro mesmo sinal.
    """
    if periodo not in dl.PERIODOS_REDE:
        periodo = "12m"

    kpis = dl.rede_kpis(periodo)
    mensal = dl.tendencia_expansao(periodo)
    retrato = dl.retrato_atual(mensal)

    is_htmx = _is_htmx(request)
    ctx = {
        "request": request,
        "kpis": kpis,
        "retrato": retrato,
        "periodos": dl.PERIODOS_REDE,
        "grafico_tendencia": charts.tendencia_expansao(mensal),
        "is_htmx": is_htmx,
        **_sidebar_ctx(None, active_tab="rede"),
    }
    if is_htmx:
        return templates.TemplateResponse(request, "pages/rede.html", ctx)
    ctx["conteudo_inicial"] = "pages/rede.html"
    return templates.TemplateResponse(request, "base.html", ctx)


@router.get("/analise")
def analise_individual_default(request: Request):
    primeira = dl.list_stores_summary()[0]["id_loja"]
    return analise_individual(request, id_loja=primeira)


@router.get("/lojas/{id_loja}")
def analise_individual(request: Request, id_loja: str):
    # idem: id_loja vem direto da URL, pode chegar minúsculo.
    id_loja = id_loja.strip().upper()
    metrics = dl.store_metrics(id_loja)
    semanal_faturamento, _ = dl.weekly_desvio_faturamento(id_loja)
    semanal_avaliacoes = dl.weekly_avaliacoes(id_loja)

    is_htmx = _is_htmx(request)
    ctx = {
        "request": request,
        "metrics": metrics,
        "is_htmx": is_htmx,
        "grafico_desvio_faturamento": charts.desvio_faturamento(semanal_faturamento),
        "grafico_avaliacoes": charts.avaliacoes_volume_nota(semanal_avaliacoes),
        "comentarios": dl.comentarios_destaque(id_loja),
        **_sidebar_ctx(id_loja, active_tab="individual"),
    }

    if is_htmx:
        return templates.TemplateResponse(request, "pages/analise_individual.html", ctx)
    ctx["conteudo_inicial"] = "pages/analise_individual.html"
    return templates.TemplateResponse(request, "base.html", ctx)


@router.get("/comparativo/fragment")
def comparativo_fragment(request: Request, loja_a: str = Query(...), loja_b: str = Query(...)):
    """Fragmento HTMX que atualiza só o bloco de comparação embutido na tela de Prioridades."""
    ctx = {"request": request, **_comparativo_ctx(loja_a, loja_b)}
    return templates.TemplateResponse(request, "components/comparativo_section.html", ctx)


@router.get("/relatorio")
def gerar_relatorio(request: Request):
    """Fragmento HTMX para o botão 'Generate Report' do header."""
    resumo = dl.list_stores_summary()
    criticas = [l for l in resumo if l["risco_critico"]]
    ctx = {"request": request, "resumo": resumo, "criticas": criticas}
    return templates.TemplateResponse(request, "components/relatorio_modal.html", ctx)
