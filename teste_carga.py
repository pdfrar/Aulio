import asyncio
import httpx
import time

URL_WEBHOOK = "http://localhost:8000/webhook"

# A lista exata dos seus números permitidos
NUMEROS = [
    "558396336492@c.us", "5583996336492@c.us", "5583999030176@c.us",
    "558399030176@c.us", "5583981219527@c.us", "558381219527@c.us",
    "558398156803@c.us", "55838156803@c.us", "5583996035018@c.us",
    "558396035018@c.us"
]

async def disparar_mensagem_falsa(client, numero):
    # Simulando o payload que a API do WhatsApp envia para o seu webhook
    payload = {
        "event": "onmessage",
        "type": "chat",
        "fromMe": False,
        "from": numero,
        "body": "Estou testando o servidor!" 
    }
    
    inicio = time.time()
    # Manda a requisição POST para o seu servidor
    resposta = await client.post(URL_WEBHOOK, json=payload)
    fim = time.time()
    
    tempo_gasto = fim - inicio
    print(f"✅ [{numero}] Respondido em {tempo_gasto:.3f} segundos | Status: {resposta.status_code}")

async def main():
    print("🚀 Preparando para bombardear o servidor com 10 mensagens simultâneas...\n")
    inicio_total = time.time()
    
    # O AsyncClient permite disparar as 10 requisições "ao mesmo tempo"
    # O timeout=None diz para o script esperar o tempo que for necessário!
    async with httpx.AsyncClient(timeout=None) as client:
        tarefas = [disparar_mensagem_falsa(client, numero) for numero in NUMEROS]
        await asyncio.gather(*tarefas) # Executa todas juntas!
        
    fim_total = time.time()
    print(f"\n🏁 Teste de Carga concluído! Tempo total para atender 10 professores: {fim_total - inicio_total:.3f} segundos")

if __name__ == "__main__":
    asyncio.run(main())