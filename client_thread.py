import grpc
import guiche_info_pb2
import guiche_info_pb2_grpc
import threading

INFO_ADDRESS = 'localhost:50051'

def fazer_chamada_grpc(classe, indice):
    try:
        with grpc.insecure_channel(INFO_ADDRESS) as channel:
            stub = guiche_info_pb2_grpc.InformationStub(channel)
            response = stub.GetTerminalOnLine(guiche_info_pb2.InfoRequest(name=classe.strip()))
            print(f"[Thread-{indice}] Terminal disponível para classe {classe.strip()}: {response.message}")
    except grpc.RpcError as e:
        print(f"[Thread-{indice}] Erro de RPC: {e.code()} - {e.details()}")

def main():
    num_threads = 5
    threads = []

    try:
        with open("carros_solicitados.txt") as f:
            linhas = [linha.strip() for linha in f if linha.strip()]
    except FileNotFoundError:
        print("Arquivo 'carros_solicitados.txt' não encontrado.")
        return

    print(f"Processando {len(linhas)} requisições com até {num_threads} threads simultâneas.\n")

    for i, classe in enumerate(linhas[:num_threads]):
        thread = threading.Thread(target=fazer_chamada_grpc, args=(classe, i))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    print("Todas as threads terminaram.")

if __name__ == '__main__':
    main()
