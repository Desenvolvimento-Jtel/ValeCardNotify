"""
inserir.py - Lê o xlsx e insere no MySQL com mapeamento explícito de colunas.
"""

import os
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

log = logging.getLogger(__name__)

MYSQL_HOST     = os.environ["MYSQL_HOST"]
MYSQL_PORT     = os.environ.get("MYSQL_PORT", "3306")
MYSQL_DB       = os.environ["MYSQL_DB"]
MYSQL_USER     = os.environ["MYSQL_USER"]
MYSQL_PASSWORD = os.environ["MYSQL_PASSWORD"]
TABELA_DESTINO = os.environ.get("MYSQL_TABELA", "controle_gestao_analitico")

MAPA_COLUNAS = {
    "DATA":                 "data",
    "PLACA":                "placa",
    "MODELO":               "modelo",
    "PRODUTO":              "produto",
    "NOME FANTASIA":        "nome_fantasia",
    "CONSUMO":              "consumo",
    "QUANTIDADE":           "quantidade",
    "VALOR UNITARIO":       "valor_unitario",
    "VALOR TOTAL":          "valor_total",
    "TIPO COMBUSTIVEL":     "tipo_combustivel",
    "RESPONSAVEL VEICULO":  "responsavel_veiculo",
    "MATRICULA":            "matricula",
    "MOTORISTA":            "motorista",
    "CIDADE":               "cidade",
    "ESTADO":               "estado",
    "UNIDADE":              "unidade",
    "NUMERO FATURA":        "numero_fatura",
    "CNPJ":                 "cnpj",
    "RAZAO SOCIAL":         "razao_social",
    "ENDERECO":             "endereco",
    "BAIRRO":               "bairro",
    "HODOMETRO":            "hodometro",
    "TIPO FROTA":           "tipo_frota",
    "NUMERO CARTAO":        "numero_cartao",
    "FILIAL":               "filial",
    "CENTRO RESULTADO":     "centro_resultado",
    "NUMERO TAG NFC":       "numero_tag_nfc",
    "CLIENTE":              "cliente",
    "G.PROJETO":            "g_projeto",
    "OBSERVACAO":           "observacao",
}


def criar_engine():
    url = (
        f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    )
    return create_engine(url, pool_pre_ping=True)


def _tratar_dataframe(df: pd.DataFrame) -> pd.DataFrame:

    # 1. Padronização inicial
    df.columns = df.columns.str.strip().str.upper()

    colunas_xlsx     = set(df.columns)
    colunas_mapa     = set(MAPA_COLUNAS.keys())
    nao_mapeadas     = colunas_xlsx - colunas_mapa
    faltando_no_xlsx = colunas_mapa - colunas_xlsx

    if nao_mapeadas:
        log.warning(f"Colunas nao mapeadas (ignoradas): {nao_mapeadas}")

    # 2. Injeta colunas faltantes como NULL
    if faltando_no_xlsx:
        log.warning(f"Colunas esperadas nao encontradas: {faltando_no_xlsx}. Inserindo como NULL.")
        for col in faltando_no_xlsx:
            df[col] = None

    # 3. Mantém apenas as colunas do mapeamento
    df = df[list(MAPA_COLUNAS.keys())].copy()

    # 4. Renomeia para os nomes do banco
    df.rename(columns=MAPA_COLUNAS, inplace=True)

    # Remove linhas totalmente vazias
    df.dropna(how="all", inplace=True)

    # ── DATA → datetime ───────────────────────────────────────────────────────
    # O Valecard exporta datas já no horário de Brasília — preservar como está
    if "data" in df.columns:
        df["data"] = pd.to_datetime(
            df["data"],
            format="%d/%m/%Y %H:%M:%S",
            errors="coerce",
            utc=False,
        )
        # Remove timezone info se existir (garante naive datetime sem conversão)
        if hasattr(df["data"].dtype, "tz") and df["data"].dtype.tz is not None:
            df["data"] = df["data"].dt.tz_localize(None)

    # ── Numéricos ─────────────────────────────────────────────────────────────
    for col in ["consumo", "quantidade", "valor_unitario", "valor_total", "hodometro"]:
        if col in df.columns:
            def converter_numero(val):
                if pd.isna(val) or val is None:
                    return None
                if isinstance(val, (int, float)):
                    return float(val)
                s = str(val).strip()
                if "," in s and "." in s:
                    s = s.replace(".", "").replace(",", ".")
                elif "," in s:
                    s = s.replace(",", ".")
                try:
                    return float(s)
                except ValueError:
                    return None
            df[col] = df[col].apply(converter_numero)

    # ── Strings ───────────────────────────────────────────────────────────────
    colunas_texto = [
        "placa", "modelo", "produto", "nome_fantasia", "tipo_combustivel",
        "responsavel_veiculo", "matricula", "motorista", "cidade", "estado",
        "unidade", "numero_fatura", "cnpj", "razao_social", "endereco",
        "bairro", "tipo_frota", "numero_cartao", "filial", "centro_resultado",
        "numero_tag_nfc", "cliente", "g_projeto", "observacao",
    ]
    for col in colunas_texto:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace(
                ["nan", "None", "none"], None
            )
            df[col] = df[col].mask(df[col].isnull(), None)

    # ── Ordena por data crescente ─────────────────────────────────────────────
    if "data" in df.columns:
        df.sort_values("data", ascending=True, inplace=True)
        df.reset_index(drop=True, inplace=True)

    df["_inserido_em"] = pd.Timestamp.now()

    log.info(f"Registros prontos para inserir: {len(df)}")
    return df


def inserir_no_mysql(caminho_xlsx: Path) -> tuple[int, int]:
    log.info(f"Lendo arquivo: {caminho_xlsx}")
    df_raw = pd.read_excel(caminho_xlsx, engine="openpyxl")
    log.info(f"Xlsx: {df_raw.shape[0]} linhas x {df_raw.shape[1]} colunas")

    df = _tratar_dataframe(df_raw)

    if df.empty:
        log.warning("Nenhum registro valido.")
        return 0, 0

    engine = criar_engine()
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
        log.info("Conexao MySQL estabelecida.")

        df.to_sql(
            name=TABELA_DESTINO,
            con=engine,
            if_exists="append",
            index=False,
            chunksize=500,
        )
        log.info(f"{len(df)} registros inseridos em '{TABELA_DESTINO}'.")
        return len(df), 0

    except SQLAlchemyError as e:
        log.error(f"Erro MySQL: {e}", exc_info=True)
        raise
    finally:
        engine.dispose()