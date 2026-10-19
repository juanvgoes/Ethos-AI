# Ethos AI

Um assistente pessoal de IA que roda **localmente** no seu computador: ela ouve sua voz, responde falando, lembra de coisas que você conta, abre programas e pode ler seus e-mails. Tudo funciona offline, sem API paga, com modelos abertos.

Inspirada na ideia de um assistente tipo JARVIS.

---

## Sumário

1. [O que ela faz](#o-que-ela-faz)
2. [Requisitos](#requisitos)
3. [Instalação passo a passo](#instalação-passo-a-passo)
4. [Como rodar](#como-rodar)
5. [Como usar](#como-usar)
6. [Trocar o modelo de IA](#trocar-o-modelo-de-ia)
7. [Configurações principais](#configurações-principais)
8. [Configurar a leitura de e-mails (Gmail)](#configurar-a-leitura-de-e-mails-gmail)
9. [Estrutura do projeto](#estrutura-do-projeto)
10. [Subir para o GitHub com segurança](#subir-para-o-github-com-segurança)
11. [Solução de problemas](#solução-de-problemas)

---

## O que ela faz

- **Conversa por voz e por texto**, em português e inglês.
- **Modos de conversa:** bate-papo (`/conversa`), professor de inglês (`/ingles`) e tradutor (`/tradutor`).
- **Memória persistente:** guarda fatos sobre você, gírias, tarefas e eventos com data, e usa isso nas próximas conversas.
- **Hora e data** sempre corretas, respondidas direto pelo relógio do computador.
- **Ferramentas que ela usa sozinha:**
  - previsão do tempo (Open-Meteo, gratuito, sem chave);
  - abrir sites e programas (YouTube, Gmail, VS Code, etc.);
  - criar arquivos de código;
  - ler e buscar e-mails no Gmail (somente leitura).
- **Atalho de tecla global:** aperte uma combinação em qualquer programa, fale, e ela responde sem você precisar abrir a janela.
- **Interface gráfica** com tela cheia, aba de conteúdo para textos longos e aba de ajuda com todos os comandos.

---

## Requisitos

**Hardware:**
- Computador com pelo menos **8 GB de RAM** (16 GB é mais confortável).
- Placa de vídeo NVIDIA é recomendada: a resposta fica bem mais rápida. Sem GPU, funciona, mas mais devagar.
- Microfone e caixa de som.

**Software:**
- **Windows 10 ou 11** (testado no Windows; o núcleo funciona em Linux e macOS, mas o atalho `.lnk` e alguns detalhes são específicos do Windows).
- **Python 3.10 ou superior** (testado com 3.14). Baixe em [python.org](https://www.python.org/downloads/). Na instalação, marque **"Add Python to PATH"**.
- **Ollama**, que roda os modelos de IA localmente. Baixe em [ollama.com](https://ollama.com).
- **Visual Studio Code** (opcional, só se quiser que ela abra o editor).

---

## Instalação passo a passo

### 1. Baixe o projeto

Clone o repositório ou baixe o ZIP e extraia numa pasta, por exemplo `C:\Ethos`.

### 2. Instale o Ollama e baixe os modelos

Instale o Ollama e **abra o aplicativo** (ele precisa estar rodando em segundo plano). Depois, no terminal:

```bash
# Modelo principal (rápido, respostas diretas). Obrigatório.
ollama pull qwen3:4b-instruct-2507-q4_K_M

# Modelo maior, reserva para tarefas mais complexas. Opcional (~6 GB).
ollama pull qwen3:8b
```

Para conferir se o modelo está instalado: `ollama list`.

### 3. Crie um ambiente e instale as bibliotecas

Abra o terminal (PowerShell) dentro da pasta do projeto e rode:

```bash
pip install ollama faster-whisper sounddevice numpy piper-tts requests pynput google-auth-oauthlib google-api-python-client Pillow
```

Opcional, só para criar o atalho na área de trabalho:

```bash
pip install pywin32
```

> Se o pip reclamar de permissão ou de "externally managed", acrescente `--break-system-packages` no final do comando.

### 4. Baixe as vozes do Piper

As vozes não vêm no repositório (são arquivos grandes). Baixe-as dentro da pasta do projeto:

```bash
python -m piper.download_voices pt_BR-faber-medium
python -m piper.download_voices en_GB-alan-medium
```

Cada voz gera dois arquivos (`.onnx` e `.onnx.json`), que devem ficar na mesma pasta dos scripts.

> Se quiser usar outra voz, veja a seção [Configurações principais](#configurações-principais).

### 5. Primeira execução

Na primeira vez, o Whisper (reconhecimento de voz) baixa o modelo de transcrição automaticamente. Isso acontece uma vez só e pode levar alguns minutos.

---

## Como rodar

### Pela interface gráfica (recomendado)

```bash
python ethos_ai_gui.py
```

### Em segundo plano, só com o atalho de tecla

```bash
python ethos_ai_gui.py --segundo-plano
```

A janela abre escondida. Você usa a tecla de atalho em qualquer programa, e a resposta sai só por voz.

### Pelo terminal (sem interface)

```bash
python ethos_ai_voz.py
```

Aqui você usa ENTER para falar ou digita a pergunta direto.

### Atalho na área de trabalho (Windows)

```bash
python criar_atalho.py
```

Cria um ícone "Ethos AI" na área de trabalho, com o ícone do projeto. Dê duplo clique para abrir a interface.

---

## Como usar

### Atalho de tecla (padrão: `Ctrl+Alt+E`)

1. Aperte a combinação. Vai soar um tom de início.
2. Fale sua pergunta.
3. Quando você parar de falar, ela entende a frase, responde e fala a resposta.
4. Se quiser cortar a gravação antes (por exemplo, num ambiente barulhento), **aperte a mesma tecla de novo**.

Enquanto ela estiver respondendo, a tecla é ignorada, para não encavalar pedidos.

### Botões da interface

| Botão | O que faz |
|---|---|
| **● FALAR** | Grava sua pergunta pelo microfone |
| **■ PARAR DE OUVIR** | Corta a gravação na hora |
| **CONVERSA / INGLÊS / TRADUTOR** | Troca o modo de conversa |
| Caixa de texto | Escreva a pergunta e aperte ENTER |

### Comandos digitados

| Comando | O que faz |
|---|---|
| `/conversa` | Bate-papo em português |
| `/ingles` | Professor de inglês |
| `/tradutor` | Traduz entre português e inglês |
| `/memoria` | Mostra tudo que ela guardou |
| `/ajuda` | Lista os comandos (no terminal) |
| `sair` | Encerra (no terminal) |

### Teclas da janela

| Tecla | Função |
|---|---|
| `F11` | Liga/desliga tela cheia |
| `Esc` | Sai da tela cheia |

### O que você pode pedir (exemplos)

- "Que horas são?" / "Que dia é hoje?"
- "Qual a previsão do tempo em Lisboa?"
- "Lembra que eu tenho prova de física dia 20."
- "O que eu fiz semana passada?" (usa os eventos que você registrou)
- "Abre o VS Code." / "Abre o YouTube." / "Toca lo-fi no YouTube."
- "Cria um arquivo chamado teste.py com um hello world."
- "Lê meus e-mails." / "Tem e-mail não lido?" / "Procura e-mail da Maria."

---

## Trocar o modelo de IA

O modelo é definido em **uma linha** do arquivo `ethos_ai_voz.py`:

```python
MODELO_IA = "qwen3:4b-instruct-2507-q4_K_M"
```

Para trocar, edite essa linha com o nome de **qualquer modelo que você tenha no Ollama** (veja com `ollama list`). Exemplos:

```python
MODELO_IA = "qwen3:8b"                   # mais inteligente, mais lento
MODELO_IA = "qwen3:4b-instruct-2507-q4_K_M"  # rápido, recomendado para voz
```

Depois de editar, salve e rode a interface de novo.

**Dicas ao escolher um modelo:**
- Para **conversa por voz**, prefira modelos rápidos. Resposta de vários segundos já incomoda.
- Modelos com o sufixo **`instruct`** respondem direto, sem "pensar em voz alta". Eles costumam ser mais rápidos e mais limpos para voz.
- Modelos maiores (8B ou mais) entendem melhor pedidos complexos, mas exigem mais memória e placa de vídeo.
- Se a sua placa de vídeo tiver pouca memória, o Ollama divide o modelo entre GPU e CPU, e aí fica lento. Use um modelo menor ou uma versão mais compactada (`q4_K_M` costuma ser um bom equilíbrio).

Para testar se um modelo roda 100% na GPU, enquanto ele estiver respondendo, rode `ollama ps` num outro terminal. A coluna **PROCESSOR** deve mostrar `100% GPU`.

**Para trocar o modelo de reconhecimento de voz** (Whisper), edite `MODELO_WHISPER` no mesmo arquivo: `"base"` é mais rápido, `"small"` entende melhor.

---

## Configurações principais

Todas ficam no topo dos arquivos, em forma de constante. Não precisa mexer em mais nada.

| Arquivo | Constante | Para que serve |
|---|---|---|
| `ethos_ai_voz.py` | `MODELO_IA` | Modelo de conversa (Ollama) |
| `ethos_ai_voz.py` | `MODELO_WHISPER` | Modelo de reconhecimento de voz |
| `ethos_ai_voz.py` | `ARQUIVOS_VOZ` | Arquivos das vozes do Piper (português e inglês) |
| `ethos_ai_voz.py` | `LIMITE_VOLUME` | Sensibilidade do microfone. Se ela não te ouve, diminua (ex.: `0.005`). Se capta barulho demais, aumente |
| `ethos_ai_voz.py` | `SILENCIO_FINAL` | Segundos de silêncio para considerar que você terminou de falar |
| `ethos_ai_voz.py` | `EFEITO_VOZ` | Intensidade do eco na voz. `0` desliga |
| `ethos_ai_voz.py` | `VOCABULARIO` | Palavras que o reconhecimento deve esperar ouvir (ex.: o nome da assistente) |
| `ethos_ai_gui.py` | `HOTKEY_FALAR` | Combinação de teclas do atalho global (padrão `<ctrl>+<alt>+e`) |
| `ferramentas_externas.py` | `CIDADE_PADRAO` | Cidade usada na previsão do tempo quando você não informa nenhuma |

**Trocar a voz:** baixe outra voz do Piper (lista em [huggingface.co/rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices)) e atualize o nome em `ARQUIVOS_VOZ`.

**Trocar o nome da assistente:** o nome "Ethos" aparece no `ETHOS AI` do cabeçalho (`ethos_ai_gui.py`), nos prompts dos modos (`MODOS` em `ethos_ai_voz.py`) e no `VOCABULARIO`. Basta substituir.

---

## Configurar a leitura de e-mails (Gmail)

Esta parte é opcional. Sem ela, o resto funciona normalmente. O acesso é **somente leitura**: a assistente não consegue enviar, apagar ou alterar e-mails.

### Passo 1: criar o projeto no Google Cloud

1. Acesse [console.cloud.google.com](https://console.cloud.google.com) e entre com a conta Gmail que ela vai ler.
2. Crie um projeto novo (qualquer nome, por exemplo "Ethos AI").

### Passo 2: ativar a Gmail API

1. Vá em **APIs e Serviços > Biblioteca**.
2. Procure por **Gmail API** e clique em **Ativar**.

### Passo 3: configurar a tela de consentimento

1. Vá em **APIs e Serviços > Tela de consentimento OAuth**.
2. Escolha **Externo** e preencha o nome do app e seu e-mail.
3. Em **Escopos**, adicione `https://www.googleapis.com/auth/gmail.readonly`.
4. Em **Usuários de teste**, adicione o seu próprio e-mail.

> Como o app não será publicado, o Google mostra um aviso de "app não verificado" na primeira autorização. Isso é esperado: é o seu próprio app.

### Passo 4: criar a credencial

1. Vá em **APIs e Serviços > Credenciais > Criar credenciais > ID do cliente OAuth**.
2. Tipo: **App para computador**.
3. Baixe o JSON, renomeie para **`credentials.json`** e coloque na pasta do projeto, ao lado do `ethos_ai_gui.py`.

### Passo 5: primeira autorização

Peça à assistente para ler seus e-mails (por exemplo, "lê meus e-mails"). Uma aba do navegador vai abrir pedindo login e autorização. Depois disso, ela salva um arquivo `token.json` e não pede de novo.

> **Nunca compartilhe** `credentials.json` nem `token.json`. Eles são listados no `.gitignore` para não irem ao GitHub.

### Ferramentas de e-mail disponíveis

- `ler_emails_recentes`: lista os últimos e-mails (remetente, assunto e trecho). Aceita filtrar só os não lidos.
- `buscar_emails`: procura e-mails por um termo (nome, empresa, assunto).

---

## Estrutura do projeto

| Arquivo | Função |
|---|---|
| `ethos_ai_gui.py` | Interface gráfica, atalho de tecla e modo segundo plano. **Comece por aqui.** |
| `ethos_ai_voz.py` | Núcleo: reconhecimento de voz (Whisper), síntese (Piper), modos de conversa e sons |
| `memoria.py` | Memória persistente (fatos, gírias, tarefas, eventos com data) |
| `ferramentas_externas.py` | Hora, data e previsão do tempo |
| `ferramentas_sistema.py` | Abrir sites e programas, criar arquivos de código |
| `ferramentas_gmail.py` | Leitura e busca de e-mails |
| `criar_atalho.py` | Cria o atalho na área de trabalho (Windows) |
| `ethos_icone.ico` | Ícone usado no atalho |

Arquivos criados automaticamente pelo programa (não fazem parte do repositório):
- `memoria_ethos.json`: sua memória.
- `token.json`: autorização do Gmail.
- Os arquivos `.onnx` das vozes.

---

## Subir para o GitHub com segurança

O arquivo `.gitignore` já impede que os itens sensíveis sejam enviados. Antes do primeiro envio, confira:

```bash
git status
```

Não deve aparecer nenhum destes arquivos na lista: `credentials.json`, `token.json`, `memoria_ethos.json`, nenhum `.onnx`, nem a pasta `__pycache__`.

Se algum deles já tiver sido enviado num commit anterior, **não basta apagar**: o histórico guarda o conteúdo. Nesse caso, troque as credenciais no Google Cloud (crie um novo ID de cliente e apague o antigo).

---

## Solução de problemas

**"Connection refused" ou `WinError 10061` ao iniciar**
O Ollama não está rodando. Abra o aplicativo Ollama e tente de novo.

**A resposta demora muito**
- Confirme com `ollama ps` se o modelo está em `100% GPU`.
- Feche navegador e programas pesados (a RAM influencia bastante).
- Troque para um modelo menor ou para uma versão `instruct`.

**Ela fala o raciocínio interno em inglês ("Let me check...")**
Use um modelo `instruct` (como o `qwen3:4b-instruct-2507-q4_K_M`). Modelos com "thinking" nem sempre respeitam a instrução de não pensar em voz alta.

**Ela não me ouve, ou não para de ouvir**
Ajuste `LIMITE_VOLUME`. Em ambiente barulhento, use o atalho de novo para cortar a gravação na hora.

**O atalho de tecla não responde**
- Confira se nenhum outro programa usa a mesma combinação.
- Programas abertos "como administrador" bloqueiam atalhos globais. Teste com o programa normal.
- Troque a combinação em `HOTKEY_FALAR`.

**O VS Code não abre pelo comando**
No VS Code, aperte `Ctrl+Shift+P` e rode *"Shell Command: Install 'code' command in PATH"*. Depois reinicie o terminal.

**Erro ao criar o atalho na área de trabalho**
Se a área de trabalho estiver no OneDrive, o script já procura o caminho certo. Se mesmo assim falhar, abra o `criar_atalho.py` e informe o caminho manualmente.

**"Não encontrei o credentials.json"**
Coloque o arquivo na mesma pasta do `ethos_ai_gui.py`, com esse nome exato.

**A voz não aparece / erro ao carregar a voz**
Confira se os dois arquivos da voz (`.onnx` e `.onnx.json`) estão na pasta do projeto e se o nome em `ARQUIVOS_VOZ` bate com eles.

**A hora está errada**
A hora vem do relógio do computador. Confira se o Windows está com o fuso horário e a sincronização corretos.

---

## Privacidade

- Toda a conversa e o reconhecimento de voz acontecem no seu computador.
- A única conexão com a internet é opcional: a previsão do tempo (Open-Meteo) e a leitura de e-mails (Gmail, se você configurar).
- Sua memória fica no arquivo `memoria_ethos.json`. Apague o arquivo para zerar tudo.

---

## Licença

Adicione aqui a licença que preferir (por exemplo, MIT) antes de publicar.
