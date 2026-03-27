"""
enviar.py - Envio de e-mails via Microsoft Graph API
"""

import os
import base64
import logging
import requests
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

GRAPH_TENANT_ID     = os.environ["GRAPH_TENANT_ID"]
GRAPH_CLIENT_ID     = os.environ["GRAPH_CLIENT_ID"]
GRAPH_CLIENT_SECRET = os.environ["GRAPH_CLIENT_SECRET"]
GRAPH_MAILBOX_ENVIO = os.environ["GRAPH_MAILBOX_ENVIO"]

EMAIL_DESTINATARIOS = [
    e.strip() for e in os.environ["EMAIL_DESTINATARIOS"].split(",") if e.strip()
]
EMAIL_DESTINATARIOS_AVISO = [
    e.strip() for e in os.environ["EMAIL_DESTINATARIOS_AVISO"].split(",") if e.strip()
]
EMAIL_LINK_JUSTIFICATIVA = os.environ["EMAIL_LINK_JUSTIFICATIVA"]

GRAPH_TOKEN_URL = f"https://login.microsoftonline.com/{GRAPH_TENANT_ID}/oauth2/v2.0/token"
GRAPH_SEND_URL  = f"https://graph.microsoft.com/v1.0/users/{GRAPH_MAILBOX_ENVIO}/sendMail"


def _obter_token() -> str:
    r = requests.post(GRAPH_TOKEN_URL, data={
        "grant_type":    "client_credentials",
        "client_id":     GRAPH_CLIENT_ID,
        "client_secret": GRAPH_CLIENT_SECRET,
        "scope":         "https://graph.microsoft.com/.default",
    })
    r.raise_for_status()
    log.info("Token Graph obtido.")
    return r.json()["access_token"]


def _enviar(token: str, payload: dict) -> None:
    r = requests.post(GRAPH_SEND_URL, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }, json=payload)
    r.raise_for_status()


def _dest(lista: list[str]) -> list[dict]:
    return [{"emailAddress": {"address": e}} for e in lista]


def enviar_email(
    caminho_xlsx: Path,
    data_inicio: str,
    data_termino: str,
    registros_inseridos: int,
    registros_atualizados: int,
) -> None:
    token         = _obter_token()
    data_execucao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # ── E-mail técnico ────────────────────────────────────────────────────────
    with open(caminho_xlsx, "rb") as f:
        xlsx_b64 = base64.b64encode(f.read()).decode()

    corpo_tecnico = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;font-size:14px;">
        <p>Extração Valecard concluída com sucesso:</p>
        <table style="border-collapse:collapse;min-width:400px;">
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px 16px 8px 0;color:#666;">Período</td>
                <td style="padding:8px 0;"><strong>{data_inicio} à {data_termino}</strong></td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px 16px 8px 0;color:#666;">Registros inseridos</td>
                <td style="padding:8px 0;"><strong>{registros_inseridos}</strong></td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px 16px 8px 0;color:#666;">Registros atualizados</td>
                <td style="padding:8px 0;"><strong>{registros_atualizados}</strong></td>
            </tr>
            <tr>
                <td style="padding:8px 16px 8px 0;color:#666;">Data execução</td>
                <td style="padding:8px 0;"><strong>{data_execucao}</strong></td>
            </tr>
        </table>
        <br>
        <p style="color:#999;font-size:12px;">Este e-mail é automático, favor não responder.</p>
    </body></html>
    """

    _enviar(token, {
        "message": {
            "subject": f"Extração Valecard — {data_inicio} à {data_termino}",
            "body": {"contentType": "HTML", "content": corpo_tecnico},
            "toRecipients": _dest(EMAIL_DESTINATARIOS),
            "attachments": [{
                "@odata.type":  "#microsoft.graph.fileAttachment",
                "name":         caminho_xlsx.name,
                "contentType":  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "contentBytes": xlsx_b64,
            }],
        },
        "saveToSentItems": "true",
    })
    log.info(f"E-mail técnico enviado → {len(EMAIL_DESTINATARIOS)} destinatário(s).")

    # ── E-mail de aviso ───────────────────────────────────────────────────────
    corpo_aviso = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;font-size:14px;">
        <p>Olá,</p>
        <p>
            Notificamos que já estão disponíveis os dados de custos do Valecard
            referente ao período de <strong>{data_inicio} a {data_termino}</strong>.
        </p>
        <p>Favor acesse o link abaixo e realize a justificativa referente ao projeto responsável:</p>
        <p style="margin:24px 0;">
            <a href="{EMAIL_LINK_JUSTIFICATIVA}"
               style="background-color:#003366;color:white;padding:12px 24px;
                      text-decoration:none;border-radius:6px;font-weight:bold;">
                Acessar Sistema de Justificativa
            </a>
        </p>
        <br>
        <p style="color:#999;font-size:12px;">Este e-mail é automático, favor não responder.</p>
    </body></html>
    """

    _enviar(token, {
        "message": {
            "subject": f"Custos Valecard disponíveis — {data_inicio} a {data_termino}",
            "body": {"contentType": "HTML", "content": corpo_aviso},
            "toRecipients": _dest(EMAIL_DESTINATARIOS_AVISO),
        },
        "saveToSentItems": "true",
    })
    log.info(f"E-mail de aviso enviado → {len(EMAIL_DESTINATARIOS_AVISO)} destinatário(s).")


def enviar_email_erro(
    erro: Exception,
    etapa: str,
    traceback_str: str,
    screenshot_path: Path = None,
) -> None:
    log.info("Enviando e-mail de erro...")
    data_execucao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    try:
        token = _obter_token()
    except Exception as e:
        log.error(f"Não foi possível obter token para e-mail de erro: {e}")
        return

    corpo_erro = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;font-size:14px;">
        <table style="background:#fff3f3;border-left:4px solid #cc0000;
                      padding:16px;width:100%;margin-bottom:24px;">
            <tr><td>
                <strong style="color:#cc0000;font-size:16px;">
                    ❌ Falha no pipeline Valecard
                </strong>
            </td></tr>
        </table>
        <table style="border-collapse:collapse;min-width:500px;margin-bottom:24px;">
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px 16px 8px 0;color:#666;width:160px;">Data execução</td>
                <td><strong>{data_execucao}</strong></td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px 16px 8px 0;color:#666;">Etapa com falha</td>
                <td><strong style="color:#cc0000;">{etapa}</strong></td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px 16px 8px 0;color:#666;">Tipo do erro</td>
                <td><strong>{type(erro).__name__}</strong></td>
            </tr>
            <tr>
                <td style="padding:8px 16px 8px 0;color:#666;">Mensagem</td>
                <td><strong>{str(erro)}</strong></td>
            </tr>
        </table>
        <p style="color:#666;margin-bottom:8px;"><strong>Traceback:</strong></p>
        <pre style="background:#f5f5f5;padding:16px;border-radius:4px;
                    font-size:12px;white-space:pre-wrap;border:1px solid #ddd;">{traceback_str}</pre>
        <br>
        <p style="color:#999;font-size:12px;">Este e-mail é automático, favor não responder.</p>
    </body></html>
    """

    anexos = []
    if screenshot_path and screenshot_path.exists():
        with open(screenshot_path, "rb") as f:
            anexos.append({
                "@odata.type":  "#microsoft.graph.fileAttachment",
                "name":         screenshot_path.name,
                "contentType":  "image/png",
                "contentBytes": base64.b64encode(f.read()).decode(),
            })
        log.info(f"Screenshot anexado: {screenshot_path.name}")

    try:
        _enviar(token, {
            "message": {
                "subject": f"❌ ERRO Pipeline Valecard — {etapa} — {data_execucao}",
                "body": {"contentType": "HTML", "content": corpo_erro},
                "toRecipients": _dest(EMAIL_DESTINATARIOS),
                "attachments": anexos,
            },
            "saveToSentItems": "true",
        })
        log.info(f"E-mail de erro enviado → {len(EMAIL_DESTINATARIOS)} destinatário(s).")
    except Exception as e:
        log.error(f"Falha ao enviar e-mail de erro: {e}")
