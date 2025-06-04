from terminal_common import build_terminal_servicer
from heartbeat_server import enviar_heartbeat
import threading
import grpc
import terminal_pb2_grpc
from concurrent import futures

estoque = {
    "Economicos": ["Chevrolet Onix", "Renault Kwid", "Peugeot 208"]
}

fila_espera = {
    "Economicos": []
}

def main():
    threading.Thread(target=enviar_heartbeat, args=("Terminal 3",), daemon=True).start()

    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servico = build_terminal_servicer("3", estoque, fila_espera)
    terminal_pb2_grpc.add_TerminalServicer_to_server(servico(), grpc_server)
    grpc_server.add_insecure_port("localhost:50153")
    print(">>> Terminal 3 iniciado")
    grpc_server.start()
    grpc_server.wait_for_termination()

if __name__ == "__main__":
    main()