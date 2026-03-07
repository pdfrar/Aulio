import os
import json
import datetime
import requests
import re
import unicodedata
from groq import Groq
from google import genai  
import sys
sys.stdout.reconfigure(encoding='utf-8')

# --- ⚙️ CONFIGURAÇÕES DAS APIS ---
GROQ_API_KEY = "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" 
GEMINI_API_KEY = "AIzaSyBqpzahCaSPI4P7QZyVWxTluAsmnpJOfCg"
    
ARQUIVO_BNCC_NUVEM = None  
client = Groq(api_key=GROQ_API_KEY)
gemini_client = genai.Client(api_key=GEMINI_API_KEY) 

def transcrever_audio(caminho_arquivo):
    try:
        with open(caminho_arquivo, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3", 
                file=audio_file,
                response_format="text"
            )
        return transcription
    except Exception as e:
        print(f"Erro na transcrição: {e}")
        return ""

def limpar_texto_para_api(texto):
    """Remove acentos e troca espaços por _ para o link da API"""
    texto_sem_acento = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8')
    return texto_sem_acento.lower().replace(" ", "_")

def buscar_bncc_ultra_rapida(disciplina, turma, conteudo):
    """Busca as habilidades na API e usa o Groq para escolher a melhor em 1 segundo"""
    
    # 1. Extrai o número da turma (Ex: "5A" vira "5")
    numeros_turma = re.findall(r'\d+', turma)
    numero = numeros_turma[0] if numeros_turma else "6" 
    
    # 2. Traduz o número para a palavra exigida pela API
    mapa_anos = {
        "1": "primeiro", "2": "segundo", "3": "terceiro", "4": "quarto",
        "5": "quinto", "6": "sexto", "7": "setimo", "8": "oitavo", "9": "nono"
    }
    ano_api = mapa_anos.get(numero, "sexto") 

    # 3. Mapeamento super rigoroso para os nomes exatos da disciplina
    nome_disc = disciplina.lower()
    disc_api = "computacao" 
    
    if "portugu" in nome_disc: disc_api = "lingua_portuguesa"
    elif "arte" in nome_disc: disc_api = "arte"
    elif "física" in nome_disc or "fisica" in nome_disc: disc_api = "educacao_fisica"
    elif "ingl" in nome_disc: disc_api = "lingua_inglesa"
    elif "matem" in nome_disc: disc_api = "matematica"
    elif "ciênc" in nome_disc or "cienc" in nome_disc: disc_api = "ciencias"
    elif "geogra" in nome_disc: disc_api = "geografia"
    elif "hist" in nome_disc: disc_api = "historia"
    elif "religi" in nome_disc: disc_api = "ensino_religioso"

    # 4. Constrói o URL com a palavra por extenso!
    url = f"https://cientificar1992.pythonanywhere.com/bncc_fundamental/disciplina/{disc_api}/{ano_api}/"
    print(f"> A procurar na API: {url}")
    
    try:
        resposta = requests.get(url)
        
        # Estratégia de segurança
        if resposta.status_code != 200:
            if numero == "7":
                url = f"https://cientificar1992.pythonanywhere.com/bncc_fundamental/disciplina/{disc_api}/sétimo/"
                resposta = requests.get(url)
            else:
                resposta = requests.get(url.rstrip('/'))
                
        if resposta.status_code != 200:
            print(f"> Erro: Nao foi possivel encontrar {disc_api} do {ano_api} ano na API.")
            return ""
            
        dados_habilidades = resposta.json()
        texto_opcoes = json.dumps(dados_habilidades, ensure_ascii=False)

        prompt = f"""
        És um especialista em BNCC.
        AULA: {conteudo}
        
        OPÇÕES DE HABILIDADES DISPONÍVEIS (em formato JSON):
        {texto_opcoes}
        
        Escolhe APENAS 1 código e descrição da habilidade que melhor se encaixa nesta aula.
        Retorna no formato exato: "CÓDIGO - Descrição".
        """
        
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": prompt}],
            temperature=0
        )
        return completion.choices[0].message.content.strip()

    except Exception as e:
        print(f"> Erro na integracao com a API da BNCC: {e}")
        return ""
    
def extrair_dados_da_aula(texto_transcrito, dados_anteriores=None):
    hoje = datetime.date.today().strftime("%d/%m/%Y")
    
    opcoes_disciplinas = [
        "lingua_portuguesa", "arte", "educacao_fisica", "lingua_inglesa", 
        "matematica", "ciencias", "geografia", "historia", "ensino_religioso", "computacao"
    ]

    regras_base = f"""
    Você é um assistente escolar inteligente. Hoje é {hoje}.
    Sua missão é analisar o texto transcrito da aula e extrair os dados para um JSON.

    Estrutura EXATA do JSON que você deve retornar:
    {{
        "disciplina": "string (O nome EXATO da disciplina que o professor falar no áudio. Ex: Educação Tecnológica, História, Inglês)",
        "turma_site": "string (Apenas o número e a letra. Ex: 5A, 8B, 1C)",
        "turma_api": "string (Prefixo + Número + Letra. Ex: F5A, M1B, I2C)",
        "conteudo": "string (Resumo formal e corrigido do assunto)",
        "tarefa": "string ou 'Nenhuma'",
        "faltosos": {{"Nome_do_Aluno": 0}},
        "data": "{hoje}"
    }}
    
    REGRA DOS FALTOSOS (CRUCIAL):
    - O campo "faltosos" é um DICIONÁRIO (chave/valor).
    - Escute atentamente o áudio: se o professor disser "Noah e Joaquim faltaram", você deve trocar "Nome_do_Aluno" pelos nomes deles. O JSON DEVE ficar assim: "faltosos": {{"Noah": 0, "Joaquim": 0}}
    - O valor 0 significa falta normal.
    - O valor 1 significa falta justificada (apenas se usar a palavra "atestado" ou "justificada").
    - SE, E SOMENTE SE, O PROFESSOR NÃO FALAR DE FALTAS, retorne o dicionário vazio: "faltosos": {{}}

    REGRA DA TURMA API (MUITO IMPORTANTE):
    Você deve classificar o nível da turma e adicionar o prefixo correto no campo 'turma_api':
    - Ensino Fundamental (1º ao 9º ano): Prefixo 'F'. Ex: 5º ano A vira F5A.
    - Ensino Médio (1ª à 3ª série): Prefixo 'M'. Ex: 1ª série B vira M1B.
    - Educação Infantil (I ao V): Prefixo 'I'. Ex: Infantil II C vira I2C.
    REGRA DE NÍVEL DE ENSINO (MUITO IMPORTANTE):
    - Se o professor falar "Ano" (ex: 1º Ano, 2º Ano), é SEMPRE Ensino Fundamental. O código da turma_api DEVE começar com F (ex: F1A, F2B).
    - Se o professor falar "Série" (ex: 1ª Série, 2ª Série), é SEMPRE Ensino Médio. O código da turma_api DEVE começar com M (ex: M1A, M2A).
    - Nunca confunda "Ano" com Ensino Médio. Se o professor disser "1º Ano", NÃO use M1A, use F1A. Se disser "2ª Série", NÃO use F2A, use M2A.
    - Se o professor disser "Infantil", use o prefixo I (ex: I2C para Infantil II C).
    
    REGRAS DE ESTILO E FORMATAÇÃO:
    - CONTEÚDO E TAREFA: Reescreva o relato num resumo profissional, objetivo e na norma-padrão.
    - Remova gírias e vícios de linguagem.
    - Se não houver tarefa citada, use "Nenhuma".
    
    REGRA DA DISCIPLINA (CRUCIAL):
    1º Passo: Ouça com atenção se o professor ditar o nome da disciplina no áudio (Ex: 'Aula de educação tecnológica...', 'Aula de inglês...'). Caso ele não cite o nome, deduza a matéria com base nos termos técnicos (ex: verbos = português, robôs = tecnologia).
    2º Passo: Para montar o JSON, você DEVE OBRIGATORIAMENTE converter a matéria identificada para APENAS UMA destas 10 strings exatas (exigidas pela API da BNCC):
    - Educação Tecnológica, Robótica, Programação, Computadores -> "computacao"
    - Língua Portuguesa, Gramática, Literatura, Redação -> "lingua_portuguesa"
    - Matemática, Cálculos, Geometria, Números -> "matematica"
    - Ciências, Biologia, Física, Química, Células -> "ciencias"
    - Geografia, Mapas, Relevo, Clima -> "geografia"
    - História, Passado, Guerras, Sociedade -> "historia"
    - Inglês, Língua Inglesa, Verb to be -> "lingua_inglesa"
    - Arte, Pintura, Música, Teatro -> "arte"
    - Educação Física, Esportes, Jogos -> "educacao_fisica"
    - Ensino Religioso, Ética, Valores, Religião -> "ensino_religioso"
    """

    if not dados_anteriores:
        prompt_sistema = f"Você é um assistente escolar. Hoje é {hoje}. Extraia dados da aula para um JSON.\n{regras_base}"
    else:
        prompt_sistema = f"""
        Você é um assistente escolar. O professor enviou uma ATUALIZAÇÃO.
        
        DADOS ATUAIS: {json.dumps(dados_anteriores, ensure_ascii=False)}
        NOVO COMANDO: "{texto_transcrito}"
        
        TAREFA: Atualize o JSON modificando APENAS o que o professor pediu. 
        Se o professor mudou o conteúdo, REAVALIE a disciplina para ver se mudou também.
        Mantenha o que não foi alterado. Retorne APENAS o JSON.
        
        {regras_base}
        """

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": f"Entrada: {texto_transcrito}"}],
            temperature=0, response_format={"type": "json_object"}
        )
        dados_aula = json.loads(completion.choices[0].message.content)
        # ... código existente ...
        dados_aula = json.loads(completion.choices[0].message.content)
        
        # COLE ESTAS DUAS LINHAS AQUI PARA O NOSSO RAIO-X:
        print(f"\n🔴 RAIO-X 1 (O que a IA ouviu): {texto_transcrito}")
        print(f"🔴 RAIO-X 2 (O JSON que a IA gerou): {dados_aula}\n")
        
        # --- O GATILHO INTELIGENTE DA BNCC ---
        # ... resto do código ...
        # --- O GATILHO INTELIGENTE DA BNCC ---
        buscar_bncc = False
        
        if not dados_anteriores or 'bncc' not in dados_anteriores:
            buscar_bncc = True  
        else:
            mudou_conteudo = dados_aula.get('conteudo') != dados_anteriores.get('conteudo')
            mudou_turma = dados_aula.get('turma_site') != dados_anteriores.get('turma_site')
            mudou_disciplina = dados_aula.get('disciplina') != dados_anteriores.get('disciplina')
            
            if mudou_conteudo or mudou_turma or mudou_disciplina:
                buscar_bncc = True
                print("> Mudanca detectada! Buscando nova habilidade na BNCC...")

        if buscar_bncc:
            disciplina = dados_aula.get('disciplina', '')
            if disciplina:
                resultado_bncc = buscar_bncc_ultra_rapida(disciplina, dados_aula.get('turma_site', ''), dados_aula.get('conteudo'))
                if resultado_bncc:
                    dados_aula['bncc'] = resultado_bncc
        elif dados_anteriores and 'bncc' in dados_anteriores:
            dados_aula['bncc'] = dados_anteriores['bncc']
                    
        return dados_aula
    except Exception as e:
        print(f"Erro na inteligencia: {e}")
        return None

def resolver_ambiguidade(texto_usuario, dicionario_conflitos, faltosos_atuais):
    prompt = f"""
    Você é um assistente especialista em resolver ambiguidades de nomes em listas de chamadas.
    
    FALTAS ORIGINAIS (Status: 0 = Falta Normal, 1 = Falta Justificada): 
    {json.dumps(faltosos_atuais, ensure_ascii=False)}
    
    CONFLITOS ENCONTRADOS (Nome curto -> Opções reais na chamada): 
    {json.dumps(dicionario_conflitos, ensure_ascii=False)}
    
    ÁUDIO/RESPOSTA DO PROFESSOR: 
    "{texto_usuario}"
    
    REGRAS CRUCIAIS DE EXTRAÇÃO:
    1. Identifique exatamente quais opções completas o professor escolheu baseando-se no dicionário de conflitos.
    2. Tenha flexibilidade com a escrita (ex: se o professor disser "Antônia", cruze com "ANTONYA"; se disser "Eduarda", cruze com "MARIA EDUARDA").
    3. Um mesmo nome curto pode ter se desdobrado em múltiplos alunos (ex: o professor escolheu a Maria Antonya E a Maria Eduarda).
    4. MANTENHA O VALOR DA FALTA (0 ou 1) ESTRITAMENTE IGUAL ao que estava no JSON de Faltas Originais. NUNCA invente justificativas (mudar 0 para 1).
    5. O seu retorno DEVE ser EXCLUSIVAMENTE um objeto JSON contendo apenas as chaves dos nomes completos finais e seus valores inteiros.
    
    EXEMPLO DE RETORNO OBRIGATÓRIO (MOLDE):
    {{
        "LARA MARIA MORAIS MELO": 0,
        "MARIA ANTONYA ALCANTARA FERNANDES": 0,
        "MARIA EDUARDA RODRIGUES PEREIRA": 0
    }}
    
    Se o professor tiver respondido algo totalmente sem sentido que não ajude a identificar os alunos, retorne {{"erro": "invalido"}}.
    """
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": prompt}],
            temperature=0, 
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"Erro ao desambiguar: {e}")
        return {"erro": "invalido"}

def traduzir_nomes_para_chamada(faltosos_extraidos, lista_oficial_alunos):
    """
    Recebe os nomes brutos extraídos do áudio e cruza com a lista oficial da turma.
    Devolve um dicionário limpo com os números da chamada.
    """
    # Se não houver faltosos citados, já retorna vazio e economiza API
    if not faltosos_extraidos or faltosos_extraidos == "Nenhuma":
        return {"F": [], "J": []}

    prompt_tradutor = f"""
    Você é um assistente escolar especialista em cruzamento de dados.

    LISTA OFICIAL DA TURMA:
    {json.dumps(lista_oficial_alunos, ensure_ascii=False)}

    ALUNOS CITADOS COMO AUSENTES NO ÁUDIO:
    {json.dumps(faltosos_extraidos, ensure_ascii=False)}

    SUA MISSÃO:
    1. Para cada aluno citado, procure-o na lista oficial.
    2. Se houver MAIS DE UM aluno que possa corresponder ao nome (Ex: citado "Maria" e existem 4 Marias na lista), NÃO adicione na falta. Coloque o nome na chave "ambiguos", e como valor uma lista de strings com todos os nomes completos possíveis achados.
    3. Se encontrar apenas UMA correspondência clara, adicione o NÚMERO DA CHAMADA na lista "F" ou "J".
    4. Se não encontrar de jeito nenhum, adicione na lista "nao_encontrados".

    Você deve retornar EXCLUSIVAMENTE um objeto JSON no formato:
    {{
        "F": [array de números da chamada (apenas correspondência exata e única)],
        "J": [array de números da chamada (justificadas)],
        "nao_encontrados": [array de strings com nomes não achados],
        "ambiguos": {{
            "Nome Citado": ["Nome Completo 1", "Nome Completo 2", "Nome Completo 3"]
        }}
    }}
    """

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": prompt_tradutor}],
            temperature=0, # Temperatura 0 é vital aqui para ele não "alucinar" números
            response_format={"type": "json_object"}
        )
        resultado_json = json.loads(completion.choices[0].message.content)
        return resultado_json
        
    except Exception as e:
        print(f"Erro na tradução de faltosos: {e}")
        return {"F": [], "J": [], "nao_encontrados": []}