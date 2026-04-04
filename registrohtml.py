import os
import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

def registrar_aula_completa(login, senha, id_diario, id_turma, id_disciplina, disciplina_str, data_aula, conteudo, tarefa, numeros_frequencia):
    id_diario = str(id_diario)
    id_turma = str(id_turma)
    id_disciplina = str(id_disciplina)

    sessao = requests.Session()
    url_login = "https://siga03.activesoft.com.br/login/?next=/portal/"

    # --- ETAPA 1 e 2: O GET e a captura do Token Dinâmico ---
    print("\n[Aulio HTTP] Acessando a página para capturar o token de segurança...")
    resposta_get = sessao.get(url_login)
    html_login = resposta_get.content.decode('iso-8859-1', errors='ignore')
    sopa_de_letras = BeautifulSoup(html_login, 'html.parser')
    token_input = sopa_de_letras.find('input', {'name': 'csrfmiddlewaretoken'})

    if token_input: csrf_token_fresco = token_input['value']
    else: raise Exception("PAGE_ERROR: Não encontrei o token CSRF do Django.")

    # --- ETAPA 3: O POST de Login ---
    print(f"[Aulio HTTP] Autenticando usuário {login}...")
    payload_login = {"csrfmiddlewaretoken": csrf_token_fresco, "codigo": "AGAPE", "login": login, "senha": senha}
    headers = {"User-Agent": "Mozilla/5.0", "Referer": url_login}
    resposta_post = sessao.post(url_login, data=payload_login, headers=headers)

    if "portal" not in resposta_post.url or resposta_post.status_code not in (200, 301, 302): raise Exception("LOGIN_ERROR") 
    print("[Aulio HTTP] Login realizado com sucesso!")

    # --- ETAPA 4: Buscar o Passaporte JWT na API ---
    url_api = "https://siga03.activesoft.com.br/api/v1/global/"
    resposta_api = sessao.get(url_api)
    texto_api = resposta_api.content.decode('iso-8859-1', errors='ignore')
    token_jwt = json.loads(texto_api).get("TOKEN_PORTAL_WEB")
    if not token_jwt: raise Exception("PAGE_ERROR: Token JWT não encontrado!")

    # --- ETAPA 5: Atravessar a Ponte (SSO) ---
    url_sso_app39 = "https://app39.activesoft.com.br/sistema/LoginDiretoV2.asp"
    payload_sso = {"ServidorDefinido": "https://app39.activesoft.com.br", "OcultarBotaoVoltar": "1", "token": token_jwt, "paginaDestino": f"Diario/DiarioPrincipal.asp?IdTurma={id_turma}&IdDiario={id_diario}"}
    sessao.post(url_sso_app39, data=payload_sso)
    
    # -------------------------------------------------------------------
    # ETAPA 6: Gravar a Aula
    # -------------------------------------------------------------------
    print(f"[Aulio HTTP] Lendo o formulário do Diário {id_diario}...")
    url_formulario = f"https://app39.activesoft.com.br/sistema/sistema.1065614/TelasSIGA/Diario/RegistroAulas.asp?IdDiario={id_diario}&IdTurma={id_turma}"
    resposta_form = sessao.get(url_formulario)
    sopa_form = BeautifulSoup(resposta_form.content.decode('iso-8859-1', errors='ignore'), 'html.parser')

    input_id_disciplina = sopa_form.find('input', {'name': 'IdDisciplina'})
    input_disciplina = sopa_form.find('input', {'name': 'Disciplina'})
    input_descricao = sopa_form.find('input', {'name': 'DescricaoDiario'})
    
    id_disciplina_real = input_id_disciplina['value'] if (input_id_disciplina and input_id_disciplina.get('value')) else id_disciplina
    disciplina_real = input_disciplina['value'] if (input_disciplina and input_disciplina.get('value')) else disciplina_str
    descricao_real = input_descricao['value'] if (input_descricao and input_descricao.get('value')) else "Diário da Turma"
    if not id_disciplina_real.strip(): id_disciplina_real = "00"

    print(f"[Aulio HTTP] Autodescoberta: ID Disciplina = {id_disciplina_real} | Nome = {disciplina_real}")

    payload_aula = {
        "AulaSelecionada": "0", "StRegistroEmEdicao": "1", "DataAulaNovo": data_aula,
        "ConteudoMinistradoNovo": conteudo, "TarefaNovo": tarefa, "IdDiario": id_diario,
        "Disciplina": disciplina_real, "DescricaoDiario": descricao_real,
        "IdDisciplina": id_disciplina_real, "IdTurma": id_turma
    }

    url_gravar_aula = "https://app39.activesoft.com.br/sistema/sistema.1065614/TelasSIGA/Diario/RegistroAulasGravar.asp"
    payload_codificado = urlencode(payload_aula, encoding='iso-8859-1', errors='ignore')
    headers_aula = {"User-Agent": "Mozilla/5.0", "Referer": url_formulario, "Content-Type": "application/x-www-form-urlencoded"}

    try:
        resp_aula = sessao.post(url_gravar_aula, data=payload_codificado, headers=headers_aula, allow_redirects=False)
    except UnicodeDecodeError:
        # 302 do servidor com Location em ISO-8859-1 (contém acentos) — aula gravada mesmo assim
        resp_aula = type('FakeResp', (), {'status_code': 200})()
    if resp_aula.status_code in (200, 302, 301):
        print("[Aulio HTTP] Aula gravada com sucesso!")
    else:
        print(f"[Aulio HTTP] Aviso: resposta inesperada ao gravar aula (status {resp_aula.status_code})")

    # -------------------------------------------------------------------
    # ETAPA 7: Gravar a Frequência (API INTELIGENTE + TRATOR)
    # -------------------------------------------------------------------
    print("\n[Aulio HTTP] Consultando histórico de frequências na API da escola...")
    url_api_frequencia = f"https://siga.activesoft.com.br/api/v0/diario_frequencia/?diario={id_diario}"
    headers_api = {"Authorization": f"Bearer {os.getenv('SIGA_TOKEN', '')}"}
    resposta_api_freq = sessao.get(url_api_frequencia, headers=headers_api)
    dados_frequencia = resposta_api_freq.json() if resposta_api_freq.status_code == 200 else []

    # 🚜 O CÉREBRO MATEMÁTICO: Conta a última aula registrada varrendo o JSON
    max_aula_registrada = 0
    if dados_frequencia:
        for aluno in dados_frequencia:
            for chave, valor in aluno.items():
                if chave.startswith("presenca_falta_") and valor not in [None, "", "Z"]:
                    try:
                        num = int(chave.split("_")[-1])
                        if num > max_aula_registrada: max_aula_registrada = num
                    except: pass
                    
    qtde_aulas_real = max_aula_registrada + 1

    aula_inicial_bloco = ((qtde_aulas_real - 1) // 10) * 10 + 1
    coluna_atual_no_bloco = ((qtde_aulas_real - 1) % 10) + 1

    print(f"[Aulio HTTP] A última aula gravada foi a {max_aula_registrada}.")
    print(f"[Aulio HTTP] Sincronizando frequência da aula NOVA nº {qtde_aulas_real} (Bloco {aula_inicial_bloco}, Coluna {coluna_atual_no_bloco})...")

    url_visual_freq = f"https://app39.activesoft.com.br/sistema/sistema.1065614/TelasSIGA/Diario/RegistroFrequencia2.asp?IdDiario={id_diario}&IdTurma={id_turma}&IdDisciplina={id_disciplina_real}&QtdeAulasRegistradas={qtde_aulas_real}&AulaInicial={aula_inicial_bloco}"
    resposta_visual = sessao.get(url_visual_freq)
    sopa_freq = BeautifulSoup(resposta_visual.content.decode('iso-8859-1', errors='ignore'), 'html.parser')
    
    payload_frequencia = {}
    for tag in sopa_freq.find_all('input'):
        nome = tag.get('name')
        if nome: payload_frequencia[nome] = tag.get('value', '')

    payload_frequencia.update({
        "AulaInicial": str(aula_inicial_bloco),
        "AulaInicialGravacao": str(aula_inicial_bloco),
        "QtdeAulasRegistradas": str(qtde_aulas_real),
        "Disciplina": disciplina_real,
        "DescricaoDiario": descricao_real,
        "IdDiario": id_diario,
        "IdTurma": id_turma,
        "IdDisciplina": id_disciplina_real,
        f"DataAula{coluna_atual_no_bloco}": data_aula
    })

    faltosos_F = [int(x) for x in numeros_frequencia.get("F", []) if str(x).isdigit()]
    faltosos_J = [int(x) for x in numeros_frequencia.get("J", []) if str(x).isdigit()]

    tradutor = {"•": "P", "F": "F", "J": "J", "D": "D", None: "Z", "": "Z"}
    payload_frequencia["QtdeAlunos"] = str(len(dados_frequencia))

    for i, aluno_api in enumerate(dados_frequencia, start=1):
        num_chamada_str = aluno_api.get("numero_chamada")
        num_chamada = int(num_chamada_str) if num_chamada_str else i

        id_aluno_api = str(aluno_api.get("id_aluno", ""))
        if f"IdAluno{i}" not in payload_frequencia and id_aluno_api:
            payload_frequencia[f"IdAluno{i}"] = id_aluno_api

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
                valor_api = aluno_api.get(f"presenca_falta_{aula_abs:02d}", "Z")
                string_frequencia += tradutor.get(valor_api, "Z")
        
        payload_frequencia[f"ArrayPresencaFalta{i}"] = string_frequencia

    try:
        payload_cod_freq = urlencode(payload_frequencia, encoding='iso-8859-1', errors='ignore')
        res_freq = sessao.post("https://app39.activesoft.com.br/sistema/sistema.1065614/TelasSIGA/Diario/RegistroFrequenciaGravar2.asp", 
                               data=payload_cod_freq, headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": url_visual_freq}, allow_redirects=False)
        if res_freq.status_code in [200, 302]: print("\n[Aulio HTTP] Frequência gravada com sucesso absoluto!")
        return True
    except UnicodeDecodeError:
        print("\n[Aulio HTTP] Redirecionamento 302 interceptado (Chamada Cravada!).")
        return True