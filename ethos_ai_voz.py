"""
Ethos AI v0.3 - conversa por voz em português e inglês, 100% local.

Fluxo:  microfone -> faster-whisper (voz vira texto) -> Ollama (IA pensa)
        -> Piper (texto vira voz neural)

Instalação (no terminal):
    pip install -U ollama faster-whisper sounddevice numpy piper-tts

Vozes (rode NA MESMA PASTA deste arquivo, uma vez cada):
    python -m piper.download_voices pt_BR-faber-medium
    python -m piper.download_voices en_US-ryan-medium

Comandos (digite no lugar de apertar ENTER):
    /conversa  -> bate-papo normal em português
    /ingles    -> treino de inglês: você fala inglês, ela responde e corrige
    /tradutor  -> você fala em português e ela traduz para inglês (e vice-versa)
    /ajuda     -> mostra os comandos
    sair       -> encerra
"""

import io
import os
import re
import threading
import time
import wave

import numpy as np
import ollama
import sounddevice as sd
from faster_whisper import WhisperModel
from piper import PiperVoice

# ======================= CONFIGURAÇÕES (mexa à vontade) =======================
MODELO_IA = "qwen3:4b-instruct-2507-q4_K_M"
MODELO_WHISPER = "small"  # "base" = mais rápido | "small" = entende melhor

# Arquivos das vozes do Piper (ficam na mesma pasta deste script)
ARQUIVOS_VOZ = {
    "pt": "pt_BR-faber-medium.onnx",
    "en": "en_GB-alan-medium.onnx",  # britânica masculina (sotaque tipo Jarvis)
}

# --- Microfone ---
TAXA = 16000           # o Whisper usa 16 kHz
LIMITE_VOLUME = 0.01   # sensibilidade: se ele não te ouve, diminua (ex.: 0.005)
SILENCIO_FINAL = 1.2   # segundos de silêncio para entender que você terminou
ESPERA_MAXIMA = 8      # segundos esperando você começar a falar
GRAVACAO_MAXIMA = 30   # limite de segurança por fala

# --- Palavra de ativação (modo "escuta contínua") ---
PALAVRA_ATIVACAO = "ei ethos"  # em minúsculas, sem acento, para comparar fácil

# --- PERSONALIZAÇÃO DO NOME "ETHOS" ---
# 1) Dica de vocabulário para o Whisper: palavras que ele deve esperar ouvir.
#    Coloque aqui nomes e termos que ele costuma errar.
VOCABULARIO = "Ethos AI, Ethos."

# 2) Correções do que ele ESCREVEU errado -> como deveria ser.
#    Rode, veja o que aparece em "VOCÊ >" e vá adicionando os erros dele aqui.
CORRECOES_OUVIDO = {
    "etos": "Ethos",
    "etus": "Ethos",
    "ethus": "Ethos",
    "éthos": "Ethos",
    "ethós": "Ethos",
}

# 3) Pronúncia da voz em português: como a palavra deve SOAR (só na fala,
#    o texto na tela continua "Ethos"). Ajuste até ficar como você quer.
PRONUNCIAS_PT = {
    "Ethos": "Étos",
}
# =============================================================================

PASTA = os.path.dirname(os.path.abspath(__file__))

# Cada modo define: em que idioma você fala, e a "personalidade" da IA.
MODOS = {
    "conversa": {
        "ouvir": "pt",
        "prompt": (
            "/no_think\n\n"
            "IMPORTANTE: não pense em voz alta, não narre seu raciocínio, não escreva "
            "frases como 'let me check', 'the user wants', 'so maybe' ou qualquer "
            "análise sobre como responder. Sua PRIMEIRA palavra já deve ser o início "
            "da resposta final, direto, sem nenhum rascunho ou reflexão antes dela.\n\n"
            "Você é a ETHOS AI, uma assistente pessoal de IA com estilo futurista, "
            "inspirada no JARVIS do Homem de Ferro. Responda sempre em português do "
            "Brasil, de forma educada, direta e com um toque leve de sarcasmo elegante. "
            "Suas respostas serão FALADAS em voz alta, então seja curta (no máximo 3 "
            "frases) e não use listas, emojis, asteriscos nem formatação. "
            "EXCEÇÃO: se o usuário pedir código, um poema, uma redação, um texto longo "
            "ou qualquer conteúdo para ser escrito/copiado (não apenas conversado), "
            "responda em DUAS partes separadas EXATAMENTE pela linha '---CONTEUDO---' "
            "(sozinha, sem mais nada nela): antes dessa linha, uma confirmação FALADA "
            "bem curta, tipo 'Pronto, já fiz.' ou 'Prontinho, está na tela.'; depois "
            "dessa linha, o conteúdo completo, sem comentários extras, sem repetir a "
            "confirmação. Use essa marcação SOMENTE nesses casos, nunca numa conversa normal."
        ),
        "aviso": ("pt", "Modo conversa ativado."),
    },
    "ingles": {
        "ouvir": "en",
        "prompt": (
            "/no_think\n\n"
            "IMPORTANT: do not think out loud, do not narrate your reasoning, do not "
            "write things like 'let me check', 'the user wants' or any analysis of "
            "how to respond. Your FIRST word must already be the start of your final "
            "answer, directly, with no draft or reflection before it.\n\n"
            "You are ETHOS AI, a friendly English tutor and conversation partner. "
            "The user is a Brazilian learning English. Reply in simple, natural English "
            "(level B1), in at most 2 short sentences, and ask a short follow-up question "
            "to keep the conversation going. Your replies will be spoken aloud, so do not "
            "use lists, emojis, asterisks or formatting. If the user made a grammar or "
            "vocabulary mistake, add at the very end a short tip IN PORTUGUESE starting "
            "with 'Dica:' showing the corrected sentence. If there was no mistake, do not "
            "add any tip."
        ),
        "aviso": ("en", "English practice mode on. Let's talk!"),
    },
    "tradutor": {
        "ouvir": None,  # o Whisper descobre sozinho se você falou português ou inglês
        "prompt": (
            "/no_think\n\n"
            "IMPORTANTE: não pense em voz alta nem narre seu raciocínio antes de "
            "traduzir. Sua PRIMEIRA palavra já deve ser o início da tradução, direto.\n\n"
            "Você é um tradutor profissional. Se o usuário falar em português, traduza "
            "para o inglês. Se falar em inglês, traduza para o português do Brasil. "
            "Responda SOMENTE com a tradução, sem comentários, sem aspas e sem explicações."
        ),
        "aviso": ("pt", "Modo tradutor ativado. Fale em português ou inglês."),
    },
}

estado = {"modo": "conversa", "historico": []}


def trocar_modo(nome):
    estado["modo"] = nome
    estado["historico"] = [{"role": "system", "content": MODOS[nome]["prompt"]}]


# ---------------------------- CARREGAMENTO ----------------------------
print("Carregando reconhecimento de voz...")
# CPU + int8 é o jeito mais simples e deixa a placa de vídeo livre para a IA
whisper = WhisperModel(MODELO_WHISPER, device="cpu", compute_type="int8")

print("Carregando vozes...")
vozes = {}
for idioma, arquivo in ARQUIVOS_VOZ.items():
    caminho = os.path.join(PASTA, arquivo)
    if os.path.exists(caminho):
        vozes[idioma] = PiperVoice.load(caminho)
    else:
        print(f"⚠ Voz '{arquivo}' não encontrada. Baixe com: "
              f"python -m piper.download_voices {arquivo.replace('.onnx', '')}")
if "pt" not in vozes:
    raise SystemExit("A voz em português é obrigatória. Baixe-a e rode de novo.")


# --------------------- FILTRO DE SEGURANÇA DO "PENSAMENTO" -------------
# Frases típicas de raciocínio vazando sem tag (o Qwen3 às vezes "pensa em
# inglês" mesmo com think=False, sem usar <think>). Se um parágrafo COMEÇA
# com uma dessas pistas, ele é descartado inteiro.
PISTAS_RACIOCINIO = (
    "let me", "so maybe", "the user", "i should", "i need to", "i will",
    "wait,", "actually,", "hmm,", "okay,", "first,", "checking the",
    "according to the rules", "so the response", "so i",
)


def remover_pensamento(texto):
    """Remove o pensamento do texto, em qualquer formato que ele apareça:
    1) <think>...</think> completo (par normal);
    2) só "...</think>" sem abertura correspondente — bug observado no Ollama
       com think=False, onde a tag de abertura é suprimida mas o texto do
       pensamento continua grudado no content, e só a tag de fechamento sobra.
       Nesse caso, tudo ANTES do último </think> é pensamento e é descartado;
    3) parágrafos de raciocínio solto em inglês, sem tag nenhuma."""
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL)

    if "</think>" in texto:
        texto = texto.rsplit("</think>", 1)[1]
    texto = texto.strip()

    paragrafos = [p for p in texto.split("\n\n") if p.strip()]
    paragrafos_limpos = [
        p for p in paragrafos
        if not p.strip().lower().startswith(PISTAS_RACIOCINIO)
    ]
    # só aplica se sobrar pelo menos um parágrafo depois de filtrar
    # (evita apagar a resposta inteira por engano)
    if paragrafos_limpos:
        texto = "\n\n".join(paragrafos_limpos)
    return texto.strip()


# ------------------------------- OUVIR --------------------------------
def corrigir_texto(texto):
    """Troca palavras que o Whisper costuma errar (ex.: 'etos' -> 'Ethos')."""
    for errado, certo in CORRECOES_OUVIDO.items():
        texto = re.sub(rf"\b{re.escape(errado)}\b", certo, texto, flags=re.IGNORECASE)
    return texto


def _gravar_ate_silencio(espera_maxima=ESPERA_MAXIMA, gravacao_maxima=GRAVACAO_MAXIMA,
                          verificar_parar=None):
    """Grava do microfone até você ficar em silêncio (ou os limites baterem).
    Devolve o áudio (numpy array) ou None se ninguém falou / foi pedido para parar.
    verificar_parar: função opcional chamada a cada pedaço; se retornar True,
    interrompe a gravação na hora (usado pelo botão de desligar o microfone)."""
    blocos = []
    falou = False
    silencio = 0.0
    total = 0.0
    passo = 0.1  # lê o microfone em pedaços de 0,1 s

    with sd.InputStream(samplerate=TAXA, channels=1, dtype="float32") as mic:
        while True:
            if verificar_parar is not None and verificar_parar():
                return None
            bloco, _ = mic.read(int(TAXA * passo))
            blocos.append(bloco)
            total += passo
            volume = float(np.sqrt(np.mean(bloco**2)))

            if volume > LIMITE_VOLUME:
                falou = True
                silencio = 0.0
            elif falou:
                silencio += passo
                if silencio >= SILENCIO_FINAL:
                    break

            if not falou and total >= espera_maxima:
                return None  # ninguém falou
            if total >= gravacao_maxima:
                break

    return np.concatenate(blocos).flatten()


def _transcrever(audio, idioma_forcado=None):
    """Transcreve um áudio já gravado. Devolve (texto_corrigido, idioma)."""
    inicio = time.time()
    segmentos, info = whisper.transcribe(
        audio,
        language=idioma_forcado,  # None = detectar sozinho
        initial_prompt=VOCABULARIO,
        vad_filter=True,
    )
    texto = " ".join(s.text.strip() for s in segmentos).strip()
    print(f"⏱ transcrição: {time.time() - inicio:.1f}s")
    idioma = info.language if info.language in ("pt", "en") else "pt"
    return corrigir_texto(texto), idioma


def ouvir(verificar_parar=None):
    """Grava até você ficar em silêncio (ou até verificar_parar() retornar
    True, se for passado — usado pelo botão 'parar de ouvir agora', útil em
    ambiente barulhento onde o silêncio de 1s pode nunca ser detectado).
    Retorna (texto, idioma_detectado)."""
    print("🎤 Ouvindo... (fale agora)")
    audio = _gravar_ate_silencio(verificar_parar=verificar_parar)
    if audio is None:
        return "", "pt"
    idioma_esperado = MODOS[estado["modo"]]["ouvir"]
    return _transcrever(audio, idioma_esperado)


def _normalizar(texto):
    """Minúsculas e sem acento, para comparar com a palavra de ativação."""
    import unicodedata
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def ouvir_com_palavra_de_ativacao(verificar_parar):
    """Modo 'escuta contínua': grava uma fala, transcreve, e só devolve algo
    se a frase contiver a palavra de ativação ('ei ethos'). Nesse caso,
    devolve o texto que veio DEPOIS da palavra de ativação (o pedido de
    verdade). Se não detectar a palavra, devolve (None, None) e quem chamou
    deve tentar de novo (loop contínuo).
    verificar_parar: função chamada periodicamente; se retornar True, a
    escuta para imediatamente (botão de desligar o microfone)."""
    audio = _gravar_ate_silencio(
        espera_maxima=3600,  # não desiste sozinho: só para quando mandarem
        verificar_parar=verificar_parar,
    )
    if audio is None:
        return None, None  # ninguém falou nesse ciclo, ou foi pedido parar

    texto, idioma = _transcrever(audio, None)  # detecta idioma sozinho aqui
    texto_normalizado = _normalizar(texto)
    gatilho_normalizado = _normalizar(PALAVRA_ATIVACAO)

    if gatilho_normalizado not in texto_normalizado:
        return None, None  # falou algo, mas não ativou a Ethos

    # extrai só o que vem depois da palavra de ativação, se tiver algo
    indice = texto_normalizado.find(gatilho_normalizado)
    resto = texto[indice + len(PALAVRA_ATIVACAO):].strip(" ,.!?-")
    if resto:
        return resto, idioma
    return "", idioma  # disse só "ei ethos" sem pedir nada ainda


# ------------------------------- FALAR --------------------------------
# Intensidade do efeito de voz (0 = desligado). Ajuste ao gosto.
EFEITO_VOZ = 1.0


def aplicar_efeito_jarvis(audio_int16, taxa):
    """Deixa a voz com cara de sistema: um eco curto e discreto e uma leve
    compressão, que dá presença sem distorcer. Recebe e devolve float."""
    x = audio_int16.astype(np.float32)
    x = x / (np.max(np.abs(x)) + 1e-9)
    if EFEITO_VOZ <= 0:
        return (x * 0.9).astype(np.float32)
    saida = x.copy()
    for atraso_s, ganho in ((0.035, 0.22), (0.09, 0.10)):
        d = int(atraso_s * taxa)
        saida[d:] += EFEITO_VOZ * ganho * x[:-d]
    saida = np.tanh(1.4 * saida) / np.tanh(1.4)  # compressão suave
    return (saida * 0.9).astype(np.float32)


def tocar_efeito(nome):
    """Efeitos sonoros curtos, gerados na hora (não precisam de arquivo).
    'ativar' = começou a ouvir; 'concluir' = entendeu o que você disse."""
    taxa = 22050
    if nome == "ativar":
        f_ini, f_fim, duracao = 880, 1320, 0.14
    elif nome == "concluir":
        f_ini, f_fim, duracao = 1320, 880, 0.12
    else:
        return
    n = int(taxa * duracao)
    frequencia = np.linspace(f_ini, f_fim, n)
    fase = 2 * np.pi * np.cumsum(frequencia) / taxa
    onda = np.sin(fase) * np.hanning(n) * 0.25
    sd.play(onda.astype(np.float32), taxa)
    sd.wait()


# Som sutil de "processando": um tique discreto que se repete enquanto a IA
# pensa. Para antes da fala começar (e nunca toca durante a gravação, para
# não ser captado pelo microfone).
_processando = threading.Event()


def _tique(frequencia):
    taxa = 22050
    n = int(taxa * 0.03)
    t = np.arange(n) / taxa
    onda = np.sin(2 * np.pi * frequencia * t) * np.hanning(n) * 0.05
    sd.play(onda.astype(np.float32), taxa)
    sd.wait()


def _loop_processando():
    alternar = True
    while _processando.is_set():
        _tique(1600 if alternar else 2000)  # dois tons alternados: "máquina trabalhando"
        alternar = not alternar
        time.sleep(0.7)


def iniciar_som_processando():
    if _processando.is_set():
        return
    _processando.set()
    threading.Thread(target=_loop_processando, daemon=True).start()


def parar_som_processando():
    _processando.clear()


def resposta_direta_horario(pergunta):
    """Perguntas de hora/data são respondidas pela própria ferramenta, sem
    passar pelo modelo (que, sendo pequeno, às vezes repete uma hora antiga
    do histórico). Devolve None se não for pergunta de hora."""
    padrao = re.compile(
        r"(que horas|que hora|horas s[aã]o|qual (é |e )?a hora|hora (é|e) agora"
        r"|que dia (é|e) hoje|qual (é |e )?a data|data de hoje)",
        re.IGNORECASE,
    )
    if padrao.search(pergunta):
        import ferramentas_externas
        return ferramentas_externas.obter_data_hora()
    return None


def falar(texto, idioma="pt"):
    """Fala o texto com a voz neural do Piper no idioma pedido."""
    if idioma not in vozes:
        idioma = "pt"
    if idioma == "pt":
        for escrita, som in PRONUNCIAS_PT.items():
            texto = re.sub(rf"\b{re.escape(escrita)}\b", som, texto, flags=re.IGNORECASE)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as arquivo:
        vozes[idioma].synthesize_wav(texto, arquivo)
    buffer.seek(0)

    with wave.open(buffer, "rb") as arquivo:
        taxa = arquivo.getframerate()
        audio = np.frombuffer(arquivo.readframes(arquivo.getnframes()), dtype=np.int16)
    audio = aplicar_efeito_jarvis(audio, taxa)
    sd.play(audio, taxa)
    sd.wait()


def idioma_da_resposta(idioma_entrada):
    """Define em que idioma a Ethos AI vai FALAR a resposta."""
    modo = estado["modo"]
    if modo == "ingles":
        return "en"
    if modo == "tradutor":
        return "en" if idioma_entrada == "pt" else "pt"  # traduz para o outro idioma
    return "pt"


# ------------------------------ RESPONDER -----------------------------
def responder(pergunta, idioma_entrada):
    historico = estado["historico"]
    historico.append({"role": "user", "content": pergunta})
    resposta = ""
    inicio = time.time()
    primeira_palavra = None

    # /no_think no FIM da última mensagem: além do parâmetro think=False (que
    # o Ollama às vezes ignora com o Qwen3 — bug conhecido), essa é a forma
    # que o próprio Qwen foi treinado para obedecer de verdade. Só entra no
    # que é mandado pro modelo; o histórico salvo continua limpo.
    mensagens_envio = historico[:-1] + [
        {"role": "user", "content": pergunta + "\n\n/no_think"}
    ]

    # Junta a resposta inteira ANTES de mostrar na tela: assim o pensamento
    # (com ou sem tag de abertura) nunca aparece, nem na tela nem na fala.
    # O preço é não ver o texto "digitando" em tempo real no terminal.
    for pedaco in ollama.chat(
        model=MODELO_IA,
        messages=mensagens_envio,
        stream=True,
        think=False,
        keep_alive="30m",  # mantém o modelo na memória entre as perguntas
    ):
        if primeira_palavra is None:
            primeira_palavra = time.time() - inicio
        resposta += pedaco["message"]["content"]

    resposta = remover_pensamento(resposta)
    print(f"ETHOS  > {resposta}\n")
    print(
        f"⏱ IA: {primeira_palavra:.1f}s até a 1ª palavra, "
        f"{time.time() - inicio:.1f}s no total"
    )
    historico.append({"role": "assistant", "content": resposta})

    # A "Dica:" (em português) só aparece na tela, não é lida pela voz em inglês
    fala = resposta.split("Dica:")[0].strip()

    inicio = time.time()
    falar(fala, idioma_da_resposta(idioma_entrada))
    print(f"⏱ fala: {time.time() - inicio:.1f}s\n")


# -------------------------------- MAIN --------------------------------
def mostrar_ajuda():
    print("  /conversa  bate-papo em português")
    print("  /ingles    treino de inglês (você fala inglês, ela corrige)")
    print("  /tradutor  tradução português <-> inglês")
    print("  ENTER      falar | ou digite o texto | 'sair' encerra\n")


def main():
    trocar_modo("conversa")
    print("=" * 58)
    print("  ETHOS AI online.")
    print("=" * 58)
    mostrar_ajuda()
    falar("Ethos AI online. Como posso ajudar?")

    while True:
        entrada = input(f"[{estado['modo']}] ENTER para falar (ou digite): ").strip()

        if entrada.lower() in ("sair", "exit", "quit"):
            falar("Encerrando sistemas. Até logo.")
            break

        if entrada.lower() in ("/ajuda", "/help"):
            mostrar_ajuda()
            continue

        if entrada.startswith("/") and entrada[1:].lower() in MODOS:
            novo = entrada[1:].lower()
            trocar_modo(novo)
            idioma_aviso, frase = MODOS[novo]["aviso"]
            print(f"ETHOS  > {frase}\n")
            falar(frase, idioma_aviso)
            continue

        if entrada:
            pergunta = entrada
            # texto digitado: tenta adivinhar o idioma só para o modo tradutor
            idioma = "en" if re.search(r"\b(the|is|are|you|and|what|how)\b", entrada, re.I) else "pt"
            if estado["modo"] == "ingles":
                idioma = "en"
        else:
            pergunta, idioma = ouvir()

        if not pergunta:
            print("(não entendi nada, tente de novo)\n")
            continue

        print(f"VOCÊ   > {pergunta}")
        responder(pergunta, idioma)


if __name__ == "__main__":
    main()
