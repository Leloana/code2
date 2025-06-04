import time
import re
import grpc
from fila_global import remover_primeiro_da_fila, obter_fila
import terminal_pb2
import terminal_pb2_grpc

mapa_classes = {
    "Executivos": "localhost:50151",
    "Minivan": "localhost:50151",
    "Intermediarios": "localhost:50152",
    "SUV": "localhost:50152",
    "Economicos": "localhost:50153"
}

estado_anterior = {}

def terminal_esta_ativo(linha):
    m = re.match(r'(Terminal \d+) está (ativo|inativo),', linha)
    if m:
        terminal, status = m.groups()
        return terminal, status == 'ativo'
    return None, False

def despachar_clientes(classe):
    terminal_destino = mapa_classes[classe]
    fila = obter_fila(classe)

    while fila:
        cliente = remover_primeiro_da_fila(classe)
        try:
            with grpc.insecure_channel(terminal_destino) as canal:
                stub = terminal_pb2_grpc.TerminalStub(canal)
                response = stub.RentACar(terminal_pb2.RentCarRequest(
                    ID_cliente=cliente["id"],
                    IP_cliente=cliente["ip"],
                    Porta_cliente=cliente["porta"],
                    Classe_veiculo=cliente["classe"]
                ))
                print(f"[DISPATCH] Cliente {cliente['id']} redirecionado com status: {response.status}")
        except grpc.RpcError as e:
            print(f"[DISPATCH] Falha ao redirecionar cliente {cliente['id']}: {e.details()}")
            # Reinsere na fila
            from fila_global import adicionar_na_fila
            adicionar_na_fila(classe, cliente)
            break

def monitorar_terminais():
    global estado_anterior

    while True:
        time.sleep(3)  # Verifica a cada 3 segundos
        try:
            with open("heartbeat.txt") as f:
                linhas = f.readlines()
        except FileNotFoundError:
            continue

        for linha in linhas:
            terminal, ativo = terminal_esta_ativo(linha)
            if not terminal:
                continue

            # Detecta reativação
            if terminal not in estado_anterior or (not estado_anterior[terminal] and ativo):
                print(f"[INFO] {terminal} voltou a ficar ativo.")
                # Despacha clientes para cada classe atendida por esse terminal
                for classe, destino in mapa_classes.items():
                    if destino.endswith(terminal[-2:]):  # Ex: '50153' para Terminal 3
                        despachar_clientes(classe)

            estado_anterior[terminal] = ativo
