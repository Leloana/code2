import os
import threading
import grpc
from concurrent import futures

from terminal_common import (
    build_terminal_servicer,
    monitorar_falhas
)
from heartbeat_server import enviar_heartbeat
import terminal_pb2_grpc

def main():
    nome_terminal = "Terminal 3"

    os.makedirs("terminal_log", exist_ok=True)

    estoque = { }

    threading.Thread(target=monitorar_falhas, args=(nome_terminal, estoque), daemon=True).start()
    threading.Thread(target=enviar_heartbeat, args=(nome_terminal,), daemon=True).start()

    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servico = build_terminal_servicer(3, estoque)
    terminal_pb2_grpc.add_TerminalServicer_to_server(servico, grpc_server)
    grpc_server.add_insecure_port("localhost:50153")

    print(">>> Terminal 3 iniciado")
    grpc_server.start()
    grpc_server.wait_for_termination()

if __name__ == "__main__":
    main()
