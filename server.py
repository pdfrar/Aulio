from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn
import requests
import os
import base64
import json         
import ia           
import registro     
from dotenv import load_dotenv  # <-- ADICIONADO

# Carrega as variáveis do arquivo .env
load_dotenv() # <-- ADICIONADO

app = FastAPI()

# --- CONFIGURAÇÕES CARREGADAS DO .ENV ---
# O segundo parâmetro é um "fallback" caso a variável não exista no .env
SESSAO = os.getenv("WPP_SESSION", "sessao-pedro-final")
TOKEN = os.getenv("WPP_TOKEN") 
DOCKER_URL = os.getenv("WPP_URL", "http://localhost:21465") 
# ---------------------------------------

ARQUIVO_USUARIOS = "usuarios.json"  

NUMEROS_PERMITIDOS = [
    "558396336492@c.us", "5583996336492@c.us", "5583999030176@c.us",
    "558399030176@c.us", "5583981219527@c.us", "558381219527@c.us",
    "558398156803@c.us", "55838156803@c.us", "5583996035018@c.us",
    "558396035018@c.us"  
]

estados_usuarios = {}

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

def tentar_executar_robo(remetente, estado_atual, login_usar, senha_usar):
    dados_aula = estado_atual['dados_aula']
    apenas_freq = estado_atual.get('apenas_frequencia', False)
    conteudo_base = dados_aula.get('conteudo', '')
    bncc_base = dados_aula.get('bncc', '')
    conteudo_final = f"{conteudo_base}\nBNCC: {bncc_base}" if bncc_base else conteudo_base
    
    try:
        registro.registrar_aula_completa(
            login=login_usar, senha=senha_usar,
            nome_turma=dados_aula.get('turma'), data=dados_aula.get('data'),
            conteudo=conteudo_final, # <--- Usa a variável fundida aqui
            tarefa=dados_aula.get('tarefa'),
            nomes_faltosos=dados_aula.get('faltosos'), apenas_frequencia=apenas_freq
        )
        enviar_mensagem_whatsapp(remetente, "✅ Sucesso absoluto! A chamada foi gravada. Pode mandar a próxima aula.\n*(Para trocar senha, digite 'Resetar')*")
        if remetente in estados_usuarios: del estados_usuarios[remetente]
        
    except Exception as e:
        erro = str(e)
        if "LOGIN_ERROR" in erro:
            apagar_usuario(remetente)
            enviar_mensagem_whatsapp(remetente, "❌ *Acesso Negado!*\nSeu login ou senha estão incorretos.\n\n♻️ Credenciais apagadas. Envie um novo áudio para recomeçar.")
            if remetente in estados_usuarios: del estados_usuarios[remetente]
            
        elif "AMBIGUOUS_NAME_ERROR:" in erro:
            conflitos_str = erro.split("AMBIGUOUS_NAME_ERROR:")[1].strip()
            conflitos = json.loads(conflitos_str)
            
            msg = "⚠️ *Atenção! A aula foi registrada, mas a chamada foi PAUSADA.*\nEncontrei alunos com o mesmo nome na sala:\n\n"
            for n, opcoes in conflitos.items():
                msg += f"👤 *{n}* pode ser:\n"
                for op in opcoes:
                    msg += f"  - {op}\n"
            msg += "\n🎙️ Responda com um áudio ou texto dizendo o nome completo correto para eu não errar!"
            
            enviar_mensagem_whatsapp(remetente, msg)
            
            # SALVA O ESTADO
            estados_usuarios[remetente]['etapa'] = 'esperando_desambiguacao'
            estados_usuarios[remetente]['conflitos'] = conflitos
            estados_usuarios[remetente]['apenas_frequencia'] = True
            
        elif "PAGE_ERROR" in erro:
            msg_erro = erro.split("PAGE_ERROR:")[1].strip()
            enviar_mensagem_whatsapp(remetente, f"⚠️ *Erro no Sistema Escolar:*\n_{msg_erro}_\n\n🔄 Responda **SIM** para eu tentar de novo. Se persistir, contate o suporte.")
            estados_usuarios[remetente]['etapa'] = 'esperando_confirmacao'
            
        else:
            enviar_mensagem_whatsapp(remetente, f"❌ Erro Inesperado:\n_{erro}_\n\nTente mandar o áudio novamente.")
            if remetente in estados_usuarios: del estados_usuarios[remetente]

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
            return {"status": "ok"}
            
        estado_atual = estados_usuarios.get(remetente)
        if eh_minha and tipo not in ['ptt', 'audio'] and not estado_atual: return {"status": "ignorado_loop"}

        # ==============================================================================
        # FLUXO DE ÁUDIO
        # ==============================================================================
        if tipo == 'ptt' or tipo == 'audio':
            msg_id = dados.get('id')
            
            # 1. RESOLVER NOMES (Desambiguação)
            if estado_atual and estado_atual['etapa'] == 'esperando_desambiguacao':
                enviar_mensagem_whatsapp(remetente, "🧠 Entendido! Resolvendo os nomes...")
                arquivo = baixar_audio_limpo(msg_id)
                texto_transcrito = ia.transcrever_audio(arquivo)
                os.remove(arquivo)
                
                novos_faltosos = ia.resolver_ambiguidade(texto_transcrito, estado_atual['conflitos'], estado_atual['dados_aula']['faltosos'])
                estado_atual['dados_aula']['faltosos'] = novos_faltosos
                
                # --- NOVO: Manda para confirmação antes de rodar o robô! ---
                lista_f = [f"{n} (*{'Justificada' if s == 1 else 'Normal'}*)" for n, s in novos_faltosos.items()]
                texto_faltosos = ", ".join(lista_f) if lista_f else "Nenhum"
                
                msg_confirma = (
                    f"✅ Nomes atualizados para:\n"
                    f"🚫 Faltosos: {texto_faltosos}\n\n"
                    f"Tudo certo agora? Responda **SIM** para finalizar a chamada, ou mande a correção novamente."
                )
                enviar_mensagem_whatsapp(remetente, msg_confirma)
                
                # Volta para a etapa de confirmação (mas com 'apenas_frequencia' ainda ativo na memória)
                estado_atual['etapa'] = 'esperando_confirmacao'
                return {"status": "ok"}

            # 2. FLUXO NORMAL DE ÁUDIO
            dados_anteriores = estado_atual['dados_aula'] if estado_atual and 'dados_aula' in estado_atual else None
            enviar_mensagem_whatsapp(remetente, "🔄 Atualizando..." if dados_anteriores else "🎧 Processando...")
            arquivo = baixar_audio_limpo(msg_id)
            
            if arquivo:
                try:
                    texto_transcrito = ia.transcrever_audio(arquivo)
                    if texto_transcrito:
                        dados_aula = ia.extrair_dados_da_aula(texto_transcrito, dados_anteriores)
                        estados_usuarios[remetente] = {"etapa": "esperando_confirmacao", "dados_aula": dados_aula}
                        
                        faltosos_dict = dados_aula.get('faltosos', {})
                        if isinstance(faltosos_dict, dict) and faltosos_dict:
                            lista_f = [f"{nome} (*{'Justificada' if status == 1 else 'Normal'}*)" for nome, status in faltosos_dict.items()]
                            texto_faltosos = ", ".join(lista_f)
                        else: texto_faltosos = "Nenhum"
                        bncc_texto = dados_aula.get('bncc', '')
                        conteudo_exibicao = f"{dados_aula.get('conteudo')}\n*(BNCC: {bncc_texto})*" if bncc_texto else dados_aula.get('conteudo')

                        msg_resposta = (
                            f"📋 **Confira os dados:**\n\n"
                            f"🏫 Turma: *{dados_aula.get('turma')}*\n"
                            f"📅 Data: *{dados_aula.get('data')}*\n"
                            f"📚 Conteúdo: {conteudo_exibicao}\n"
                            f"🏠 Tarefa: {dados_aula.get('tarefa')}\n"
                            f"🚫 Faltosos: {texto_faltosos}\n\n"
                            f"✅ Responda **SIM** para continuar.\n"
                            f"🔄 Ou mande **outro áudio** para corrigir."
                        )
                        enviar_mensagem_whatsapp(remetente, msg_resposta)
                    os.remove(arquivo)
                except Exception as e: enviar_mensagem_whatsapp(remetente, "❌ Erro ao processar áudio.")

        # ==============================================================================
        # FLUXO DE TEXTO
        # ==============================================================================
        elif tipo == 'chat' and estado_atual:
            etapa = estado_atual['etapa']
            
            # 1. RESOLVER NOMES (Desambiguação via Texto)
            if etapa == 'esperando_desambiguacao':
                enviar_mensagem_whatsapp(remetente, "🧠 Resolvendo os nomes...")
                novos_faltosos = ia.resolver_ambiguidade(texto_msg, estado_atual['conflitos'], estado_atual['dados_aula']['faltosos'])
                estado_atual['dados_aula']['faltosos'] = novos_faltosos
                
                # --- NOVO: Manda para confirmação antes de rodar o robô! ---
                lista_f = [f"{n} (*{'Justificada' if s == 1 else 'Normal'}*)" for n, s in novos_faltosos.items()]
                texto_faltosos = ", ".join(lista_f) if lista_f else "Nenhum"
                
                msg_confirma = (
                    f"✅ Nomes atualizados para:\n"
                    f"🚫 Faltosos: {texto_faltosos}\n\n"
                    f"Tudo certo agora? Responda **SIM** para finalizar a chamada, ou mande a correção novamente."
                )
                enviar_mensagem_whatsapp(remetente, msg_confirma)
                
                estado_atual['etapa'] = 'esperando_confirmacao'
                return {"status": "ok"}

            if etapa == 'esperando_confirmacao':
                if texto_msg.lower() in ['sim', 'ok', 'pode', 'confirmo', 'certo', 'vai', 's', 'bora', 'tá certo']:
                    usuarios_salvos = carregar_usuarios()
                    if remetente in usuarios_salvos:
                        login_salvo = usuarios_salvos[remetente]['login']
                        senha_salva = usuarios_salvos[remetente]['senha']
                        
                        dados_aula = estado_atual.get('dados_aula', {})

                        if estado_atual.get('apenas_frequencia'):
                            enviar_mensagem_whatsapp(remetente, f"🚀 Retomando chamada de {dados_aula.get('turma')}...")
                        else:
                            enviar_mensagem_whatsapp(remetente, f"🚀 Registrando aula em {dados_aula.get('turma')}...")
                            
                        background_tasks.add_task(tentar_executar_robo, remetente, estado_atual, login_salvo, senha_salva)
                    else:
                        estados_usuarios[remetente]['etapa'] = 'esperando_login'
                        enviar_mensagem_whatsapp(remetente, "🔒 Digite seu **LOGIN**:")
                else: enviar_mensagem_whatsapp(remetente, "Mande **SIM** para confirmar ou outro áudio para corrigir.")

            elif etapa == 'esperando_login':
                estados_usuarios[remetente]['login_salvo'] = texto_msg
                estados_usuarios[remetente]['etapa'] = 'esperando_senha'
                enviar_mensagem_whatsapp(remetente, "👍 Agora digite sua **SENHA**:")
            
            elif etapa == 'esperando_senha':
                login_final = estado_atual['login_salvo']
                senha_final = texto_msg
                salvar_usuario(remetente, login_final, senha_final)
                enviar_mensagem_whatsapp(remetente, "💾 Credenciais salvas!\n🚀 Iniciando robô...")
                background_tasks.add_task(tentar_executar_robo, remetente, estado_atual, login_salvo, senha_salva)

    except Exception as e: print(f"Erro webhook: {e}")
    return {"status": "ok"}

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=8000)