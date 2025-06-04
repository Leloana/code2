from datetime import datetime
import threading
from concurrent import futures
import grpc
import backup_pb2
import backup_pb2_grpc
from heartbeat_server import enviar_heartbeat
from limpar_logs import limpar_log_backup

PORT = "localhost:50052"

def log_backup(mensagem):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("Backup.txt", "a", encoding="utf-8") as f:
        f.write(f"{mensagem} em [{timestamp}] \n")

class BackupService(backup_pb2_grpc.BackupServicer):
    def RegistrarTransacao(self, request, context):
        status_formatado = (
            "CONCLUIDA" if request.status == "CONCLUIDO"
            else "PENDENTE" if request.status == "PENDENTE"
            else "DEVOLVIDA" if request.status == "DEVOLVIDO"
            else request.status
        )

        log_backup(f"Requisição recebida do terminal para cliente {request.cliente} classe {request.classe} {request.veiculo} {status_formatado}")
        return backup_pb2.BackupResponse(confirmacao="OK")

def server():
    limpar_log_backup()
    threading.Thread(target=enviar_heartbeat, args=("Backup",), daemon=True).start()

    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    backup_pb2_grpc.add_BackupServicer_to_server(BackupService(), servidor)
    servidor.add_insecure_port(PORT)
    print(f"Servidor de Backup ativo em {PORT}")
    servidor.start()
    servidor.wait_for_termination()

if __name__ == '__main__':
    server()
