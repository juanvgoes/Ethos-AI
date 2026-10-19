"""
Ethos AI - interface gráfica em janela própria (tkinter, já vem com o Python).
Sem navegador, sem servidor, sem instalar nada novo.

Coloque na MESMA pasta do ethos_ai_voz.py e rode:
    python ethos_ai_gui.py
"""

import math
import queue
import re
import sys
import threading
import time
import tkinter as tk

import ollama

import ethos_ai_voz as ethos  # carrega Whisper e vozes (demora um pouco)
import ferramentas_externas
import ferramentas_gmail
import ferramentas_sistema
import memoria
from tkinter import ttk

BG, FG, DIM, LINHA = "#131418", "#eef0f5", "#7d818c", "#2a2c33"
NOMES = {"espera": "EM ESPERA", "ouvindo": "OUVINDO", "pensando": "PROCESSANDO", "falando": "FALANDO"}
LEMAS = ["Aprender é construir", "Uma pergunta de cada vez", "Pronto para ajudar",
         "Simples, direto e útil"]

fila = queue.Queue()          # mensagens das threads de trabalho -> janela
ocupado = threading.Lock()    # impede dois pedidos ao mesmo tempo
_ouvindo = threading.Event()  # ligado enquanto o microfone está gravando
_app = None                   # referência à instância do App, definida no main


def enviar(**msg):
    fila.put(msg)


def extrair_frases(buffer):
    """Devolve (frases_completas, resto_do_texto)."""
    frases = []
    while True:
        for m in re.finditer(r"[.!?…]+\s|\n", buffer):
            if m.end() >= 20:
                frases.append(buffer[:m.end()].strip())
                buffer = buffer[m.end():]
                break
        else:
            return frases, buffer


TODAS_FERRAMENTAS = (
    memoria.FERRAMENTAS + ferramentas_externas.FERRAMENTAS
    + ferramentas_sistema.FERRAMENTAS + ferramentas_gmail.FERRAMENTAS
)


def executar_ferramenta(nome, args):
    if nome in memoria._FUNCOES:
        return memoria.executar(nome, args)
    resultado = ferramentas_externas.executar(nome, args)
    if resultado is None:
        resultado = ferramentas_sistema.executar(nome, args)
    if resultado is None:
        resultado = ferramentas_gmail.executar(nome, args)
    return resultado if resultado is not None else f"Ferramenta desconhecida: {nome}"


def com_no_think(historico):
    """Devolve uma cópia do histórico com '/no_think' anexado na última
    mensagem do usuário. Além do parâmetro think=False (que o Ollama às
    vezes ignora com o Qwen3 — bug conhecido), essa é a forma que o próprio
    modelo foi treinado para obedecer de verdade. Não altera o histórico
    original nem aparece na tela."""
    copia = list(historico)
    if copia and copia[-1]["role"] == "user":
        copia[-1] = {**copia[-1], "content": copia[-1]["content"] + "\n\n/no_think"}
    return copia


def montar_historico():
    """Reconstrói o histórico com o resumo de memória sempre atualizado no topo."""
    historico = ethos.estado["historico"]
    base = historico[0]["content"].split("\n\nO que você sabe sobre o usuário")[0]
    res = memoria.resumo()
    if res:
        base += "\n\nO que você sabe sobre o usuário, gírias e tarefas (use as ferramentas para atualizar):\n" + res
    historico[0]["content"] = base
    return historico


def responder_texto(pergunta):
    """Chat de texto puro (sem voz), para a aba Conteúdo: escreve a pergunta e a
    resposta completa ali, sem tocar na área de fala."""
    historico = montar_historico()
    historico.append({"role": "user", "content": pergunta})
    enviar(transcricao=f"\nVOCÊ:\n{pergunta}\n\nETHOS:\n")

    ethos.iniciar_som_processando()
    hora_direta = ethos.resposta_direta_horario(pergunta)
    if hora_direta is not None:
        checagem = {"message": {"content": hora_direta, "tool_calls": None}}
    else:
        checagem = ollama.chat(model=ethos.MODELO_IA, messages=com_no_think(historico),
                               tools=TODAS_FERRAMENTAS, think=False, keep_alive="30m")
    chamadas = checagem["message"].get("tool_calls") or []
    if chamadas:
        historico.append(checagem["message"])
        for c in chamadas:
            resultado = executar_ferramenta(c["function"]["name"], c["function"]["arguments"])
            historico.append({"role": "tool", "content": resultado})
        # só precisa de uma 2ª chamada quando usou ferramenta
        bruto = ""
        for pedaco in ollama.chat(model=ethos.MODELO_IA, messages=com_no_think(historico),
                                  stream=True, think=False, keep_alive="30m"):
            bruto += pedaco["message"]["content"]
    else:
        bruto = checagem["message"]["content"] or ""
    ethos.parar_som_processando()
    resposta = ethos.remover_pensamento(bruto)
    enviar(transcricao=resposta)
    historico.append({"role": "assistant", "content": resposta})
    enviar(transcricao="\n" + "─" * 40 + "\n")


def responder(pergunta, idioma):
    historico = montar_historico()
    historico.append({"role": "user", "content": pergunta})
    enviar(estado="pensando")

    # 1ª chamada (sem streaming): além de checar se a IA quer usar alguma
    # ferramenta, o texto que ela já devolve aqui (quando NÃO usa ferramenta)
    # é reaproveitado como a resposta final — evita pagar o custo de "pensar"
    # duas vezes (antes isso chamava o modelo de novo sempre, dobrando o
    # tempo de espera à toa).
    inicio_geracao = time.time()
    ethos.iniciar_som_processando()
    hora_direta = ethos.resposta_direta_horario(pergunta)
    if hora_direta is not None:
        checagem = {"message": {"content": hora_direta, "tool_calls": None}}
    else:
        checagem = ollama.chat(model=ethos.MODELO_IA, messages=com_no_think(historico),
                               tools=TODAS_FERRAMENTAS, think=False, keep_alive="30m")
    chamadas = checagem["message"].get("tool_calls") or []

    if chamadas:
        historico.append(checagem["message"])
        for c in chamadas:
            resultado = executar_ferramenta(c["function"]["name"], c["function"]["arguments"])
            historico.append({"role": "tool", "content": resultado})
        # só precisa de uma 2ª chamada quando usou ferramenta, para responder
        # com base no resultado dela
        bruto = ""
        for p in ollama.chat(model=ethos.MODELO_IA, messages=com_no_think(historico),
                             stream=True, think=False, keep_alive="30m"):
            bruto += p["message"]["content"]
    else:
        bruto = checagem["message"]["content"] or ""

    tempo_geracao = time.time() - inicio_geracao
    ethos.parar_som_processando()
    texto_pronto = ethos.remover_pensamento(bruto)
    print(
        f"⏱ GUI: {tempo_geracao:.1f}s gerando (bruto: {len(bruto)} chars, "
        f"limpo: {len(texto_pronto)} chars){' [usou ferramenta]' if chamadas else ''}"
    )

    idioma_voz = ethos.idioma_da_resposta(idioma)
    falas = queue.Queue()

    def locutor():
        while True:
            frase = falas.get()
            if frase is None:
                return
            enviar(estado="falando")
            ethos.falar(frase, idioma_voz)

    voz = threading.Thread(target=locutor, daemon=True)
    voz.start()

    MARCA = "---CONTEUDO---"

    # quebra em pedacinhos pequenos só para a fala sair suave, frase a frase,
    # igual já acontecia antes (a diferença é que agora chega tudo de uma vez,
    # não mais token a token da rede)
    TAMANHO_PEDACO = 20
    pedacos_prontos = [
        texto_pronto[i:i + TAMANHO_PEDACO]
        for i in range(0, len(texto_pronto), TAMANHO_PEDACO)
    ] or [""]

    resposta, enviado, fala_buffer, cortou, modo_conteudo = "", 0, "", False, False
    for texto_limpo in pedacos_prontos:
        resposta += texto_limpo

        if modo_conteudo:
            enviar(conteudo=texto_limpo)
            continue

        if MARCA in resposta:
            indice = resposta.index(MARCA)
            novo = resposta[enviado:indice]
            if novo:
                enviar(token=novo)
                fala_buffer += novo
            modo_conteudo, enviado = True, len(resposta)
            enviar(conteudo=f"\n[da conversa por voz]\n")
            resto = resposta[indice + len(MARCA):]
            if resto:
                enviar(conteudo=resto)
            if fala_buffer.strip():
                falas.put(fala_buffer.strip())
            continue

        # ainda não sabemos se os últimos caracteres fazem parte da marcação:
        # só liberamos o que com certeza não faz parte dela
        ainda_nao_enviado = resposta[enviado:]
        guardar = min(len(MARCA) - 1, len(ainda_nao_enviado))
        novo = ainda_nao_enviado[: len(ainda_nao_enviado) - guardar] if guardar else ainda_nao_enviado
        if not novo:
            continue
        enviado += len(novo)
        enviar(token=novo)
        fala_buffer += novo
        if "Dica:" in fala_buffer:
            fala_buffer, cortou = fala_buffer.split("Dica:")[0], True
            if fala_buffer.strip():
                falas.put(fala_buffer.strip())
            fala_buffer = ""
            continue
        frases, fala_buffer = extrair_frases(fala_buffer)
        for frase in frases:
            falas.put(frase)

    if not modo_conteudo and not cortou:
        # solta o pedacinho final que ficou retido esperando confirmar que não
        # era o começo da marcação (senão as últimas letras somem da fala)
        sobrou = resposta[enviado:]
        if sobrou:
            enviar(token=sobrou)
            fala_buffer += sobrou
        if "Dica:" in fala_buffer:
            fala_buffer = fala_buffer.split("Dica:")[0]
        if fala_buffer.strip():
            falas.put(fala_buffer.strip())
    falas.put(None)
    if modo_conteudo:
        enviar(conteudo="\n" + "─" * 40 + "\n")
    historico.append({"role": "assistant", "content": resposta.split(MARCA)[0].strip()})
    voz.join()


def tarefa(acao, dados):
    if not ocupado.acquire(blocking=False):
        return
    try:
        if acao == "texto_longo":
            responder_texto(dados)
            return
        if acao == "ouvir":
            enviar(estado="ouvindo")
            ethos.tocar_efeito("ativar")
            _ouvindo.set()
            try:
                pergunta, idioma = ethos.ouvir(verificar_parar=lambda: _app._parar_gravacao_agora)
            finally:
                _ouvindo.clear()
            if pergunta:
                ethos.tocar_efeito("concluir")
        elif acao == "texto":
            pergunta, idioma = dados, "pt"
        elif acao == "texto_ativado":
            pergunta, idioma = dados, "pt"  # já veio transcrito e filtrado
        elif acao == "modo":
            ethos.trocar_modo(dados)
            enviar(modo=dados, voce="")
            idioma_aviso, frase = ethos.MODOS[dados]["aviso"]
            enviar(token=frase, estado="falando")
            ethos.falar(frase, idioma_aviso)
            return
        else:
            return
        if not pergunta:
            enviar(voce="(não entendi, tente de novo)")
            return
        enviar(voce="» " + pergunta)
        responder(pergunta, idioma)
    except Exception as erro:
        enviar(voce=f"Erro: {erro}") if acao != "texto_longo" else enviar(transcricao=f"\n[Erro: {erro}]\n")
    finally:
        ethos.parar_som_processando()
        enviar(estado="espera")
        ocupado.release()


def blend(cor_a, cor_b, k):
    """Mistura duas cores #rrggbb (k=0 -> a, k=1 -> b). Simula transparência."""
    a = [int(cor_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(cor_b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * k) for x, y in zip(a, b))


class App:
    def __init__(self, raiz):
        self.raiz, self.estado, self.amp, self.t, self.lema = raiz, "espera", 0.1, 0.0, 0
        raiz.title("ETHOS AI")
        raiz.configure(bg=BG)
        raiz.geometry("780x920")
        raiz.minsize(480, 560)

        # F11 liga/desliga tela cheia; Esc sai da tela cheia (padrão do Windows)
        self.tela_cheia = False
        raiz.bind("<F11>", self.alternar_tela_cheia)
        raiz.bind("<Escape>", self.sair_tela_cheia)

        self._parar_gravacao_agora = False  # sinalizado pelo botão "PARAR DE OUVIR"

        estilo = ttk.Style()
        estilo.theme_use("clam")
        estilo.configure("TNotebook", background=BG, borderwidth=0)
        estilo.configure("TNotebook.Tab", background=BG, foreground=DIM,
                         padding=(16, 8), font=("Segoe UI", 9))
        estilo.map("TNotebook.Tab", background=[("selected", BG)],
                  foreground=[("selected", FG)])

        abas = ttk.Notebook(raiz)
        abas.pack(fill="both", expand=True)
        self.abas = abas

        aba_conversa = tk.Frame(abas, bg=BG)
        aba_conteudo = tk.Frame(abas, bg=BG)
        aba_ajuda = tk.Frame(abas, bg=BG)
        abas.add(aba_conversa, text="CONVERSA")
        abas.add(aba_conteudo, text="CONTEÚDO")
        abas.add(aba_ajuda, text="AJUDA")

        self._montar_aba_ajuda(aba_ajuda)

        tk.Label(aba_conteudo, bg=BG, fg=DIM, font=("Segoe UI", 10), justify="left",
                 text="Cole aqui um texto/código grande. Opcionalmente escreva uma instrução no campo "
                      "abaixo (ex.: 'revise este código') e clique em ENVIAR. As respostas aparecem "
                      "aqui mesmo, como um chat de texto — sem voz.",
                 wraplength=700).pack(pady=(14, 4), padx=16, anchor="w")
        self.conteudo = tk.Text(aba_conteudo, bg="#1a1b20", fg=FG, insertbackground=FG,
                                font=("Consolas", 12), relief="flat", padx=16, pady=16,
                                wrap="word")
        self.conteudo.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        botoes_cont = tk.Frame(aba_conteudo, bg=BG)
        botoes_cont.pack(pady=(0, 10), fill="x", padx=16)
        self.instrucao = tk.Entry(botoes_cont, bg=BG, fg=FG, insertbackground=FG, relief="flat",
                                  highlightthickness=1, highlightbackground=LINHA,
                                  highlightcolor=FG, font=("Segoe UI", 10))
        self.instrucao.insert(0, "")
        self.instrucao.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))
        self.instrucao.bind("<Return>", lambda e: self.enviar_conteudo())
        self.botao(botoes_cont, "COPIAR", self.copiar_conteudo).pack(side="left", padx=3)
        self.botao(botoes_cont, "LIMPAR", lambda: self.conteudo.delete("1.0", "end")).pack(side="left", padx=3)
        self.botao(botoes_cont, "ENVIAR ▸", self.enviar_conteudo).pack(side="left", padx=3)

        raiz = aba_conversa  # tudo abaixo vai dentro da aba "Conversa"

        # IMPORTANTE: os controles fixos (rodapé, botão falar/mic, modos) são
        # "pack"ados ANTES do conteúdo que cresce (texto da IA). Quem é fixado
        # em cima/baixo primeiro sempre fica visível; só a área do meio
        # (scroll) é que encolhe quando o texto da resposta é grande. Isso
        # garante que os botões nunca saiam da tela, não importa o tamanho
        # da resposta.
        self.rodape = tk.Label(raiz, text=LEMAS[0].upper(), bg=BG, fg=DIM, font=("Segoe UI", 9, "italic"))
        self.rodape.pack(side="bottom", pady=10)

        baixo = tk.Frame(raiz, bg=BG)
        baixo.pack(side="bottom", pady=8)
        self.botao_falar = self.botao(baixo, "●  FALAR", lambda: self.acao("ouvir", None))
        self.botao_falar.pack(side="left", padx=6)
        self.botao(baixo, "■ PARAR DE OUVIR", self.parar_de_ouvir_agora).pack(side="left", padx=6)
        self.entrada = tk.Entry(baixo, width=30, bg=BG, fg=FG, insertbackground=FG, relief="flat",
                                highlightthickness=1, highlightbackground=LINHA,
                                highlightcolor=FG, font=("Segoe UI", 11))
        self.entrada.pack(side="left", ipady=6, padx=6)
        self.entrada.bind("<Return>", self.enviar_texto)

        barra = tk.Frame(raiz, bg=BG)
        barra.pack(side="bottom", pady=8)
        self.botoes = {}
        for nome, rotulo in (("conversa", "CONVERSA"), ("ingles", "INGLÊS"), ("tradutor", "TRADUTOR")):
            self.botoes[nome] = self.botao(barra, rotulo, lambda n=nome: self.acao("modo", n))
            self.botoes[nome].pack(side="left", padx=5)
        self.marcar("conversa")

        # Área central: cresce/encolhe, e ganha scroll quando o texto da IA
        # é maior que o espaço disponível (em vez de empurrar os botões
        # fixos acima para fora da tela).
        meio = tk.Frame(raiz, bg=BG)
        meio.pack(side="top", fill="both", expand=True)

        tk.Label(meio, text="E T H O S   A I", bg=BG, fg=FG,
                 font=("Segoe UI", 11)).pack(pady=(14, 0))
        self.tela = tk.Canvas(meio, width=440, height=440, bg=BG, highlightthickness=0)
        self.tela.pack(pady=(6, 0))
        self.st = tk.Label(meio, text="EM ESPERA", bg=BG, fg=DIM, font=("Segoe UI", 10))
        self.st.pack(pady=(0, 10))
        self.voce = tk.Label(meio, text="", bg=BG, fg=DIM, font=("Segoe UI", 11), wraplength=680)
        self.voce.pack()

        # a resposta da IA vive dentro de um canvas com scroll: se o texto for
        # curto, ocupa só o espaço necessário; se for grande, vira scroll em
        # vez de esticar a janela ou empurrar os botões
        caixa_ia = tk.Frame(meio, bg=BG)
        caixa_ia.pack(fill="both", expand=True, padx=16, pady=(8, 4))
        canvas_ia = tk.Canvas(caixa_ia, bg=BG, highlightthickness=0)
        scroll_ia = tk.Scrollbar(caixa_ia, orient="vertical", command=canvas_ia.yview,
                                 bg=BG, troughcolor=BG)
        canvas_ia.configure(yscrollcommand=scroll_ia.set)
        canvas_ia.pack(side="left", fill="both", expand=True)
        interior = tk.Frame(canvas_ia, bg=BG)
        janela_interior = canvas_ia.create_window((0, 0), window=interior, anchor="n")
        self.ia = tk.Label(interior, text="", bg=BG, fg=FG, font=("Segoe UI", 14),
                           wraplength=680, justify="center")
        self.ia.pack()

        def _ajustar_scroll(_e=None):
            canvas_ia.configure(scrollregion=canvas_ia.bbox("all"))
            # centraliza o texto horizontalmente e mostra a barra só quando precisa
            largura = canvas_ia.winfo_width()
            canvas_ia.coords(janela_interior, largura / 2, 0)
            precisa_scroll = interior.winfo_reqheight() > canvas_ia.winfo_height()
            if precisa_scroll:
                scroll_ia.pack(side="right", fill="y")
            else:
                scroll_ia.pack_forget()

        interior.bind("<Configure>", _ajustar_scroll)
        canvas_ia.bind("<Configure>", _ajustar_scroll)
        self._ajustar_scroll_ia = _ajustar_scroll

        raiz.after(9000, self.trocar_lema)
        self.animar()
        self.ler_fila()

    def _montar_aba_ajuda(self, aba):
        canvas = tk.Canvas(aba, bg=BG, highlightthickness=0)
        scroll = tk.Scrollbar(aba, orient="vertical", command=canvas.yview, bg=BG)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        interior = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=interior, anchor="nw")
        interior.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def titulo(texto):
            tk.Label(interior, text=texto, bg=BG, fg=FG, font=("Segoe UI", 12, "bold"),
                     anchor="w").pack(fill="x", padx=20, pady=(18, 4))

        def item(cmd, explicacao):
            linha = tk.Frame(interior, bg=BG)
            linha.pack(fill="x", padx=20, pady=2)
            tk.Label(linha, text=cmd, bg=BG, fg=FG, font=("Consolas", 10, "bold"),
                     width=22, anchor="w").pack(side="left")
            tk.Label(linha, text=explicacao, bg=BG, fg=DIM, font=("Segoe UI", 10),
                     anchor="w", wraplength=480, justify="left").pack(side="left", fill="x")

        titulo("MODOS DE CONVERSA (botões ou digite)")
        item("/conversa", "Bate-papo comum em português, respostas curtas.")
        item("/ingles", "Professor de inglês — conversa em EN, corrige erros em PT.")
        item("/tradutor", "Traduz automaticamente entre português e inglês.")

        titulo("COMANDOS DIGITADOS (na caixa de texto)")
        item("/memoria", "Mostra tudo que ela guardou: fatos, tarefas, eventos recentes.")
        item("sair / exit / quit", "Encerra o programa (modo terminal).")

        titulo("VOZ E MICROFONE")
        item("● FALAR", "Grava sua pergunta; para sozinho após ~1,2s de silêncio.")
        item("■ PARAR DE OUVIR", "Corta a gravação na hora — útil em ambiente barulhento, "
                                 "quando o silêncio nunca é detectado sozinho.")
        item("Atalho de tecla", "Aperte Ctrl+Alt+E em qualquer programa, fale, e ela responde.")

        titulo("JANELA")
        item("F11", "Liga/desliga o modo tela cheia.")
        item("Esc", "Sai do modo tela cheia.")

        titulo("FERRAMENTAS QUE ELA PODE USAR SOZINHA")
        item("Data e hora", "Pergunte 'que horas são' ou 'que dia é hoje'.")
        item("Memória", "Ela salva e lembra fatos, gírias, tarefas e eventos que você conta.")
        item("Abrir programas", "'Abre o VS Code', 'toca X no YouTube', 'abre o Gmail'.")
        item("Criar arquivos", "'Cria um arquivo chamado X com esse código'.")
        item("Ler e-mails", "'Lê meus e-mails', 'tem e-mail não lido?', 'procura e-mail de X'.")

    def parar_de_ouvir_agora(self):
        """Corta a gravação em andamento na hora, mesmo sem 1s de silêncio
        detectado (útil em ambiente barulhento, onde o silêncio nunca é
        reconhecido naturalmente). Funciona tanto no FALAR comum quanto na
        escuta contínua — o texto já gravado até aqui ainda é transcrito e
        considerado."""
        self._parar_gravacao_agora = True
        self.raiz.after(400, lambda: setattr(self, "_parar_gravacao_agora", False))

    def alternar_tela_cheia(self, _evento=None):
        self.tela_cheia = not self.tela_cheia
        self.raiz.attributes("-fullscreen", self.tela_cheia)

    def sair_tela_cheia(self, _evento=None):
        if self.tela_cheia:
            self.tela_cheia = False
            self.raiz.attributes("-fullscreen", False)

    def copiar_conteudo(self):
        self.raiz.clipboard_clear()
        self.raiz.clipboard_append(self.conteudo.get("1.0", "end-1c"))

    def enviar_conteudo(self):
        texto = self.conteudo.get("1.0", "end-1c").strip()
        if not texto:
            return
        instrucao = self.instrucao.get().strip()
        self.instrucao.delete(0, "end")
        pergunta = f"{instrucao}\n\n{texto}" if instrucao else \
            f"Dê uma olhada no que colei abaixo e me diga o que achar:\n\n{texto}"
        self.conteudo.delete("1.0", "end")
        self.acao("texto_longo", pergunta)

    def botao(self, pai, texto, comando):
        return tk.Button(pai, text=texto, command=comando, bg=BG, fg=FG, activebackground=LINHA,
                         activeforeground=FG, relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=LINHA, padx=14, pady=7, font=("Segoe UI", 9), cursor="hand2")

    def marcar(self, modo):
        for nome, b in self.botoes.items():
            b.config(highlightbackground=FG if nome == modo else LINHA)

    def acao(self, acao, dados):
        threading.Thread(target=tarefa, args=(acao, dados), daemon=True).start()

    def enviar_texto(self, _):
        texto = self.entrada.get().strip()
        if not texto:
            return
        self.entrada.delete(0, "end")
        if texto.lower() in ("/memoria", "/tarefas"):
            self.voce.config(text="» " + texto)
            self.ia.config(text=memoria.resumo() or "(nada guardado ainda)")
            return
        self.acao("texto", texto)

    def trocar_lema(self):
        self.lema += 1
        self.rodape.config(text=LEMAS[self.lema % len(LEMAS)].upper())
        self.raiz.after(9000, self.trocar_lema)

    def ler_fila(self):
        while not fila.empty():
            m = fila.get()
            if "estado" in m:
                self.estado = m["estado"]
                self.st.config(text=NOMES[self.estado])
            if "voce" in m:
                self.voce.config(text=m["voce"])
                self.ia.config(text="")
            if "token" in m:
                self.ia.config(text=self.ia.cget("text") + m["token"])
            if "modo" in m:
                self.marcar(m["modo"])
            if "conteudo" in m:
                self.conteudo.insert("end", m["conteudo"])
                self.conteudo.see("end")
            if "transcricao" in m:
                self.conteudo.insert("end", m["transcricao"])
                self.conteudo.see("end")
        self.raiz.after(50, self.ler_fila)

    def hexagono(self, r, rot, cor, larg):
        pts = []
        for i in range(6):
            a = rot + i * math.pi / 3
            pts += [220 + r * math.cos(a), 220 + r * math.sin(a)]
        self.tela.create_polygon(pts, outline=cor, fill="", width=larg)

    def animar(self):
        self.t += 0.033
        alvo = {"espera": .12, "ouvindo": .55, "pensando": .3, "falando": .85}[self.estado]
        self.amp += (alvo - self.amp) * .06
        vel = 1.4 if self.estado == "pensando" else .22
        self.tela.delete("all")
        for i in range(6):
            voz = abs(math.sin(self.t * 6 + i * 1.3)) if self.estado == "falando" else 1
            r = 62 + i * 28 + math.sin(self.t * 1.6 + i) * self.amp * 12 * voz
            cor = blend(BG, FG, .8 - i * .12)
            self.hexagono(r, (-1 if i % 2 else 1) * self.t * vel * (1 + i * .25) + i * .35, cor, 2 if i == 0 else 1)
        rc = 20 + self.amp * 18 * (.6 + .4 * math.sin(self.t * 9) if self.estado == "falando" else 1)
        for k in range(7):  # brilho do núcleo (círculos que vão clareando)
            raio = rc * (2.2 - k * .3)
            self.tela.create_oval(220 - raio, 220 - raio, 220 + raio, 220 + raio,
                                  fill=blend(BG, "#ffffff", .08 + k * .15), outline="")
        self.raiz.after(33, self.animar)


# ------------------ atalho de tecla global (funciona com outros programas abertos) ------------------
HOTKEY_FALAR = "<ctrl>+<alt>+e"   # troque aqui se quiser outra combinação


def _ao_apertar_atalho():
    """Roda numa thread do teclado (não na thread do tkinter).
    - Se já está gravando: a mesma tecla para a gravação.
    - Se está livre: começa a gravar e responder.
    - Se está respondendo/falando: ignora, para não encavalar."""
    if _ouvindo.is_set():
        _app._parar_gravacao_agora = True
        threading.Timer(0.4, lambda: setattr(_app, "_parar_gravacao_agora", False)).start()
    elif not ocupado.locked():
        _app.acao("ouvir", None)


def iniciar_atalho_global():
    from pynput import keyboard
    ouvinte = keyboard.GlobalHotKeys({HOTKEY_FALAR: _ao_apertar_atalho})
    ouvinte.daemon = True
    ouvinte.start()
    return ouvinte


if __name__ == "__main__":
    ethos.trocar_modo("conversa")
    raiz = tk.Tk()
    _app = App(raiz)
    iniciar_atalho_global()
    # "--segundo-plano" abre a janela escondida; o atalho continua funcionando
    if "--segundo-plano" in sys.argv:
        raiz.withdraw()
    raiz.mainloop()
