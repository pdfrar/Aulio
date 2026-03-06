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

    Estrutura EXATA do JSON:
    {{
        "disciplina": "A disciplina identificada com base no conteúdo. Deve ser UMA destas: {', '.join(opcoes_disciplinas)}",
        "turma_site": "string (Apenas o número e a letra. Ex: 5A, 8B, 1C)",
        "turma_api": "string (Prefixo + Número + Letra. Ex: F5A, M1B, I2C)",
        "conteudo": "string (Resumo formal e corrigido do assunto)",
        "tarefa": "string ou 'Nenhuma'",
        "faltosos": {{"nome_do_aluno": 0 ou 1}},
        "data": "{hoje}"
    }}
    
    REGRA DA TURMA API (MUITO IMPORTANTE):
    Você deve classificar o nível da turma e adicionar o prefixo correto no campo 'turma_api':
    - Ensino Fundamental (1º ao 9º ano): Prefixo 'F'. Ex: 5º ano A vira F5A.
    - Ensino Médio (1ª à 3ª série): Prefixo 'M'. Ex: 1ª série B vira M1B.
    - Educação Infantil (I ao V): Prefixo 'I'. Ex: Infantil II C vira I2C.

    REGRAS DE ESTILO E FORMATAÇÃO:
    - CONTEÚDO E TAREFA: Reescreva o relato num resumo profissional, objetivo e na norma-padrão.
    - Remova gírias e vícios de linguagem.
    - Se não houver tarefa citada, use "Nenhuma".
    
    REGRA DA DISCIPLINA (CRUCIAL):
    Analise os termos técnicos e o assunto falado para definir a disciplina. Siga este guia:
    1. Se falar de robótica, programação, tecnologia, computadores -> "computacao"
    2. Se falar de verbos, gramática, literatura, redação -> "lingua_portuguesa"
    3. Se falar de cálculos, equações, geometria, números -> "matematica"
    4. Se falar de células, corpo humano, natureza, física, química -> "ciencias"
    5. Se falar de mapas, relevo, clima, população -> "geografia"
    6. Se falar de passado, guerras, revoluções, sociedade -> "historia"
    7. Se falar de inglês, verb to be, vocabulary -> "lingua_inglesa"
    8. Se falar de pintura, cores, música, teatro -> "arte"
    9. Se falar de esportes, jogos, corpo em movimento -> "educacao_fisica"
    10. Se falar de ética, valores, fé, religião -> "ensino_religioso"

    REGRA DOS FALTOSOS: O padrão é 0 (Normal). Só use 1 se a falta for explicitamente justificada no áudio.
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
    Você é um assistente de dados focado EXCLUSIVAMENTE em corrigir nomes de alunos.
    
    DADOS RECEBIDOS:
    1. Faltas Originais: {json.dumps(faltosos_atuais, ensure_ascii=False)}
    2. Opções de Nomes Completos: {json.dumps(dicionario_conflitos, ensure_ascii=False)}
    3. Mensagem do Professor: "{texto_usuario}"
    
    SUA MISSÃO VITAL:
    - Analise a mensagem do professor. Ele indicou CLARAMENTE qual nome completo das opções é o correto?
    - SE SIM: Retorne um JSON substituindo o nome curto pelo nome completo escolhido. MANTENHA O VALOR DA FALTA (0 ou 1) INTACTO. Nunca mude 0 para 1.
    - SE NÃO (ex: se ele mandou apenas "oi", "ok", áudio mudo, ou algo sem sentido): Retorne EXATAMENTE este JSON: {{"erro": "invalido"}}
    
    Retorne APENAS um objeto JSON e nada mais.
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
        return {"erro": "invalido"} # Em caso de erro técnico, também avisa que falhou!