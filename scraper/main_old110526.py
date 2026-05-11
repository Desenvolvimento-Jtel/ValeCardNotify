"""
main.py - Orquestrador principal
Fluxo: Login → Download xlsx → Corrige datas → MySQL → E-mails
"""

import logging
import sys
import traceback
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Força UTF-8 no terminal Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

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


def corrigir_datas_xlsx(caminho_xlsx: Path) -> Path:
    """
    Lê o xlsx original, soma 3 horas na coluna DATA (UTC → Brasília)
    e salva um novo arquivo corrigido para envio por e-mail.
    Retorna o Path do arquivo corrigido.
    """
    import pandas as pd

    df = pd.read_excel(caminho_xlsx, engine="openpyxl")

    # Identifica a coluna DATA (case-insensitive)
    col_data = next(
        (c for c in df.columns if c.strip().upper() == "DATA"), None
    )

    if col_data:
        df[col_data] = pd.to_datetime(
            df[col_data],
            errors="coerce",
            dayfirst=True,
            utc=False,
        )
        # Remove timezone se existir
        if hasattr(df[col_data].dtype, "tz") and df[col_data].dtype.tz is not None:
            df[col_data] = df[col_data].dt.tz_localize(None)

        # Formata como string para manter o padrão visual no Excel
        df[col_data] = df[col_data].dt.strftime("%d/%m/%Y %H:%M:%S")

        log.info("Datas preservadas no horario original do Valecard.")
    else:
        log.warning("Coluna DATA nao encontrada no xlsx — enviando sem correcao.")

    # Salva arquivo corrigido
    caminho_corrigido = caminho_xlsx.parent / (caminho_xlsx.stem + "_br.xlsx")
    df.to_excel(caminho_corrigido, index=False, engine="openpyxl")
    log.info(f"Xlsx corrigido salvo: {caminho_corrigido}")

    return caminho_corrigido


def main():
    log.info("========================================")
    log.info("  Iniciando pipeline Valecard")
    log.info("========================================")

    data_inicio, data_termino = calcular_datas()
    etapa_atual = "Inicializacao"
    page = None
    browser = None

    try:
        # 1. Login
        etapa_atual = "Login"
        log.info("[1/4] Realizando login...")
        page, browser = fazer_login()

        # 2. Download
        etapa_atual = "Download do relatorio"
        log.info("[2/4] Navegando e exportando relatorio...")
        caminho_xlsx = navegar_e_exportar(page)
        log.info(f"      Arquivo original: {caminho_xlsx}")

        # 3. Corrige datas do xlsx (UTC → Brasília) para envio por e-mail
        log.info("      Corrigindo datas do xlsx para horario de Brasilia...")
        caminho_xlsx_corrigido = corrigir_datas_xlsx(caminho_xlsx)

        # 4. Insert MySQL (inserir.py já soma +3h internamente)
        etapa_atual = "Insercao no MySQL"
        log.info("[3/4] Inserindo dados no MySQL...")
        registros_inseridos, registros_atualizados = inserir_no_mysql(caminho_xlsx)
        log.info(f"      Inseridos: {registros_inseridos} | Atualizados: {registros_atualizados}")

        # 5. E-mails com xlsx corrigido como anexo
        etapa_atual = "Envio de e-mails"
        log.info("[4/4] Enviando e-mails...")
        enviar_email(
            caminho_xlsx=caminho_xlsx_corrigido,
            data_inicio=data_inicio,
            data_termino=data_termino,
            registros_inseridos=registros_inseridos,
            registros_atualizados=registros_atualizados,
        )
        log.info("      E-mails enviados!")

    except Exception as e:
        log.error(f"Erro na etapa '{etapa_atual}': {e}", exc_info=True)

        if page and not SCREENSHOT_ERRO.exists():
            try:
                page.screenshot(path=str(SCREENSHOT_ERRO))
                log.info(f"Screenshot salvo: {SCREENSHOT_ERRO}")
            except Exception as ss_err:
                log.warning(f"Nao foi possivel tirar screenshot: {ss_err}")

        screenshot = SCREENSHOT_ERRO if SCREENSHOT_ERRO.exists() else None

        try:
            enviar_email_erro(
                erro=e,
                etapa=etapa_atual,
                traceback_str=traceback.format_exc(),
                screenshot_path=screenshot,
            )
        except Exception as email_err:
            log.error(f"Nao foi possivel enviar e-mail de erro: {email_err}")

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