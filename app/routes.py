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
    }


@router.get("/")
def prioridades(request: Request):
    ranking = dl.list_prioridades()
    criticas = ranking["criticas"]
    loja_a = criticas[0]["id_loja"]
    loja_b = criticas[1]["id_loja"] if len(criticas) > 1 else dl.list_lojas_options()[1]["id_loja"]

    ctx = {
        "request": request,
        "criticas": criticas,
        **_comparativo_ctx(loja_a, loja_b),
        **_sidebar_ctx(None, active_tab="prioridades"),
    }
    if _is_htmx(request):
        return templates.TemplateResponse(request, "pages/prioridades.html", ctx)
    ctx["conteudo_inicial"] = "pages/prioridades.html"
    return templates.TemplateResponse(request, "base.html", ctx)


@router.get("/analise")
def analise_individual_default(request: Request):
    primeira = dl.list_stores_summary()[0]["id_loja"]
    return analise_individual(request, id_loja=primeira)


@router.get("/lojas/{id_loja}")
def analise_individual(request: Request, id_loja: str):
    metrics = dl.store_metrics(id_loja)
    semanal_faturamento, _ = dl.weekly_desvio_faturamento(id_loja)
    semanal_avaliacoes = dl.weekly_avaliacoes(id_loja)

    ctx = {
        "request": request,
        "metrics": metrics,
        "grafico_desvio_faturamento": charts.desvio_faturamento(semanal_faturamento),
        "grafico_avaliacoes": charts.avaliacoes_volume_nota(semanal_avaliacoes),
        "comentarios_criticos": dl.comentarios_criticos(id_loja),
        **_sidebar_ctx(id_loja, active_tab="individual"),
    }

    if _is_htmx(request):
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
