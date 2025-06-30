import grpc
import terminal_pb2
import terminal_pb2_grpc
import backup_pb2
import backup_pb2_grpc
from concurrent import futures
from datetime import datetime
import threading
import guiche_info_pb2
import guiche_info_pb2_grpc
import heartbeat_pb2
import heartbeat_pb2_grpc
from google.protobuf import empty_pb2
import time

PORTAS_TERMINAIS = {
    "Terminal 1": "50151",
    "Terminal 2": "50152",
    "Terminal 3": "50153"
}

modelos = {
    "Executivos": ["BMW Série 5", "Toyota Corolla Altis Híbrido"],
    "Minivan": ["Chevrolet Spin", "Fiat Doblo", "Nissan Livina", "Citroën C4 Picasso", "Chevrolet Zafira"],
    "Intermediarios": ["Honda City", "Fiat Cronos", "Volkswagen Virtus"],
    "SUV": ["Jeep Commander", "Audi Q7", "Lexus RX"],
    "Economicos": ["Chevrolet Onix", "Renault Kwid", "Peugeot 208"]
}

classes_disponiveis = ["Executivos", "Minivan", "Intermediarios", "SUV", "Economicos"]

lock = threading.Lock()

def log_terminal(terminal_id, mensagem):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(f"terminal_log/terminal_{terminal_id}.txt", "a", encoding="utf-8") as f:
        f.write(f"{mensagem} em [{timestamp}]\n")

def obter_proximo_cliente(classe: str):
    with grpc.insecure_channel("localhost:50051") as canal:
        stub = guiche_info_pb2_grpc.InformationStub(canal)
        try:
            resposta = stub.ObterProximoCliente(guiche_info_pb2.ClasseFila(classe=classe))
            return {
                "id": resposta.id,
                "ip": resposta.ip,
                "porta": resposta.porta,
                "classe": resposta.classe
            }
        except grpc.RpcError as e:
            print(f"[{classe}] Nenhum cliente aguardando: {e.details()}")
            return None

def assumir_classe_via_info_server(classe, nome_terminal):
    with grpc.insecure_channel("localhost:50051") as canal:
        stub = guiche_info_pb2_grpc.InformationStub(canal)
        try:
            resposta = stub.AssumirClasse(guiche_info_pb2.ClasseFila(classe=classe, nome_terminal=nome_terminal))
            return resposta.status == "OK"
        except grpc.RpcError as e:
            print(f"[ERRO] Falha ao assumir classe {classe}: {e.details()}")
            return False

def monitorar_falhas(nome_terminal, estoque_local):
    while True:
        time.sleep(5)

        try:
            with grpc.insecure_channel("localhost:50051") as canal:
                stub = guiche_info_pb2_grpc.InformationStub(canal)
                resposta = stub.GetClasseLivre(empty_pb2.Empty())
                classe_livre = resposta.classe
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                # Nenhuma classe livre no momento
                continue
            print(f"[{nome_terminal}] Erro gRPC ao chamar GetClasseLivre: {e.details()}")
            continue
        except Exception as e:
            print(f"[{nome_terminal}] Erro inesperado: {e}")
            continue
        # Tenta assumir a classe
        sucesso = assumir_classe_via_info_server(classe_livre, nome_terminal)
        if sucesso:
            print(f"[{nome_terminal}] Assumiu a classe {classe_livre} via InfoServer")

            if classe_livre not in estoque_local:
                estoque_local[classe_livre] = modelos[classe_livre][:]
                print(f"[{nome_terminal}] Estoque atualizado: {classe_livre} → {estoque_local[classe_livre]}")
        else:
            print(f"[{nome_terminal}] Falhou ao assumir a classe {classe_livre}")



def build_terminal_servicer(terminal_id, estoque):
    class TerminalServicer(terminal_pb2_grpc.TerminalServicer):
        def RentACar(self, request, context):
            cliente = request.ID_cliente
            classe = request.Classe_veiculo

            with grpc.insecure_channel("localhost:50051") as canal:
                stub_info = guiche_info_pb2_grpc.InformationStub(canal)
                resposta = stub_info.ObterResponsavelClasse(guiche_info_pb2.ClasseFila(classe=classe))
                responsavel = resposta.terminal

            print(responsavel)
            if responsavel != f"Terminal {terminal_id}":
                porta = PORTAS_TERMINAIS.get(responsavel)
                endereco = f"localhost:{porta}"
                print(f"[{terminal_id}] Redirecionando para {responsavel} ({endereco}) para classe {classe}")
                try:
                    with grpc.insecure_channel(endereco) as canal:
                        stub_terminal = terminal_pb2_grpc.TerminalStub(canal)
                        return stub_terminal.RentACar(request)
                except Exception as e:
                    print(f"[ERRO REDIRECIONAMENTO] {e}")
                    return terminal_pb2.RentCarResponse(message="Falha na comunicação", status="ERRO")

            if classe in estoque:
                log_terminal(terminal_id, f"Requisição recebida do cliente {cliente} para classe {classe}")
                with lock:
                    if estoque[classe]:
                        veiculo = estoque[classe].pop(0)
                        log_terminal(terminal_id, f"Resposta enviada ao cliente {cliente}: CONCLUIDO {classe} {veiculo}")
                        try:
                            log_terminal(terminal_id, f"Requisição enviada ao servidor de backup {cliente} para classe {classe} {veiculo} CONCLUIDA")
                            with grpc.insecure_channel("localhost:50052") as canal:
                                stub = backup_pb2_grpc.BackupStub(canal)
                                stub.RegistrarTransacao(backup_pb2.BackupRequest(
                                    cliente=cliente, classe=classe, veiculo=veiculo, status="CONCLUIDO"
                                ))
                                log_terminal(terminal_id, f"Resposta recebida do servidor de backup {cliente} {classe} {veiculo} CONCLUIDA")
                        except Exception as e:
                            print(f"[ERRO BACKUP] {e}")
                        return terminal_pb2.RentCarResponse(message=veiculo, status="CONCLUIDO")
                    else:
                        try:
                            with grpc.insecure_channel("localhost:50051") as canal:
                                stub = guiche_info_pb2_grpc.InformationStub(canal)
                                stub.AdicionarNaFila(guiche_info_pb2.ClienteNaFila(
                                    id=cliente,
                                    ip=request.IP_cliente,
                                    porta=request.Porta_cliente,
                                    classe=classe
                                ))
                        except Exception as e:
                            print(f"[ERRO INFO-FILA] Falha ao adicionar {cliente} na fila do InfoServer: {e}")

                        log_terminal(terminal_id, f"Resposta enviada ao cliente {cliente}: PENDENTE {classe}")
                        try:
                            log_terminal(terminal_id, f"Requisição enviada ao servidor de backup {cliente} para classe {classe} PENDENTE")
                            with grpc.insecure_channel("localhost:50052") as canal:
                                stub = backup_pb2_grpc.BackupStub(canal)
                                stub.RegistrarTransacao(backup_pb2.BackupRequest(
                                    cliente=cliente, classe=classe, veiculo="", status="PENDENTE"
                                ))
                                log_terminal(terminal_id, f"Resposta recebida do servidor de backup {cliente} {classe} PENDENTE")
                        except Exception as e:
                            print(f"[ERRO BACKUP] {e}")
                        return terminal_pb2.RentCarResponse(message=classe, status="PENDENTE")

            return terminal_pb2.RentCarResponse(message="Classe não encontrada", status="ERRO")

        def ReturnACar(self, request, context):
            veiculo = request.Nome_veiculo
            classe = request.Classe_veiculo
            cliente = request.ID_cliente

            with grpc.insecure_channel("localhost:50051") as canal:
                stub_info = guiche_info_pb2_grpc.InformationStub(canal)
                resposta = stub_info.ObterResponsavelClasse(guiche_info_pb2.ClasseFila(classe=classe))
                responsavel = resposta.terminal

            if responsavel != f"Terminal {terminal_id}":
                print(f"[{terminal_id}] Redirecionando para {responsavel} para classe {classe}")
                endereco = f"localhost:{PORTAS_TERMINAIS[responsavel]}"
                with grpc.insecure_channel(endereco) as canal:
                    stub_terminal = terminal_pb2_grpc.TerminalStub(canal)
                    return stub_terminal.ReturnACar(request)

            log_terminal(terminal_id, f"Devolução recebida: cliente {cliente} devolveu {veiculo} da classe {classe}")
            with lock:
                estoque.setdefault(classe, []).append(veiculo)
                try:
                    log_terminal(terminal_id, f"Requisição enviada ao servidor de backup {cliente} para classe {classe} {veiculo} DEVOLVIDO")
                    with grpc.insecure_channel("localhost:50052") as canal:
                        stub = backup_pb2_grpc.BackupStub(canal)
                        stub.RegistrarTransacao(backup_pb2.BackupRequest(
                            cliente=cliente, classe=classe, veiculo=veiculo, status="DEVOLVIDO"
                        ))
                        log_terminal(terminal_id, f"Resposta recebida do servidor de backup {cliente} {classe} {veiculo} DEVOLVIDO")
                except Exception as e:
                    print(f"[ERRO BACKUP] {e}")

                proximo = obter_proximo_cliente(classe)
                if proximo:
                    log_terminal(terminal_id, f"Callback enviado ao cliente {proximo['id']} para veículo {veiculo}")
                    try:
                        canal_cb = grpc.insecure_channel(f"{proximo['ip']}:{proximo['porta']}")
                        stub_cb = terminal_pb2_grpc.CallbackServiceStub(canal_cb)
                        stub_cb.ReceiveCallback(terminal_pb2.CallbackMessage(
                            message_content=f"Veículo {veiculo} da classe {classe} está disponível!"
                        ))
                    except Exception as e:
                        print(f"[ERRO CALLBACK] {e}")
            return terminal_pb2.ReturnCarResponse(message=True)
    
    return TerminalServicer
