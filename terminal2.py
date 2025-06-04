from terminal_common import build_terminal_servicer
from heartbeat_server import enviar_heartbeat
import threading
import grpc
import terminal_pb2_grpc
from concurrent import futures

estoque = {
    "Intermediarios": ["Honda City", "Fiat Cronos", "Volkswagen Virtus"],
    "SUV": ["Jeep Commander", "Audi Q7", "Lexus RX"]
}

fila_espera = {
    "Intermediarios": [],
    "SUV": []
}

def main():
    threading.Thread(target=enviar_heartbeat, args=("Terminal 2",), daemon=True).start()

    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servico = build_terminal_servicer("2", estoque, fila_espera)
    terminal_pb2_grpc.add_TerminalServicer_to_server(servico(), grpc_server)
    grpc_server.add_insecure_port("localhost:50152")
    print(">>> Terminal 2 iniciado")
    grpc_server.start()
    grpc_server.wait_for_termination()

if __name__ == "__main__":
    main()