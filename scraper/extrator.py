"""
extrator.py - Navegação, filtros e download do relatório xlsx
Período fixo: segunda-feira anterior até domingo de ontem
"""

import logging
from pathlib import Path
from datetime import date, timedelta
from playwright.sync_api import (
    Page,
    Locator,
    TimeoutError as PlaywrightTimeoutError,
)

log = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def _aguardar_networkidle(page: Page, etapa: str, timeout: int = 10_000) -> None:
    """Usa networkidle apenas como sinal auxiliar, nunca como validação da tela."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
        log.info("Rede estabilizada (%s).", etapa)
    except PlaywrightTimeoutError:
        log.warning(
            "A pagina nao atingiu networkidle em %sms (%s). "
            "Continuando para validar os elementos da tela.",
            timeout,
            etapa,
        )


def _salvar_diagnostico(page: Page, nome: str) -> None:
    """Registra a tela atual antes de propagar uma falha de navegação."""
    try:
        page.screenshot(path=str(OUTPUT_DIR / f"{nome}.png"), full_page=True)
    except Exception as erro:
        log.warning("Nao foi possivel salvar o screenshot %s: %s", nome, erro)

    try:
        (OUTPUT_DIR / f"{nome}.html").write_text(
            page.content(), encoding="utf-8"
        )
    except Exception as erro:
        log.warning("Nao foi possivel salvar o HTML %s: %s", nome, erro)

    log.info("URL em %s: %s", nome, page.url)


def _aguardar_visivel(
    page: Page, elemento: Locator, etapa: str, diagnostico: str, timeout: int = 30_000
) -> None:
    """Confirma a navegação por um elemento real e salva diagnóstico ao falhar."""
    try:
        elemento.wait_for(state="visible", timeout=timeout)
    except PlaywrightTimeoutError:
        _salvar_diagnostico(page, diagnostico)
        log.error("Elemento esperado nao apareceu (%s).", etapa)
        raise


def calcular_datas() -> tuple[str, str]:
    """
    Calcula o período da última semana completa:
      - Início  = última segunda-feira
      - Término = último domingo

    Exemplos:
      Hoje = segunda 17/03 → início 10/03, término 16/03
      Hoje = terça  17/03  → início 10/03, término 16/03
      Hoje = quarta 18/03  → início 10/03, término 16/03
      Hoje = segunda 24/03 → início 17/03, término 23/03

    Sempre retorna a semana seg→dom mais recente já encerrada.
    """
    hoje = date.today()

    # Domingo da semana passada = hoje - dias desde domingo - 1
    # weekday(): seg=0, ter=1, qua=2, qui=3, sex=4, sab=5, dom=6
    dias_desde_domingo = (hoje.weekday() + 1) % 7  # quantos dias passou do último domingo
    ultimo_domingo     = hoje - timedelta(days=dias_desde_domingo)
    ultima_segunda     = ultimo_domingo - timedelta(days=6)

    fmt = lambda d: d.strftime("%d/%m/%Y")
    log.info(f"Período: {fmt(ultima_segunda)} (seg) a {fmt(ultimo_domingo)} (dom)")
    return fmt(ultima_segunda), fmt(ultimo_domingo)


def _preencher_data_angular(page: Page, placeholder: str, valor: str) -> None:
    campo = page.locator(f"input[placeholder='{placeholder}']")
    campo.click()
    campo.click(click_count=3)
    page.keyboard.type(valor, delay=80)
    page.keyboard.press("Tab")
    page.wait_for_timeout(400)


def navegar_e_exportar(page: Page) -> Path:
    """
    Executa o fluxo completo pós-login:
      1. Clica no card "Gerar Relatórios"
      2. Seleciona "Controle Gestao - Analitico"
      3. Preenche filtros de data
      4. Clica em LISTA
      5. Exporta e captura o xlsx
    """

    # 1. Card Gerar Relatórios
    log.info("Clicando em 'Gerar Relatórios'...")
    page.locator("div[role='button']", has_text="Gerar Relatórios").click()
    _aguardar_networkidle(page, "abertura de Gerar Relatorios")

    # 2. Select do relatório (Angular Material)
    seletor_relatorios = page.locator("mat-select").filter(
        has=page.locator("span.mat-select-placeholder", has_text="Relatórios")
    )
    _aguardar_visivel(
        page,
        seletor_relatorios,
        "seletor de relatorios",
        "erro_gerar_relatorios",
    )
    log.info("Abrindo seletor de relatórios...")
    seletor_relatorios.click()
    page.wait_for_timeout(800)

    log.info("Selecionando 'Controle Gestao - Analitico'...")
    opcao_relatorio = page.locator(
        "mat-option span.mat-option-text",
        has_text="Controle Gestao - Analitico",
    )
    _aguardar_visivel(
        page,
        opcao_relatorio,
        "opcao Controle Gestao - Analitico",
        "erro_opcao_relatorio",
    )
    opcao_relatorio.click()
    _aguardar_networkidle(page, "selecao do relatorio")

    campo_data_inicio = page.locator("input[placeholder='Data Início']")
    campo_data_termino = page.locator("input[placeholder='Data Término']")
    _aguardar_visivel(
        page,
        campo_data_inicio,
        "campo Data Inicio",
        "erro_campos_relatorio",
    )
    _aguardar_visivel(
        page,
        campo_data_termino,
        "campo Data Termino",
        "erro_campos_relatorio",
    )

    # 3. Filtros de data
    data_inicio, data_termino = calcular_datas()

    log.info(f"Preenchendo Data Início: {data_inicio}")
    _preencher_data_angular(page, "Data Início", data_inicio)

    log.info(f"Preenchendo Data Término: {data_termino}")
    _preencher_data_angular(page, "Data Término", data_termino)

    # 4. Botão LISTA
    botao_lista = page.locator("button[name='submit']", has_text="LISTA")
    _aguardar_visivel(
        page,
        botao_lista,
        "botao LISTA",
        "erro_filtros_relatorio",
    )
    log.info("Clicando em LISTA...")
    botao_lista.click()
    log.info("Aguardando tabela carregar...")
    _aguardar_networkidle(page, "carregamento da tabela", timeout=15_000)
    page.wait_for_timeout(2_000)

    # 5. Exportar EXCEL
    botao_exportar = page.get_by_role(
        "button", name="ícone exportExportar(EXCEL)"
    )
    _aguardar_visivel(
        page,
        botao_exportar,
        "botao Exportar (EXCEL)",
        "erro_tabela_relatorio",
        timeout=60_000,
    )
    log.info("Clicando em Exportar (EXCEL)...")
    with page.expect_download(timeout=60_000) as download_info:
        botao_exportar.click()

    download     = download_info.value
    nome_sugerido = download.suggested_filename or "relatorio"
    log.info(f"Nome sugerido pelo site: {nome_sugerido}")

    caminho = OUTPUT_DIR / (Path(nome_sugerido).stem + ".xlsx")
    download.save_as(str(caminho))
    log.info(f"Arquivo salvo: {caminho} ({caminho.stat().st_size / 1024:.1f} KB)")

    return caminho
