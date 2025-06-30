import grpc
from concurrent import futures
import threading
import time
from datetime import datetime
from google.protobuf import empty_pb2
from limpar_logs import limpar_log_heartbeat

import heartbeat_pb2
import heartbeat_pb2_grpc

HEARTBEAT_TIMEOUT = 5  # segundos sem batimento = considerado inativo
log_lock = threading.Lock()
last_signals = {}

# Lista de serviços que esperamos monitorar
servicos_esperados = [
    "Terminal 1",
    "Terminal 2",
    "Terminal 3",
    "Backup"
]

def enviar_heartbeat(servico_nome):
    while True:
        try:
            with grpc.insecure_channel("localhost:50053") as canal:
                stub = heartbeat_pb2_grpc.HeartbeatStub(canal)
                stub.EnviarSinal(heartbeat_pb2.HeartbeatRequest(servico=servico_nome))
        except Exception as e:
            print(f"[ERRO HEARTBEAT] {e}")
        time.sleep(5)

def log_heartbeat(mensagem):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_lock:
        with open("heartbeat.txt", "a", encoding="utf-8") as f:
            f.write(f"{mensagem} em [{timestamp}] \n")

class HeartbeatServicer(heartbeat_pb2_grpc.HeartbeatServicer):
    def EnviarSinal(self, request, context):
        servico = request.servico
        now = time.time()
        last_signals[servico] = now
        # log_heartbeat(f"{servico} está ativo, última mensagem recebida em {datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S')}")
        return empty_pb2.Empty()
    
    def ListarServicosAtivos(self, request, context):
        now = time.time()
        ativos = []
        for servico in servicos_esperados:
            timestamp = last_signals.get(servico, 0)
            if (now - timestamp) <= HEARTBEAT_TIMEOUT:
                ativos.append(servico)
        return heartbeat_pb2.ListaServicos(servicos=ativos)

def monitor_inativos():
    for servico in servicos_esperados:
        last_signals.setdefault(servico, 0)  # evita sobreposição caso já tenha sinal


    while True:
        time.sleep(HEARTBEAT_TIMEOUT)
        now = time.time()

        for servico in servicos_esperados:
            timestamp = last_signals.get(servico, 0)
            ativo = (now - timestamp) <= HEARTBEAT_TIMEOUT

            if ativo:
                log_heartbeat(f"{servico} está ativo, última mensagem recebida")
            elif not ativo:
                if timestamp == 0:
                    log_heartbeat(f"{servico} está inativo, nenhuma mensagem recebida até agora")
                else:
                    log_heartbeat(f"{servico} está inativo, última mensagem recebida")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    heartbeat_pb2_grpc.add_HeartbeatServicer_to_server(HeartbeatServicer(), server)
    server.add_insecure_port("localhost:50053")
    print(">>> Servidor de Heartbeat iniciado na porta 50053")
    server.start()

    threading.Thread(target=monitor_inativos, daemon=True).start()
    server.wait_for_termination()

if __name__ == "__main__":
    limpar_log_heartbeat()
    serve()
