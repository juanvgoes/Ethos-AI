"""
Cria um atalho "Ethos AI" na área de trabalho do Windows, com o ícone
hexagonal (ethos_icone.ico) e apontando para o ethos_ai_gui.py desta pasta.

Rode UMA VEZ, depois de garantir que o Python usado tem as bibliotecas do
projeto instaladas:
    pip install pywin32 --break-system-packages
    python criar_atalho.py

Depois disso, é só dar duplo clique no ícone "Ethos AI" na área de trabalho
para abrir a GUI, sem precisar abrir terminal nem digitar nada.
"""

import os
import sys

try:
    import win32com.client
except ImportError:
    print(
        "Falta a biblioteca pywin32 para criar o atalho.\n"
        "Rode primeiro:  pip install pywin32\n"
        "Depois rode este script de novo."
    )
    sys.exit(1)

PASTA = os.path.dirname(os.path.abspath(__file__))
SCRIPT_ALVO = os.path.join(PASTA, "ethos_ai_gui.py")
ICONE = os.path.join(PASTA, "ethos_icone.ico")


def descobrir_area_de_trabalho():
    """Pergunta ao próprio Windows onde fica a área de trabalho. Isso cobre
    o caso de o OneDrive ter movido a pasta (ex.: ...\\OneDrive\\Desktop),
    em que C:\\Users\\<nome>\\Desktop não existe."""
    try:
        import winreg
        chave = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        )
        valor, _ = winreg.QueryValueEx(chave, "Desktop")
        caminho = os.path.expandvars(valor)
        if os.path.isdir(caminho):
            return caminho
    except Exception:
        pass
    # plano B: procura nos dois lugares mais comuns
    casa = os.path.expanduser("~")
    for candidato in (os.path.join(casa, "Desktop"),
                      os.path.join(casa, "OneDrive", "Desktop")):
        if os.path.isdir(candidato):
            return candidato
    return None


AREA_TRABALHO = descobrir_area_de_trabalho()
if AREA_TRABALHO is None:
    print("Não consegui encontrar a pasta da área de trabalho.")
    sys.exit(1)
ATALHO = os.path.join(AREA_TRABALHO, "Ethos AI.lnk")
print(f"Criando atalho em: {ATALHO}")

if not os.path.exists(SCRIPT_ALVO):
    print(f"Não encontrei {SCRIPT_ALVO}. Coloque este script na mesma pasta do ethos_ai_gui.py.")
    sys.exit(1)

if not os.path.exists(ICONE):
    print(f"Aviso: não encontrei {ICONE}. O atalho será criado sem ícone customizado.")

shell = win32com.client.Dispatch("WScript.Shell")
atalho = shell.CreateShortCut(ATALHO)
# pythonw.exe (em vez de python.exe) abre sem a janela preta de terminal atrás
pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
atalho.Targetpath = pythonw if os.path.exists(pythonw) else sys.executable
atalho.Arguments = f'"{SCRIPT_ALVO}"'
atalho.WorkingDirectory = PASTA
if os.path.exists(ICONE):
    atalho.IconLocation = ICONE
atalho.Description = "Abrir a Ethos AI"
atalho.save()

print(f"Atalho criado em: {ATALHO}")
print("Dê duplo clique nele na área de trabalho para abrir a Ethos AI.")
