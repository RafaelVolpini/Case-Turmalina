from fastapi import APIRouter, Query, Request
from fastapi.templating import Jinja2Templates

from app import charts, data_loader as dl

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _is_htmx(request: Request) -> bool:
    """Detecta se a requisição veio de um fragmento HTMX.
    Entrada: request (Request).
    Retorno: bool."""
    return request.headers.get("HX-Request") == "true"


def _sidebar_ctx(active_id: str | None = None, active_tab: str = "individual") -> dict:
    """Monta o contexto de template da sidebar de lojas.
    Entrada: active_id (str | None, loja selecionada), active_tab (str, aba ativa).
    Retorno: dict com lojas_sidebar, active_loja, active_tab e n_criticas."""
    return {
        "lojas_sidebar": dl.list_stores_summary(),
        "active_loja": active_id,
        "active_tab": active_tab,
        "n_criticas": dl.N_LOJAS_INTERVENCAO,
    }


def _comparativo_ctx(loja_a: str, loja_b: str) -> dict:
    """Monta o contexto de template com métricas e gráficos comparando duas lojas.
    Entrada: loja_a (str), loja_b (str), ids de loja.
    Retorno: dict com métricas ("a", "b"), gráficos e comentários de atenção das duas lojas."""
    loja_a, loja_b = loja_a.strip().upper(), loja_b.strip().upper()  # entrada externa pode vir minúscula
    metrics_a = dl.store_metrics(loja_a)
    metrics_b = dl.store_metrics(loja_b)

    mensal_margem_a, mensal_margem_b = dl.monthly_desvio_margem_comparativo(loja_a, loja_b)
    mensal_fat_a, mensal_fat_b = dl.monthly_faturamento_comparativo(loja_a, loja_b)
    mensal_aval_a, mensal_aval_b = dl.monthly_avaliacoes_comparativo(loja_a, loja_b)

    return {
        "opcoes": dl.list_lojas_options(),
        "loja_a": loja_a,
        "loja_b": loja_b,
        "a": metrics_a,
        "b": metrics_b,
        "grafico_faturamento_mensal": charts.comparativo_faturamento_mensal(
            mensal_fat_a, mensal_fat_b, metrics_a["nome_loja"], metrics_b["nome_loja"],
        ),
        "grafico_desvio_margem": charts.comparativo_desvio_margem(
            mensal_margem_a, mensal_margem_b, metrics_a["nome_loja"], metrics_b["nome_loja"],
        ),
        "grafico_avaliacoes": charts.comparativo_avaliacoes(
            mensal_aval_a, mensal_aval_b, metrics_a["nome_loja"], metrics_b["nome_loja"],
        ),
        # comparativo mostra só pontos de atenção; elogios ficam na Análise Individual
        "comentarios_atencao_a": dl.comentarios_destaque(loja_a)["pontos_atencao"],
        "comentarios_atencao_b": dl.comentarios_destaque(loja_b)["pontos_atencao"],
    }


@router.get("/")
def prioridades(request: Request):
    """Rota da tela 'Prioridades'.
    Entrada: request (Request).
    Retorno: TemplateResponse com o ranking de prioridade e o comparativo das duas lojas críticas."""
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
    """Rota da tela 'Rede'.
    Entrada: request (Request), periodo (str, "6m"/"12m"/"fundacao").
    Retorno: TemplateResponse com KPIs, retrato e tendência de expansão da rede."""
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
    """Rota da tela 'Análise Individual' sem loja selecionada -- usa a primeira da lista.
    Entrada: request (Request).
    Retorno: TemplateResponse (delega para analise_individual)."""
    primeira = dl.list_stores_summary()[0]["id_loja"]
    return analise_individual(request, id_loja=primeira)


@router.get("/lojas/{id_loja}")
def analise_individual(request: Request, id_loja: str):
    """Rota da tela 'Análise Individual' de uma loja.
    Entrada: request (Request), id_loja (str).
    Retorno: TemplateResponse com métricas, gráficos e comentários da loja."""
    id_loja = id_loja.strip().upper()  # pode chegar minúsculo pela URL
    metrics = dl.store_metrics(id_loja)
    semanal_margem, _ = dl.weekly_desvio_margem(id_loja)
    semanal_avaliacoes = dl.weekly_avaliacoes(id_loja)

    is_htmx = _is_htmx(request)
    ctx = {
        "request": request,
        "metrics": metrics,
        "is_htmx": is_htmx,
        "grafico_desvio_margem": charts.desvio_margem(semanal_margem),
        "grafico_avaliacoes": charts.avaliacoes_volume_nota(semanal_avaliacoes),
        "comentarios": dl.comentarios_destaque(id_loja),
        # mix de produtos sempre visível aqui (diferente de Prioridades, que só mostra quando motivo é margem)
        "mix_pior_categoria": dl.pior_categoria_margem(id_loja),
        **_sidebar_ctx(id_loja, active_tab="individual"),
    }

    if is_htmx:
        return templates.TemplateResponse(request, "pages/analise_individual.html", ctx)
    ctx["conteudo_inicial"] = "pages/analise_individual.html"
    return templates.TemplateResponse(request, "base.html", ctx)


@router.get("/comparativo/fragment")
def comparativo_fragment(request: Request, loja_a: str = Query(...), loja_b: str = Query(...)):
    """Fragmento HTMX que atualiza o bloco de comparação da tela de Prioridades.
    Entrada: request (Request), loja_a (str), loja_b (str).
    Retorno: TemplateResponse do fragmento comparativo_section.html."""
    ctx = {"request": request, **_comparativo_ctx(loja_a, loja_b)}
    return templates.TemplateResponse(request, "components/comparativo_section.html", ctx)


@router.get("/relatorio")
def gerar_relatorio(request: Request):
    """Fragmento HTMX com o relatório semanal de todas as lojas.
    Entrada: request (Request).
    Retorno: TemplateResponse do fragmento relatorio_modal.html."""
    resumo = dl.list_stores_summary()
    criticas = [l for l in resumo if l["risco_critico"]]
    ctx = {"request": request, "resumo": resumo, "criticas": criticas}
    return templates.TemplateResponse(request, "components/relatorio_modal.html", ctx)
