"""
login.py - Login no portal Valecard (USUARIO TERCEIRO)
"""

import os
import logging
from playwright.sync_api import sync_playwright, Page, Browser

log = logging.getLogger(__name__)

SITE_URL      = os.environ["SITE_URL"]
SITE_USERNAME = os.environ["SITE_USERNAME"]
SITE_PASSWORD = os.environ["SITE_PASSWORD"]
TENANT_VALUE  = "usuarioterceiro.valecard.com.br"

# HEADLESS=false abre o browser visível (útil para testes locais)
# HEADLESS=true  roda sem interface (padrão em produção/GitHub Actions)
HEADLESS = os.environ.get("HEADLESS", "true").strip().lower() != "false"


def fazer_login() -> tuple[Page, Browser]:
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=HEADLESS,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-setuid-sandbox",
            "--no-zygote",
        ],
        slow_mo=200,  # aguarda 200ms entre cada ação — estabiliza em cloud
    )
    log.info(f"Browser iniciado — headless: {HEADLESS}")
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        locale="pt-BR",
        accept_downloads=True,
    )
    page = context.new_page()

    log.info(f"Acessando: {SITE_URL}")
    page.goto(SITE_URL, wait_until="domcontentloaded", timeout=60_000)

    # Screenshot imediato para diagnóstico — ver o que carregou
    os.makedirs("output", exist_ok=True)
    page.screenshot(path="output/pagina_inicial.png")
    log.info(f"URL após goto: {page.url}")
    log.info(f"Titulo da pagina: {page.title()}")

    # Aguarda a página estabilizar completamente
    page.wait_for_selector("#tenantList", state="visible", timeout=60_000)
    page.wait_for_timeout(2_000)

    log.info("Selecionando tipo de acesso: USUARIO TERCEIRO")
    page.select_option("#tenantList", value=TENANT_VALUE)
    page.wait_for_timeout(1_500)

    log.info("Preenchendo usuário...")
    page.click("#username_tmp")
    page.fill("#username_tmp", SITE_USERNAME)
    page.dispatch_event("#username_tmp", "input")
    page.dispatch_event("#username_tmp", "change")
    page.wait_for_timeout(500)

    log.info("Preenchendo senha...")
    page.click("#password")
    page.fill("#password", SITE_PASSWORD)
    page.dispatch_event("#password", "input")
    page.dispatch_event("#password", "change")
    page.wait_for_timeout(500)

    log.info("Clicando em LOGIN...")
    page.click("button[type='submit']")

    page.wait_for_load_state("networkidle", timeout=60_000)
    page.wait_for_timeout(3_000)

    page.screenshot(path="output/pos_login_debug.png")
    log.info(f"URL após login: {page.url}")

    try:
        page.wait_for_selector("div[role='button']", timeout=30_000)
    except Exception as e:
        page.screenshot(path="output/erro_screenshot.png")
        log.error("Falha ao confirmar login — screenshot salvo em output/erro_screenshot.png")
        log.error(f"URL atual: {page.url}")
        browser.close()
        raise

    log.info("Login realizado com sucesso.")
    return page, browser
