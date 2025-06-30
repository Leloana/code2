import grpc
import guiche_info_pb2
import guiche_info_pb2_grpc

from limpar_logs import limpar_logs_clientes,limpar_logs_terminais

import terminal_pb2
import terminal_pb2_grpc

import threading
from multiprocessing.pool import ThreadPool
import time
from concurrent import futures

import random
from datetime import datetime

INFO_ADDRESS = 'localhost:50051'

nomes = ["Alice", "Bob", "Charlie", "David", "Eve","Nick", "Ema", "Maria"]


# Implementação do CallbackService (o cliente atua como servidor aqui)
class CallbackServiceServicer(terminal_pb2_grpc.CallbackServiceServicer):
    def ReceiveCallback(self, request, context):
        """
        Implementa o método ReceiveCallback.
        Recebe uma mensagem de callback do servidor principal.
        """
        message_content = request.message_content
        print(f"\nCliente (Servidor Callback): Recebeu callback: '{message_content}'")
        return terminal_pb2.CallbackResponse(status="Callback Recebido OK")




# Função para iniciar o servidor gRPC do cliente em um thread separado
def start_client_as_server(port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1)) # Apenas 1 worker para este exemplo
    terminal_pb2_grpc.add_CallbackServiceServicer_to_server(CallbackServiceServicer(), server)
    server.add_insecure_port(f'[::]:{port}')
    print(f"Cliente (Servidor Callback) iniciado na porta {port}...")
    server.start()
    # Mantém o servidor em execução até que o thread seja interrompido
    try:
        server.wait_for_termination()
    except Exception as e:
        print(f"Cliente (Servidor Callback) interrompido: {e}")

def log_cliente(nome, mensagem):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(f"clientes_log/cliente_{nome}.txt", "a", encoding="utf-8") as f:
        f.write(f"{mensagem} em [{timestamp}]\n")

def cliente(classe: str, ind: int, i: int):
    classe = classe.strip()
    IP = 'localhost'
    if i < 10:
        Porta = '4000' + str(i)
    elif i < 100:
        Porta = '400' + str(i)
    elif i < 1000:
        Porta = '40' + str(i)

    nome_cliente = nomes[ind]

    server_thread = threading.Thread(target=start_client_as_server, args=(Porta,), daemon=True)
    server_thread.start()
    time.sleep(1)

    try:
        log_cliente(nome_cliente, f"Requisição enviada ao guichê de informações")
        with grpc.insecure_channel(INFO_ADDRESS) as info:
            stub_info = guiche_info_pb2_grpc.InformationStub(info)
            response = stub_info.GetTerminalOnLine(guiche_info_pb2.Empty())
            log_cliente(nome_cliente, f"Resposta recebida do guichê: terminal disponível: {response.message}")

        if not response.message:
            print(f"[AVISO] {nome_cliente}: nenhum terminal disponível no momento.")
            return

        log_cliente(nome_cliente, f"Requisição enviada ao terminal {response.message} para classe {classe} ")
        
        tentativas = 3
        espera = 2 
        for tentativa in range(tentativas):
            try:
                with grpc.insecure_channel(response.message) as channel:
                    stub_terminal = terminal_pb2_grpc.TerminalStub(channel)

                    request = terminal_pb2.RentCarRequest(
                        ID_cliente=nome_cliente,
                        IP_cliente=IP,
                        Porta_cliente=Porta,
                        Classe_veiculo=classe
                    )
                    response = stub_terminal.RentACar(request)

                    if response.status == "CONCLUIDO":
                        veiculo_nome = response.message
                        log_cliente(nome_cliente, f"Resposta recebida de {response.message}: CONCLUIDO {veiculo_nome}")

                        tempo_uso = random.randint(2, 5)
                        time.sleep(tempo_uso)

                        try:
                            with grpc.insecure_channel(INFO_ADDRESS) as info:
                                stub_info = guiche_info_pb2_grpc.InformationStub(info)
                                resposta_info = stub_info.GetTerminalOnLine(guiche_info_pb2.InfoRequest(name=classe))
                                terminal_para_devolver = resposta_info.message
                        
                        except grpc.RpcError as e:
                            print(f"[AVISO] {nome_cliente}: falha ao obter terminal para devolução - {e.details()}")
                            return

                        if not terminal_para_devolver:
                            print(f"[AVISO] {nome_cliente}: nenhum terminal disponível para devolução.")
                            return

                        try:
                            with grpc.insecure_channel(terminal_para_devolver) as canal:
                                stub_terminal = terminal_pb2_grpc.TerminalStub(canal)
                                retorno = stub_terminal.ReturnACar(terminal_pb2.ReturnCarRequest(
                                    ID_cliente=nome_cliente,
                                    Nome_veiculo=veiculo_nome,
                                    Classe_veiculo=classe
                                ))
                        except grpc.RpcError as e:
                            print(f"[AVISO] {nome_cliente}: erro ao devolver veículo - {e.details()}")
                            return

                        break

                    else:
                        log_cliente(nome_cliente, f"Resposta recebida de {response.message}: PENDENTE {classe}")
            except grpc.RpcError as e:
                print(f"[AVISO] {nome_cliente}: tentativa {tentativa} falhou")
                if tentativa < tentativas - 1:
                    time.sleep(espera)
                else:
                    print(f"[AVISO] {nome_cliente}: terminal redirecionado está indisponível")
                    log_cliente(nome_cliente, f"terminal redirecionado está indisponível: PENDENTE {classe}")

    except grpc.RpcError as e:
        print(f"[ERRO] {nome_cliente}: Erro gRPC inesperado: {e.code()} - {e.details()}")


def main():
    num_threads = 5

    lines = []
    try:
        with open('carros_solicitados.txt', 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Erro: O arquivo 'carros_solicitados.txt' não foi encontrado.")
        return
    except Exception as e:
        print(f"Erro ao ler o arquivo 'carros_solicitados.txt': {e}")
        return

    if not lines:
        print("Atenção: O arquivo 'carros_solicitados.txt' está vazio ou não contém classes válidas.")
        return


    f = open('carros_solicitados.txt', 'r')
    lines = f.readlines()



    print(f"\nProcessando {len(lines)} requisições com até {num_threads} threads simultâneas.")

    # Change: Use ThreadPool from multiprocessing.pool
    # 'processes' argument is used for ThreadPool, not 'max_workers'
    with ThreadPool(processes=num_threads) as pool:
        # Change: Use apply_async and store AsyncResult objects
        client_results = [pool.apply_async(cliente, (lines[i], i % 8, i)) for i in range(len(lines))]
        for i, result_async in enumerate(client_results):
                try:
                    # .get() will block until the result is ready and re-raise exceptions
                    result = result_async.get()
                    #print(f"Resultado da requisição {i}: {result}")
                except Exception as exc:
                    print(f"Requisição {i} gerou uma exceção ao obter o resultado: {exc}")

if __name__ == '__main__':
    limpar_logs_clientes()
    limpar_logs_terminais()
    main()
'''
os clientes utilizam portas entre:
40000 a 50000
'''

