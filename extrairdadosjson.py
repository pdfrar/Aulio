import requests
import json
import time

# ==========================================================
# CONFIGURAÇÕES
# ==========================================================
BASE_URL = "https://siga.activesoft.com.br" 
TOKEN = "Bearer ZaAmsMtiTSf3nxpuTJuZ2zkgOmVMhr"
PERIODO = "2026"
# ==========================================================

HEADERS = {
    "Authorization": TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def extrair_dados_completos():
    try:
        # 1. Coleta a enturmacação detalhada
        url_detalhes = f"{BASE_URL}/api/v0/enturmacao_com_detalhes/"
        print("--- Passo 1: Coletando Detalhes das Turmas ---")
        res_e = requests.get(url_detalhes, headers=HEADERS)
        
        if res_e.status_code != 200:
            print(f"Erro na Enturmação Detalhada: {res_e.status_code}")
            return
            
        dados_detalhes = res_e.json()
        
        # Criamos um mapa: {id_da_turma: "Nome Completo da Turma"}
        # Note: a documentação diz 'turma_id', mas verificamos se é 'id_turma' por segurança
        mapa_nomes_turmas = {}
        for item in dados_detalhes:
            t_id = item.get('turma_id') or item.get('id_turma')
            t_nome = item.get('nome_turma_completo', "Nome não disponível")
            if t_id:
                mapa_nomes_turmas[t_id] = t_nome

        ids_unicos_turmas = list(mapa_nomes_turmas.keys())
        print(f"Foram identificadas {len(ids_unicos_turmas)} turmas únicas.")

        # 2. Loop para buscar os diários de cada turma e vincular o nome
        print(f"\n--- Passo 2: Extraindo Diários e Vinculando Nomes ---")
        lista_final = []
        
        for idx, id_t in enumerate(ids_unicos_turmas):
            nome_turma = mapa_nomes_turmas[id_t]
            print(f"[{idx+1}/{len(ids_unicos_turmas)}] Processando: {nome_turma[:40]}...", end="\r")
            
            url_diarios = f"{BASE_URL}/api/v0/diarios/"
            params = {"turma": id_t, "periodo": PERIODO}
            
            res_d = requests.get(url_diarios, headers=HEADERS, params=params)
            
            if res_d.status_code == 200:
                diarios_encontrados = res_d.json()
                
                for d in diarios_encontrados:
                    lista_final.append({
                        "id_diario": d.get('id'),
                        "nome_disciplina": d.get('nome_disciplina'),
                        "id_turma": id_t,
                        "nome_turma_completo": nome_turma
                    })
            
            # Pausa para evitar bloqueio (Rate Limit)
            time.sleep(0.1)

        # 3. Salva o resultado final
        print(f"\n\n--- Passo 3: Salvando resultados ---")
        nome_arquivo = 'diarios_com_turmas_2026.json'
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(lista_final, f, indent=4, ensure_ascii=False)
        
        print(f"Sucesso! {len(lista_final)} diários mapeados.")
        print(f"Arquivo gerado: {nome_arquivo}")

    except Exception as e:
        print(f"\nErro crítico: {e}")

if __name__ == "__main__":
    extrair_dados_completos()