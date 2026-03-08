import os
import json
import datetime
import httpx
import re
import unicodedata
from google import genai
from google.genai import types
import sys
sys.stdout.reconfigure(encoding='utf-8')

# --- ⚙️ CONFIGURAÇÕES DAS APIS ---
GEMINI_API_KEY = "AIzaSyBqpzahCaSPI4P7QZyVWxTluAsmnpJOfCg" 
client = genai.Client(api_key=GEMINI_API_KEY)

# --- 🚀 SISTEMA DE CACHE DA BNCC ---
ARQUIVO_CACHE_BNCC = "cache_bncc.json"

def carregar_cache_bncc():
    if os.path.exists(ARQUIVO_CACHE_BNCC):
        try:
            with open(ARQUIVO_CACHE_BNCC, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def salvar_cache_bncc(cache):
    try:
        with open(ARQUIVO_CACHE_BNCC, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=4, ensure_ascii=False)
    except: pass

# ------------------------------------

async def transcrever_audio(caminho_arquivo):
    """ Mantido apenas para quando o professor mandar áudio curto para resolver as Marias """
    try:
        with open(caminho_arquivo, "rb") as f:
            audio_bytes = f.read()
            
        prompt = "Transcreva o áudio exatamente como foi dito. Apenas o texto do áudio."
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=[types.Part.from_bytes(data=audio_bytes, mime_type='audio/mp4'), prompt]
        )   
        return response.text
    except Exception as e:
        print(f"Erro na transcrição: {e}")
        return ""

def limpar_texto_para_api(texto):
    texto_sem_acento = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8')
    return texto_sem_acento.lower().replace(" ", "_")

async def buscar_bncc_ultra_rapida(disciplina, turma, conteudo):
    if not disciplina or not conteudo: return ""
    
    # ⚡ 1. VERIFICA O CACHE ANTES DE IR PRA NUVEM!
    cache = carregar_cache_bncc()
    chave_busca = limpar_texto_para_api(f"{disciplina}_{turma}_{conteudo[:30]}")
    
    if chave_busca in cache:
        print("\n> ⚡ [VELOCIDADE DA LUZ] BNCC encontrada no Cache Local!")
        return cache[chave_busca]

    # 2. Se não tem no cache, busca na API normal...
    numeros_turma = re.findall(r'\d+', turma)
    numero = numeros_turma[0] if numeros_turma else "6" 
    
    mapa_anos = {"1": "primeiro", "2": "segundo", "3": "terceiro", "4": "quarto", "5": "quinto", "6": "sexto", "7": "setimo", "8": "oitavo", "9": "nono"}
    ano_api = mapa_anos.get(numero, "sexto") 
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

    url = f"https://cientificar1992.pythonanywhere.com/bncc_fundamental/disciplina/{disc_api}/{ano_api}/"
    print(f"\n> 🐢 [INDO NA NUVEM] Procurando BNCC na API: {url}")
    
    try:
        async with httpx.AsyncClient() as http_client:
            resposta = await http_client.get(url)
            if resposta.status_code != 200:
                if numero == "7":
                    url = f"https://cientificar1992.pythonanywhere.com/bncc_fundamental/disciplina/{disc_api}/sétimo/"
                    resposta = await http_client.get(url)
                else:
                    resposta = await http_client.get(url.rstrip('/'))
                    
            if resposta.status_code != 200: return ""
            texto_opcoes = json.dumps(resposta.json(), ensure_ascii=False)

        prompt = f"""
        És um especialista em BNCC. AULA: {conteudo}
        OPÇÕES DE HABILIDADES DISPONÍVEIS: {texto_opcoes}
        Escolhe APENAS 1 código e descrição que melhor se encaixa nesta aula.
        Retorna no formato exato: "CÓDIGO - Descrição".
        """
        
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0)
        )
        resultado_final = response.text.strip()
        
        # 💾 Salva o resultado no Cache para a próxima vez!
        cache[chave_busca] = resultado_final
        salvar_cache_bncc(cache)
        
        return resultado_final

    except Exception as e: return ""
    
async def extrair_dados_da_aula(caminho_arquivo_audio, dados_anteriores=None):
    hoje = datetime.date.today().strftime("%d/%m/%Y")
    
    regras_base = f"""
    Você é um assistente escolar inteligente. Hoje é {hoje}.
    Sua missão é OUVIR o áudio e extrair os dados para um JSON.

    Estrutura EXATA do JSON:
    {{
        "disciplina": "string",
        "turma_site": "string (Apenas número e letra. Ex: 5A)",
        "turma_api": "string (Prefixo F, M ou I + Número + Letra. Ex: F5A)",
        "conteudo": "string",
        "tarefa": "string ou 'Nenhuma'",
        "faltosos": {{"Nome_do_Aluno": 0}},
        "data": "{hoje}"
    }}
    
    REGRA DOS FALTOSOS: Se o professor disser ausências, retorne {{"Noah": 0, "Joaquim": 0}}. Se justificada, valor 1. Se não falar de faltas, retorne vazio {{}}.
    REGRA DA DISCIPLINA: Mapeie para (computacao, lingua_portuguesa, matematica, ciencias, geografia, historia, lingua_inglesa, arte, educacao_fisica, ensino_religioso).
    """

    if not dados_anteriores:
        prompt_sistema = f"Você é um assistente escolar. Ouça o áudio e extraia os dados para um JSON.\n{regras_base}"
    else:
        prompt_sistema = f"""
        O professor enviou uma ATUALIZAÇÃO EM ÁUDIO.
        DADOS ATUAIS: {json.dumps(dados_anteriores, ensure_ascii=False)}
        TAREFA: Ouça o áudio e atualize o JSON modificando APENAS o que o professor pediu.
        {regras_base}
        """

    try:
        with open(caminho_arquivo_audio, "rb") as f:
            audio_bytes = f.read()

        # 🚀 AQUI ESTÁ A MAGIA MULTIMODAL: Enviando o áudio e o Prompt juntos!
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type='audio/mp4'),
                prompt_sistema
            ],
            config=types.GenerateContentConfig(temperature=0, response_mime_type="application/json")
        )
        dados_aula = json.loads(response.text)
        print(f"\n🔴 RAIO-X MULTIMODAL (O JSON gerado direto do áudio): {dados_aula}\n")
        return dados_aula
    except Exception as e:
        print(f"Erro na inteligencia multimodal: {e}")
        return None

async def resolver_ambiguidade(entrada_usuario, dicionario_conflitos, faltosos_atuais):
    prompt = f"""
    Você é um assistente cirúrgico na resolução de conflitos de nomes em listas de presença.
    FALTAS ORIGINAIS (0 = Falta, 1 = Justificada): {json.dumps(faltosos_atuais, ensure_ascii=False)}
    DICIONÁRIO DE CONFLITOS: {json.dumps(dicionario_conflitos, ensure_ascii=False)}
    
    REGRAS DE EXTRAÇÃO:
    1. Extraia TODOS os alunos mencionados pelo professor (no áudio ou texto).
    2. ⚠️ ALERTA DE NOME COMPOSTO: Preste muita atenção a nomes como "Lara Maria". Mapeie para a opção completa dela.
    3. Mantenha o valor (0 ou 1) que o nome curto tinha nas FALTAS ORIGINAIS.
    4. Retorne APENAS um JSON com os NOMES COMPLETOS resolvidos como chaves, e o status como valor. NUNCA crie chaves extras.
    """
    try:
        if entrada_usuario.endswith('.m4a'): # Se for áudio, ele escuta direto!
            with open(entrada_usuario, "rb") as f: audio_bytes = f.read()
            contents = [types.Part.from_bytes(data=audio_bytes, mime_type='audio/mp4'), prompt, "Ouça o áudio e resolva o conflito com base no dicionário."]
        else: # Se for texto digitado, ele lê normal
            contents = [prompt, f'RESPOSTA DO PROFESSOR: "{entrada_usuario}"']
            
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash', contents=contents,
            config=types.GenerateContentConfig(temperature=0, response_mime_type="application/json")
        )
        return json.loads(response.text.strip())
    except Exception as e: return {"erro": "invalido"}

async def traduzir_nomes_para_chamada(faltosos_extraidos, lista_oficial_alunos):
    if not faltosos_extraidos or faltosos_extraidos == "Nenhuma":
        return {"F": [], "J": [], "nao_encontrados": [], "ambiguos": {}}

    prompt_tradutor = f"""
    Você é um assistente escolar especialista em cruzamento de dados.
    LISTA OFICIAL: {json.dumps(lista_oficial_alunos, ensure_ascii=False)}
    ALUNOS CITADOS: {json.dumps(faltosos_extraidos, ensure_ascii=False)}

    PASSO A PASSO OBRIGATÓRIO:
    1. Leia TODOS os alunos citados.
    2. Se tiver MAIS DE UM aluno correspondente, coloque na chave "ambiguos" com as opções.
    3. Se tiver APENAS UMA correspondência, coloque o 'numero_chamada' na lista "F" (se 0) ou "J" (se 1).
    4. Se não achar, coloque em "nao_encontrados".

    RETORNO OBRIGATÓRIO (JSON puro):
    {{ "F": [], "J": [], "nao_encontrados": [], "ambiguos": {{"Nome": ["Opcao 1", "Opcao 2"]}} }}
    """
    try:
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_tradutor,
            config=types.GenerateContentConfig(temperature=0, response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception: return {"F": [], "J": [], "nao_encontrados": [], "ambiguos": {}}