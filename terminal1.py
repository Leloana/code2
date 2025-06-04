from terminal_common import build_terminal_servicer
from heartbeat_server import enviar_heartbeat
import threading
import grpc
import terminal_pb2_grpc
from concurrent import futures

estoque = {
    "Executivos": ["BMW Série 5", "Toyota Corolla Altis Híbrido"],
    "Minivan": ["Chevrolet Spin", "Fiat Doblo", "Nissan Livina","Citroën C4 Picasso","Chevrolet Zafira"]
}
fila_espera = {
    "Executivos": [],
    "Minivan": []
}

def main():
    threading.Thread(target=enviar_heartbeat, args=("Terminal 1",), daemon=True).start()

    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servico = build_terminal_servicer("1", estoque, fila_espera)
    terminal_pb2_grpc.add_TerminalServicer_to_server(servico(), grpc_server)
    grpc_server.add_insecure_port("localhost:50151")
    print(">>> Terminal 1 iniciado")
    grpc_server.start()
    grpc_server.wait_for_termination()

if __name__ == "__main__":
    main()
