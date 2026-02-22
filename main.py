import os
import ia          # Seu arquivo de inteligência
import registro    # Seu robô Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURAÇÕES DO PROFESSOR ---
LOGIN = "Pedro"
SENHA = "Agape2025!"
ARQUIVO_AUDIO = "WhatsApp-Ptt-2026-02-08-at-20.46.21.mp3"

def main():
    print("🚀 INICIANDO SISTEMA DE REGISTRO POR VOZ...")

    # 1. VERIFICAÇÃO DO ÁUDIO
    if not os.path.exists(ARQUIVO_AUDIO):
        print(f"❌ Erro: O arquivo '{ARQUIVO_AUDIO}' não existe.")
        print("   -> Rode o script 'gerar_teste.py' primeiro.")
        return

    # 2. INTELIGÊNCIA ARTIFICIAL (Transcrição + Interpretação)
    try:
        print(f"\n🎧 Ouvindo áudio: {ARQUIVO_AUDIO}...")
        texto_transcrito = ia.transcrever_audio(ARQUIVO_AUDIO)
        print(f"   📝 Texto entendido: \"{texto_transcrito}\"")

        print("\n🧠 Processando dados da aula...")
        dados_aula = ia.processar_mensagem(texto_transcrito)
        
        # Exibe o que a IA entendeu para você conferir
        print("   📦 Dados extraídos (JSON):")
        print(f"      - Turma:    {dados_aula.get('turma')}")
        print(f"      - Data:     {dados_aula.get('data')}")
        print(f"      - Conteúdo: {dados_aula.get('conteudo')}")
        print(f"      - Tarefa:   {dados_aula.get('tarefa')}")
        print(f"      - Faltosos: {dados_aula.get('faltosos')}")

    except Exception as e:
        print(f"❌ Erro na IA: {e}")
        return

    # 3. AUTOMAÇÃO (Selenium)
    print("\n🤖 Iniciando o Robô Professor...")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)
        driver.maximize_window()

        # Chama a função coringa passando os dados vindos da IA
        registro.registrar_aula_completa(
            driver=driver,
            login=LOGIN,
            senha=SENHA,
            nome_turma=dados_aula['turma'],      # "5A" -> IA converteu
            data=dados_aula['data'],             # "08/02/2026"
            conteudo=dados_aula['conteudo'],
            tarefa=dados_aula['tarefa'],
            nomes_faltosos=dados_aula['faltosos'] # ["Ludmilla", "João"]
        )
        
        print("\n✅ CICLO COMPLETO FINALIZADO COM SUCESSO!")

    except Exception as e:
        print(f"\n❌ Erro no Robô: {e}")

    finally:
        input("\nPressione ENTER para fechar o navegador...")
        if 'driver' in locals():
            driver.quit()

if __name__ == "__main__":
    main()