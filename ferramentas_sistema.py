"""
Ferramentas da Ethos AI que fazem coisas no seu computador:
abrir música no YouTube e abrir/criar arquivos no VS Code.

Precisa do comando "code" disponível no terminal (vem com o VS Code,
em Configurações > "Adicionar ao PATH" na instalação, ou reinstale
marcando essa opção).
"""

import os
import subprocess
import webbrowser
from urllib.parse import quote


def abrir_musica_youtube(busca):
    """Abre a pesquisa dessa música/artista no YouTube, no navegador."""
    url = f"https://www.youtube.com/results?search_query={quote(busca)}"
    webbrowser.open(url)
    return f"Abri a pesquisa de '{busca}' no YouTube."


def abrir_site(url_ou_nome):
    """Abre um site. Aceita atalhos para alguns sites comuns."""
    atalhos = {
        "youtube": "https://youtube.com", "google": "https://google.com",
        "spotify": "https://open.spotify.com", "gmail": "https://mail.google.com",
        "github": "https://github.com",
    }
    url = atalhos.get(url_ou_nome.lower().strip(), url_ou_nome)
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Abri {url}."


def abrir_vscode(caminho=None):
    """Abre uma pasta ou arquivo no VS Code. Sem caminho, abre uma janela nova."""
    try:
        subprocess.Popen(["code", caminho] if caminho else ["code", "-n"], shell=True)
        return f"Abri o VS Code{' em ' + caminho if caminho else ''}."
    except FileNotFoundError:
        return ("Não encontrei o comando 'code'. No VS Code, aperte Ctrl+Shift+P, "
                "digite 'Shell Command: Install code command in PATH' e tente de novo.")


def criar_arquivo_codigo(caminho, conteudo):
    """Cria (ou sobrescreve) um arquivo com o conteúdo dado e abre no VS Code."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(caminho)) or ".", exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(conteudo)
        subprocess.Popen(["code", caminho], shell=True)
        return f"Criei e abri '{caminho}' no VS Code."
    except Exception as erro:
        return f"Não consegui criar o arquivo: {erro}"


FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "abrir_musica_youtube",
        "description": "Abre no navegador a pesquisa de uma música ou artista no YouTube.",
        "parameters": {"type": "object", "properties": {
            "busca": {"type": "string", "description": "nome da música e/ou artista"}},
            "required": ["busca"]}}},
    {"type": "function", "function": {
        "name": "abrir_site",
        "description": "Abre um site no navegador (YouTube, Google, Spotify, Gmail, GitHub ou qualquer URL).",
        "parameters": {"type": "object", "properties": {
            "url_ou_nome": {"type": "string"}}, "required": ["url_ou_nome"]}}},
    {"type": "function", "function": {
        "name": "abrir_vscode",
        "description": "Abre uma pasta ou arquivo no VS Code.",
        "parameters": {"type": "object", "properties": {
            "caminho": {"type": "string", "description": "caminho da pasta/arquivo; opcional"}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "criar_arquivo_codigo",
        "description": "Cria um arquivo de código com o conteúdo dado e abre no VS Code.",
        "parameters": {"type": "object", "properties": {
            "caminho": {"type": "string", "description": "ex.: 'C:/Users/SeuUsuario/Projetos/teste.py'"},
            "conteudo": {"type": "string"}},
            "required": ["caminho", "conteudo"]}}},
]

_FUNCOES = {
    "abrir_musica_youtube": abrir_musica_youtube, "abrir_site": abrir_site,
    "abrir_vscode": abrir_vscode, "criar_arquivo_codigo": criar_arquivo_codigo,
}


def executar(nome, args):
    if nome not in _FUNCOES:
        return None
    try:
        return _FUNCOES[nome](**args)
    except Exception as erro:
        return f"Erro ao executar {nome}: {erro}"
