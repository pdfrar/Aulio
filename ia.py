import os
import json
import datetime
from groq import Groq
from google import genai  # <-- NOVA BIBLIOTECA AQUI!

# --- ⚙️ CONFIGURAÇÕES DAS APIS ---
GROQ_API_KEY = "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" 
GEMINI_API_KEY = "AIzaSyBqpzahCaSPI4P7QZyVWxTluAsmnpJOfCg"

ARQUIVO_BNCC_NUVEM = None  # <--- ADICIONE ESTA LINHA AQUI
client = Groq(api_key=GROQ_API_KEY)
gemini_client = genai.Client(api_key=GEMINI_API_KEY) # <-- NOVO CLIENTE GEMINI

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

import os
import json
import datetime
import requests
import re
import unicodedata
from groq import Groq

# ... (Suas configurações de API e transcrever_audio continuam iguais) ...

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
        "1": "primeiro",
        "2": "segundo",
        "3": "terceiro",
        "4": "quarto",
        "5": "quinto",
        "6": "sexto",
        "7": "setimo", # Maioria dos URLs não usa acento, mas tratamos isso abaixo se falhar
        "8": "oitavo",
        "9": "nono"
    }
    ano_api = mapa_anos.get(numero, "sexto") # Se não encontrar, usa "sexto" como padrão

    # 3. Mapeamento super rigoroso para os nomes exatos da disciplina
    nome_disc = disciplina.lower()
    disc_api = "computacao" # Padrão de segurança
    
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
    print(f"⚡ A procurar na API: {url}")
    
    try:
        resposta = requests.get(url)
        
        # Estratégia de segurança: tenta com acento no "sétimo" ou sem barra no final se a primeira tentativa falhar
        if resposta.status_code != 200:
            if numero == "7":
                url = f"https://cientificar1992.pythonanywhere.com/bncc_fundamental/disciplina/{disc_api}/sétimo/"
                resposta = requests.get(url)
            else:
                resposta = requests.get(url.rstrip('/'))
                
        if resposta.status_code != 200:
            print(f"⚠️ Erro: Não foi possível encontrar {disc_api} do {ano_api} ano na API.")
            return ""
            
        dados_habilidades = resposta.json()
        
        # Transforma o resultado da API num texto para a Inteligência ler
        texto_opcoes = json.dumps(dados_habilidades, ensure_ascii=False)

        # 5. Pede ao Llama 3 (Groq) para escolher a melhor habilidade
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
        print(f"❌ Erro na integração com a API da BNCC: {e}")
        return ""
    
def extrair_dados_da_aula(texto_transcrito, dados_anteriores=None):
    hoje = datetime.date.today().strftime("%d/%m/%Y")
    
    # Centralizamos as regras para a IA não esquecer delas na hora da correção
    regras_base = f"""
    Você é um assistente escolar. Hoje é {hoje}.
    Extraia dados da aula para um JSON seguindo EXATAMENTE esta estrutura:
    {{
        "disciplina": "Adivinhe a disciplina. Retorne EXATAMENTE UMA destas opções: lingua_portuguesa, arte, educacao_fisica, lingua_inglesa, matematica, ciencias, geografia, historia, ensino_religioso, computacao",
        "turma": "string (Ex: 5A, 8B, 9C)",
        "conteudo": "string (Resumo formal do assunto)",
        "tarefa": "string ou 'Nenhuma'",
        "faltosos": {{"nome_do_aluno": 0 ou 1}},
        "data": "{hoje}"
    }}
    
    REGRAS DE ESTILO E FORMATAÇÃO (MUITO IMPORTANTE):
    - CONTEÚDO E TAREFA: Não transcreva literalmente o que o professor falou. Reescreva o relato transformando-o num resumo profissional, objetivo e estritamente redigido na norma-padrão da língua portuguesa. 
    - Corrija erros de concordância, remova hesitações, gírias ou vícios de linguagem falada.
    - Se o professor não mencionar tarefa de casa, o valor do campo "tarefa" DEVE ser a palavra "Nenhuma".
    
    REGRA DA DISCIPLINA: Se o assunto envolver robótica, programação, circuitos ou tecnologia, o valor DEVE ser "computacao".
    
    REGRA DOS FALTOSOS: O padrão é 0 (Normal). Só use 1 se a falta for justificada ("atestado", "doente", etc).
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
        
        # --- O GATILHO INTELIGENTE DA BNCC ---
        buscar_bncc = False
        
        if not dados_anteriores or 'bncc' not in dados_anteriores:
            buscar_bncc = True  # É a primeira vez, busca a BNCC!
        else:
            # Verifica se o professor alterou algo que impacte a BNCC
            mudou_conteudo = dados_aula.get('conteudo') != dados_anteriores.get('conteudo')
            mudou_turma = dados_aula.get('turma') != dados_anteriores.get('turma')
            mudou_disciplina = dados_aula.get('disciplina') != dados_anteriores.get('disciplina')
            
            if mudou_conteudo or mudou_turma or mudou_disciplina:
                buscar_bncc = True
                print("🔄 Mudança detectada! Buscando nova habilidade na BNCC...")

        # Executa a busca se o gatilho foi ativado
        if buscar_bncc:
            disciplina = dados_aula.get('disciplina', '')
            if disciplina:
                resultado_bncc = buscar_bncc_ultra_rapida(disciplina, dados_aula.get('turma'), dados_aula.get('conteudo'))
                if resultado_bncc:
                    dados_aula['bncc'] = resultado_bncc
        elif dados_anteriores and 'bncc' in dados_anteriores:
            # Se foi só uma correção de faltas, mantém a BNCC que já estava lá
            dados_aula['bncc'] = dados_anteriores['bncc']
                    
        return dados_aula
    except Exception as e:
        print(f"Erro na inteligência: {e}")
        return None

def resolver_ambiguidade(texto_usuario, dicionario_conflitos, faltosos_atuais):
    prompt = f"""
    O professor relatou faltosos, mas há alunos com o mesmo nome na sala.
    
    FALTOSOS ORIGINAIS COM ERRO: {json.dumps(faltosos_atuais, ensure_ascii=False)}
    CONFLITOS DETECTADOS: {json.dumps(dicionario_conflitos, ensure_ascii=False)}
    RESPOSTA DO PROFESSOR: "{texto_usuario}"
    
    SUA TAREFA:
    Substitua os nomes no dicionário pelo NOME COMPLETO DO ALUNO correto escolhido pelo professor.
    MANTENHA OS VALORES (0 ou 1) ORIGINAIS (0=Normal, 1=Justificada) para cada aluno.
    Retorne APENAS o JSON dos faltosos atualizado.
    """
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": prompt}],
            temperature=0, response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"Erro ao desambiguar: {e}")
        return faltosos_atuais