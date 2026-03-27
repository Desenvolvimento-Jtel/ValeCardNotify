# ValeCard Notify — Simples

Pipeline semanal: **Login → Download xlsx → MySQL → E-mails**  
Disparo automático toda **segunda-feira às 08:00 (Brasília)**.

---

## Estrutura

```
.
├── .github/workflows/scraper.yml   # Agendamento GitHub Actions
├── scraper/
│   ├── main.py                     # Orquestrador
│   ├── login.py                    # Login Valecard
│   └── extrator.py                 # Filtros + download xlsx
├── email_sender/
│   └── enviar.py                   # E-mails via Microsoft Graph API
├── db/
│   └── inserir.py                  # Insert MySQL
├── .env.example                    # Modelo de credenciais
├── .gitignore
└── requirements.txt
```

---

## Período extraído

Fixo toda semana:
- **Início:** segunda-feira anterior (hoje − 7 dias)
- **Término:** domingo de ontem (hoje − 1 dia)

---

## Secrets no GitHub

**Settings → Secrets and variables → Actions → New repository secret**

| Secret | Descrição |
|---|---|
| `SITE_URL` | URL do portal Valecard |
| `SITE_USERNAME` | Usuário |
| `SITE_PASSWORD` | Senha |
| `GRAPH_TENANT_ID` | ID do tenant Azure AD |
| `GRAPH_CLIENT_ID` | ID do app registration |
| `GRAPH_CLIENT_SECRET` | Secret do app |
| `GRAPH_MAILBOX_ENVIO` | E-mail remetente |
| `EMAIL_DESTINATARIOS` | Técnicos (vírgula) |
| `EMAIL_DESTINATARIOS_AVISO` | Gestores (vírgula) |
| `EMAIL_LINK_JUSTIFICATIVA` | URL do sistema |
| `MYSQL_HOST` | Host do banco |
| `MYSQL_PORT` | Porta (3306) |
| `MYSQL_DB` | Nome do banco |
| `MYSQL_USER` | Usuário MySQL |
| `MYSQL_PASSWORD` | Senha MySQL |
| `MYSQL_TABELA` | Nome da tabela destino |

---

## Teste local

```bat
# 1. Copiar e preencher credenciais
copy .env.example .env

# 2. Criar ambiente e instalar
conda create -n valecardnotify python=3.11 -y
conda activate valecardnotify
pip install -r requirements.txt
python -m playwright install chromium

# 3. Executar
python scraper/main.py
```
