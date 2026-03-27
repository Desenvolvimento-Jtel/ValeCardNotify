"""
main.py - Orquestrador principal
Fluxo: Login → Download xlsx → MySQL → E-mails
"""

import logging
import sys
import traceback
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # carrega o .env antes de qualquer import que leia os environ

from scraper.login import fazer_login
from scraper.extrator import navegar_e_exportar, calcular_datas
from email_sender.enviar import enviar_email, enviar_email_erro
from db.inserir import inserir_no_mysql

Path("output").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("output/execucao.log"),
    ],
)
log = logging.getLogger(__name__)

SCREENSHOT_ERRO = Path("output/erro_screenshot.png")


def main():
    log.info("========================================")
    log.info("  Iniciando pipeline Valecard")
    log.info("========================================")

    data_inicio, data_termino = calcular_datas()
    etapa_atual = "Inicialização"
    page = None
    browser = None

    try:
        # 1. Login
        etapa_atual = "Login"
        log.info("[1/3] Realizando login...")
        page, browser = fazer_login()

        # 2. Download
        etapa_atual = "Download do relatório"
        log.info("[2/3] Navegando e exportando relatório...")
        caminho_xlsx = navegar_e_exportar(page)
        log.info(f"      Arquivo: {caminho_xlsx}")

        # 3. Insert MySQL
        etapa_atual = "Inserção no MySQL"
        log.info("[3/3] Inserindo dados no MySQL...")
        registros_inseridos, registros_atualizados = inserir_no_mysql(caminho_xlsx)
        log.info(f"      Inseridos: {registros_inseridos} | Atualizados: {registros_atualizados}")

        # 4. E-mails
        etapa_atual = "Envio de e-mails"
        log.info("[4/4] Enviando e-mails...")
        enviar_email(
            caminho_xlsx=caminho_xlsx,
            data_inicio=data_inicio,
            data_termino=data_termino,
            registros_inseridos=registros_inseridos,
            registros_atualizados=registros_atualizados,
        )
        log.info("      E-mails enviados!")

    except Exception as e:
        log.error(f"Erro na etapa '{etapa_atual}': {e}", exc_info=True)

        # Tira screenshot se page disponível e screenshot ainda não foi tirado
        if page and not SCREENSHOT_ERRO.exists():
            try:
                page.screenshot(path=str(SCREENSHOT_ERRO))
                log.info(f"Screenshot salvo: {SCREENSHOT_ERRO}")
            except Exception as ss_err:
                log.warning(f"Não foi possível tirar screenshot: {ss_err}")

        # Verifica se screenshot existe (pode ter sido salvo no login.py)
        screenshot = SCREENSHOT_ERRO if SCREENSHOT_ERRO.exists() else None
        if screenshot:
            log.info(f"Screenshot encontrado: {screenshot}")
        else:
            log.warning("Nenhum screenshot disponível para anexar.")

        try:
            enviar_email_erro(
                erro=e,
                etapa=etapa_atual,
                traceback_str=traceback.format_exc(),
                screenshot_path=screenshot,
            )
        except Exception as email_err:
            log.error(f"Não foi possível enviar e-mail de erro: {email_err}")

        raise

    finally:
        if browser:
            browser.close()
            log.info("Browser encerrado.")
        log.info("========================================")
        log.info("  Pipeline finalizado")
        log.info("========================================")


if __name__ == "__main__":
    main()
