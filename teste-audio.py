import ia  # Importa o seu módulo de IA (certifique-se que o nome do arquivo é ia.py ou cerebro.py)
import os

arquivo_audio = "comando_teste.mp3"

if os.path.exists(arquivo_audio):
    print(f"🎧 Ouvindo o arquivo: {arquivo_audio}...")
    
    # 1. Transcreve (Áudio -> Texto)
    texto_transcrito = ia.transcrever_audio(arquivo_audio)
    print(f"\n📝 Texto Transcrito pela Groq:\n'{texto_transcrito}'")
    
    # 2. Processa (Texto -> JSON)
    print("\n🧠 Extraindo dados para JSON...")
    dados = ia.processar_mensagem(texto_transcrito)
    
    print("\n📦 JSON FINAL:")
    print(dados)
else:
    print("❌ Rode o 'gerar_teste.py' primeiro para criar o áudio.")