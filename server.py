from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn
import requests
import os
import base64
import json         
import ia           
import extrairdadosjson
import httpx
import asyncio
import registrohtml     
import sigaapi
from dotenv import load_dotenv
import sys
import traceback
import difflib
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

app = FastAPI()

SESSAO = os.getenv("WPP_SESSION", "sessao-pedro-final")
TOKEN = os.getenv("WPP_TOKEN")
DOCKER_URL = os.getenv("WPP_URL", "http://localhost:21465")

SIGA_BASE_URL = os.getenv("SIGA_BASE_URL", "https://siga.activesoft.com.br")
SIGA_TOKEN = f"Bearer {os.getenv('SIGA_TOKEN', '')}"
ARQUIVO_DIARIOS = "diarios_com_turmas_2026.json"
ARQUIVO_USUARIOS = "usuarios.json"
ARQUIVO_ESTADOS = "estados_conversas.json"

_ESTADO_LOCK_PATH = "estados_conversas.json.lock"

NUMEROS_PERMITIDOS = [
    "558396336492@c.us", "5583996336492@c.us", "5583981219527@c.us", "558381219527@c.us",
    "558398156803@c.us", "55838156803@c.us",
    "558399030176@c.us", "5583999030176@c.us"
]

# ==============================================================================
# SISTEMA DE MEMÓRIA (read always from disk, write atomically via .tmp + rename)
# ==============================================================================

def carregar_estados_disco():
    if os.path.exists(ARQUIVO_ESTADOS):
        try:
            with open(ARQUIVO_ESTADOS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Erro ao carregar estados: {e}")
    return {}

def salvar_estados_disco(estados_dict):
    tmp_path = ARQUIVO_ESTADOS + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(estados_dict, f, indent=4, ensure_ascii=False)
    os.replace(tmp_path, ARQUIVO_ESTADOS)

def carregar_boas_vindas():
    path = ".boas_vindas.json"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def salvar_boas_vindas(welcomed_set):
    path = ".boas_vindas.json"
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(list(welcomed_set), f)
    os.replace(path + ".tmp", path)

# Inicia puxando do HD direto! Adeus "estados_usuarios = {}"
estados_usuarios = carregar_estados_disco()
boas_vindas_enviadas = carregar_boas_vindas() 

import unicodedata

def remover_acentos(txt):
    if not txt: return ""
    return unicodedata.normalize('NFKD', txt).encode('ASCII', 'ignore').decode('utf-8').lower()

def descobrir_dados_do_diario(turma_site, turma_api, disciplina_ia):
    mapa_banco = {
        # Removido o "IA" solto para não dar match com o final de Histor"ia" ou Geograf"ia"
        "computacao": ["Educação Tecnológica", "Computação", "Robótica", "Informática", "Inteligência Artificial", "Pensamento Computacional", "Tecnologia"],
        "inteligencia_artificial": ["Inteligência Artificial", "Computação", "Educação Tecnológica"],
        "lingua_portuguesa": ["Língua Portuguesa", "Português", "Redação", "Literatura"],
        "lingua_inglesa": ["Inglês", "Língua Inglesa"],
        "matematica": ["Matemática"],
        "ciencias": ["Ciências", "Ciência", "Biologia", "Física", "Química"],
        "geografia": ["Geografia"],
        "historia": ["História", "Sociologia", "Filosofia"],
        "arte": ["Arte", "Artes"],
        "educacao_fisica": ["Educação Física"],
        "ensino_religioso": ["Ensino Religioso", "Religião"],
        "aprendizagem e desenvolvimento": ["Aprendizagem e Desenvolvimento", "Aprendizagem"]
    }
    nomes_possiveis = mapa_banco.get(disciplina_ia.lower(), [disciplina_ia])

    try:
        with open(ARQUIVO_DIARIOS, "r", encoding="utf-8") as f:
            diarios = json.load(f)
            
        numero_turma = ''.join(filter(str.isdigit, turma_site))
        letra_turma = ''.join(filter(str.isalpha, turma_site)).upper()
        
        if turma_api.startswith('I') and numero_turma:
            romanos = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V"}
            numero_turma = romanos.get(numero_turma, numero_turma)
            
        nivel_api = turma_api[0].upper() if turma_api else 'F'
        
        candidatos = []
        for diario in diarios:
            nome_turma = diario.get("nome_turma_completo", "")
            
            if nivel_api == 'M' and ("Médio" not in nome_turma and "Série" not in nome_turma): continue
            if nivel_api == 'F' and "Fundamental" not in nome_turma: continue
            if nivel_api == 'I' and "Infantil" not in nome_turma: continue
            
            nome_disc = diario.get("nome_disciplina", "")
            bateu_disciplina = any(remover_acentos(nome) in remover_acentos(nome_disc) for nome in nomes_possiveis)
            
            if bateu_disciplina and numero_turma in nome_turma and letra_turma in nome_turma:
                candidatos.append(diario)
                
        if not candidatos: 
            print(f"🔴 ERRO: Não achei diário de {disciplina_ia} no nível {nivel_api} da turma {numero_turma}{letra_turma}!")
            return None 
            
        diario_escolhido = candidatos[0]
        nome_turma = diario_escolhido.get("nome_turma_completo", "")
        nome_disc = diario_escolhido.get("nome_disciplina", "")
        
        # 🎯 O CÓDIGO LIMPO: Puxa o ID real direto do JSON atualizado!
        id_disc_real = str(diario_escolhido.get("id_disciplina", "")).strip()
        
        # Deixamos o "00" apenas como um fallback extremo de segurança caso a API da escola fique fora do ar
        if not id_disc_real or id_disc_real.lower() == "none":
            id_disc_real = "00"
        
        return {
            "id_diario": str(diario_escolhido["id_diario"]), 
            "id_turma": str(diario_escolhido["id_turma"]), 
            "id_disciplina": id_disc_real, 
            "disciplina_str": f"{nome_turma} - {nome_disc}"
        }
    except Exception as e: 
        print(f"Erro ao buscar diário no JSON: {e}")
        
    return None

def carregar_usuarios():
    if os.path.exists(ARQUIVO_USUARIOS):
        with open(ARQUIVO_USUARIOS, "r") as f: return json.load(f)
    return {}

def salvar_usuario(numero, login, senha):
    usuarios = carregar_usuarios()
    usuarios[numero] = {"login": login, "senha": senha}
    with open(ARQUIVO_USUARIOS, "w") as f: json.dump(usuarios, f, indent=4)

def apagar_usuario(numero):
    usuarios = carregar_usuarios()
    if numero in usuarios:
        del usuarios[numero]
        with open(ARQUIVO_USUARIOS, "w") as f: json.dump(usuarios, f, indent=4)
        return True
    return False

async def enviar_mensagem_whatsapp(numero, texto):
    url = f"{DOCKER_URL}/api/{SESSAO}/send-message"
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    payload = {"phone": numero, "message": texto}
    try: 
        async with httpx.AsyncClient() as client:
            resposta = await client.post(url, json=payload, headers=headers)
            # Se o WPPConnect não der o OK (200 ou 201), ele dedura o erro!
            if resposta.status_code not in [200, 201]:
                print(f"\n🔴 [DOCKER RECUSOU A MENSAGEM] Status: {resposta.status_code} | Resposta: {resposta.text}\n")
    except Exception as e: 
        print(f"\n🔴 [ERRO DE CONEXÃO COM O DOCKER] Não consegui acessar {url}. Erro: {e}\n")

async def baixar_audio_limpo(message_id):
    url = f"{DOCKER_URL}/api/{SESSAO}/download-media"
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    payload = {"messageId": message_id}
    try:
        async with httpx.AsyncClient() as client:
            resposta = await client.post(url, json=payload, headers=headers)
            if resposta.status_code != 200: return None
            
        dados = resposta.text
        try:
            json_dados = resposta.json()
            if isinstance(json_dados, dict) and 'base64' in json_dados: dados = json_dados['base64']
        except: pass
        if "base64," in dados: dados = dados.split("base64,")[-1]
        dados = dados.strip().replace('\n', '').replace('\r', '').replace(' ', '').replace('"', '')
        pad = len(dados) % 4
        if pad > 0: dados += '=' * (4 - pad)
        try: audio_bytes = base64.b64decode(dados)
        except: return None
        nome_arquivo = f"audio_{message_id}.m4a"
        with open(nome_arquivo, "wb") as f: f.write(audio_bytes)
        return nome_arquivo
    except: return None

async def exibir_resumo_confirmacao(remetente, dados_aula, ids_diario, numeros_frequencia, lista_oficial, lista_limpa_para_ia):
    nomes_confirmados = []
    
    # Criamos sets de strings para uma comparação rápida e segura
    faltas_f = set(str(x) for x in numeros_frequencia.get('F', []))
    faltas_j = set(str(x) for x in numeros_frequencia.get('J', []))
    
    for aluno in lista_oficial:
        # Pegamos o número da chamada como string
        num_str = str(aluno.get('numero_chamada', ''))
        
        if num_str in faltas_f:
            nomes_confirmados.append(f"{aluno.get('nome')} (*Falta*)")
        elif num_str in faltas_j:
            nomes_confirmados.append(f"{aluno.get('nome')} (*Justificada*)")
            
    texto_faltosos = ", ".join(nomes_confirmados) if nomes_confirmados else "Nenhum"
    
    nao_encontrados = numeros_frequencia.get("nao_encontrados", [])
    if nao_encontrados:
        nomes_perdidos = ", ".join(nao_encontrados)
        texto_faltosos += f"\n\n⚠️ *Atenção:* Os alunos _{nomes_perdidos}_ não foram encontrados na lista desta turma e foram ignorados!"

    estados_usuarios[remetente] = {
        "etapa": "esperando_confirmacao", 
        "dados_aula": dados_aula,
        "ids_diario": ids_diario,
        "numeros_frequencia": numeros_frequencia,
        "lista_limpa_para_ia": lista_limpa_para_ia,
        "lista_oficial": lista_oficial
    }
    salvar_estados_disco(estados_usuarios) # SALVA AQUI!
    
    bncc_texto = dados_aula.get('bncc', '')
    conteudo_exibicao = f"{dados_aula.get('conteudo')}\n*(BNCC: {bncc_texto})*" if bncc_texto else dados_aula.get('conteudo')

    msg_resposta = (
        f"📋 **Confira os dados:**\n\n"
        f"🏫 Turma: *{ids_diario['disciplina_str']}*\n"
        f"📅 Data: *{dados_aula.get('data')}*\n"
        f"📚 Conteúdo: {conteudo_exibicao}\n"
        f"🏠 Tarefa: {dados_aula.get('tarefa')}\n"
        f"🚫 Faltosos: {texto_faltosos}\n\n"
        f"✅ Responda **SIM** para gravar no sistema.\n"
        f"🔄 Ou mande **outro áudio** para corrigir."
    )
    await enviar_mensagem_whatsapp(remetente, msg_resposta)

async def tentar_executar_robo(remetente, estado_atual, login_usar, senha_usar):
    dados_aula = estado_atual['dados_aula']
    ids_diario = estado_atual['ids_diario']
    numeros_frequencia = estado_atual['numeros_frequencia']
    conteudo_base = dados_aula.get('conteudo', '')
    bncc_base = dados_aula.get('bncc', '')
    conteudo_final = f"{conteudo_base}\nBNCC: {bncc_base}" if bncc_base else conteudo_base
    
    try:
        await asyncio.to_thread(
            registrohtml.registrar_aula_completa,
            login=login_usar, senha=senha_usar, id_diario=ids_diario['id_diario'], id_turma=ids_diario['id_turma'],
            id_disciplina=ids_diario.get('id_disciplina', '82'), disciplina_str=ids_diario['disciplina_str'],
            data_aula=dados_aula.get('data'), conteudo=conteudo_final, tarefa=dados_aula.get('tarefa'), numeros_frequencia=numeros_frequencia
        )
        await enviar_mensagem_whatsapp(remetente, "✅ *Registro Concluído!*\nA aula e a chamada foram gravadas no sistema em tempo recorde. 🚀\n*(Para trocar senha, digite 'Resetar')*")
        
        # LIMPA E SALVA O ESTADO
        if remetente in estados_usuarios: 
            del estados_usuarios[remetente]
            salvar_estados_disco(estados_usuarios)

    except Exception as e:
        print("\n🔴🔴🔴 ERRO DETALHADO NA GRAVAÇÃO 🔴🔴🔴")
        traceback.print_exc()
        print("🔴🔴🔴------------------------------🔴🔴🔴\n")
        
        erro_str = str(e)
        
        # O Robô agora avisa o professor no WhatsApp dependendo do erro!
        if "LOGIN_ERROR" in erro_str or "Token JWT não encontrado" in erro_str:
            msg_erro = (
                "❌ *Acesso Negado no Sistema!*\n\n"
                "Eu não consegui acessar o diário. Isso acontece quando:\n"
                "1. O login/senha está incorreto.\n"
                "2. O sistema está pedindo para você **atualizar a sua senha** ou há algum bloqueio.\n\n"
                "⚠️ *Suas credenciais salvas foram apagadas por segurança.* Entre no site da escola pelo computador, resolva o aviso, e depois mande um novo áudio aqui para recomeçar!"
            )
            apagar_usuario(remetente) # Apaga a senha inválida do banco
            
            # Limpa o estado atual para o professor não ficar preso na mesma tela
            if remetente in estados_usuarios: 
                del estados_usuarios[remetente]
                salvar_estados_disco(estados_usuarios)
                
        else:
            # Se for outro tipo de erro (ex: site fora do ar)
            msg_erro = (
                "❌ *Ops! Ocorreu uma falha técnica ao gravar a aula.*\n\n"
                f"Detalhe do erro: _{erro_str}_\n\n"
                "Por favor, tente responder SIM novamente em alguns instantes, ou mande a palavra *Resetar*."
            )
            
        # Dispara a mensagem de erro pro Zap do professor
        await enviar_mensagem_whatsapp(remetente, msg_erro)
            
@app.post("/webhook")
async def receber_mensagem(request: Request, background_tasks: BackgroundTasks):
    try:
        dados = await request.json()
        if dados.get('event') != 'onmessage': return {"status": "ignorado"}
        
        tipo = dados.get('type')
        eh_minha = dados.get('fromMe', False)
        remetente = dados.get('from')
        texto_msg = dados.get('body', '').strip()

        if not eh_minha and remetente not in NUMEROS_PERMITIDOS: return {"status": "bloqueado"}
        
        if tipo == 'chat' and texto_msg.lower() == 'resetar':
            if apagar_usuario(remetente): await enviar_mensagem_whatsapp(remetente, "♻️ Suas credenciais foram apagadas. Envie um novo áudio para recomeçar.")
            if remetente in estados_usuarios: 
                del estados_usuarios[remetente]
                salvar_estados_disco(estados_usuarios)
            if remetente in boas_vindas_enviadas:
                boas_vindas_enviadas.remove(remetente)
                salvar_boas_vindas(boas_vindas_enviadas) 
            return {"status": "ok"}
            
        estado_atual = estados_usuarios.get(remetente)
        if eh_minha and tipo not in ['ptt', 'audio'] and not estado_atual: return {"status": "ignorado_loop"}

        if remetente not in boas_vindas_enviadas:
            boas_vindas_enviadas.add(remetente)
            salvar_boas_vindas(boas_vindas_enviadas)
            usuarios_salvos = carregar_usuarios()
            if remetente not in usuarios_salvos:
                msg_intro = "👋 Olá! Eu sou o *Aulio*, seu assistente inteligente para registro de aulas.\nMeu objetivo é transformar seus áudios em diários preenchidos no sistema escolar em segundos! 🚀\n"
                await enviar_mensagem_whatsapp(remetente, msg_intro)
                if tipo == 'chat':
                    await enviar_mensagem_whatsapp(remetente, "🎙️ Para começarmos, grave um áudio relatando como foi sua aula.")
                    await enviar_mensagem_whatsapp(remetente, "📝 Informe por áudio ou texto os seguintes dados sobre a aula:\n • Série e Turma;\n • Disciplina;\n • Conteúdo da aula;\n • Tarefas (sala ou casa);\n • Faltosos.")
                    await enviar_mensagem_whatsapp(remetente, "Fico no aguardo para registrar sua aula! 😃")
                    return {"status": "ok"}

        if tipo == 'chat' and not estado_atual:
            await enviar_mensagem_whatsapp(remetente, "🎙️ Estou pronto! Pode me enviar o áudio com o resumo da sua aula.")
            return {"status": "ok"}

        # ==============================================================================
        # FLUXO HÍBRIDO (ÁUDIO)
        # ==============================================================================
        if tipo == 'ptt' or tipo == 'audio':
            msg_id = dados.get('id')
            print(f"\n[Aulio Cérebro] Áudio recebido do remetente {remetente}.")
            
            if estado_atual and estado_atual.get('etapa') == 'esperando_desambiguacao':
                
                # --- ADICIONE ESTA LINHA AQUI! ---
                await enviar_mensagem_whatsapp(remetente, "🎧 Escutando os nomes...")
                
                arquivo = await baixar_audio_limpo(msg_id)
                texto_msg = arquivo
                tipo = 'chat'
            
            else:
                dados_anteriores = estado_atual['dados_aula'] if estado_atual and 'dados_aula' in estado_atual else None
                await enviar_mensagem_whatsapp(remetente, "🔄 Atualizando..." if dados_anteriores else "🎧 Processando áudio e cruzando dados...")
                
                arquivo = await baixar_audio_limpo(msg_id)
                if arquivo:
                    try:
                       # O Aulio agora é Multimodal! Ele engole o arquivo de áudio direto.
                        dados_aula = await ia.extrair_dados_da_aula(arquivo, dados_anteriores)

                        # 🛡️ ESCUDO ANTI-CRASH: Se a IA da nuvem falhar, o bot avisa e não quebra!
                        if not dados_aula:
                            await enviar_mensagem_whatsapp(remetente, "❌ Erro nos servidores da Inteligência Artificial. Por favor, tente enviar o áudio novamente.")
                            os.remove(arquivo)
                            return {"status": "ok"}

                        ids_diario = descobrir_dados_do_diario(dados_aula.get('turma_site', ''), dados_aula.get('turma_api', ''), dados_aula.get('disciplina', ''))
                        if not ids_diario:
                            await enviar_mensagem_whatsapp(remetente, "❌ Não achei o diário desta turma. Tente outro áudio.")
                            os.remove(arquivo)
                            return {"status": "ok"}
                            
                        # --- Carrega alunos do banco SQLite (ou JSON de turma) ---
                        import sqlite3
                        lista_oficial = []
                        id_turma_busca = str(ids_diario.get('id_turma', ''))
                        db_path = "alunos.db"

                        if os.path.exists(db_path):
                            try:
                                con = sqlite3.connect(db_path)
                                cur = con.cursor()
                                cur.execute(
                                    "SELECT numero_chamada, nome FROM alunos_diario WHERE id_turma = ? ORDER BY numero_chamada",
                                    (id_turma_busca,)
                                )
                                lista_oficial = [{"numero_chamada": row[0], "nome": row[1]} for row in cur.fetchall()]
                                con.close()
                            except Exception as e:
                                print(f"[BANCO] Erro ao ler SQLite: {e}")

                        # Fallback: JSON por turma
                        if not lista_oficial:
                            json_path = f"alunos_turma_{id_turma_busca}.json"
                            try:
                                with open(json_path, "r", encoding="utf-8") as f:
                                    lista_oficial = json.load(f)
                            except FileNotFoundError:
                                print(f"[BANCO] ❌ JSON '{json_path}' não encontrado.")

                        print(f"[BANCO] Turma {id_turma_busca}: {len(lista_oficial)} alunos.")

                        if not lista_oficial:
                            print(f"[BANCO] ❌ Lista vazia! Execute extrairdadosjson.py para atualizar o banco.")
                            await enviar_mensagem_whatsapp(remetente, f"⚠️ A lista de alunos não foi encontrada no banco local. Parei o registro.")
                            os.remove(arquivo)
                            return {"status": "ok"} 
                            
                        lista_limpa_para_ia = [{"numero_chamada": aluno.get('numero_chamada'), "nome": aluno.get('nome', 'Sem Nome')} for aluno in lista_oficial]
                            
                        # ------------------------------------------------------------------
                        # 🚀 PARALELISMO REAL: Busca BNCC e Traduz Faltosos AO MESMO TEMPO!
                        # ------------------------------------------------------------------
                        faltosos_extraidos = dados_aula.get('faltosos', {})
                        disciplina_atual = dados_aula.get('disciplina', '')
                        turma_atual = dados_aula.get('turma_api', '')
                        conteudo_atual = dados_aula.get('conteudo', '')
                        
                        # Criamos as duas tarefas pendentes
                        tarefa_faltosos = ia.traduzir_nomes_para_chamada(faltosos_extraidos, lista_limpa_para_ia)
                        tarefa_bncc = ia.buscar_bncc_ultra_rapida(disciplina_atual, turma_atual, conteudo_atual)
                        
                        # Mandamos o servidor executar as duas simultaneamente e esperar!
                        numeros_frequencia, texto_bncc = await asyncio.gather(tarefa_faltosos, tarefa_bncc)
                        
                        # Se achou BNCC, adiciona de volta no dicionário para exibição
                        if texto_bncc:
                            dados_aula['bncc'] = texto_bncc
                            
                        if not numeros_frequencia: numeros_frequencia = {"F": [], "J": [], "nao_encontrados": [], "ambiguos": {}}

                        # 🔍 MATCH LOCAL por substring — resolve nomes curtos como "Eduardo"
                        def encontrar_aluno(nome_busca, lista_alunos):
                            busca = remover_acentos(nome_busca.lower().strip())
                            matches = []
                            
                            # Tentativa 1: Busca exata / Substring (Como era antes)
                            for a in lista_alunos:
                                nome_comp = remover_acentos(a.get("nome", "").lower())
                                if busca in nome_comp or nome_comp in busca:
                                    matches.append(a)
                                    
                            if len(matches) == 1:
                                return matches[0].get("numero_chamada"), matches[0].get("nome")
                            elif len(matches) > 1:
                                return "ambiguous", [m.get("nome", "") for m in matches]
                                
                            # Tentativa 2: "Fuzzy Matching" (Se a IA escrever Ludmilla, Yago, etc)
                            # Vamos comparar a primeira palavra do nome buscado com a primeira palavra de todos os alunos
                            palavras_busca = busca.split()
                            if not palavras_busca: return None, None
                            
                            primeiro_nome_busca = palavras_busca[0]
                            
                            for a in lista_alunos:
                                nome_comp = remover_acentos(a.get("nome", "").lower())
                                palavras_oficiais = nome_comp.split()
                                if not palavras_oficiais: continue
                                
                                primeiro_nome_oficial = palavras_oficiais[0]
                                
                                # Verifica a semelhança entre as palavras (Ludmilla vs Ludmila dá ~94% de semelhança)
                                similaridade = difflib.SequenceMatcher(None, primeiro_nome_busca, primeiro_nome_oficial).ratio()
                                
                                # Se bater mais de 80% de semelhança na primeira palavra, considera um match!
                                if similaridade >= 0.8:
                                    # Se a busca tiver sobrenome (ex: Ludmilla Silva), a gente checa se o sobrenome também parece
                                    if len(palavras_busca) > 1 and len(palavras_oficiais) > 1:
                                        sim_sobrenome = difflib.SequenceMatcher(None, palavras_busca[1], palavras_oficiais[1]).ratio()
                                        if sim_sobrenome >= 0.8:
                                            matches.append(a)
                                    else:
                                        matches.append(a)

                            if len(matches) == 1:
                                return matches[0].get("numero_chamada"), matches[0].get("nome")
                            elif len(matches) > 1:
                                return "ambiguous", [m.get("nome", "") for m in matches]
                                
                            return None, None

                        nao_achados = list(numeros_frequencia.get("nao_encontrados", []))
                        print(f"[MATCH LOCAL] nao_achados: {nao_achados}")
                        print(f"[MATCH LOCAL] lista_oficial nomes: {[a.get('nome','') for a in lista_oficial]}")
                        for nome_busca in nao_achados:
                            num_ch, nome = encontrar_aluno(nome_busca, lista_oficial)
                            print(f"[MATCH LOCAL] buscando '{nome_busca}' → resultado num={num_ch}, nome={nome}")
                            if num_ch is not None and num_ch != "ambiguous":
                                print(f"[MATCH LOCAL] Encontrou '{nome_busca}' → Nº {num_ch} ({nome})")
                                
                                # 🛡️ CORREÇÃO: Puxa o status verdadeiro (0 ou 1) lá do JSON do LLaMA
                                valor_real = faltosos_extraidos.get(nome_busca, 0)
                                
                                if str(valor_real) == '1':
                                    numeros_frequencia["J"].append(num_ch)
                                    print(f"  -> Salvando como Justificada (J)")
                                else:
                                    numeros_frequencia["F"].append(num_ch)
                                    print(f"  -> Salvando como Falta Normal (F)")
                                    
                                numeros_frequencia["nao_encontrados"].remove(nome_busca)
                            elif num_ch == "ambiguous":
                                numeros_frequencia["ambiguos"][nome_busca] = nome

                        # --- ALERTA DE AMBIGUIDADE ---
                        ambiguos = numeros_frequencia.get("ambiguos", {})
                        if ambiguos:
                            msg_conflito = "⚠️ *Atenção! Encontrei alunos com nomes parecidos:*\n\n"
                            for nome_curto, opcoes in ambiguos.items():
                                msg_conflito += f"👤 *{nome_curto}* pode ser:\n"
                                for op in opcoes: msg_conflito += f"  - {op}\n"
                                msg_conflito += "\n"
                            msg_conflito += "🎙️ Responda com um *áudio* ou *texto* dizendo o nome completo correto para eu não errar!"
                            
                            estados_usuarios[remetente] = {
                                "etapa": "esperando_desambiguacao", "dados_aula": dados_aula, "ids_diario": ids_diario,
                                "lista_limpa_para_ia": lista_limpa_para_ia, "lista_oficial": lista_oficial, "ambiguos": ambiguos
                            }
                            salvar_estados_disco(estados_usuarios)
                            
                            await enviar_mensagem_whatsapp(remetente, msg_conflito)
                            if os.path.exists(arquivo): os.remove(arquivo)
                            return {"status": "ok"}

                        await exibir_resumo_confirmacao(remetente, dados_aula, ids_diario, numeros_frequencia, lista_oficial, lista_limpa_para_ia)
                        if os.path.exists(arquivo): os.remove(arquivo)
                        
                    except Exception as e: 
                        print("\n🔴🔴🔴 ERRO DETALHADO NO ÁUDIO 🔴🔴🔴")
                        traceback.print_exc()
                        await enviar_mensagem_whatsapp(remetente, "❌ Erro interno ao processar áudio.")
                        if os.path.exists(arquivo): os.remove(arquivo)
                        return {"status": "ok"}

        # ==============================================================================
        # FLUXO DE TEXTO (E AUDIOS CONVERTIDOS EM TEXTO)
        # ==============================================================================
        if tipo == 'chat' and estado_atual:
            etapa = estado_atual['etapa']

            if etapa == 'esperando_desambiguacao':
                
                # --- ADICIONE ESTAS DUAS LINHAS AQUI! ---
                if not str(texto_msg).endswith('.m4a'):
                    await enviar_mensagem_whatsapp(remetente, "⏳ Verificando os nomes...")
                    
                resolvido = await ia.resolver_ambiguidade(texto_msg, estado_atual['ambiguos'], estado_atual['dados_aula'].get('faltosos', {}))
                
                # Se era um arquivo de áudio, limpa do PC agora!
                if texto_msg.endswith('.m4a') and os.path.exists(texto_msg):
                    os.remove(texto_msg)
                
                if resolvido and "erro" not in resolvido:
                    
                    # 1. Tira os nomes curtos e confusos da lista de faltosos
                    for nome_curto in estado_atual['ambiguos'].keys():
                        if nome_curto in estado_atual['dados_aula']['faltosos']:
                            del estado_atual['dados_aula']['faltosos'][nome_curto]
                            
                    # 2. Adiciona os nomes completos certos (isso mantém o Noah na lista se ele não teve ambiguidade!)
                    estado_atual['dados_aula']['faltosos'].update(resolvido)
                    
                    # 3. Manda a IA traduzir a lista final e perfeita para números da chamada
                    nova_freq = await ia.traduzir_nomes_para_chamada(estado_atual['dados_aula']['faltosos'], estado_atual['lista_limpa_para_ia'])
                    
                    await exibir_resumo_confirmacao(
                        remetente, estado_atual['dados_aula'], estado_atual['ids_diario'], 
                        nova_freq, estado_atual['lista_oficial'], estado_atual['lista_limpa_para_ia']
                    )
                else:
                    await enviar_mensagem_whatsapp(remetente, "❌ Não entendi muito bem. Diga de forma clara qual é o nome completo!")

            elif etapa == 'esperando_confirmacao':
                if texto_msg.lower() in ['sim', 'ok', 'pode', 'confirmo', 'certo', 'vai', 's', 'bora', 'tá certo', 'sim.']:
                    usuarios_salvos = carregar_usuarios()
                    if remetente in usuarios_salvos:
                        login_salvo = usuarios_salvos[remetente]['login']
                        senha_salva = usuarios_salvos[remetente]['senha']
                        dados_aula = estado_atual.get('dados_aula', {})

                        # 🛡️ O BUG ESTAVA AQUI: Puxando do estado_atual com segurança!
                        diario_str = estado_atual['ids_diario']['disciplina_str']
                        await enviar_mensagem_whatsapp(remetente, f"🚀 Registrando aula em {diario_str}...")
                        
                        background_tasks.add_task(tentar_executar_robo, remetente, estado_atual, login_salvo, senha_salva)
                    else:
                        estados_usuarios[remetente]['etapa'] = 'esperando_login'
                        salvar_estados_disco(estados_usuarios)
                        await enviar_mensagem_whatsapp(remetente, "Certo, vamos iniciar o registro.\n🔒 Digite apenas seu **LOGIN**:\nA senha será solicitada na próxima mensagem.")
                else: 
                    await enviar_mensagem_whatsapp(remetente, "Mande **SIM** para confirmar ou outro áudio para corrigir.")

            elif etapa == 'esperando_login':
                estados_usuarios[remetente]['login_salvo'] = texto_msg
                estados_usuarios[remetente]['etapa'] = 'esperando_senha'
                salvar_estados_disco(estados_usuarios) # SALVA AQUI!
                await enviar_mensagem_whatsapp(remetente, "👍 Agora digite sua **SENHA**:")
            
            elif etapa == 'esperando_senha':
                salvar_usuario(remetente, estado_atual['login_salvo'], texto_msg)
                await enviar_mensagem_whatsapp(remetente, "💾 Credenciais salvas!\n🚀 Iniciando robô...")
                background_tasks.add_task(tentar_executar_robo, remetente, estado_atual, estado_atual['login_salvo'], texto_msg)

    except Exception as e: print(f"Erro webhook genérico: {e}")
    return {"status": "ok"}

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=8000)