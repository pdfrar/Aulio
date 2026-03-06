from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn
import requests
import os
import base64
import json         
import ia           
import registro     
import sigaapi 
from dotenv import load_dotenv
import sys
import traceback 
sys.stdout.reconfigure(encoding='utf-8')

# Carrega as variáveis do arquivo .env
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

# --- INTEGRAÇÃO COM A API ---
def validar_alunos_api(turma_codigo_api, faltosos_dict):
    conflitos, resolvidos, nao_encontrados = {}, {}, []
    if faltosos_dict and isinstance(faltosos_dict, dict) and turma_codigo_api:
        siga = sigaapi.SigaAPI(SIGA_BASE_URL, SIGA_TOKEN, ARQUIVO_DIARIOS)
        for nome_alvo, status in faltosos_dict.items():
            resultados = siga.buscar_aluno_na_turma(turma_codigo_api, nome_alvo)
            if len(resultados) > 1:
                conflitos[nome_alvo] = [r.get('nome') for r in resultados]
            elif len(resultados) == 1:
                resolvidos[resultados[0].get('nome')] = status
            else:
                nao_encontrados.append(nome_alvo)
    return conflitos, resolvidos, nao_encontrados

def gerar_mensagem_conflito(conflitos):
    msg = "⚠️ *Atenção! Encontrei alunos com nomes parecidos na turma:*\n\n"
    for n, opcoes in conflitos.items():
        msg += f"👤 *{n}* pode ser:\n"
        for op in opcoes: msg += f"  - {op}\n"
    msg += "\n🎙️ Responda com um áudio ou texto dizendo o nome completo correto para eu não errar!"
    return msg

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
            nome_turma=dados_aula.get('turma_site'),
            data=dados_aula.get('data'),
            conteudo=conteudo_final, 
            tarefa=dados_aula.get('tarefa'),
            nomes_faltosos=dados_aula.get('faltosos'), apenas_frequencia=apenas_freq
        )
        enviar_mensagem_whatsapp(remetente, "✅ Registro de aula cadastrado! A chamada foi gravada. Pode mandar a próxima aula.\n*(Para trocar senha, digite 'Resetar')*")
        if remetente in estados_usuarios: del estados_usuarios[remetente]
        
    except Exception as e:
        erro = str(e)
        if "LOGIN_ERROR" in erro:
            apagar_usuario(remetente)
            enviar_mensagem_whatsapp(remetente, "❌ *Acesso Negado!*\nSeu login ou senha estão incorretos.\n\n♻️ Credenciais apagadas. Envie um novo áudio para recomeçar.")
            if remetente in estados_usuarios: del estados_usuarios[remetente]
            
        elif "PAGE_ERROR" in erro:
            msg_erro = erro.split("PAGE_ERROR:")[1].strip()
            enviar_mensagem_whatsapp(remetente, f"⚠️ *Erro no Sistema Escolar:*\n_{msg_erro}_\n\n🔄 Responda **SIM** para eu tentar de novo. Se persistir, contate o suporte.")
            estados_usuarios[remetente]['etapa'] = 'esperando_confirmacao'
            
        else:
            enviar_mensagem_whatsapp(remetente, f"❌ Erro Inesperado: Tente mandar o áudio novamente.")
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
            if remetente in boas_vindas_enviadas: boas_vindas_enviadas.remove(remetente) 
            return {"status": "ok"}
            
        estado_atual = estados_usuarios.get(remetente)
        if eh_minha and tipo not in ['ptt', 'audio'] and not estado_atual: return {"status": "ignorado_loop"}

        # ==============================================================================
        # ONBOARDING E BOAS-VINDAS
        # ==============================================================================
        if remetente not in boas_vindas_enviadas:
            boas_vindas_enviadas.add(remetente)
            usuarios_salvos = carregar_usuarios()
            
            if remetente not in usuarios_salvos:
                msg_intro = (
                    "👋 Olá! Eu sou o *Aulio*, seu assistente inteligente para registro de aulas.\n"
                    "Meu objetivo é transformar seus áudios em diários preenchidos no sistema escolar em segundos! 🚀\n"
                )
                enviar_mensagem_whatsapp(remetente, msg_intro)
                
                if tipo == 'chat':
                    enviar_mensagem_whatsapp(remetente, "🎙️ Para começarmos, grave um áudio relatando como foi sua aula (turma, conteúdo e faltosos).")
                    return {"status": "ok"}

        if tipo == 'chat' and not estado_atual:
            enviar_mensagem_whatsapp(remetente, "🎙️ Estou pronto! Pode me enviar o áudio com o resumo da sua aula.")
            return {"status": "ok"}

        # ==============================================================================
        # FLUXO DE ÁUDIO
        # ==============================================================================
        if tipo == 'ptt' or tipo == 'audio':
            msg_id = dados.get('id')
            
            # 1. RESOLVER NOMES
            if estado_atual and estado_atual['etapa'] == 'esperando_desambiguacao':
                enviar_mensagem_whatsapp(remetente, "🧠 Validando os nomes corrigidos...")
                arquivo = baixar_audio_limpo(msg_id)
                texto_transcrito = ia.transcrever_audio(arquivo)
                os.remove(arquivo)
                
                novos_faltosos = ia.resolver_ambiguidade(texto_transcrito, estado_atual['conflitos'], estado_atual['dados_aula']['faltosos'])
                
                # --- NOVO BLOQUEIO DE ERRO DA IA ---
                if "erro" in novos_faltosos:
                    enviar_mensagem_whatsapp(remetente, "❌ Não entendi qual aluno você escolheu. Por favor, diga ou digite o nome de uma das opções acima.")
                    return {"status": "ok"}
                
                conflitos, resolvidos, nao_encontrados = validar_alunos_api(estado_atual['dados_aula'].get('turma_api'), novos_faltosos)
                
                if conflitos:
                    estado_atual['conflitos'] = conflitos
                    enviar_mensagem_whatsapp(remetente, gerar_mensagem_conflito(conflitos))
                    return {"status": "ok"}
                
                estado_atual['dados_aula']['faltosos'] = resolvidos
                lista_f = [f"{n} (*{'Justificada' if s == 1 else 'Normal'}*)" for n, s in resolvidos.items()]
                texto_faltosos = ", ".join(lista_f) if lista_f else "Nenhum"
                
                aviso_nao_enc = f"\n⚠️ *Aviso:* Não localizados na API: {', '.join(nao_encontrados)}\n" if nao_encontrados else ""
                
                msg_confirma = (
                    f"✅ Nomes atualizados para:\n"
                    f"🚫 Faltosos: {texto_faltosos}\n"
                    f"{aviso_nao_enc}\n"
                    f"Tudo certo agora? Responda **SIM** para finalizar a chamada."
                )
                enviar_mensagem_whatsapp(remetente, msg_confirma)
                estado_atual['etapa'] = 'esperando_confirmacao'
                return {"status": "ok"}

            # 2. FLUXO NORMAL DE ÁUDIO
            print(f"\n[DEBUG 1] Áudio recebido do remetente {remetente}.")
            dados_anteriores = estado_atual['dados_aula'] if estado_atual and 'dados_aula' in estado_atual else None
            enviar_mensagem_whatsapp(remetente, "🔄 Atualizando..." if dados_anteriores else "🎧 Processando e validando alunos no sistema...")
            
            arquivo = baixar_audio_limpo(msg_id)
            if arquivo:
                try:
                    texto_transcrito = ia.transcrever_audio(arquivo)
                    if texto_transcrito:
                        dados_aula = ia.extrair_dados_da_aula(texto_transcrito, dados_anteriores)

                        if not dados_aula:
                            print("🔴 [ERRO FATAL] A função ia.extrair_dados_da_aula retornou None/Vazio!")
                            enviar_mensagem_whatsapp(remetente, "❌ O cérebro do robô falhou ao extrair o JSON da aula. Tente novamente.")
                            os.remove(arquivo)
                            return {"status": "ok"}

                        turma_api = dados_aula.get('turma_api')
                        faltosos = dados_aula.get('faltosos', {})
                        
                        conflitos, resolvidos, nao_encontrados = validar_alunos_api(turma_api, faltosos)
                        
                        if conflitos:
                            estados_usuarios[remetente] = {"etapa": "esperando_desambiguacao", "dados_aula": dados_aula, "conflitos": conflitos}
                            enviar_mensagem_whatsapp(remetente, gerar_mensagem_conflito(conflitos))
                        else:
                            dados_aula['faltosos'] = resolvidos 
                            estados_usuarios[remetente] = {"etapa": "esperando_confirmacao", "dados_aula": dados_aula}
                            
                            lista_f = [f"{nome} (*{'Justificada' if status == 1 else 'Normal'}*)" for nome, status in resolvidos.items()]
                            texto_faltosos = ", ".join(lista_f) if lista_f else "Nenhum"
                            
                            aviso_nao_enc = f"\n⚠️ *Aviso:* Não localizados na API: {', '.join(nao_encontrados)}\n" if nao_encontrados else ""

                            bncc_texto = dados_aula.get('bncc', '')
                            conteudo_exibicao = f"{dados_aula.get('conteudo')}\n*(BNCC: {bncc_texto})*" if bncc_texto else dados_aula.get('conteudo')

                            msg_resposta = (
                                f"📋 **Confira os dados:**\n\n"
                                f"🏫 Turma: *{dados_aula.get('turma_site')}*\n"
                                f"📅 Data: *{dados_aula.get('data')}*\n"
                                f"📚 Conteúdo: {conteudo_exibicao}\n"
                                f"🏠 Tarefa: {dados_aula.get('tarefa')}\n"
                                f"🚫 Faltosos: {texto_faltosos}\n"
                                f"{aviso_nao_enc}\n"
                                f"✅ Responda **SIM** para continuar.\n"
                                f"🔄 Ou mande **outro áudio** para corrigir."
                            )
                            enviar_mensagem_whatsapp(remetente, msg_resposta)
                    
                    os.remove(arquivo)
                except Exception as e: 
                    print("\n🔴🔴🔴 ERRO DETALHADO NO ÁUDIO 🔴🔴🔴")
                    traceback.print_exc()
                    print("🔴🔴🔴------------------------------🔴🔴🔴\n")
                    enviar_mensagem_whatsapp(remetente, "❌ Erro interno ao processar áudio.")

        # ==============================================================================
        # FLUXO DE TEXTO
        # ==============================================================================
        elif tipo == 'chat' and estado_atual:
            etapa = estado_atual['etapa']
            
            if etapa == 'esperando_desambiguacao':
                enviar_mensagem_whatsapp(remetente, "🧠 Validando os nomes corrigidos...")
                novos_faltosos = ia.resolver_ambiguidade(texto_msg, estado_atual['conflitos'], estado_atual['dados_aula']['faltosos'])
                
                # --- NOVO BLOQUEIO DE ERRO DA IA ---
                if "erro" in novos_faltosos:
                    enviar_mensagem_whatsapp(remetente, "❌ Não entendi qual aluno você escolheu. Por favor, digite o nome exato de uma das opções acima.")
                    return {"status": "ok"}
                
                conflitos, resolvidos, nao_encontrados = validar_alunos_api(estado_atual['dados_aula'].get('turma_api'), novos_faltosos)
                
                if conflitos:
                    estado_atual['conflitos'] = conflitos
                    enviar_mensagem_whatsapp(remetente, gerar_mensagem_conflito(conflitos))
                    return {"status": "ok"}
                
                estado_atual['dados_aula']['faltosos'] = resolvidos
                lista_f = [f"{n} (*{'Justificada' if s == 1 else 'Normal'}*)" for n, s in resolvidos.items()]
                texto_faltosos = ", ".join(lista_f) if lista_f else "Nenhum"
                aviso_nao_enc = f"\n⚠️ *Aviso:* Não localizados na API: {', '.join(nao_encontrados)}\n" if nao_encontrados else ""
                
                msg_confirma = (
                    f"✅ Nomes atualizados para:\n"
                    f"🚫 Faltosos: {texto_faltosos}\n"
                    f"{aviso_nao_enc}\n"
                    f"Tudo certo agora? Responda **SIM** para finalizar a chamada."
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
                            enviar_mensagem_whatsapp(remetente, f"🚀 Retomando chamada de {dados_aula.get('turma_site')}...")
                        else:
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
                login_final = estado_atual['login_salvo']
                senha_final = texto_msg
                salvar_usuario(remetente, login_final, senha_final)
                enviar_mensagem_whatsapp(remetente, "💾 Credenciais salvas!\n🚀 Iniciando robô...")
                background_tasks.add_task(tentar_executar_robo, remetente, estado_atual, login_final, senha_final)

    except Exception as e: 
        print(f"Erro webhook genérico: {e}")
    return {"status": "ok"}

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=8000)