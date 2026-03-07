import os
import time
import json
import requests

TOKEN_API = "ZaAmsMtiTSf3nxpuTJuZ2zkgOmVMhr"
HEADERS = {
    "Authorization": f"Bearer {TOKEN_API}",
    "Content-Type": "application/json"
}

ARQUIVO_CACHE_MESTRE = "cache_alunos_todos_diarios.json"
ARQUIVO_DIARIOS = "diarios_com_turmas_2026.json"

def atualizar_banco_local_completo():
    """
    Função de otimização máxima: Baixa a base de alunos uma vez, 
    varre todos os diários e gera um arquivo único de cache.
    """
    print("\n[Aulio Data] Iniciando sincronização em massa de TODOS os diários...")
    
    # 1. Carrega a lista de diários que você já tem
    try:
        with open(ARQUIVO_DIARIOS, 'r', encoding='utf-8') as f:
            lista_diarios = json.load(f)
    except FileNotFoundError:
        print(f"[Erro] Não encontrei o arquivo {ARQUIVO_DIARIOS} na pasta.")
        exit()

    # 2. Puxa o bancão de nomes UMA ÚNICA VEZ (Otimização Monstra!)
    print("[Aulio Data] Baixando a base mestre de alunos (isso pode demorar uns segundos)...")
    url_alunos = "https://siga.activesoft.com.br/api/v0/lista_alunos/"
    resposta_alunos = requests.get(url_alunos, headers=HEADERS)
    todos_alunos = resposta_alunos.json()
    
    # Blindagem do envelope do Django
    if isinstance(todos_alunos, dict):
        if "results" in todos_alunos: todos_alunos = todos_alunos["results"]
        elif "data" in todos_alunos: todos_alunos = todos_alunos["data"]

    # Cria o Dicionário Rápido (Matrícula -> Nome)
    dicionario_nomes = {}
    for aluno in todos_alunos:
        mat = str(aluno.get("matricula"))
        dicionario_nomes[mat] = aluno.get("nome")
        
    # 3. Dicionário Mestre que vai guardar tudo
    dados_consolidados = {}
    
    print("[Aulio Data] Cruzando os dados por diário...")
    # 4. Loop por todos os diários
    for diario_info in lista_diarios:
        id_diario = diario_info["id_diario"]
        nome_disc = diario_info.get("nome_disciplina", "Desconhecida")
        print(f"  -> Processando Diário {id_diario} ({nome_disc})...")
        
        url_frequencia = f"https://siga.activesoft.com.br/api/v0/diario_frequencia/?diario={id_diario}"
        resposta_freq = requests.get(url_frequencia, headers=HEADERS)
        
        # --- BLINDAGEM 1: Verifica se o servidor devolveu erro (Ex: 500 ou 404) ---
        if resposta_freq.status_code != 200:
            print(f"     [Aviso] A API recusou o diário {id_diario} (Status HTTP {resposta_freq.status_code}). Pulando...")
            continue
            
        # --- BLINDAGEM 2: Tenta ler o JSON de forma segura ---
        try:
            dados_chamada = resposta_freq.json()
        except requests.exceptions.JSONDecodeError:
            print(f"     [Aviso] O diário {id_diario} devolveu texto quebrado ou vazio em vez de JSON. Pulando...")
            continue
            
        if isinstance(dados_chamada, dict):
            if "results" in dados_chamada: dados_chamada = dados_chamada["results"]
            elif "detail" in dados_chamada: 
                print(f"     [Aviso] Falha ao ler diário {id_diario}: {dados_chamada['detail']}")
                continue 

        # Monta a lista da turma
        lista_final_ia = []
        for index, aluno_freq in enumerate(dados_chamada, start=1):
            mat_freq = str(aluno_freq.get("matricula"))
            nome_completo = dicionario_nomes.get(mat_freq, "NOME NÃO ENCONTRADO")
            
            lista_final_ia.append({
                "numero_chamada": index,
                "matricula": mat_freq,
                "nome": nome_completo
            })
            
        # Adiciona a lista da turma no nosso Dicionário Mestre
        dados_consolidados[str(id_diario)] = lista_final_ia
        
    # 5. Salva o Arquivo Único Mestre
    with open(ARQUIVO_CACHE_MESTRE, 'w', encoding='utf-8') as f:
        json.dump(dados_consolidados, f, ensure_ascii=False, indent=4)
        
    print(f"\n[Aulio Data] 🎉 Sincronização concluída! {len(dados_consolidados)} diários salvos em '{ARQUIVO_CACHE_MESTRE}'.")
    return dados_consolidados

def obter_lista_chamada(id_diario):
    url = f"https://siga.activesoft.com.br/api/v0/diario_frequencia/?diario={id_diario}"
    headers = {
        "Authorization": "Bearer ZaAmsMtiTSf3nxpuTJuZ2zkgOmVMhr", 
        "Content-Type": "application/json"
    }
    try:
        resposta = requests.get(url, headers=headers)
        
        # A BLINDAGEM CONTRA O 'é' e o 'º'
        texto_limpo = resposta.content.decode('iso-8859-1', errors='ignore')
        dados = json.loads(texto_limpo)
        
        return dados
    except Exception as e:
        print(f"Erro ao obter lista: {e}")
        return []
# --- Teste de Execução ---
if __name__ == "__main__":
    # Testando o acesso a um diário específico
    alunos_teste = obter_lista_chamada(7552)
    if alunos_teste:
        print(f"\nTeste Leitura Rápida: O aluno 1 do diário 7552 é {alunos_teste[0]['nome']}")