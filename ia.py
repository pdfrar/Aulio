import os
import json
import datetime
import httpx
import re
import unicodedata
from groq import AsyncGroq
from dotenv import load_dotenv  # <--- ADICIONE ISSO
import sys
sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()
# --- ⚙️ CONFIGURAÇÕES DAS APIS ---
# O Groq vai puxar automaticamente do seu arquivo .env a variável GROQ_API_KEY
API_KEY = os.getenv("GROQ_API_KEY")
client = AsyncGroq(api_key=API_KEY)

MODELO_AUDIO = "whisper-large-v3"
MODELO_TEXTO = "llama-3.3-70b-versatile"

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

def limpar_texto_para_api(texto):
    texto_sem_acento = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8')
    return texto_sem_acento.lower().replace(" ", "_")

# ------------------------------------
# 1. OS OUVIDOS (Whisper)
# ------------------------------------
async def transcrever_audio(caminho_arquivo):
    """ O Groq Whisper transforma o áudio em texto em milissegundos """
    try:
        with open(caminho_arquivo, "rb") as file:
            transcricao = await client.audio.transcriptions.create(
                file=(caminho_arquivo, file.read()),
                model=MODELO_AUDIO,
                language="pt",
                response_format="json"
            )
        return transcricao.text
    except Exception as e:
        print(f"Erro na transcrição Whisper: {e}")
        return ""

# ------------------------------------
# 2. O CÉREBRO (LLaMA 3.1)
# ------------------------------------
async def buscar_bncc_ultra_rapida(disciplina, turma_api, conteudo):
    if not disciplina or not conteudo: return ""
    
    cache = carregar_cache_bncc()
    chave_busca = limpar_texto_para_api(f"{disciplina}_{turma_api}_{conteudo[:30]}")
    
    if chave_busca in cache:
        print("\n> ⚡ [VELOCIDADE DA LUZ] BNCC encontrada no Cache Local!")
        return cache[chave_busca]

    nivel = turma_api[0].upper() if turma_api else 'F'
    numeros_turma = re.findall(r'\d+', turma_api)
    numero = numeros_turma[0] if numeros_turma else "6" 

    url = ""
    
    # [A lógica de mapeamento da URL continua exatamente a mesma]
    if nivel == 'I':
        if numero in ["1", "2", "3"]: ano_api = "bem_pequenas"
        elif numero in ["4", "5", "6"]: ano_api = "pequenas"
        else: ano_api = "pequenas"
        
        cont_lower = conteudo.lower()
        if any(x in cont_lower for x in ["letra", "palavra", "história", "fala", "escuta", "leitura", "alfabeto", "vogal"]): campo = "escuta"
        elif any(x in cont_lower for x in ["número", "conta", "quantidade", "espaço", "tempo", "matemática", "forma"]): campo = "espacos"
        elif any(x in cont_lower for x in ["corpo", "movimento", "dança", "pular", "correr", "esporte"]): campo = "corpo"
        elif any(x in cont_lower for x in ["cor", "desenho", "pintar", "som", "música", "traço", "arte"]): campo = "tracos"
        else: campo = "escuta"
            
        url = f"https://cientificar1992.pythonanywhere.com/bncc_infantil/campo/{campo}/{ano_api}/"

    elif nivel == 'M':
        nome_disc = disciplina.lower()
        if "portugu" in nome_disc or "redaç" in nome_disc: disc_api = "lingua_portuguesa_medio"
        elif "matem" in nome_disc: disc_api = "matematica_medio"
        elif "ciênc" in nome_disc or "químic" in nome_disc or "biologia" in nome_disc: disc_api = "ciencias_natureza"
        elif "hist" in nome_disc or "geogra" in nome_disc or "sociologia" in nome_disc or "filosofia" in nome_disc: disc_api = "ciencias_humanas"
        elif "arte" in nome_disc or "física" in nome_disc or "ingl" in nome_disc: disc_api = "linguagens"
        else: disc_api = "computacao_medio"
        
        url = f"https://cientificar1992.pythonanywhere.com/bncc_medio/disciplina/{disc_api}/"

    else: 
        mapa_anos = {"1": "primeiro", "2": "segundo", "3": "terceiro", "4": "quarto", "5": "quinto", "6": "sexto", "7": "setimo", "8": "oitavo", "9": "nono", "7a": "sétimo"}
        ano_api = mapa_anos.get(numero, "sexto") 
        nome_disc = disciplina.lower()
        
        if "portugu" in nome_disc: disc_api = "lingua_portuguesa"
        elif "arte" in nome_disc: disc_api = "arte"
        elif "física" in nome_disc or "fisica" in nome_disc: disc_api = "educacao_fisica"
        elif "ingl" in nome_disc: disc_api = "lingua_inglesa"
        elif "matem" in nome_disc: disc_api = "matematica"
        elif "ciênc" in nome_disc or "cienc" in nome_disc: disc_api = "ciencias"
        elif "geogra" in nome_disc: disc_api = "geografia"
        elif "hist" in nome_disc: disc_api = "historia"
        elif "religi" in nome_disc: disc_api = "ensino_religioso"
        else: disc_api = "computacao"

        url = f"https://cientificar1992.pythonanywhere.com/bncc_fundamental/disciplina/{disc_api}/{ano_api}/"

    print(f"\n> 🐢 [INDO NA NUVEM] Procurando BNCC na API: {url}")
    
    try:
        async with httpx.AsyncClient() as http_client:
            resposta = await http_client.get(url)
            if resposta.status_code != 200 and nivel == 'F' and numero == "7":
                url_fallback = f"https://cientificar1992.pythonanywhere.com/bncc_fundamental/disciplina/{disc_api}/sétimo/"
                resposta = await http_client.get(url_fallback)
            elif resposta.status_code != 200:
                resposta = await http_client.get(url.rstrip('/'))
                
            if resposta.status_code != 200: return ""
            texto_opcoes = json.dumps(resposta.json(), ensure_ascii=False)

        prompt = f"""
        Você é um especialista em BNCC. AULA: {conteudo}
        OPÇÕES DE HABILIDADES DISPONÍVEIS: {texto_opcoes}
        Escolha APENAS 1 código e descrição que melhor se encaixa nesta aula.
        Retorne apenas o texto limpo no formato exato: "CÓDIGO - Descrição".
        """
        
        response = await client.chat.completions.create(
            model=MODELO_TEXTO,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        resultado_final = response.choices[0].message.content.strip()
        
        cache[chave_busca] = resultado_final
        salvar_cache_bncc(cache)
        return resultado_final

    except Exception as e: 
        print(f"Erro na busca da BNCC: {e}")
        return ""
    
async def extrair_dados_da_aula(caminho_arquivo_audio, dados_anteriores=None):
    hoje = datetime.date.today().strftime("%d/%m/%Y")
    
    # PASSO 1: Ouvir o áudio com o Whisper
    texto_audio = await transcrever_audio(caminho_arquivo_audio)
    if not texto_audio:
        print("Erro: Whisper não conseguiu ouvir o áudio.")
        return None

    # PASSO 2: Analisar o texto com a LLaMA
    regras_base = f"""
    Você é um assistente escolar inteligente. Hoje é {hoje}.
    Sua missão é ler a transcrição do áudio do professor e extrair os dados para um JSON.

    Estrutura EXATA e OBRIGATÓRIA do JSON:
    {{
        "disciplina": "string (Ex: Educação Tecnológica. Se for Infantil, mantenha exato: Aprendizagem e Desenvolvimento)",
        "turma_site": "string (Apenas número e letra. Ex: 5A, 4C)",
        "turma_api": "string (Prefixo F, M ou I + Número + Letra. Ex: F5A, I4C)",
        "conteudo": "string formatado na norma culta",
        "tarefa": "string ou 'Nenhuma' formatado na norma culta",
        "faltosos": {{"Nome_do_Aluno": "0 ou 1"}},
        "data": "{hoje}"
    }}
    
    REGRA DOS FALTOSOS (MUITO IMPORTANTE): 
    - Falta normal = 0. Falta justificada = 1.
    - Exemplo: Se faltaram Noah (normal) e Joaquim (justificada), retorne {{"Noah": 0, "Joaquim": 1}}. Se não houver faltas, retorne {{}}.
    - SE FOR UMA ATUALIZAÇÃO: Se o professor pedir para justificar a falta de alguém que já estava na lista, você OBRIGATORIAMENTE deve mudar o valor dessa pessoa de 0 para 1.
    
    REGRA DA DISCIPLINA (CRÍTICO): 
    - Ensino Fundamental/Médio: Mapeie para (computacao, lingua_portuguesa, matematica, ciencias, geografia, historia, lingua_inglesa, arte, educacao_fisica, ensino_religioso).
    - Educação Infantil: NÃO MAPEIE. Escreva o nome exato falado.
    
    REGRA DE VOCABULÁRIO TÉCNICO: 
    - Se a disciplina for Robótica, Computação, Inteligência Artificial ou Tecnologia, e o áudio falar de "gráficos", "grafos" ou "grafos e aplicações", CORRIJA OBRIGATORIAMENTE o conteúdo para a palavra "Grafos".
    
    REGRA DA TURMA API (ALERTA MÁXIMO):
    - Se o professor disser a palavra "INFANTIL": A turma_api DEVE OBRIGATORIAMENTE começar com 'I' (Ex: I4C). PROIBIDO usar a palavra "Ano" para turmas do Infantil.
    - Se o professor disser "ANO" (Ex: 5º Ano): Prefixo 'F' (Ex: F5A).
    - Se o professor disser "SÉRIE" (Ex: 1ª Série): Prefixo 'M' (Ex: M1B).
    """

    if not dados_anteriores:
        prompt_sistema = f"{regras_base}\n\nTRANSCRIÇÃO DO ÁUDIO:\n\"{texto_audio}\""
    else:
        prompt_sistema = f"""
        O professor enviou uma ATUALIZAÇÃO.
        DADOS ATUAIS: {json.dumps(dados_anteriores, ensure_ascii=False)}
        NOVA TRANSCRIÇÃO: "{texto_audio}"
        TAREFA: Atualize o JSON modificando APENAS o que o professor pediu na nova transcrição.
        {regras_base}
        """

    try:
        # A Mágica do Groq: Forçando o output a ser um JSON válido nativamente
        response = await client.chat.completions.create(
            model=MODELO_TEXTO,
            messages=[
                {"role": "system", "content": "Você é uma API de extração de dados que responde exclusivamente em JSON."},
                {"role": "user", "content": prompt_sistema}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        
        dados_aula = json.loads(response.choices[0].message.content)
        print(f"\n🔴 RAIO-X LLaMA (O JSON gerado do texto): {dados_aula}\n")
        
        buscar_bncc = False
        if not dados_anteriores or 'bncc' not in dados_anteriores:
            buscar_bncc = True  
        else:
            mudou_conteudo = dados_aula.get('conteudo') != dados_anteriores.get('conteudo')
            mudou_turma = dados_aula.get('turma_site') != dados_anteriores.get('turma_site')
            mudou_disciplina = dados_aula.get('disciplina') != dados_anteriores.get('disciplina')
            if mudou_conteudo or mudou_turma or mudou_disciplina:
                buscar_bncc = True

        if buscar_bncc:
            disciplina = dados_aula.get('disciplina', '')
            if disciplina:
                resultado_bncc = await buscar_bncc_ultra_rapida(disciplina, dados_aula.get('turma_api', ''), dados_aula.get('conteudo'))
                if resultado_bncc:
                    dados_aula['bncc'] = resultado_bncc
        elif dados_anteriores and 'bncc' in dados_anteriores:
            dados_aula['bncc'] = dados_anteriores['bncc']
                    
        return dados_aula
    except Exception as e:
        print(f"Erro na inteligencia da LLaMA: {e}")
        return None

async def resolver_ambiguidade(entrada_usuario, dicionario_conflitos, faltosos_atuais):
    try:
        # Se for áudio, passa no Whisper primeiro
        if entrada_usuario.endswith('.m4a'):
            texto_professor = await transcrever_audio(entrada_usuario)
        else:
            texto_professor = entrada_usuario

        prompt = f"""
        Você é um assistente cirúrgico na resolução de conflitos de nomes em listas de presença. Responda EXCLUSIVAMENTE em formato JSON.
        FALTAS ORIGINAIS (0 = Falta, 1 = Justificada): {json.dumps(faltosos_atuais, ensure_ascii=False)}
        DICIONÁRIO DE CONFLITOS: {json.dumps(dicionario_conflitos, ensure_ascii=False)}
        RESPOSTA DO PROFESSOR: "{texto_professor}"
        
        REGRAS DE EXTRAÇÃO:
        1. Extraia TODOS os alunos mencionados pelo professor na resposta.
        2. Mapeie para a opção completa do DICIONÁRIO DE CONFLITOS.
        3. Mantenha o valor (0 ou 1) que o nome curto tinha nas FALTAS ORIGINAIS.
        4. Retorne APENAS um JSON com os NOMES COMPLETOS resolvidos como chaves, e o status como valor. NUNCA crie chaves extras.
        """
        
        response = await client.chat.completions.create(
            model=MODELO_TEXTO,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e: 
        print(f"Erro ao resolver ambiguidade: {e}")
        return {"erro": "invalido"}

async def traduzir_nomes_para_chamada(faltosos_extraidos, lista_oficial_alunos):
    if not faltosos_extraidos or faltosos_extraidos == "Nenhuma":
        return {"F": [], "J": [], "nao_encontrados": [], "ambiguos": {}}

    prompt_tradutor = f"""
    Você é um sistema computacional. Responda EXCLUSIVAMENTE em formato JSON.
    É ESTRITAMENTE PROIBIDO EXPLICAR SEU RACIOCÍNIO. NÃO ESCREVA TEXTO FORA DO JSON.
    NÃO CRIE CHAVES QUE SEJAM FRASES OU JUSTIFICATIVAS. AS CHAVES DEVEM SER APENAS OS NOMES DOS ALUNOS.
    
    LISTA OFICIAL: {json.dumps(lista_oficial_alunos, ensure_ascii=False)}
    ALUNOS CITADOS E STATUS (0 = Falta, 1 = Justificada): {json.dumps(faltosos_extraidos, ensure_ascii=False)}

    PASSO A PASSO OBRIGATÓRIO (APLIQUE SILENCIOSAMENTE):
    1. Leia os nomes em ALUNOS CITADOS. O número associado a cada nome é o STATUS da falta (0 ou 1).
    2. FAÇA CORRESPONDÊNCIA PARCIAL: procure na LISTA OFICIAL o aluno que contenha o nome citado. Ignore diferenças de acentos ou maiúsculas/minúsculas.
    3. CLASSIFICAÇÃO RIGOROSA (REGRA DE OURO):
       - Se o status for 0, coloque O NUMERO DA CHAMADA (inteiro) na lista "F".
       - Se o status for 1, coloque O NUMERO DA CHAMADA (inteiro) na lista "J".
       - PROIBIDO inventar status. Siga o número do dicionário.
    4. Se NENHUM nome da lista bater, coloque O NOME CITADO na lista "nao_encontrados".
    5. Se tiver MAIS DE UMA correspondência, coloque O NOME CITADO na lista "ambiguos", e as opções encontradas como valor.

    RETORNO OBRIGATÓRIO (JSON PURO, SEM COMENTÁRIOS, SEM TEXTO EXPLICATIVO):
    {{
        "F": [],
        "J": [],
        "nao_encontrados": [],
        "ambiguos": {{"NomeCitado": ["Opção 1", "Opção 2"]}}
    }}
    """
    try:
        response = await client.chat.completions.create(
            model=MODELO_TEXTO,
            messages=[{"role": "user", "content": prompt_tradutor}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Erro na tradução de chamada: {e}")
        return {"F": [], "J": [], "nao_encontrados": [], "ambiguos": {}}