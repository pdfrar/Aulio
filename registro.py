import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def registrar_aula_completa(login, senha, nome_turma, data, conteudo, tarefa, nomes_faltosos, apenas_frequencia=False):
    print(f"\n🔎 INICIANDO ROBÔ (TURMA: {nome_turma} | DATA: {data})")
    
    print("🚀 Abrindo navegador...")
    # Quando for iniciar o navegador no seu código, use esta configuração:
    opcoes = Options()
    opcoes.add_argument("--headless") # Roda invisível (SEM TELA)
    opcoes.add_argument("--no-sandbox") # Segurança: obrigatório no Linux
    opcoes.add_argument("--disable-dev-shm-usage") # Evita travar por falta de memória

    # Aponta para o ChromeDriver que acabamos de instalar no Ubuntu
    servico = Service("/usr/bin/chromedriver")

    # Inicia o navegador
    driver = webdriver.Chrome(service=servico, options=opcoes)
    driver.maximize_window()

    wait = WebDriverWait(driver, 15)
    short_wait = WebDriverWait(driver, 2)

    try: 
        def procurar_em_frames(by, value):
            driver.switch_to.default_content()
            try: return short_wait.until(EC.presence_of_element_located((by, value)))
            except: pass
            for frame in driver.find_elements(By.TAG_NAME, "frame") + driver.find_elements(By.TAG_NAME, "iframe"):
                try:
                    driver.switch_to.default_content()
                    driver.switch_to.frame(frame)
                    return short_wait.until(EC.presence_of_element_located((by, value)))
                except: pass
            return None

        def clicar_js(elemento): driver.execute_script("arguments[0].click();", elemento)

        def encontrar_link_inteligente(termo_busca):
            if not termo_busca: return None
            padrao_site = termo_busca.upper().strip()
            match = re.match(r"^(\d+)([A-Z])$", padrao_site)
            if match: padrao_site = f"{match.group(1)}º ANO - {match.group(2)}"
            
            def varrer_cards():
                cards = driver.find_elements(By.CLASS_NAME, "card")
                if not cards: cards = driver.find_elements(By.TAG_NAME, "tr")
                for card in cards:
                    try:
                        if padrao_site in card.text.upper():
                            try: link = card.find_element(By.PARTIAL_LINK_TEXT, "Diário de classe")
                            except: link = card.find_element(By.TAG_NAME, "a")
                            return link.get_attribute("href")
                    except: continue
                return None

            driver.switch_to.default_content()
            url = varrer_cards()
            if url: return url

            for frame in driver.find_elements(By.TAG_NAME, "frame") + driver.find_elements(By.TAG_NAME, "iframe"):
                driver.switch_to.default_content()
                driver.switch_to.frame(frame)
                url = varrer_cards()
                if url: return url
            return None

        # ==============================================================================
        # 1. LOGIN
        # ==============================================================================
        print("🔐 Login...")
        driver.get("https://siga03.activesoft.com.br/login/?instituicao=AGAPE")
        try:
            wait.until(EC.visibility_of_element_located((By.ID, "id_login"))).send_keys(login)
            driver.find_element(By.ID, "id_senha").send_keys(senha)
            clicar_js(driver.find_element(By.CSS_SELECTOR, "[data-cy='botao-login']"))
            time.sleep(3) 
            driver.switch_to.default_content()
            if len(driver.find_elements(By.ID, "id_login")) > 0 and driver.find_element(By.ID, "id_login").is_displayed():
                raise ValueError("LOGIN_ERROR: Login ou senha incorretos.")
        except: pass

        # ==============================================================================
        # 2. BUSCAR TURMA
        # ==============================================================================
        print("📂 Acessando Lista de Turmas...")
        turmas_apareceram = False
        xpath_exibir = "//*[contains(text(), 'Exibir') or @value='Exibir' or @title='Exibir']"

        for _ in range(3):
            btn_exibir = procurar_em_frames(By.XPATH, xpath_exibir)
            if btn_exibir:
                clicar_js(btn_exibir)
                time.sleep(3)
                driver.switch_to.default_content()
                if len(driver.find_elements(By.CLASS_NAME, "card")) > 0 or len(driver.find_elements(By.TAG_NAME, "table")) > 0:
                    turmas_apareceram = True; break
                for frame in driver.find_elements(By.TAG_NAME, "iframe"):
                    driver.switch_to.default_content()
                    driver.switch_to.frame(frame)
                    if len(driver.find_elements(By.CLASS_NAME, "card")) > 0:
                        turmas_apareceram = True; break
                if turmas_apareceram: break
            else: time.sleep(2)

        if not turmas_apareceram: raise RuntimeError("PAGE_ERROR: O sistema não carregou a lista de turmas.")
        url_turma = encontrar_link_inteligente(nome_turma)
        if url_turma: driver.get(url_turma)
        else: raise RuntimeError(f"PAGE_ERROR: Turma '{nome_turma}' não encontrada.")

        # ==============================================================================
        # 3. REGISTRAR AULA (PULA SE FOR APENAS FREQUÊNCIA)
        # ==============================================================================
        if not apenas_frequencia:
            print("📝 Registrando Aula...")
            link_registro = procurar_em_frames(By.CSS_SELECTOR, "a[href*='RegistroAulas.asp']")
            if link_registro:
                driver.get(link_registro.get_attribute("href"))
                campo_data = procurar_em_frames(By.ID, "DataAulaNovo")
                if campo_data:
                    campo_data.clear()
                    campo_data.send_keys(data)
                    driver.find_element(By.NAME, "ConteudoMinistradoNovo").send_keys(conteudo if conteudo else "Conteúdo não informado")
                    if tarefa: driver.find_element(By.NAME, "TarefaNovo").send_keys(tarefa)
                    clicar_js(driver.find_element(By.ID, "btnGravarNovo"))
                    try:
                        WebDriverWait(driver, 5).until(EC.alert_is_present())
                        driver.switch_to.alert.accept()
                        time.sleep(1)
                    except: pass
                else: raise RuntimeError("PAGE_ERROR: Formulário de aula falhou.")
            else: raise RuntimeError("PAGE_ERROR: Link de Registro de Aula falhou.")
        else:
            print("⏭️ Pulando Registro de Aula (Indo direto para Frequência)...")

        # ==============================================================================
        # 4. VOLTAR E ESPERAR
        # ==============================================================================
        if url_turma: driver.get(url_turma)
        else: driver.execute_script("window.history.go(-2)")
        time.sleep(4) 

        # ==============================================================================
        # 5. FREQUÊNCIA COM VARREDURA DE DUPLICATAS
        # ==============================================================================
        print("🙋‍♂️ Frequência...")
        link_freq = procurar_em_frames(By.CSS_SELECTOR, "a[href*='RegistroFrequencia2.asp']")
        
        if link_freq:
            driver.get(link_freq.get_attribute("href"))
            if not procurar_em_frames(By.ID, "TableFreq"): raise RuntimeError("PAGE_ERROR: Tabela de frequência sumiu.")

            while True:
                colunas_com_p = driver.find_elements(By.XPATH, "//a[@class='AlterarFrequencia' and normalize-space(text())='P']")
                try: existe_proximo = driver.find_element(By.XPATH, "//input[@value='Próximo']").is_displayed()
                except: existe_proximo = False

                if len(colunas_com_p) >= 10 and existe_proximo:
                    clicar_js(driver.find_element(By.XPATH, "//input[@value='Próximo']"))
                    time.sleep(3); procurar_em_frames(By.ID, "TableFreq")
                    continue 
                else:
                    if colunas_com_p:
                        ultima = colunas_com_p[-1]
                        id_col = ultima.get_attribute("id")
                        clicar_js(ultima)
                        time.sleep(2) 
                        
                        if nomes_faltosos and isinstance(nomes_faltosos, dict) and len(nomes_faltosos) > 0:
                            suffix = "10" if id_col == "0" else id_col.zfill(2)

                            conflitos = {}
                            nomes_resolvidos = {}

                            # 1. VARREDURA (Checa todos os nomes antes de clicar)
                            for nome_alvo, tipo_falta in nomes_faltosos.items():
                                nome_alvo_limpo = nome_alvo.upper().strip()
                                linhas_tabela = driver.find_elements(By.XPATH, "//table[@id='TableFreq']/tbody/tr")
                                
                                linhas_encontradas = []
                                for linha in linhas_tabela:
                                    if nome_alvo_limpo in linha.text.upper():
                                        nome_completo = linha.text.split('\n')[0][:45].strip()
                                        linhas_encontradas.append(nome_completo)
                                
                                if len(linhas_encontradas) > 1:
                                    conflitos[nome_alvo] = linhas_encontradas
                                elif len(linhas_encontradas) == 1:
                                    nomes_resolvidos[linhas_encontradas[0]] = tipo_falta
                                else:
                                    print(f"        ❌ Aluno não encontrado: {nome_alvo}")

                            # SE HOUVER CONFLITO, GERA ERRO E PARA A CHAMADA AQUI!
                            if conflitos:
                                raise ValueError(f"AMBIGUOUS_NAME_ERROR:{json.dumps(conflitos, ensure_ascii=False)}")

                            # 2. EXECUÇÃO (Só roda se não houver conflitos)
                            print(f"      🎲 Lançando faltas (Coluna ID: {suffix})...")
                            for nome_completo, tipo_falta in nomes_resolvidos.items():
                                linhas_tabela = driver.find_elements(By.XPATH, "//table[@id='TableFreq']/tbody/tr")
                                for linha in linhas_tabela:
                                    if nome_completo.upper() in linha.text.upper():
                                        try:
                                            xpath_chk = f".//img[substring(@id, string-length(@id) - string-length('{suffix}') + 1) = '{suffix}']"
                                            chk = linha.find_element(By.XPATH, xpath_chk)
                                            clicar_js(chk)
                                            if tipo_falta == 1:
                                                time.sleep(0.5)
                                                clicar_js(chk)
                                            print(f"        ✅ Falta marcada: {nome_completo}")
                                        except: pass
                                        break

                        clicar_js(driver.find_element(By.CSS_SELECTOR, "input[value='Gravar']"))
                        try:
                            WebDriverWait(driver, 5).until(EC.alert_is_present())
                            driver.switch_to.alert.accept()
                        except: pass
                        break 
                    else: raise RuntimeError("PAGE_ERROR: Nenhuma aula disponível hoje.")
        else: raise RuntimeError("PAGE_ERROR: Botão de lançar frequência sumiu.")
            
    except Exception as e: raise e
    finally: driver.quit()