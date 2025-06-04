filas_globais = {
    "Economicos": [],
    "Minivan": [],
    "Intermediarios": [],
    "SUV": [],
    "Executivos": []
}

def adicionar_na_fila(classe, cliente_info):
    filas_globais.setdefault(classe, []).append(cliente_info)

def remover_primeiro_da_fila(classe):
    if filas_globais.get(classe):
        return filas_globais[classe].pop(0)
    return None

def obter_fila(classe):
    return filas_globais.get(classe, [])
