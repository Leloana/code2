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
# Mapeamento terminal → endereço
PORTAS_TERMINAIS = {
    "Terminal 1": "50151",
    "Terminal 2": "50152",
    "Terminal 3": "50153",
    "Terminal 4": "50154",
    "Terminal 5": "50155"
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
        
def adicionar_cliente_na_fila(cliente_id, ip, porta, classe):
    try:
        with grpc.insecure_channel("localhost:50051") as canal:
            stub = guiche_info_pb2_grpc.InformationStub(canal)
            stub.AdicionarNaFila(guiche_info_pb2.ClienteNaFila(
                id=cliente_id,
                ip=ip,
                porta=porta,
                classe=classe
            ))
            print(f"[INFO] Cliente {cliente_id} reinserido na fila da classe {classe}")
    except Exception as e:
        print(f"[ERRO] Falha ao reinserir cliente {cliente_id} na fila: {e}")


def eleger_terminal(ativos: set[str]) -> str | None:
    try:
        terminais = [t for t in ativos if t.startswith("Terminal")]
        if not terminais:
            return None

        vencedor = max(terminais, key=lambda t: int(t.split()[-1]))
        print(f"[ELEIÇÃO] Terminal eleito: {vencedor}")
        return vencedor
    except Exception as e:
        print(f"[ERRO ELEIÇÃO] Falha ao eleger terminal: {e}")
        return None

def assumir_classe(classe: str, nome_terminal: str):
    try:
        with grpc.insecure_channel("localhost:50051") as canal:
            stub = guiche_info_pb2_grpc.InformationStub(canal)
            stub.AssumirClasse(
                guiche_info_pb2.ClasseFila(
                    classe=classe,
                    nome_terminal=nome_terminal
                )
            )
            log_terminal(nome_terminal.split()[-1], f"[ASSUMIU CLASSE] {classe}")
            print(f"[{nome_terminal}] Assumiu a classe '{classe}' com sucesso.")
    except grpc.RpcError as e:
        print(f"[{nome_terminal}] Erro ao assumir classe '{classe}': {e.details()}")

def notificar_terminal_eleito(classe: str, terminal_destino: str):
    try:
        porta = PORTAS_TERMINAIS.get(terminal_destino)
        if not porta:
            print(f"[ERRO] Porta do terminal '{terminal_destino}' não encontrada.")
            return

        with grpc.insecure_channel(f"localhost:{porta}") as canal:
            stub = terminal_pb2_grpc.TerminalStub(canal)
            stub.ReceberClasseViaEleicao(terminal_pb2.ClasseTransferida(classe=classe))
            print(f"[INFO] Notificado {terminal_destino} para puxar classe '{classe}' via eleição.")
    except Exception as e:
        print(f"[ERRO] Falha ao notificar {terminal_destino}: {e}")

def monitorar_falhas(nome_terminal, estoque_local):
    id_este_terminal = int(nome_terminal.split()[-1])
    ativos_anteriores = set()

    while True:
        time.sleep(5)
        try:
            # Consulta heartbeat
            with grpc.insecure_channel("localhost:50053") as canal:
                stub_hb = heartbeat_pb2_grpc.HeartbeatStub(canal)
                resposta = stub_hb.ListarServicosAtivos(empty_pb2.Empty())
                ativos_atuais = set(resposta.servicos)

            # Se for o único ativo, assume todas as classes órfãs
            terminais_ativos = {t for t in ativos_atuais if t.startswith("Terminal")}

# Se este for o único terminal ativo, assume todas as classes
            if terminais_ativos == {nome_terminal}:
                print(f"[{nome_terminal}] Único terminal ativo. Assumindo todas as classes.")
                with grpc.insecure_channel("localhost:50051") as canal_info:
                    stub_info = guiche_info_pb2_grpc.InformationStub(canal_info)
                    for classe in classes_disponiveis:
                        try:
                            resposta = stub_info.ObterResponsavelClasse(
                                guiche_info_pb2.ClasseFila(classe=classe)
                            )
                            if resposta.terminal != nome_terminal:
                                assumir_classe(classe, nome_terminal)
                                if classe not in estoque_local:
                                        estoque_local[classe] = modelos[classe][:]
                                        log_terminal(id_este_terminal, f"[RECEPÇÃO NOVA CLASSE] Agora responsável por {classe}")
                                        log_terminal(id_este_terminal, f"[ATUALIZAÇÃO DE ESTOQUE] Estoque Atual: {estoque_local}")
                                        print(f"{classe} classe Adicionada :{estoque_local}")
                        except grpc.RpcError as e:
                            print(f"[{nome_terminal}] Erro ao assumir classe '{classe}': {e.details()}")
                ativos_anteriores = ativos_atuais
                continue  # Volta para próxima iteração sem fazer eleição

            # Detecta terminais que caíram
            terminais_caidos = {t for t in (ativos_anteriores - ativos_atuais) if t != nome_terminal}

            for terminal_caiu in terminais_caidos:
                print(f"[{nome_terminal}] Detectado terminal inativo: {terminal_caiu}")

                try:
                    with grpc.insecure_channel("localhost:50051") as canal_info:
                        stub_info = guiche_info_pb2_grpc.InformationStub(canal_info)

                        # Lista de classes que estavam com o terminal caído
                        classes_a_transferir = []

                        for classe in classes_disponiveis:
                            try:
                                resposta = stub_info.ObterResponsavelClasse(
                                    guiche_info_pb2.ClasseFila(classe=classe)
                                )
                                if resposta.terminal == terminal_caiu:
                                    print(f"[{nome_terminal}] Classe '{classe}' era de {terminal_caiu}")
                                    classes_a_transferir.append(classe)
                            except grpc.RpcError as e:
                                print(f"[{nome_terminal}] Erro ao consultar classe '{classe}': {e.details()}")

                        # Se houver classes para transferir, realiza uma única eleição
                        if classes_a_transferir:
                            print(f"[ELEICAO][{nome_terminal}] Iniciando eleição para classes de {terminal_caiu}")
                            vencedor = eleger_terminal(ativos_atuais)
                            print(f"[ELEICAO][{vencedor}] foi eleito para assumir as classes de {terminal_caiu}")

                            for classe in classes_a_transferir:
                                if vencedor == nome_terminal:
                                    # Sempre atualiza o InfoServer
                                    assumir_classe(classe, nome_terminal)

                                    # Só atualiza estoque se ainda não tiver
                                    if classe not in estoque_local:
                                        estoque_local[classe] = modelos[classe][:]
                                        log_terminal(id_este_terminal, f"[RECEPÇÃO NOVA CLASSE] Agora responsável por {classe}")
                                        log_terminal(id_este_terminal, f"[ATUALIZAÇÃO DE ESTOQUE] Estoque Atual: {estoque_local}")
                                        print(f"{classe} classe Adicionada :{estoque_local}")
                                else:
                                    notificar_terminal_eleito(classe, vencedor)

                except Exception as e:
                    print(f"[{nome_terminal}] Erro ao processar queda de {terminal_caiu}: {e}")


            ativos_anteriores = ativos_atuais

        except Exception as e:
            print(f"[{nome_terminal}] Erro no monitoramento de falhas: {e}")

def build_terminal_servicer(terminal_id, estoque):
    class TerminalServicer(terminal_pb2_grpc.TerminalServicer):
        def __init__(self):
            self.terminal_id = terminal_id
            self.estoque = estoque
            
        def RemoverClasse(self, request, context):
            classe = request.classe
            if classe in estoque:
                del estoque[classe]
                log_terminal(terminal_id, f"[SAÍDA DE CLASSE] Deixou de ser responsável por {classe}")
                print(f"Classe {classe} Removida :{estoque}")
            return terminal_pb2.Confirmando(status="OK")
        
        def AssumirNovaClasse(self, request, context):
            classe = request.classe
            if classe not in estoque:
                with grpc.insecure_channel("localhost:50051") as canal:
                    stub_info = guiche_info_pb2_grpc.InformationStub(canal)
                    resposta = stub_info.ObterEstoqueAtual(guiche_info_pb2.ClasseFila(classe=classe))
                    estoque[classe] = list(resposta.modelos)

                log_terminal(terminal_id, f"[RECEPÇÃO NOVA CLASSE] Agora responsável por {classe}")
                log_terminal(terminal_id, f"[ATUALIZAÇÃO DE ESTOQUE] Estoque Atual: {estoque}")  
                print(f"{classe} classe Adicionada :{estoque}")
            return terminal_pb2.Confirmando(status="OK")
        
        def ReceberClasseViaEleicao(self, request, context):
            classe = request.classe
            terminal_nome = f"Terminal {self.terminal_id}"

            with grpc.insecure_channel("localhost:50051") as canal:
                stub_info = guiche_info_pb2_grpc.InformationStub(canal)
                try:
                    resposta = stub_info.ObterResponsavelClasse(
                        guiche_info_pb2.ClasseFila(classe=classe)
                    )
                    if resposta.terminal == terminal_nome:
                        print(f"[{terminal_nome}] Já sou responsável pela classe '{classe}', ignorando.")
                    else:
                        print(f"[{terminal_nome}] Assumindo classe '{classe}' por notificação externa.")
                        stub_info.AssumirClasse(
                            guiche_info_pb2.ClasseFila(
                                classe=classe,
                                nome_terminal=terminal_nome
                            )
                        )
                        if classe not in self.estoque:
                            with grpc.insecure_channel("localhost:50051") as canal:
                                stub_info = guiche_info_pb2_grpc.InformationStub(canal)
                                resposta = stub_info.ObterEstoqueAtual(guiche_info_pb2.ClasseFila(classe=classe))
                                self.estoque[classe] = list(resposta.modelos)

                            log_terminal(self.terminal_id, f"[RECEPÇÃO NOVA CLASSE] Agora responsável por {classe}")
                            log_terminal(self.terminal_id, f"[ATUALIZAÇÃO DE ESTOQUE] Estoque Atual: {self.estoque}")
                            print(f"[{terminal_nome}] Classe '{classe}' adicionada ao estoque.")
                except grpc.RpcError as e:
                    print(f"[{terminal_nome}] Erro ao tentar assumir classe '{classe}': {e.details()}")

            return terminal_pb2.Confirmando(status="OK")

        def RentACar(self, request, context):
            cliente = request.ID_cliente
            classe = request.Classe_veiculo

            with grpc.insecure_channel("localhost:50051") as canal:
                stub_info = guiche_info_pb2_grpc.InformationStub(canal)
                resposta = stub_info.ObterResponsavelClasse(guiche_info_pb2.ClasseFila(classe=classe))
                responsavel = resposta.terminal

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
                    adicionar_cliente_na_fila(cliente,request.IP_cliente,request.Porta_cliente,classe)
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
                        adicionar_cliente_na_fila(cliente,request.IP_cliente,request.Porta_cliente,classe)

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
                try:
                    with grpc.insecure_channel(endereco) as canal:
                        stub_terminal = terminal_pb2_grpc.TerminalStub(canal)
                        return stub_terminal.ReturnACar(request)
                except Exception as e:
                    print(f"[AVISO] {cliente}: erro ao devolver veículo - {e}")
                    return terminal_pb2.ReturnCarResponse(message=False)

            log_terminal(terminal_id, f"Devolução recebida: cliente {cliente} devolveu {veiculo} da classe {classe}")

            with lock:
                estoque.setdefault(classe, []).append(veiculo)

                # REGISTRO NO BACKUP ORIGINAL
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

                # REGISTRO NO INFOSERVER (estoque centralizado)
                try:
                    with grpc.insecure_channel("localhost:50051") as canal:
                        stub_info = guiche_info_pb2_grpc.InformationStub(canal)
                        stub_info.RegistrarTransacao(guiche_info_pb2.RegistroEstoqueRequest(
                            cliente=cliente, classe=classe, veiculo=veiculo, status="DEVOLVIDO"
                        ))
                except Exception as e:
                    print(f"[ERRO INFOSERVER BACKUP] {e}")

                # Tenta callback
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


    
    return TerminalServicer()


