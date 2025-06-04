import os

def limpar_log_heartbeat():
    caminho = "heartbeat.txt"
    if os.path.exists(caminho):
        with open(caminho, "w", encoding="utf-8") as f:
            f.truncate(0)

def limpar_log_backup():
    caminho = "Backup.txt"
    if os.path.exists(caminho):
        with open(caminho, "w", encoding="utf-8") as f:
            f.truncate(0)

def limpar_logs_clientes():
    diretorio = "clientes_log"
    if os.path.isdir(diretorio):
        for arquivo in os.listdir(diretorio):
            caminho = os.path.join(diretorio, arquivo)
            if os.path.isfile(caminho) and arquivo.endswith(".txt"):
                with open(caminho, "w", encoding="utf-8") as f:
                    f.truncate(0)

def limpar_logs_terminais():
    diretorio = "terminal_log"
    if os.path.isdir(diretorio):
        for arquivo in os.listdir(diretorio):
            caminho = os.path.join(diretorio, arquivo)
            if os.path.isfile(caminho) and arquivo.endswith(".txt"):
                with open(caminho, "w", encoding="utf-8") as f:
                    f.truncate(0)
