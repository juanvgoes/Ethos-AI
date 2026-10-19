"""
Ferramentas da Ethos AI que usam internet: data/hora e previsão do tempo.
Usa a Open-Meteo (open-meteo.com), gratuita e sem precisar de chave.
"""

import datetime

# Cidade usada quando você não informa nenhuma e não há cidade salva na memória.
# Troque pela sua (ex.: "Lisboa", "Belo Horizonte", "Nova York").
CIDADE_PADRAO = "São Paulo"

import requests

DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo"]


def obter_data_hora():
    agora = datetime.datetime.now()
    return (f"Hoje é {DIAS[agora.weekday()]}, "
            f"{agora.strftime('%d/%m/%Y')}, e agora são {agora.strftime('%H:%M')}.")


def obter_previsao_tempo(local=None):
    import memoria  # import aqui dentro para evitar ciclo de importação
    cidade = local or memoria.memoria["fatos"].get("cidade") or \
        memoria.memoria["fatos"].get("localização") or CIDADE_PADRAO

    try:
        geo = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                           params={"name": cidade, "count": 1, "language": "pt"}, timeout=6).json()
        if not geo.get("results"):
            return f"Não encontrei a cidade '{cidade}'."
        lugar = geo["results"][0]
        lat, lon, nome = lugar["latitude"], lugar["longitude"], lugar["name"]

        clima = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat, "longitude": lon, "current": "temperature_2m,weather_code",
            "timezone": "auto",
        }, timeout=6).json()["current"]

        descricoes = {
            0: "céu limpo", 1: "poucas nuvens", 2: "parcialmente nublado", 3: "nublado",
            45: "neblina", 51: "garoa fraca", 61: "chuva fraca", 63: "chuva moderada",
            65: "chuva forte", 80: "pancadas de chuva", 95: "trovoadas",
        }
        descricao = descricoes.get(clima["weather_code"], "condições variadas")
        return f"Em {nome} agora: {clima['temperature_2m']:.0f}°C, {descricao}."
    except Exception as erro:
        return f"Não consegui buscar a previsão agora ({erro})."


FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "obter_data_hora",
        "description": "Retorna a data e a hora atuais.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "obter_previsao_tempo",
        "description": "Retorna a temperatura e condição do tempo agora numa cidade.",
        "parameters": {"type": "object", "properties": {
            "local": {"type": "string", "description": "cidade; se não informado, usa a cidade salva na memória ou a CIDADE_PADRAO"}},
            "required": []}}},
]

_FUNCOES = {"obter_data_hora": obter_data_hora, "obter_previsao_tempo": obter_previsao_tempo}


def executar(nome, args):
    if nome not in _FUNCOES:
        return None  # não é daqui; quem chamou tenta outro módulo
    try:
        return _FUNCOES[nome](**args)
    except Exception as erro:
        return f"Erro ao executar {nome}: {erro}"
