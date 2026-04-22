import os
import requests
import json
from bs4 import BeautifulSoup
import urllib.parse
from urllib.parse import urlparse, parse_qs, urlencode
from dotenv import load_dotenv
from datetime import datetime
import re

load_dotenv()

def descobrir_diario_ativo(html_lista_diarios):
    """
    Analisa a tabela de bimestres do Siga e retorna o IdDiario 
    do primeiro bimestre que estiver com o botão 'Registro de aulas' aberto.
    """
    print("[Aulio Inteligência] Analisando tabela de bimestres para encontrar o diário ativo...")
    sopa = BeautifulSoup(html_lista_diarios, 'html.parser')
    
    # Busca todos os links da página
    links = sopa.find_all('a', href=True)
    
    for link in links:
        texto = link.text.strip().lower()
        href = link['href']
        
        # O pulo do gato: acha o link exato que permite registrar aula
        if "registro de aulas" in texto or "registroaulas.asp" in href.lower():
            # Desmembra a URL para pegar os parâmetros
            parsed_url = urlparse(href)
            parametros = parse_qs(parsed_url.query)
            
            if 'IdDiario' in parametros:
                id_diario_ativo = parametros['IdDiario'][0]
                print(f"[Aulio Inteligência] Alvo travado! O Diário aberto é o ID: {id_diario_ativo}")
                return id_diario_ativo
                
    raise Exception("STATUS_ERROR: Nenhum diário aberto encontrado. Todos os prazos podem ter expirado ou o professor não tem acesso.")

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

    print("\n================== 🐛 DEBUG AULIO ==================")
    servidor_base = "https://app39.activesoft.com.br"
    url_sso = f"{servidor_base}/sistema/LoginDiretoV2.asp"
    
    # 1. Aplicando os cabeçalhos salvadores (Disfarce)
    sessao.headers.update({
        "Sec-Fetch-Dest": "iframe",
        "Referer": f"{servidor_base}/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    })

    # 2. O PASSO QUE FALTAVA: Entrar no Lobby PRIMEIRO para gerar o IdPeriodo
    print(f"[DEBUG 1] Fazendo POST no SSO para carregar o ProfessorPrincipal...")
    payload_sso_lobby = {
        "ServidorDefinido": servidor_base, 
        "OcultarBotaoVoltar": "1", 
        "token": token_jwt, 
        "paginaDestino": "ProfessorPrincipal.asp" 
    }
    resp_lobby = sessao.post(url_sso, data=payload_sso_lobby)
    print(f"[DEBUG 1.1] Status do Lobby: {resp_lobby.status_code} | URL Final: {resp_lobby.url}")
    print(f"[DEBUG 1.2] Cookies da sessão: {sessao.cookies.get_dict()}")

    # 3. Agora sim, com o IdPeriodo na memória do servidor, vamos pedir a tabela!
    disciplina_encoded = urllib.parse.quote(disciplina_str.encode('iso-8859-1'))
    
    # 🛡️ TRAVA DE SEGURANÇA: Se o ID vier vazio do server.py, injeta "00" pro Siga não crashar!
    id_disciplina_seguro = id_disciplina if id_disciplina.strip() else "00"
    
    # Injetamos a variável segura na URL
    url_radar = f"{servidor_base}/sistema/sistema.1065614/TelasSIGA/Diario/DiarioPrincipal.asp?IdTurma={id_turma}&IdDisciplina={id_disciplina_seguro}&Disciplina={disciplina_encoded}"
    
    print(f"\n[DEBUG 2] Fazendo GET na Tabela de Diários...")
    print(f"[DEBUG 2.1] URL Alvo: {url_radar}")
    
    resposta_radar = sessao.get(url_radar)
    print(f"[DEBUG 2.2] Status da Tabela: {resposta_radar.status_code}")
    
    html_radar = resposta_radar.content.decode('iso-8859-1', errors='ignore')
    
    # 4. O DETECTOR DE FALHAS AUTOMÁTICO (O que você pediu!)
    # Note que os devs do Siga escreveram "Nenehuma" errado no HTML deles
    if "Nenehuma turma/disciplina selecionada" in html_radar or "Nenhum diário de classe foi encontrado" in html_radar:
        print("\n❌ [DEBUG ERRO CRÍTICO] O Siga barrou a requisição!")
        print("Motivo: Ele retornou a página de erro de turma vazia.")
        print("Ação: Salvando o HTML no Windows para análise...")
        with open("debug_radar_ERRO.html", "w", encoding="utf-8") as f:
            f.write(html_radar)
        print("=================================================\n")
        raise Exception("PAGE_ERROR: O Siga perdeu a sessão e não carregou a tabela.")
    
    print("\n✅ [DEBUG SUCESSO] A tabela renderizou perfeitamente!")
    print("=================================================\n")

    # -------------------------------------------------------------------
    # ETAPA 5.5 (Continuação): Leitura das Datas
    # -------------------------------------------------------------------
    sopa_radar = BeautifulSoup(html_radar, 'html.parser')

    print("[Aulio Inteligência] Buscando o bimestre mais próximo do prazo...")
    hoje = datetime.now()
    candidatos_abertos = [] # Lista para guardar (data, id)

    linhas_tabela = sopa_radar.find_all('tr')

    for linha in linhas_tabela:
        texto_linha = linha.text.strip()
        datas_encontradas = re.findall(r'\d{2}/\d{2}/\d{4}', texto_linha)
        
        if datas_encontradas:
            data_limite_str = datas_encontradas[-1] # Pega a última data da linha
            try:
                data_limite = datetime.strptime(data_limite_str, "%d/%m/%Y")
                
                # Se o diário ainda não venceu...
                if data_limite >= hoje:
                    links = linha.find_all('a', href=True)
                    for link in links:
                        params = urllib.parse.parse_qs(urllib.parse.urlparse(link['href']).query)
                        params_lower = {k.lower(): v for k, v in params.items()}
                        id_extracao = params_lower.get('iddiario', [None])[0]
                        
                        if id_extracao:
                            # Guardamos a data e o ID para comparar depois
                            candidatos_abertos.append((data_limite, id_extracao))
                            break 
            except:
                continue

    if candidatos_abertos:
        # 🎯 A MÁGICA: Ordenamos pela data e pegamos a MENOR (a mais próxima de hoje)
        candidatos_abertos.sort(key=lambda x: x[0])
        data_escolhida, id_diario_aberto = candidatos_abertos[0]
        
        id_diario = id_diario_aberto
        print(f"[Aulio Inteligência] 🎯 Alvo travado no Bimestre que vence em {data_escolhida.strftime('%d/%m/%Y')} (ID: {id_diario})")
    else:
        raise Exception("STATUS_ERROR: Nenhum bimestre ativo encontrado na tabela.")

    # -------------------------------------------------------------------
    # ETAPA 6: Gravar a Aula (Agora com o id_diario garantido como aberto)
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
        html_resposta_aula = resp_aula.content.decode('iso-8859-1', errors='ignore')
        
        # 🐕 CÃO DE GUARDA: Procura se o Siga cuspiu algum pop-up de erro (alert) na tela
        alertas = re.findall(r"alerta\(['\"](.*?)['\"]\)", html_resposta_aula, re.IGNORECASE)
        alertas.extend(re.findall(r"alert\(['\"](.*?)['\"]\)", html_resposta_aula, re.IGNORECASE))
        
        if alertas:
            msg_erro_siga = alertas[0].replace('\\n', ' ')
            print(f"\n❌ [Siga Bloqueou a Aula] Motivo: {msg_erro_siga}")
            raise Exception(f"Siga recusou o registro: {msg_erro_siga}")
            
    except UnicodeDecodeError:
        resp_aula = type('FakeResp', (), {'status_code': 200})()
        
    if resp_aula.status_code in (200, 302, 301):
        print("[Aulio HTTP] Aula gravada com sucesso no banco de dados!")
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

    # 🛡️ MAPA DE IDENTIDADE: Liga a API ao ID real do aluno, ignorando a ordem visual
    mapa_api_alunos = {str(a.get("id_aluno", "")): a for a in dados_frequencia if a.get("id_aluno")}
    
    # Quantidade real de linhas no formulário (ex: 30 linhas, mesmo que o último seja o Nº 31)
    qtde_linhas_html = int(payload_frequencia.get("QtdeAlunos", len(dados_frequencia)))

    for i in range(1, qtde_linhas_html + 1):
        # 1. Pergunta ao formulário: "Quem é o aluno que está fisicamente na linha i?"
        id_aluno_siga = str(payload_frequencia.get(f"IdAluno{i}", ""))
        
        # 2. Puxa a ficha completa dele na API
        aluno_api = mapa_api_alunos.get(id_aluno_siga, {})

        num_chamada_str = aluno_api.get("numero_chamada")
        num_chamada = int(num_chamada_str) if num_chamada_str else i
        nome_display = aluno_api.get("nome_aluno") or aluno_api.get("aluno") or aluno_api.get("nome") or "Estudante"

        string_frequencia = ""
        
        # 3. Reconstrói a linha do tempo (10 aulas)
        for pos in range(1, 11):
            aula_abs = aula_inicial_bloco + pos - 1
            
            # SE FOR A AULA DE HOJE: Toma a decisão com base no nosso áudio
            if pos == coluna_atual_no_bloco:
                if num_chamada in faltosos_F: 
                    string_frequencia += "F"
                    print(f"  👉 Falta Normal (F) para Nº {num_chamada} - {nome_display} (Linha do site: {i})")
                elif num_chamada in faltosos_J: 
                    string_frequencia += "J"
                    print(f"  👉 Falta Justificada (J) para Nº {num_chamada} - {nome_display} (Linha do site: {i})")
                else: 
                    string_frequencia += "P"
            
            # SE FOR O PASSADO/FUTURO: Copia exatamente o que está na API
            else:
                valor_api = aluno_api.get(f"presenca_falta_{aula_abs:02d}")
                
                # O FIX DO APAGÃO: Se a API mandar "P", a gente preserva o "P"!
                if not valor_api or valor_api == "Z":
                    string_frequencia += "Z" # Vazio
                elif valor_api == "•":
                    string_frequencia += "P" # Ponto vira Presença
                else:
                    string_frequencia += str(valor_api).upper() # Mantém P, F, J ou D

        # 4. Salva a string blindada na linha física correta do formulário
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