"""
Ferramentas de Gmail para a Ethos AI (somente LEITURA).

Pré-requisitos (siga nesta ordem):
1. Tenha o arquivo credentials.json na MESMA pasta deste arquivo
   (gerado no Google Cloud Console, Client ID tipo "App para computador").
2. Instale as bibliotecas do Google:
   pip install google-auth-oauthlib google-api-python-client

Na PRIMEIRA vez que a Ethos tentar ler e-mails, uma janela do navegador
vai abrir pedindo pra você logar e autorizar o acesso. Depois disso, um
arquivo token.json é salvo nesta pasta e as próximas vezes não pedem
autorização de novo (a menos que você apague o token.json).

Escopo usado: gmail.readonly — só LEITURA. A Ethos não consegue enviar,
apagar ou modificar nenhum e-mail com este código.
"""

import base64
import os
import datetime

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_CREDENCIAIS = os.path.join(PASTA, "credentials.json")
ARQUIVO_TOKEN = os.path.join(PASTA, "token.json")

ESCOPOS = ["https://www.googleapis.com/auth/gmail.readonly"]

_servico = None  # cache: evita reautenticar a cada chamada na mesma sessão


def _obter_servico():
    """Autentica (ou reusa o token salvo) e devolve o objeto de serviço do Gmail."""
    global _servico
    if _servico is not None:
        return _servico

    # imports aqui dentro para o arquivo não quebrar se as libs do Google
    # ainda não tiverem sido instaladas, antes mesmo de tentar usar a ferramenta
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(ARQUIVO_TOKEN):
        creds = Credentials.from_authorized_user_file(ARQUIVO_TOKEN, ESCOPOS)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(ARQUIVO_CREDENCIAIS):
                raise FileNotFoundError(
                    "Não encontrei o credentials.json na pasta do projeto. "
                    "Baixe-o no Google Cloud Console e coloque na mesma pasta "
                    "do ethos_ai_gui.py."
                )
            fluxo = InstalledAppFlow.from_client_secrets_file(ARQUIVO_CREDENCIAIS, ESCOPOS)
            creds = fluxo.run_local_server(port=0)
        with open(ARQUIVO_TOKEN, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    _servico = build("gmail", "v1", credentials=creds)
    return _servico


def _decodificar_corpo(payload):
    """Extrai o texto simples de uma mensagem do Gmail (lida com partes aninhadas)."""
    if payload.get("mimeType") == "text/plain" and "data" in payload.get("body", {}):
        dados = payload["body"]["data"]
        return base64.urlsafe_b64decode(dados).decode("utf-8", errors="ignore")
    for parte in payload.get("parts", []) or []:
        texto = _decodificar_corpo(parte)
        if texto:
            return texto
    return ""


def ler_emails_recentes(quantidade=5, apenas_nao_lidos=False):
    """Lê os e-mails mais recentes da caixa de entrada e devolve um resumo
    (remetente, assunto e um trecho do corpo de cada um)."""
    try:
        servico = _obter_servico()
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Não consegui me autenticar no Gmail: {e}"

    quantidade = max(1, min(int(quantidade), 15))  # trava de segurança
    query = "is:unread" if apenas_nao_lidos else ""

    resultado = servico.users().messages().list(
        userId="me", labelIds=["INBOX"], q=query, maxResults=quantidade
    ).execute()
    mensagens = resultado.get("messages", [])

    if not mensagens:
        return "Não encontrei nenhum e-mail" + (" não lido" if apenas_nao_lidos else "") + " na caixa de entrada."

    partes = []
    for m in mensagens:
        msg = servico.users().messages().get(
            userId="me", id=m["id"], format="full"
        ).execute()
        cabecalhos = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        remetente = cabecalhos.get("From", "desconhecido")
        assunto = cabecalhos.get("Subject", "(sem assunto)")
        corpo = _decodificar_corpo(msg["payload"]).strip()
        trecho = (corpo[:200] + "...") if len(corpo) > 200 else corpo
        partes.append(f"De: {remetente} | Assunto: {assunto} | Trecho: {trecho}")

    return "\n---\n".join(partes)


def buscar_emails(termo, quantidade=5):
    """Busca e-mails que contenham um termo específico (no assunto ou remetente)."""
    try:
        servico = _obter_servico()
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Não consegui me autenticar no Gmail: {e}"

    quantidade = max(1, min(int(quantidade), 15))
    resultado = servico.users().messages().list(
        userId="me", q=termo, maxResults=quantidade
    ).execute()
    mensagens = resultado.get("messages", [])

    if not mensagens:
        return f"Não encontrei nenhum e-mail relacionado a '{termo}'."

    partes = []
    for m in mensagens:
        msg = servico.users().messages().get(
            userId="me", id=m["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        cabecalhos = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        remetente = cabecalhos.get("From", "desconhecido")
        assunto = cabecalhos.get("Subject", "(sem assunto)")
        data = cabecalhos.get("Date", "")
        partes.append(f"De: {remetente} | Assunto: {assunto} | Data: {data}")

    return "\n---\n".join(partes)


# --------------------- registro de ferramentas (tool calling) ---------------------
FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "ler_emails_recentes",
        "description": (
            "Lê os e-mails mais recentes da caixa de entrada do Gmail do usuário, "
            "com remetente, assunto e um trecho do conteúdo. Use quando o usuário "
            "pedir para ver, ler ou checar os e-mails/a caixa de entrada."
        ),
        "parameters": {"type": "object", "properties": {
            "quantidade": {"type": "integer", "description": "quantos e-mails trazer (padrão 5, máximo 15)"},
            "apenas_nao_lidos": {"type": "boolean", "description": "true para trazer só os não lidos"}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "buscar_emails",
        "description": (
            "Busca e-mails do Gmail que contenham um termo específico no "
            "assunto, remetente ou conteúdo (ex.: nome de uma pessoa, empresa "
            "ou assunto). Use quando o usuário pedir para procurar/achar um "
            "e-mail específico."
        ),
        "parameters": {"type": "object", "properties": {
            "termo": {"type": "string", "description": "o que buscar"},
            "quantidade": {"type": "integer", "description": "quantos resultados trazer (padrão 5, máximo 15)"}},
            "required": ["termo"]}}},
]

_FUNCOES = {
    "ler_emails_recentes": ler_emails_recentes,
    "buscar_emails": buscar_emails,
}


def executar(nome, args):
    if nome in _FUNCOES:
        return _FUNCOES[nome](**args)
    return None
