import os
import sys
import requests
import json
import time
import sqlite3
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

_SIGA_TOKEN = os.getenv("SIGA_TOKEN", "")
HEADERS = {
    "Authorization": f"Bearer {_SIGA_TOKEN}",
    "Content-Type": "application/json"
}

ARQUIVO_DIARIOS = "diarios_com_turmas_2026.json"
BASE_URL = os.getenv("SIGA_BASE_URL", "https://siga.activesoft.com.br")
ARQUIVO_BANCO = "alunos.db"


def obter_conexao_banco():
    con = sqlite3.connect(ARQUIVO_BANCO)
    con.execute("""
        CREATE TABLE IF NOT EXISTS alunos_diario (
            id_diario   TEXT NOT NULL,
            id_turma    TEXT NOT NULL,
            numero_chamada INTEGER,
            matricula   TEXT,
            nome        TEXT NOT NULL,
            PRIMARY KEY (id_turma, numero_chamada)
        )
    """)
    return con


def reconstruir_mapa_diarios():
    """Baixa todas as turmas e diários, salvando inclusive o ID da disciplina."""
    print("[Aulio Data] Construindo mapa de diários e turmas com IDs de disciplina...")

    url_enturmacao = f"{BASE_URL}/api/v0/enturmacao_com_detalhes/"
    res_turmas = requests.get(url_enturmacao, headers=HEADERS)
    if res_turmas.status_code != 200:
        print(f"[Aulio Data] Erro ao buscar turmas: {res_turmas.status_code}")
        return False

    dados_turmas = res_turmas.json()
    if isinstance(dados_turmas, dict) and "results" in dados_turmas:
        dados_turmas = dados_turmas["results"]

    mapa_nomes_turmas = {}
    for aluno in dados_turmas:
        t_id = str(aluno.get("turma_id"))
        nome_completo = aluno.get("nome_turma_completo")
        if t_id and nome_completo and t_id not in mapa_nomes_turmas:
            mapa_nomes_turmas[t_id] = nome_completo

    print(f"[Aulio Data] {len(mapa_nomes_turmas)} turmas únicas mapeadas.")

    lista_final = []
    for t_id, nome_turma_completo in mapa_nomes_turmas.items():
        print(f"  -> Puxando diários e disciplinas da turma {t_id}...")
        url_diarios = f"{BASE_URL}/api/v0/diarios/?turma={t_id}"
        res_diarios = requests.get(url_diarios, headers=HEADERS)

        if res_diarios.status_code == 200:
            dados_diarios = res_diarios.json()
            if isinstance(dados_diarios, dict) and "results" in dados_diarios:
                dados_diarios = dados_diarios["results"]

            for diario in dados_diarios:
                id_diario = str(diario.get("id"))
                nome_disc = str(diario.get("nome_disciplina", "DESCONHECIDA")).upper()
                
                # 🎯 O PULO DO GATO: Capturamos o ID da disciplina retornado pela API
                # A API do Siga geralmente envia como 'disciplina' ou 'id_disciplina'
                id_disc = str(diario.get("disciplina") or diario.get("id_disciplina") or "")

                if id_diario:
                    lista_final.append({
                        "id_diario": id_diario,
                        "nome_disciplina": nome_disc,
                        "id_disciplina": id_disc, # Novo campo!
                        "id_turma": t_id,
                        "nome_turma_completo": nome_turma_completo
                    })
        else:
            print(f"     [Aviso] Falha turma {t_id}: {res_diarios.status_code}")

        time.sleep(0.2)

    with open(ARQUIVO_DIARIOS, "w", encoding="utf-8") as f:
        json.dump(lista_final, f, ensure_ascii=False, indent=4)

    print(f"[Aulio Data] {len(lista_final)} diários (com IDs de disciplina) salvos.")
    return True


def atualizar_cache_alunos():
    """Baixa alunos de cada TURMA e sincroniza com o banco local."""
    print("[Aulio Data] Atualizando banco de alunos por turma...")

    if not os.path.exists(ARQUIVO_DIARIOS):
        ok = reconstruir_mapa_diarios()
        if not ok: return False

    with open(ARQUIVO_DIARIOS, "r", encoding="utf-8") as f:
        diarios = json.load(f)

    turmas_unicas = {}
    for diario in diarios:
        tid = str(diario.get("id_turma"))
        turmas_unicas[tid] = diario.get("nome_turma_completo", "?")

    con = obter_conexao_banco()
    cur = con.cursor()
    cur.execute("DELETE FROM alunos_diario")
    con.commit()

    for id_turma, turma_nome in turmas_unicas.items():
        print(f"\n  Sincronizando {turma_nome}...", end=" ")

        resp = requests.get(
            f"{BASE_URL}/api/v0/acesso/alunos/?id_turma={id_turma}",
            headers=HEADERS
        )
        if resp.status_code != 200: continue

        j = resp.json()
        if isinstance(j, dict) and "results" in j: j = j["results"]

        alunos = [a for a in j if a.get("situacao_aluno_turma") == "Cursando" and str(a.get("id_turma")) == id_turma]
        alunos.sort(key=lambda a: a.get("nome", ""))

        alunos_turma = []
        for idx, a in enumerate(alunos, start=1):
            aluno_info = {
                "numero_chamada": idx,
                "matricula": str(a.get("matricula", "")),
                "nome": a.get("nome", "Sem Nome")
            }
            alunos_turma.append(aluno_info)
            cur.execute(
                "INSERT OR REPLACE INTO alunos_diario (id_diario, id_turma, numero_chamada, matricula, nome) VALUES (?, ?, ?, ?, ?)",
                ("", id_turma, idx, aluno_info["matricula"], aluno_info["nome"])
            )

        with open(f"alunos_turma_{id_turma}.json", "w", encoding="utf-8") as f:
            json.dump(alunos_turma, f, ensure_ascii=False, indent=4)

        time.sleep(0.15)

    con.commit()
    con.close()
    print(f"\n[Aulio Data] Sincronização completa!")
    return True


if __name__ == "__main__":
    reconstruir_mapa_diarios()
    atualizar_cache_alunos()