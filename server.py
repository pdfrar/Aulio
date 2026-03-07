from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn
import requests
import os
import base64
import json         
import ia           
import extrairdadosjson  
import registrohtml     
import sigaapi
from dotenv import load_dotenv
import sys
import traceback 
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv() 

app = FastAPI()

SESSAO = os.getenv("WPP_SESSION", "sessao-pedro-final")
TOKEN = os.getenv("WPP_TOKEN") 
DOCKER_URL = os.getenv("WPP_URL", "http://localhost:21465") 

SIGA_BASE_URL = "https://siga.activesoft.com.br"
SIGA_TOKEN = "Bearer ZaAmsMtiTSf3nxpuTJuZ2zkgOmVMhr"
ARQUIVO_DIARIOS = "diarios_com_turmas_2026.json"
ARQUIVO_USUARIOS = "usuarios.json"  

NUMEROS_PERMITIDOS = [
    "558396336492@c.us", "5583996336492@c.us", "5583999030176@c.us",
    "558399030176@c.us", "5583981219527@c.us", "558381219527@c.us",
    "558398156803@c.us", "55838156803@c.us", "5583996035018@c.us",
    "558396035018@c.us"  
]

estados_usuarios = {}
boas_vindas_enviadas = set() 

import unicodedata

def remover_acentos(txt):
    if not txt: return ""
    return unicodedata.normalize('NFKD', txt).encode('ASCII', 'ignore').decode('utf-8').lower()

def descobrir_dados_do_diario(turma_site, turma_api, disciplina_ia):
    mapa_banco = {
        "computacao": ["Educação Tecnológica", "Computação", "Robótica", "Informática"],
        "lingua_portuguesa": ["Língua Portuguesa", "Português", "Redação"],
        "lingua_inglesa": ["Inglês", "Língua Inglesa"],
        "matematica": ["Matemática"],
        "ciencias": ["Ciências", "Ciência"],
        "geografia": ["Geografia"],
        "historia": ["História"],
        "arte": ["Arte", "Artes"],
        "educacao_fisica": ["Educação Física"],
        "ensino_religioso": ["Ensino Religioso", "Religião"]
    }
    nomes_possiveis = mapa_banco.get(disciplina_ia, [disciplina_ia])

    try:
        with open(ARQUIVO_DIARIOS, "r", encoding="utf-8") as f:
            diarios = json.load(f)
            
        numero_turma = ''.join(filter(str.isdigit, turma_site))
        letra_turma = ''.join(filter(str.isalpha, turma_site)).upper()
        
        candidatos = []
        for diario in diarios:
            nome_turma = diario.get("nome_turma_completo", "")
            nome_disc = diario.get("nome_disciplina", "")
            bateu_disciplina = any(remover_acentos(nome) in remover_acentos(nome_disc) for nome in nomes_possiveis)
            if bateu_disciplina and numero_turma in nome_turma and letra_turma in nome_turma:
                candidatos.append(diario)
                
        if not candidatos: return None 
        
        texto_dica = (turma_site + " " + turma_api).lower()
        quer_fundamental = "ano" in texto_dica or "f" in turma_api.lower()
        quer_medio = "série" in texto_dica or "serie" in texto_dica or "m" in turma_api.lower()

        diarios_filtrados = []
        for diario in candidatos:
            nome_turma = diario.get("nome_turma_completo", "")
            if quer_fundamental and "Fundamental" in nome_turma:
                diarios_filtrados.append(diario)
            elif quer_medio and ("Médio" in nome_turma or "Série" in nome_turma):
                diarios_filtrados.append(diario)

        if not diarios_filtrados: diarios_filtrados = candidatos
            
        diario_escolhido = diarios_filtrados[0]
        nome_turma = diario_escolhido.get("nome_turma_completo", "")
        nome_disc = diario_escolhido.get("nome_disciplina", "")
        
        return {
            "id_diario": diario_escolhido["id_diario"], 
            "id_turma": diario_escolhido["id_turma"], 
            "id_disciplina": "00", 
            "disciplina_str": f"{nome_turma} - {nome_disc}"
        }
    except Exception as e: print(f"Erro ao buscar diário no JSON: {e}")
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

def enviar_mensagem_whatsapp(numero, texto):
    url = f"{DOCKER_URL}/api/{SESSAO}/send-message"
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    payload = {"phone": numero, "message": texto}
    try: requests.post(url, json=payload, headers=headers)
    except: pass

def baixar_audio_limpo(message_id):
    url = f"{DOCKER_URL}/api/{SESSAO}/download-media"
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    payload = {"messageId": message_id}
    try:
        resposta = requests.post(url, json=payload, headers=headers)
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

# ==============================================================================
# NOVA FUNÇÃO DE EXIBIÇÃO: Impede duplicação de código!
# ==============================================================================
def exibir_resumo_confirmacao(remetente, dados_aula, ids_diario, numeros_frequencia, lista_oficial, lista_limpa_para_ia):
    nomes_confirmados = []
    for aluno in lista_oficial:
        num = aluno.get('numero_chamada')
        num_str = str(num) 
        
        faltas_f = [str(x) for x in numeros_frequencia.get('F', [])]
        faltas_j = [str(x) for x in numeros_frequencia.get('J', [])]
        
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
    enviar_mensagem_whatsapp(remetente, msg_resposta)


def tentar_executar_robo(remetente, estado_atual, login_usar, senha_usar):
    dados_aula = estado_atual['dados_aula']
    ids_diario = estado_atual['ids_diario']
    numeros_frequencia = estado_atual['numeros_frequencia']
    conteudo_base = dados_aula.get('conteudo', '')
    bncc_base = dados_aula.get('bncc', '')
    conteudo_final = f"{conteudo_base}\nBNCC: {bncc_base}" if bncc_base else conteudo_base
    
    try:
        registrohtml.registrar_aula_completa(
            login=login_usar, senha=senha_usar, id_diario=ids_diario['id_diario'], id_turma=ids_diario['id_turma'],
            id_disciplina=ids_diario.get('id_disciplina', '82'), disciplina_str=ids_diario['disciplina_str'],
            data_aula=dados_aula.get('data'), conteudo=conteudo_final, tarefa=dados_aula.get('tarefa'), numeros_frequencia=numeros_frequencia
        )
        enviar_mensagem_whatsapp(remetente, "✅ *Registro Concluído!*\nA aula e a chamada foram gravadas no sistema em tempo recorde. 🚀\n*(Para trocar senha, digite 'Resetar')*")
        if remetente in estados_usuarios: del estados_usuarios[remetente]
    except Exception as e:
        print("\n🔴🔴🔴 ERRO DETALHADO NA GRAVAÇÃO 🔴🔴🔴")
        traceback.print_exc()
        print("🔴🔴🔴------------------------------🔴🔴🔴\n")
        if "LOGIN_ERROR" in str(e): apagar_usuario(remetente)
            
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
            if apagar_usuario(remetente): enviar_mensagem_whatsapp(remetente, "♻️ Suas credenciais foram apagadas. Envie um novo áudio para recomeçar.")
            if remetente in estados_usuarios: del estados_usuarios[remetente]
            if remetente in boas_vindas_enviadas: boas_vindas_enviadas.remove(remetente) 
            return {"status": "ok"}
            
        estado_atual = estados_usuarios.get(remetente)
        if eh_minha and tipo not in ['ptt', 'audio'] and not estado_atual: return {"status": "ignorado_loop"}

        if remetente not in boas_vindas_enviadas:
            boas_vindas_enviadas.add(remetente)
            usuarios_salvos = carregar_usuarios()
            if remetente not in usuarios_salvos:
                msg_intro = "👋 Olá! Eu sou o *Aulio*, seu assistente inteligente para registro de aulas.\nMeu objetivo é transformar seus áudios em diários preenchidos no sistema escolar em segundos! 🚀\n"
                enviar_mensagem_whatsapp(remetente, msg_intro)
                if tipo == 'chat':
                    enviar_mensagem_whatsapp(remetente, "🎙️ Para começarmos, grave um áudio relatando como foi sua aula (turma, conteúdo e faltosos).")
                    return {"status": "ok"}

        if tipo == 'chat' and not estado_atual:
            enviar_mensagem_whatsapp(remetente, "🎙️ Estou pronto! Pode me enviar o áudio com o resumo da sua aula.")
            return {"status": "ok"}

        # ==============================================================================
        # FLUXO HÍBRIDO (ÁUDIO)
        # ==============================================================================
        if tipo == 'ptt' or tipo == 'audio':
            msg_id = dados.get('id')
            print(f"\n[Aulio Cérebro] Áudio recebido do remetente {remetente}.")
            
            # SE O PROFESSOR MANDOU ÁUDIO PARA TIRAR A DÚVIDA DA MARIA:
            if estado_atual and estado_atual.get('etapa') == 'esperando_desambiguacao':
                arquivo = baixar_audio_limpo(msg_id)
                texto_msg = ia.transcrever_audio(arquivo)
                if os.path.exists(arquivo): os.remove(arquivo)
                tipo = 'chat' # Engana o sistema para ele pular para o bloco de texto ali embaixo!
            
            # SE FOR O ÁUDIO NORMAL DA AULA:
            else:
                dados_anteriores = estado_atual['dados_aula'] if estado_atual and 'dados_aula' in estado_atual else None
                enviar_mensagem_whatsapp(remetente, "🔄 Atualizando..." if dados_anteriores else "🎧 Processando áudio e cruzando dados...")
                
                arquivo = baixar_audio_limpo(msg_id)
                if arquivo:
                    try:
                        texto_transcrito = ia.transcrever_audio(arquivo)
                        if not texto_transcrito: raise Exception("Falha na transcrição")
                        
                        dados_aula = ia.extrair_dados_da_aula(texto_transcrito, dados_anteriores)
                        if not dados_aula: raise Exception("Falha na extração de dados")

                        ids_diario = descobrir_dados_do_diario(dados_aula.get('turma_site', ''), dados_aula.get('turma_api', ''), dados_aula.get('disciplina', ''))
                        if not ids_diario:
                            enviar_mensagem_whatsapp(remetente, "❌ Não achei o diário desta turma. Tente outro áudio.")
                            os.remove(arquivo)
                            return {"status": "ok"}
                            
                        ARQUIVO_CACHE_ALUNOS = "cache_alunos_todos_diarios.json"
                        lista_oficial = []
                        try:
                            with open(ARQUIVO_CACHE_ALUNOS, "r", encoding="utf-8") as f:
                                lista_oficial = json.load(f).get(str(ids_diario['id_diario']), [])
                        except Exception as e: pass
                            
                        if not lista_oficial:
                            enviar_mensagem_whatsapp(remetente, f"⚠️ A lista de alunos não foi encontrada no banco local. Parei o registro.")
                            os.remove(arquivo)
                            return {"status": "ok"}
                            
                        lista_limpa_para_ia = [{"numero_chamada": aluno.get('numero_chamada'), "nome": aluno.get('nome', 'Sem Nome')} for aluno in lista_oficial]
                            
                        faltosos_extraidos = dados_aula.get('faltosos', {})
                        try: numeros_frequencia = ia.traduzir_nomes_para_chamada(faltosos_extraidos, lista_limpa_para_ia)
                        except Exception as e: numeros_frequencia = {"F": [], "J": [], "nao_encontrados": [], "ambiguos": {}}
                        if not numeros_frequencia: numeros_frequencia = {"F": [], "J": [], "nao_encontrados": [], "ambiguos": {}}
                        
                        # --- ALERTA DE AMBIGUIDADE (AS VÁRIAS MARIAS) ---
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
                            enviar_mensagem_whatsapp(remetente, msg_conflito)
                            if os.path.exists(arquivo): os.remove(arquivo)
                            return {"status": "ok"}

                        # Se não deu conflito, segue normal usando nossa função limpa!
                        exibir_resumo_confirmacao(remetente, dados_aula, ids_diario, numeros_frequencia, lista_oficial, lista_limpa_para_ia)
                        if os.path.exists(arquivo): os.remove(arquivo)
                        
                    except Exception as e: 
                        print("\n🔴🔴🔴 ERRO DETALHADO NO ÁUDIO 🔴🔴🔴")
                        traceback.print_exc()
                        enviar_mensagem_whatsapp(remetente, "❌ Erro interno ao processar áudio.")
                        if os.path.exists(arquivo): os.remove(arquivo)
                        return {"status": "ok"}

        # ==============================================================================
        # FLUXO DE TEXTO (E AUDIOS CONVERTIDOS EM TEXTO)
        # ==============================================================================
        if tipo == 'chat' and estado_atual:
            etapa = estado_atual['etapa']

            # NOVO: O Professor tirando a dúvida das Marias
            if etapa == 'esperando_desambiguacao':
                resolvido = ia.resolver_ambiguidade(texto_msg, estado_atual['ambiguos'], estado_atual['dados_aula'].get('faltosos', {}))
                
                if resolvido and "erro" not in resolvido:
                    enviar_mensagem_whatsapp(remetente, "🔄 Nomes confirmados! Recalculando faltas...")
                    estado_atual['dados_aula']['faltosos'] = resolvido
                    nova_freq = ia.traduzir_nomes_para_chamada(resolvido, estado_atual['lista_limpa_para_ia'])
                    
                    # Chama a tela de confirmacao final
                    exibir_resumo_confirmacao(
                        remetente, estado_atual['dados_aula'], estado_atual['ids_diario'], 
                        nova_freq, estado_atual['lista_oficial'], estado_atual['lista_limpa_para_ia']
                    )
                else:
                    enviar_mensagem_whatsapp(remetente, "❌ Não entendi muito bem. Diga de forma clara qual é o nome completo!")

            elif etapa == 'esperando_confirmacao':
                if texto_msg.lower() in ['sim', 'ok', 'pode', 'confirmo', 'certo', 'vai', 's', 'bora', 'tá certo']:
                    usuarios_salvos = carregar_usuarios()
                    if remetente in usuarios_salvos:
                        login_salvo = usuarios_salvos[remetente]['login']
                        senha_salva = usuarios_salvos[remetente]['senha']
                        dados_aula = estado_atual.get('dados_aula', {})

                        enviar_mensagem_whatsapp(remetente, f"🚀 Registrando aula em {dados_aula.get('turma_site')}...")
                        background_tasks.add_task(tentar_executar_robo, remetente, estado_atual, login_salvo, senha_salva)
                    else:
                        estados_usuarios[remetente]['etapa'] = 'esperando_login'
                        enviar_mensagem_whatsapp(remetente, "Certo, vamos iniciar o registro.\n🔒 Digite apenas seu **LOGIN**:\nA senha será solicitada na próxima mensagem.")
                else: enviar_mensagem_whatsapp(remetente, "Mande **SIM** para confirmar ou outro áudio para corrigir.")

            elif etapa == 'esperando_login':
                estados_usuarios[remetente]['login_salvo'] = texto_msg
                estados_usuarios[remetente]['etapa'] = 'esperando_senha'
                enviar_mensagem_whatsapp(remetente, "👍 Agora digite sua **SENHA**:")
            
            elif etapa == 'esperando_senha':
                salvar_usuario(remetente, estado_atual['login_salvo'], texto_msg)
                enviar_mensagem_whatsapp(remetente, "💾 Credenciais salvas!\n🚀 Iniciando robô...")
                background_tasks.add_task(tentar_executar_robo, remetente, estado_atual, estado_atual['login_salvo'], texto_msg)

    except Exception as e: print(f"Erro webhook genérico: {e}")
    return {"status": "ok"}

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=8000)