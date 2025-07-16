import grpc
from concurrent import futures
import threading
from google.protobuf import empty_pb2
import terminal_pb2_grpc
import terminal_pb2
import guiche_info_pb2
import guiche_info_pb2_grpc
import heartbeat_pb2_grpc
import heartbeat_pb2

# Mapeamento terminal → endereço
TERMINAL_PORTS = {
    'Terminal 1': 'localhost:50151',
    'Terminal 2': 'localhost:50152',
    'Terminal 3': 'localhost:50153',
    'Terminal 4': 'localhost:50154',
    'Terminal 5': 'localhost:50155'
}

classes_disponiveis = ["Executivos", "Minivan", "Intermediarios", "SUV", "Economicos"]

# Estado atual do sistema
estado_global = {
    "ativos": set(),
    "classe_para_terminal": {},
}

from terminal_common import modelos

# Estoque centralizado de backup
estoque_backup = {
    classe: modelos[classe][:]
    for classe in classes_disponiveis
}



filas = {classe: [] for classe in classes_disponiveis}

# ==================== FUNÇÕES DE DISTRIBUIÇÃO ====================

def atualizar_terminais_ativos():
    try:
        with grpc.insecure_channel("localhost:50053") as canal:
            stub = heartbeat_pb2_grpc.HeartbeatStub(canal)
            resposta = stub.ListarServicosAtivos(empty_pb2.Empty())
            estado_global["ativos"] = set(resposta.servicos)
            return resposta.servicos
    except Exception as e:
        print(f"[ERRO] Falha ao consultar heartbeat: {e}")
        return []

def balancear_classes_para_terminal(terminal_religado):
    if terminal_religado not in TERMINAL_PORTS:
        return

    # Só considera terminais válidos (com porta mapeada)
    ativos_validos = [t for t in estado_global["ativos"] if t in TERMINAL_PORTS]

    contagem = {
        t: sum(1 for c in estado_global["classe_para_terminal"].values() if c == t)
        for t in ativos_validos
    }

    mais_sobrecarregado = max(contagem, key=contagem.get, default=None)

    if not mais_sobrecarregado or contagem[mais_sobrecarregado] <= 1:
        print(f"[BALANCEAMENTO] Nenhuma classe transferida para {terminal_religado}")
        return

    for classe, responsavel in estado_global["classe_para_terminal"].items():
        if responsavel == mais_sobrecarregado:
            estado_global["classe_para_terminal"][classe] = terminal_religado
            print(f"[BALANCEAMENTO] Classe '{classe}' movida de {mais_sobrecarregado} para {terminal_religado}")

            try:
                # Notificar terminal que cedeu a classe
                with grpc.insecure_channel(TERMINAL_PORTS[mais_sobrecarregado]) as canal:
                    stub = terminal_pb2_grpc.TerminalStub(canal)
                    stub.RemoverClasse(terminal_pb2.ClasseTransferida(classe=classe))
                    print(f"[INFO] {mais_sobrecarregado} removeu a classe '{classe}'")
            except Exception as e:
                print(f"[ERRO] Falha ao notificar {mais_sobrecarregado} para remover classe: {e}")

            try:
                # Notificar terminal que recebeu a classe
                with grpc.insecure_channel(TERMINAL_PORTS[terminal_religado]) as canal:
                    stub = terminal_pb2_grpc.TerminalStub(canal)
                    stub.AssumirNovaClasse(terminal_pb2.ClasseTransferida(classe=classe))
                    print(f"[INFO] {terminal_religado} assumiu e atualizou estoque para classe '{classe}'")
            except Exception as e:
                print(f"[ERRO] Falha ao notificar {terminal_religado} para assumir classe: {e}")

            break
    
    print(estado_global)
    
lock_estado = threading.Lock()

def terminal_inativo(nome_terminal):
    estado_global["ativos"].discard(nome_terminal)
    classes_afetadas = [
        classe for classe, t in estado_global["classe_para_terminal"].items()
        if t == nome_terminal
    ]
    for classe in classes_afetadas:
        print(f"[INFO] Classe {classe} liberada (era do {nome_terminal})")
        del estado_global["classe_para_terminal"][classe]

def monitorar_terminais():
    print("[INFO] Monitorando terminais via heartbeat...")
    ativos_anteriores = estado_global["ativos"].copy()  # <- SALVAR antes do loop
    while True:
        ativos_atuais = set(atualizar_terminais_ativos())

        for terminal in ativos_anteriores - ativos_atuais:
            print(f"[ALERTA] {terminal} desligado")
            terminal_inativo(terminal)

        for terminal in ativos_atuais - ativos_anteriores:
            print(f"[INFO] {terminal} ligado")
            balancear_classes_para_terminal(terminal)

        estado_global["ativos"] = ativos_atuais
        ativos_anteriores = ativos_atuais.copy()  # <- atualizar para próxima iteração

        import time
        time.sleep(5)


# ==================== SERVIÇO gRPC ====================

class InfoServicer(guiche_info_pb2_grpc.InformationServicer):
    def GetTerminalOnLine(self, request, context):
        atualizar_terminais_ativos()
        for tid in TERMINAL_PORTS:
            if tid in estado_global["ativos"]:
                return guiche_info_pb2.InfoReply(message=TERMINAL_PORTS[tid])
        context.set_code(grpc.StatusCode.UNAVAILABLE)
        context.set_details("Nenhum terminal ativo")
        return guiche_info_pb2.InfoReply()

    def AdicionarNaFila(self, request, context):
        cliente = {
            "id": request.id,
            "ip": request.ip,
            "porta": request.porta,
            "classe": request.classe
        }
        if request.classe not in filas:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f"Classe '{request.classe}' inválida.")
            return guiche_info_pb2.Confirmacao(status="Erro")

        filas[request.classe].append(cliente)
        print(f">> Cliente adicionado à fila '{request.classe}': {cliente}")
        return guiche_info_pb2.Confirmacao(status="OK")

    def ObterProximoCliente(self, request, context):
        classe = request.classe
        if classe not in filas or not filas[classe]:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Fila vazia")
            return guiche_info_pb2.ClienteFilaInfo()
        cliente = filas[classe].pop(0)
        return guiche_info_pb2.ClienteFilaInfo(**cliente)

    def AssumirClasse(self, request, context):
        classe = request.classe
        terminal = request.nome_terminal
        print(f"[INFO] Classe {classe} foi assumida por {terminal} via chamada direta")
        estado_global["classe_para_terminal"][classe] = terminal
        print(estado_global)
        return guiche_info_pb2.Confirmacao(status="OK")
    
    def RegistrarTransacao(self, request, context):
        classe = request.classe
        veiculo = request.veiculo
        status = request.status

        if status == "CONCLUIDO" and veiculo:
            if classe in estoque_backup and veiculo in estoque_backup[classe]:
                estoque_backup[classe].remove(veiculo)
                print(f"[BACKUP] Veículo '{veiculo}' removido do estoque da classe '{classe}'")
        return guiche_info_pb2.Confirmacao(status="OK")

    def ObterEstoqueAtual(self, request, context):
        classe = request.classe
        if classe not in estoque_backup:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Classe não encontrada")
            return guiche_info_pb2.EstoqueClasse()
        
        return guiche_info_pb2.EstoqueClasse(modelos=estoque_backup[classe])


    
    def ObterResponsavelClasse(self, request, context):
        terminal = estado_global["classe_para_terminal"].get(request.classe, "")
        return guiche_info_pb2.TerminalResponsavel(terminal=terminal)
    
    def GetClasseLivre(self, request, context):
        for classe in classes_disponiveis:
            if classe not in estado_global["classe_para_terminal"]:
                print(f"[INFO] Classe livre identificada: {classe}")
                return guiche_info_pb2.ClasseLivre(classe=classe)
        
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details("Nenhuma classe livre no momento.")
        return guiche_info_pb2.ClasseLivre()
    
# ==================== START ====================

def serve():
    threading.Thread(target=monitorar_terminais, daemon=True).start()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    guiche_info_pb2_grpc.add_InformationServicer_to_server(InfoServicer(), server)
    server.add_insecure_port('[::]:50051')
    print(">>> Guichê de Informações iniciado na porta 50051")
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
