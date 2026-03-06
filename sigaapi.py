import requests
import json
import unicodedata
import re

# ==========================================================
# CONFIGURAÇÕES
# ==========================================================
BASE_URL = "https://siga.activesoft.com.br"
TOKEN = "Bearer ZaAmsMtiTSf3nxpuTJuZ2zkgOmVMhr"
ARQUIVO_DIARIOS = "diarios_com_turmas_2026.json"

def limpar_texto(texto):
    if not texto: return ""
    nfkd_form = unicodedata.normalize('NFKD', str(texto))
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).upper().strip()

class SigaAPI:
    def __init__(self, base_url, token, arquivo_mapeamento):
        self.base_url = base_url
        self.headers = {
            "Authorization": token, "Content-Type": "application/json", "Accept": "application/json"
        }
        self.arquivo_mapeamento = arquivo_mapeamento
        self.mapa_turmas = self._carregar_mapeamento_turmas()
        # cache para traduções de abreviações (nome curto -> (id, nome_completo))
        self.cache = self._carregar_cache()

    def _carregar_mapeamento_turmas(self):
        try:
            with open(self.arquivo_mapeamento, 'r', encoding='utf-8') as f:
                dados = json.load(f)
            turmas_lista = []
            vistos = set()
            for item in dados:
                t_id = item.get('id_turma')
                t_nome = item.get('nome_turma_completo')
                if t_id and t_id not in vistos:
                    turmas_lista.append((t_id, t_nome))
                    vistos.add(t_id)
            return turmas_lista
        except Exception: return []

    def _cache_filepath(self):
        return f"{self.arquivo_mapeamento}.cache.json"

    def _carregar_cache(self):
        path = self._cache_filepath()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _salvar_cache(self):
        path = self._cache_filepath()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def traduzir_nome_curto(self, nome_curto):
        """
        Tradução com prefixos obrigatórios:
        F5A -> Fundamental 5º Ano A
        M1B -> Médio 1ª Série B
        I2C -> Infantil II C

        A função agora utiliza cache para acelerar buscas e aprende automaticamente
        após encontrar um resultado; o cache é gravado em disco.
        """
        busca = limpar_texto(nome_curto)
        # checar cache primeiro
        if busca in self.cache:
            entry = self.cache.get(busca)
            if entry:
                return tuple(entry)

        numeros = re.findall(r'\d+', busca)
        num_val = int(numeros[0]) if numeros else 0
        
        # Identifica a letra da turma (ex: A, B, C) - geralmente é a última letra
        letras_apenas = re.sub(r'[^A-Z]', '', busca)
        letra_turma = letras_apenas[-1] if letras_apenas else ""
        
        # Identificação dos prefixos
        quer_fundamental = 'F' in busca
        quer_medio = 'M' in busca
        quer_infantil = 'I' in busca

        # Otimização de busca (Turmas altas no final do arquivo)
        lista_busca = self.mapa_turmas
        if quer_medio or (quer_fundamental and num_val >= 6):
            print(f"⚡ Otimização: Buscando do final para o início...")
            lista_busca = reversed(self.mapa_turmas)

        for t_id, t_nome_completo in lista_busca:
            nome_full = limpar_texto(t_nome_completo)
            
            # Validação da letra da turma
            if f" {letra_turma}" not in nome_full and f"-{letra_turma}" not in nome_full:
                continue

            # 1. BLOCO FUNDAMENTAL (F5A, F9B...)
            if quer_fundamental:
                if "MEDIO" not in nome_full and "INFANTIL" not in nome_full:
                    # Checa "5 ANO", "5O ANO" (normalizado de 5º) ou "5A ANO"
                    if any(f"{num_val}{s} ANO" in nome_full for s in ["", "O", "A"]):
                        # salvar no cache antes de retornar
                        self.cache[busca] = (t_id, t_nome_completo)
                        self._salvar_cache()
                        return t_id, t_nome_completo
                continue

            # 2. BLOCO MÉDIO (M1A, M3B...)
            if quer_medio:
                if "MEDIO" in nome_full:
                    if any(f"{num_val}{s} SERIE" in nome_full for s in ["", "O", "A"]):
                        self.cache[busca] = (t_id, t_nome_completo)
                        self._salvar_cache()
                        return t_id, t_nome_completo
                continue

            # 3. BLOCO INFANTIL (I2A, I3B...)
            if quer_infantil:
                if "INFANTIL" in nome_full:
                    romanos = ["I", "II", "III", "IV", "V"]
                    romano = romanos[num_val-1] if 0 < num_val <= len(romanos) else ""
                    if romano and f"INFANTIL {romano}" in nome_full:
                        self.cache[busca] = (t_id, t_nome_completo)
                        self._salvar_cache()
                        return t_id, t_nome_completo
                continue

        # se chegou aqui, não encontrou nada
        return None, None

    def treinar_turma(self, nome_curto, nome_completo):
        """Armazena manualmente um mapeamento entre abreviação e turma completa.

        O método busca o id correspondente a nome_completo nos dados carregados e
        atualiza o cache. Usado quando o bot erra ou quando se quer gravar uma
        tradução customizada.
        """
        chave = limpar_texto(nome_curto)
        busc_full = limpar_texto(nome_completo)
        for t_id, t_nome in self.mapa_turmas:
            if busc_full == limpar_texto(t_nome):
                self.cache[chave] = (t_id, t_nome)
                self._salvar_cache()
                return True
        # se não encontrou a turma nos dados originais, ainda assim grava o par
        self.cache[chave] = (None, nome_completo)
        self._salvar_cache()
        return False

    def buscar_aluno_na_turma(self, nome_curto_turma, nome_aluno_busca):
        id_t, nome_completo = self.traduzir_nome_curto(nome_curto_turma)
        if not id_t:
            print(f"❌ Turma '{nome_curto_turma}' não localizada.")
            return []
        
        print(f"📡 Buscando em: {nome_completo}")
        url = f"{self.base_url}/api/v0/acesso/alunos/"
        try:
            res = requests.get(url, headers=self.headers)
            if res.status_code == 200:
                termo = limpar_texto(nome_aluno_busca)
                return [a for a in res.json() if a.get('id_turma') == id_t and termo in limpar_texto(a.get('nome', ''))]
            return []
        except Exception as e:
            print(f"Erro: {e}"); return []

if __name__ == "__main__":
    siga = SigaAPI(BASE_URL, TOKEN, ARQUIVO_DIARIOS)

    # EXEMPLOS DE BUSCA:
    # "F5A" -> 5º Ano Fundamental A
    # "M1B" -> 1ª Série Médio B
    # "I2C" -> Infantil II C
    
    TURMA = "F7C" 
    ALUNO = "ESTER"

    print(f"--- CONSULTA INTELIGENTE v6.0 (Com Prefixos) ---")
    resultados = siga.buscar_aluno_na_turma(TURMA, ALUNO)

    if resultados:
        for r in resultados:
            print(f"✅ {r['nome']} (Matrícula: {r['matricula']})")
    else:
        print(f"⚠️ Nenhum resultado para '{ALUNO}' na turma '{TURMA}'.")