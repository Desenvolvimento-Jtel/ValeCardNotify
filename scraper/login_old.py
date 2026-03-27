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
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    log.info(f"Browser iniciado — headless: {HEADLESS}")
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        locale="pt-BR",
        accept_downloads=True,
    )
    page = context.new_page()

    log.info(f"Acessando: {SITE_URL}")
    page.goto(SITE_URL, wait_until="networkidle", timeout=30_000)

    log.info("Selecionando tipo de acesso: USUARIO TERCEIRO")
    page.select_option("#tenantList", value=TENANT_VALUE)
    page.wait_for_timeout(800)

    log.info("Preenchendo usuário...")
    page.click("#username_tmp")
    page.fill("#username_tmp", SITE_USERNAME)
    page.dispatch_event("#username_tmp", "input")
    page.dispatch_event("#username_tmp", "change")

    log.info("Preenchendo senha...")
    page.click("#password")
    page.fill("#password", SITE_PASSWORD)
    page.dispatch_event("#password", "input")
    page.dispatch_event("#password", "change")

    log.info("Clicando em LOGIN...")
    page.click("button[type='submit']")

    page.wait_for_load_state("networkidle", timeout=30_000)
    page.wait_for_timeout(2_000)
    page.screenshot(path="output/pos_login_debug.png")
    log.info(f"URL após login: {page.url}")

    try:
        page.wait_for_selector("div[role='button']", timeout=20_000)
    except Exception as e:
        # Tira screenshot da tela atual antes de propagar o erro
        page.screenshot(path="output/erro_screenshot.png")
        log.error(f"Falha ao confirmar login — screenshot salvo em output/erro_screenshot.png")
        log.error(f"URL atual: {page.url}")
        browser.close()
        raise

    log.info("Login realizado com sucesso.")
    return page, browser
