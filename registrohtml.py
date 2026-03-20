import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urlencode

def registrar_aula_completa(login, senha, id_diario, id_turma, id_disciplina, disciplina_str, data_aula, conteudo, tarefa, numeros_frequencia):
    """
    Função principal que o server.py vai chamar para realizar todo o fluxo.
    numeros_frequencia: Dicionário no formato {"F": [1, 2], "J": [3]}
    """
    
    # Garantindo que IDs sejam strings
    id_diario = str(id_diario)
    id_turma = str(id_turma)
    id_disciplina = str(id_disciplina)
    
    sessao = requests.Session()
    url_login = "https://siga03.activesoft.com.br/login/?next=/portal/"

    # --- ETAPA 1 e 2: O GET e a captura do Token Dinâmico ---
    print("\n[Aulio HTTP] Acessando a página para capturar o token de segurança...")
    resposta_get = sessao.get(url_login)
    html_login = resposta_get.content.decode('iso-8859-1', errors='ignore') # <-- BLINDADO
    sopa_de_letras = BeautifulSoup(html_login, 'html.parser')
    token_input = sopa_de_letras.find('input', {'name': 'csrfmiddlewaretoken'})

    if token_input:
        csrf_token_fresco = token_input['value']
    else:
        raise Exception("PAGE_ERROR: Não encontrei o token CSRF do Django.")

    # --- ETAPA 3: O POST de Login ---
    print(f"[Aulio HTTP] Autenticando usuário {login}...")
    payload_login = {
        "csrfmiddlewaretoken": csrf_token_fresco,
        "codigo": "AGAPE",
        "login": login,
        "senha": senha 
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": url_login 
    }

    resposta_post = sessao.post(url_login, data=payload_login, headers=headers)

    if "portal" not in resposta_post.url and resposta_post.status_code != 200:
        raise Exception("LOGIN_ERROR") 
    
    print("[Aulio HTTP] Login realizado com sucesso!")

    # --- ETAPA 4: Buscar o Passaporte JWT na API ---
    url_api = "https://siga03.activesoft.com.br/api/v1/global/"
    resposta_api = sessao.get(url_api)
    texto_api = resposta_api.content.decode('iso-8859-1', errors='ignore') # <-- BLINDADO
    dados_api = json.loads(texto_api)
    token_jwt = dados_api.get("TOKEN_PORTAL_WEB")

    if not token_jwt:
        raise Exception("PAGE_ERROR: Token JWT não encontrado na resposta da API!")

    # --- ETAPA 5: Atravessar a Ponte (SSO) ---
    url_sso_app39 = "https://app39.activesoft.com.br/sistema/LoginDiretoV2.asp"
    payload_sso = {
        "ServidorDefinido": "https://app39.activesoft.com.br",
        "OcultarBotaoVoltar": "1",
        "token": token_jwt,
        # Usamos apenas a Chave Mestra: IdTurma e IdDiario
        "paginaDestino": f"Diario/DiarioPrincipal.asp?IdTurma={id_turma}&IdDiario={id_diario}" 
    }
    resposta_sso = sessao.post(url_sso_app39, data=payload_sso)
    
    # -------------------------------------------------------------------
    # ETAPA 6: Gravar a Aula (O SNIPER AUTODIDATA)
    # -------------------------------------------------------------------
    print(f"[Aulio HTTP] Lendo o formulário do Diário {id_diario}...")
    
    # Abrimos o diário SÓ com o IdDiario e IdTurma. O ActiveSoft permite isso.
    url_formulario = f"https://app39.activesoft.com.br/sistema/sistema.1065614/TelasSIGA/Diario/RegistroAulas.asp?IdDiario={id_diario}&IdTurma={id_turma}"
    resposta_form = sessao.get(url_formulario)
    html_form = resposta_form.content.decode('iso-8859-1', errors='ignore')
    sopa_form = BeautifulSoup(html_form, 'html.parser')

    # 1. A Autodescoberta (O bot lê o que o TI escondeu na página e copia)
    input_id_disciplina = sopa_form.find('input', {'name': 'IdDisciplina'})
    input_disciplina = sopa_form.find('input', {'name': 'Disciplina'})
    input_descricao = sopa_form.find('input', {'name': 'DescricaoDiario'})
    
    id_disciplina_real = input_id_disciplina['value'] if input_id_disciplina else ""
    disciplina_real = input_disciplina['value'] if input_disciplina else ""
    descricao_real = input_descricao['value'] if input_descricao else "Diário 1º Bimestre"

    print(f"[Aulio HTTP] Autodescoberta: ID Disciplina Oculto = {id_disciplina_real} | Nome = {disciplina_real}")

    # 2. O Payload Imbatível (Parroteando os dados reais do sistema)
    payload_aula = {
        "AulaSelecionada": "0",
        "StRegistroEmEdicao": "1",
        "DataAulaNovo": data_aula,
        "ConteudoMinistradoNovo": conteudo,
        "TarefaNovo": tarefa,
        "IdDiario": id_diario,
        "Disciplina": disciplina_real,
        "DescricaoDiario": descricao_real,
        "IdDisciplina": id_disciplina_real, # <-- Pegou sozinho da página!
        "IdTurma": id_turma
    }

    print(f"[Aulio HTTP] Disparando gravação da aula...")
    url_gravar_aula = "https://app39.activesoft.com.br/sistema/sistema.1065614/TelasSIGA/Diario/RegistroAulasGravar.asp"
    
    payload_codificado = urlencode(payload_aula, encoding='iso-8859-1', errors='ignore')
    headers_aula = {
        "User-Agent": "Mozilla/5.0",
        "Referer": url_formulario,
        "Content-Type": "application/x-www-form-urlencoded" 
    }

    try:
        resposta_gravar = sessao.post(url_gravar_aula, data=payload_codificado, headers=headers_aula, allow_redirects=False)
    except UnicodeDecodeError:
        print("[Aulio HTTP] Redirecionamento 302 interceptado (Aula cravada no sistema!).")

    # -------------------------------------------------------------------
    # ETAPA 7: Gravar a Frequência (SNIPER)
    # -------------------------------------------------------------------
    # -------------------------------------------------------------------
    # ETAPA 7: Gravar a Frequência (SNIPER)
    # -------------------------------------------------------------------
    lista_de_checkboxes = sopa_form.find_all('input', {'name': 'aulas'})
    qtde_aulas_real = len(lista_de_checkboxes) + 1 

    aula_inicial_bloco = ((qtde_aulas_real - 1) // 10) * 10 + 1
    coluna_atual_no_bloco = ((qtde_aulas_real - 1) % 10) + 1

    print(f"\n[Aulio HTTP] Sincronizando frequência da aula {qtde_aulas_real} (Bloco {aula_inicial_bloco}, Coluna {coluna_atual_no_bloco})...")

    url_visual_freq = f"https://app39.activesoft.com.br/sistema/sistema.1065614/TelasSIGA/Diario/RegistroFrequencia2.asp?IdDiario={id_diario}&IdTurma={id_turma}&IdDisciplina={id_disciplina_real}&QtdeAulasRegistradas={qtde_aulas_real}&AulaInicial={aula_inicial_bloco}"
    
    resposta_visual = sessao.get(url_visual_freq)
    sopa_freq = BeautifulSoup(resposta_visual.content.decode('iso-8859-1', errors='ignore'), 'html.parser')
    
    payload_frequencia = {}
    for tag in sopa_freq.find_all('input'):
        nome = tag.get('name')
        if nome:
            payload_frequencia[nome] = tag.get('value', '')

    payload_frequencia.update({
        "AulaInicial": str(aula_inicial_bloco),
        "AulaInicialGravacao": str(aula_inicial_bloco),
        "QtdeAulasRegistradas": str(qtde_aulas_real),
        "Disciplina": disciplina_real,
        "DescricaoDiario": descricao_real
    })

    url_api_frequencia = f"https://siga.activesoft.com.br/api/v0/diario_frequencia/?diario={id_diario}"
    headers_api = {"Authorization": "Bearer ZaAmsMtiTSf3nxpuTJuZ2zkgOmVMhr"}
    dados_frequencia = sessao.get(url_api_frequencia, headers=headers_api).json()

    # ⚡ O FILTRO BLINDADO DE DADOS: Força tudo a ser um Número Inteiro!
    faltosos_F = [int(x) for x in numeros_frequencia.get("F", []) if str(x).isdigit()]
    faltosos_J = [int(x) for x in numeros_frequencia.get("J", []) if str(x).isdigit()]
    
    print(f"[Aulio HTTP] Faltas Normais (F): {faltosos_F}")
    print(f"[Aulio HTTP] Faltas Justificadas (J): {faltosos_J}")

    tradutor = {"•": "P", "F": "F", "J": "J", "D": "D", None: "Z"}

    if not dados_frequencia:
        print("[Aulio HTTP] 🔴 ALERTA CRÍTICO: A API da escola não retornou a lista de alunos para este diário!")

    for i, aluno_api in enumerate(dados_frequencia, start=1):
        # ⚡ BUSCA PELO NÚMERO DA CHAMADA EXATO (Proteção contra alunos transferidos)
        num_chamada_str = aluno_api.get("numero_chamada")
        num_chamada = int(num_chamada_str) if num_chamada_str else i

        string_frequencia = ""
        for pos in range(1, 11):
            aula_abs = aula_inicial_bloco + pos - 1
            if pos == coluna_atual_no_bloco:
                if num_chamada in faltosos_F: 
                    string_frequencia += "F"
                    print(f"  👉 Cravando Falta (F) para o Nº {num_chamada} - {aluno_api.get('nome')}")
                elif num_chamada in faltosos_J: 
                    string_frequencia += "J"
                    print(f"  👉 Cravando Justificada (J) para o Nº {num_chamada} - {aluno_api.get('nome')}")
                else: 
                    string_frequencia += "P"
            else:
                valor_api = aluno_api.get(f"presenca_falta_{aula_abs:02d}")
                string_frequencia += tradutor.get(valor_api, "Z")
        
        payload_frequencia[f"ArrayPresencaFalta{i}"] = string_frequencia

    try:
        print("[Aulio HTTP] Disparando gravação da chamada...")
        payload_cod_freq = urlencode(payload_frequencia, encoding='iso-8859-1', errors='ignore')
        res_freq = sessao.post("https://app39.activesoft.com.br/sistema/sistema.1065614/TelasSIGA/Diario/RegistroFrequenciaGravar2.asp", 
                               data=payload_cod_freq, headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": url_visual_freq}, allow_redirects=False)
        return True
    except UnicodeDecodeError:
        return True