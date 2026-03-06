import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode

# Cria a sessão VIP que vai guardar os cookies
sessao = requests.Session()

url_login = "https://siga03.activesoft.com.br/login/?next=/portal/"

# --- ETAPA 1 e 2: O GET e a captura do Token Dinâmico ---
print("Acessando a página para capturar o token de segurança...")
resposta_get = sessao.get(url_login)
sopa_de_letras = BeautifulSoup(resposta_get.text, 'html.parser')
token_input = sopa_de_letras.find('input', {'name': 'csrfmiddlewaretoken'})

if token_input:
    csrf_token_fresco = token_input['value']
    print(f"Sucesso! Token capturado: {csrf_token_fresco[:10]}...")
else:
    print("Erro: Não encontrei o token.")
    exit()

# --- ETAPA 3: O POST de Login ---
print("Enviando os dados de login...")
payload_login = {
    "csrfmiddlewaretoken": csrf_token_fresco,
    "codigo": "AGAPE",
    "login": "Pedro",
    "senha": "Agape2025!" 
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": url_login 
}

resposta_post = sessao.post(url_login, data=payload_login, headers=headers)

if "portal" in resposta_post.url or resposta_post.status_code == 200:
    print("Login realizado com sucesso! O Selenium já pode chorar.")
else:
    print("Falha no login. Verifique se a senha está correta.")

# --- ETAPA 4: Buscar o Passaporte JWT na API ---
print("\n--- Buscando o Passaporte (API) ---")
url_api = "https://siga03.activesoft.com.br/api/v1/global/"
resposta_api = sessao.get(url_api)
dados_api = resposta_api.json()
token_jwt = dados_api.get("TOKEN_PORTAL_WEB")

if not token_jwt:
    print("Erro catastrófico: Token não encontrado na resposta da API!")
    exit()
print(f"Passaporte VIP (JWT) em mãos: {token_jwt[:15]}...")

# --- ETAPA 5: Atravessar a Ponte (SSO para o Prédio B) ---
print("\n--- Esquentando a Sessão no Prédio B (ASP) ---")
url_sso_app39 = "https://app39.activesoft.com.br/sistema/LoginDiretoV2.asp"
payload_sso = {
    "ServidorDefinido": "https://app39.activesoft.com.br",
    "OcultarBotaoVoltar": "1",
    "token": token_jwt,
    "paginaDestino": "Diario/DiarioPrincipal.asp?IdTurma=365&IdDisciplina=82"
}
resposta_sso = sessao.post(url_sso_app39, data=payload_sso)
print(f"Status da recepção no ASP: {resposta_sso.status_code}")

# -------------------------------------------------------------------
# ETAPA 6: Gravar a Aula de Robótica (Modo Seguro/Produção)
# -------------------------------------------------------------------
print("\n--- Iniciando gravação da aula ---")

url_gravar_aula = "https://app39.activesoft.com.br/sistema/sistema.1065614/TelasSIGA/Diario/RegistroAulasGravar.asp"

# Textos alterados para não alarmar pais e coordenadores
payload_aula = {
    "AulaSelecionada": "0",
    "StRegistroEmEdicao": "1",
    "DataAulaNovo": "05/03/2026", 
    "ConteudoMinistradoNovo": "Teste de registro de aula, por favor desconsiderar", 
    "TarefaNovo": "Teste de registro de aula, por favor desconsiderar", 
    "IdDiario": "7552", 
    # TRUQUE DE MESTRE: Trocamos "1º" por "1" e tiramos os acentos. 
    # Isso impede o servidor de quebrar o redirecionamento!
    "Disciplina": "Ensino Fundamental I / 1 Ano / 2026 / 1 ANO - A - Educacao Tecnologica",
    "DescricaoDiario": "Diario 1 Bimestre",
    "IdDisciplina": "82",
    "IdTurma": "365"
}

# O resto continua idêntico:
payload_codificado = urlencode(payload_aula, encoding='iso-8859-1')

headers_aula = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://app39.activesoft.com.br/sistema/sistema.1065614/TelasSIGA/Diario/RegistroAulas.asp",
    "Content-Type": "application/x-www-form-urlencoded" 
}

resposta_gravar = sessao.post(
    url_gravar_aula, 
    data=payload_codificado, 
    headers=headers_aula, 
    allow_redirects=False
)

print(f"Status HTTP Final: {resposta_gravar.status_code}")
# Se for 302 (Found/Redirect), significa que deu tudo certo e ele tentou nos redirecionar para a página visual!
if resposta_gravar.status_code == 302:
    print("Sucesso Absoluto! Status 302: O servidor salvou e tentou nos redirecionar, mas o Aulio ignorou com classe.")
else:
    print(f"Algo diferente aconteceu. Status HTTP Final: {resposta_gravar.status_code}")

# -------------------------------------------------------------------
# ETAPA 7: ARQUITETURA HÍBRIDA 3.0 (O Fim do Selenium)
# -------------------------------------------------------------------
print("\n--- 7.1 Lendo o histórico perfeito da API Oficial ---")
url_api_frequencia = "https://siga.activesoft.com.br/api/v0/diario_frequencia/?diario=7552"
headers_api = {
    "Authorization": "Bearer ZaAmsMtiTSf3nxpuTJuZ2zkgOmVMhr", # Coloque seu token correto aqui
    "Content-Type": "application/json"
}
resposta_api_freq = sessao.get(url_api_frequencia, headers=headers_api)
dados_frequencia = resposta_api_freq.json()

print("\n--- 7.2 Contando as aulas no ASP (A Sacada Mestre) ---")
# Acessamos a lista de aulas
url_lista_aulas = "https://app39.activesoft.com.br/sistema/sistema.1065614/TelasSIGA/Diario/RegistroAulas.asp?IdDiario=7552&IdTurma=365&IdDisciplina=82"
resposta_aulas = sessao.get(url_lista_aulas)
sopa_aulas = BeautifulSoup(resposta_aulas.text, 'html.parser')

# A MÁGICA: O Aulio conta quantas checkboxes com name="aulas" existem na tela!
lista_de_checkboxes = sopa_aulas.find_all('input', {'name': 'aulas'})
qtde_aulas_real = len(lista_de_checkboxes)

if qtde_aulas_real == 0:
    print("Aviso: Não encontrei nenhuma aula registrada para preencher a frequência.")
    exit()

coluna_atual = qtde_aulas_real
print(f"Diagnóstico: O Aulio contou {qtde_aulas_real} checkboxes. Preenchendo a coluna {coluna_atual}.")

print("\n--- 7.3 Raspando os IDs reais e atirando! ---")
# Agora entramos na tela de frequência PASSANDO A QUANTIDADE na URL
url_visual_freq = f"https://app39.activesoft.com.br/sistema/sistema.1065614/TelasSIGA/Diario/RegistroFrequencia2.asp?IdDiario=7552&IdTurma=365&IdDisciplina=82&QtdeAulasRegistradas={qtde_aulas_real}"
resposta_visual = sessao.get(url_visual_freq)
sopa_freq = BeautifulSoup(resposta_visual.text, 'html.parser')

total_alunos = len(dados_frequencia)

# Montando a Casca do Payload 
payload_frequencia = {
    "AulaInicial": "1", 
    "ContPresencaAluno": str(total_alunos),
    "IdDiario": "7552",
    "IdTurma": "365",
    "IdDisciplina": "82",
    "Disciplina": "Ensino Fundamental I / 1 Ano / 2026 / 1 ANO - A - Educacao Tecnologica",
    "DescricaoDiario": "Diario 1 Bimestre",
    "QtdeAulasRegistradas": str(qtde_aulas_real), # Agora sim, dinâmico e exato!
    "exibirMensagemFrequencia": "0",
    "AulaInicialGravacao": "1",
    "linkTelaCriacaoAulas": "RegistroAulas.asp"
}

tradutor_api_asp = {"•": "P", "F": "F", "J": "J", "D": "D", None: "Z"}

# Simulação do Áudio: Faltaram os alunos de chamada 2 e 3
alunos_que_faltaram = [2, 3] 

for i, aluno_api in enumerate(dados_frequencia, start=1):
    # Pegamos o ID primário que o ASP escondeu no HTML
    input_id = sopa_freq.find('input', {'name': f'IdAluno{i}'})
    
    if input_id:
        id_banco_asp = input_id['value']
    else:
        # Fallback de segurança usando a matrícula se o HTML falhar
        id_banco_asp = aluno_api["matricula"] 
    
    payload_frequencia[f"IdAluno{i}"] = id_banco_asp
    
    # Construindo a String de 10 letras ("PPZZZZZZZZ", "FFZZZZZZZZ"...)
    string_frequencia = ""
    for aula_num in range(1, 11):
        if aula_num == coluna_atual:
            # O PRESENTE: A aula que acabamos de criar hoje
            if i in alunos_que_faltaram:
                string_frequencia += "F"
            else:
                string_frequencia += "P"
        else:
            # O PASSADO E FUTURO: O que a API Oficial nos contou
            valor_api = aluno_api.get(f"presenca_falta_{aula_num:02d}")
            string_frequencia += tradutor_api_asp.get(valor_api, "Z")
            
    payload_frequencia[f"ArrayPresencaFalta{i}"] = string_frequencia

print("Payload perfeito construído. Enviando requisição final ao banco de dados...")

from urllib.parse import urlencode
payload_codificado_freq = urlencode(payload_frequencia, encoding='iso-8859-1')
headers_freq = {
    "User-Agent": "Mozilla/5.0",
    "Referer": url_visual_freq,
    "Content-Type": "application/x-www-form-urlencoded"
}

resposta_freq = sessao.post(
    "https://app39.activesoft.com.br/sistema/sistema.1065614/TelasSIGA/Diario/RegistroFrequenciaGravar2.asp", 
    data=payload_codificado_freq, 
    headers=headers_freq, 
    allow_redirects=False
)

if resposta_freq.status_code == 302:
    print(f"🎯 SUCESSO TOTAL! Frequência cravada na coluna {coluna_atual} com perfeição cirúrgica!")
else:
    print(f"Ops, código HTTP retornado: {resposta_freq.status_code}")