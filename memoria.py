"""
Memória da Ethos AI: fatos sobre você, gírias que ela aprende e tarefas.
Guarda tudo num arquivo JSON simples (memoria_ethos.json) na mesma pasta.
"""

import datetime
import json
import os

ARQUIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoria_ethos.json")

_padrao = {"fatos": {}, "girias": {}, "tarefas": [], "eventos": []}


def carregar():
    if os.path.exists(ARQUIVO):
        with open(ARQUIVO, encoding="utf-8") as f:
            dados = json.load(f)
        for chave in _padrao:
            dados.setdefault(chave, _padrao[chave])
        return dados
    return {k: (v.copy() if hasattr(v, "copy") else v) for k, v in _padrao.items()}


def salvar(dados):
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


memoria = carregar()


# ------------------------------ ações ------------------------------
def salvar_fato(chave, valor):
    memoria["fatos"][chave.lower().strip()] = valor
    salvar(memoria)
    return f"Anotado: {chave} = {valor}."


def esquecer_fato(chave):
    existia = memoria["fatos"].pop(chave.lower().strip(), None)
    salvar(memoria)
    return f"Esqueci '{chave}'." if existia is not None else f"Não tinha nada sobre '{chave}'."


def aprender_giria(termo, significado):
    memoria["girias"][termo.lower().strip()] = significado
    salvar(memoria)
    return f"Aprendido: '{termo}' significa '{significado}'."


def adicionar_tarefa(texto):
    novo_id = (max((t["id"] for t in memoria["tarefas"]), default=0)) + 1
    memoria["tarefas"].append({"id": novo_id, "texto": texto, "feita": False})
    salvar(memoria)
    return f"Tarefa #{novo_id} adicionada: {texto}."


def concluir_tarefa(id_tarefa):
    for t in memoria["tarefas"]:
        if t["id"] == id_tarefa:
            t["feita"] = True
            salvar(memoria)
            return f"Tarefa #{id_tarefa} concluída."
    return f"Não achei a tarefa #{id_tarefa}."


def remover_tarefa(id_tarefa):
    antes = len(memoria["tarefas"])
    memoria["tarefas"] = [t for t in memoria["tarefas"] if t["id"] != id_tarefa]
    salvar(memoria)
    return f"Tarefa #{id_tarefa} removida." if len(memoria["tarefas"]) < antes else f"Não achei a tarefa #{id_tarefa}."


def registrar_evento(texto, data=None):
    """Guarda algo que aconteceu/foi feito, com a data (padrão: hoje)."""
    data = (data or datetime.date.today().isoformat())
    memoria["eventos"].append({"data": data, "texto": texto})
    memoria["eventos"].sort(key=lambda e: e["data"])
    salvar(memoria)
    return f"Anotado em {data}: {texto}."


def consultar_eventos(data_inicio=None, data_fim=None):
    """Retorna os eventos registrados num período (ISO: AAAA-MM-DD).
    Sem datas, retorna os últimos 10 eventos registrados."""
    eventos = memoria["eventos"]
    if data_inicio or data_fim:
        inicio = data_inicio or "0000-00-00"
        fim = data_fim or "9999-99-99"
        eventos = [e for e in eventos if inicio <= e["data"] <= fim]
    else:
        eventos = eventos[-10:]
    if not eventos:
        return "Não encontrei nenhum evento registrado nesse período."
    return "; ".join(f"{e['data']}: {e['texto']}" for e in eventos)


# -------------------- resumo para a IA "lembrar" --------------------
def resumo():
    """Texto curto com tudo que ela sabe, para entrar no system prompt."""
    partes = []
    if memoria["fatos"]:
        partes.append("Fatos sobre o usuário: " +
                       "; ".join(f"{k}: {v}" for k, v in memoria["fatos"].items()))
    if memoria["girias"]:
        partes.append("Gírias/termos aprendidos: " +
                       "; ".join(f"'{k}' = {v}" for k, v in memoria["girias"].items()))
    pendentes = [t for t in memoria["tarefas"] if not t["feita"]]
    if pendentes:
        partes.append("Tarefas pendentes: " +
                       "; ".join(f"#{t['id']} {t['texto']}" for t in pendentes))
    recentes = memoria["eventos"][-8:]
    if recentes:
        partes.append(
            "Eventos/coisas feitas recentemente (use a ferramenta consultar_eventos "
            "para buscar um período específico, ex.: 'semana passada'): " +
            "; ".join(f"{e['data']}: {e['texto']}" for e in recentes)
        )
    hoje = datetime.date.today()
    partes.append(f"Data de hoje (referência para calcular 'ontem', 'semana passada' etc.): {hoje.isoformat()}")
    return "\n".join(partes) if partes else ""


# --------------------- ferramentas (tool calling) --------------------
FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "salvar_fato",
        "description": "Salva uma informação sobre o usuário para lembrar depois (nome, preferências, dados pessoais).",
        "parameters": {"type": "object", "properties": {
            "chave": {"type": "string", "description": "do que se trata, ex.: 'curso', 'time do coração'"},
            "valor": {"type": "string", "description": "a informação em si"}},
            "required": ["chave", "valor"]}}},
    {"type": "function", "function": {
        "name": "esquecer_fato",
        "description": "Apaga uma informação salva sobre o usuário.",
        "parameters": {"type": "object", "properties": {
            "chave": {"type": "string"}}, "required": ["chave"]}}},
    {"type": "function", "function": {
        "name": "aprender_giria",
        "description": "Aprende uma gíria, apelido ou termo informal usado pelo usuário e o que ele significa.",
        "parameters": {"type": "object", "properties": {
            "termo": {"type": "string"}, "significado": {"type": "string"}},
            "required": ["termo", "significado"]}}},
    {"type": "function", "function": {
        "name": "adicionar_tarefa",
        "description": "Adiciona uma tarefa ou lembrete pedido pelo usuário.",
        "parameters": {"type": "object", "properties": {
            "texto": {"type": "string"}}, "required": ["texto"]}}},
    {"type": "function", "function": {
        "name": "concluir_tarefa",
        "description": "Marca uma tarefa como concluída, pelo número dela.",
        "parameters": {"type": "object", "properties": {
            "id_tarefa": {"type": "integer"}}, "required": ["id_tarefa"]}}},
    {"type": "function", "function": {
        "name": "remover_tarefa",
        "description": "Remove/apaga uma tarefa, pelo número dela.",
        "parameters": {"type": "object", "properties": {
            "id_tarefa": {"type": "integer"}}, "required": ["id_tarefa"]}}},
    {"type": "function", "function": {
        "name": "registrar_evento",
        "description": (
            "Registra algo que o usuário fez, viveu ou aconteceu, para lembrar depois "
            "(ex.: 'fui ao médico', 'terminei o projeto X', 'viajei para tal lugar'). "
            "Chame isso sempre que o usuário contar algo relevante que fez ou que aconteceu."
        ),
        "parameters": {"type": "object", "properties": {
            "texto": {"type": "string", "description": "o que aconteceu, de forma breve"},
            "data": {"type": "string", "description": "data no formato AAAA-MM-DD; se não informado, usa hoje"}},
            "required": ["texto"]}}},
    {"type": "function", "function": {
        "name": "consultar_eventos",
        "description": (
            "Busca o que foi registrado num período de tempo (ex.: 'o que eu fiz semana "
            "passada'). Calcule as datas em AAAA-MM-DD com base na data de hoje informada "
            "no contexto antes de chamar esta ferramenta."
        ),
        "parameters": {"type": "object", "properties": {
            "data_inicio": {"type": "string", "description": "AAAA-MM-DD, início do período"},
            "data_fim": {"type": "string", "description": "AAAA-MM-DD, fim do período"}},
            "required": []}}},
]

_FUNCOES = {
    "salvar_fato": salvar_fato, "esquecer_fato": esquecer_fato,
    "aprender_giria": aprender_giria, "adicionar_tarefa": adicionar_tarefa,
    "concluir_tarefa": concluir_tarefa, "remover_tarefa": remover_tarefa,
    "registrar_evento": registrar_evento, "consultar_eventos": consultar_eventos,
}


def executar(nome, args):
    if nome not in _FUNCOES:
        return f"Ferramenta desconhecida: {nome}"
    try:
        return _FUNCOES[nome](**args)
    except Exception as erro:
        return f"Erro ao executar {nome}: {erro}"
