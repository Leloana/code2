import grpc
from concurrent import futures
import re

import guiche_info_pb2
import guiche_info_pb2_grpc
from monitorar_retorno_terminais import monitorar_terminais
import threading

# Mapeamento terminal → endereço
TERMINAL_PORTS = {
    'Terminal 1': 'localhost:50151',
    'Terminal 2': 'localhost:50152',
    'Terminal 3': 'localhost:50153',
}

class InfoServicer(guiche_info_pb2_grpc.InformationServicer):
    def GetTerminalOnLine(self, request, context):
        state = {}

        try:
            with open('heartbeat.txt', encoding='utf-8') as f:
                print(">> [INFO] Lendo status do heartbeat.txt")
                for line in f:
                    line = line.strip()
                    m = re.match(r'^(Terminal \d+)\s+está\s+(ativo|inativo),', line)
                    if m:
                        tid, st = m.groups()
                        tid = tid.strip()
                        st = st.strip()
                        state[tid] = st
                        print(f"   - Encontrado: {tid} está {st}")
        except FileNotFoundError:
            print("[ERRO] Arquivo heartbeat.txt não encontrado")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Arquivo heartbeat.txt não encontrado")
            return guiche_info_pb2.InfoReply()

        for tid in TERMINAL_PORTS:
            if state.get(tid) == 'ativo':
                print(f">> [INFO] Escolhido: {tid} → {TERMINAL_PORTS[tid]}")
                return guiche_info_pb2.InfoReply(message=TERMINAL_PORTS[tid])

        print(">> [AVISO] Nenhum terminal ativo disponível")
        context.set_code(grpc.StatusCode.UNAVAILABLE)
        context.set_details('Nenhum terminal ativo')
        return guiche_info_pb2.InfoReply()

def serve():
    threading.Thread(target=monitorar_terminais, daemon=True).start()
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    guiche_info_pb2_grpc.add_InformationServicer_to_server(InfoServicer(), server)
    server.add_insecure_port('[::]:50051')
    print("Guichê de Informações iniciado na porta 50051")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
