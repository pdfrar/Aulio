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
    """Baixa todas as turmas e diários, salva em JSON."""
    print("[Aulio Data] Construindo mapa de diários e turmas...")

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
        print(f"  -> Puxando diários da turma {t_id}...")
        url_diarios = f"{BASE_URL}/api/v0/diarios/?turma={t_id}"
        res_diarios = requests.get(url_diarios, headers=HEADERS)

        if res_diarios.status_code == 200:
            dados_diarios = res_diarios.json()
            if isinstance(dados_diarios, dict) and "results" in dados_diarios:
                dados_diarios = dados_diarios["results"]

            for diario in dados_diarios:
                id_diario = str(diario.get("id"))
                nome_disc = str(diario.get("nome_disciplina", "DESCONHECIDA")).upper()
                if id_diario:
                    lista_final.append({
                        "id_diario": id_diario,
                        "nome_disciplina": nome_disc,
                        "id_turma": t_id,
                        "nome_turma_completo": nome_turma_completo
                    })
        else:
            print(f"     [Aviso] Falha turma {t_id}: {res_diarios.status_code}")

        time.sleep(0.2)

    with open(ARQUIVO_DIARIOS, "w", encoding="utf-8") as f:
        json.dump(lista_final, f, ensure_ascii=False, indent=4)

    print(f"[Aulio Data] {len(lista_final)} diários salvos no {ARQUIVO_DIARIOS}.")
    return True


def atualizar_cache_alunos():
    """
    Baixa alunos de cada TURMA (1 req por turma), salva:
    1) alunos_turma_XXX.json — 1 arquivo por turma
    2) SQLite (alunos.db) — index por id_turma para consulta rápida
    """
    print("[Aulio Data] Atualizando banco de alunos por turma...")

    if not os.path.exists(ARQUIVO_DIARIOS):
        ok = reconstruir_mapa_diarios()
        if not ok:
            print("[Aulio Data] Erro ao reconstruir diários. Abortando.")
            return False

    with open(ARQUIVO_DIARIOS, "r", encoding="utf-8") as f:
        diarios = json.load(f)
    print(f"[Aulio Data] {len(diarios)} diários carregados.")

    # Agrupa diários por turma
    turmas_unicas = {}
    for diario in diarios:
        tid = str(diario.get("id_turma"))
        turmas_unicas[tid] = diario.get("nome_turma_completo", "?")
    print(f"[Aulio Data] {len(turmas_unicas)} turmas únicas.")

    con = obter_conexao_banco()
    cur = con.cursor()
    cur.execute("DELETE FROM alunos_diario")
    con.commit()

    for id_turma, turma_nome in turmas_unicas.items():
        print(f"\n  Turma {id_turma} ({turma_nome})", end=" ... ")

        resp = requests.get(
            f"{BASE_URL}/api/v0/acesso/alunos/?id_turma={id_turma}",
            headers=HEADERS
        )
        if resp.status_code != 200:
            print(f"STATUS {resp.status_code}")
            continue

        j = resp.json()
        if isinstance(j, dict) and "results" in j:
            j = j["results"]

        alunos = [a for a in j
                  if a.get("situacao_aluno_turma") == "Cursando"
                  and str(a.get("id_turma")) == id_turma]
        alunos.sort(key=lambda a: a.get("nome", ""))
        print(f"{len(alunos)} alunos", end="")

        alunos_turma = []
        for idx, a in enumerate(alunos, start=1):
            aluno_info = {
                "numero_chamada": idx,
                "matricula": str(a.get("matricula", "")),
                "nome": a.get("nome", "Sem Nome")
            }
            alunos_turma.append(aluno_info)
            # Salva no SQLite (1 req por turma → N diários)
            cur.execute(
                "INSERT OR REPLACE INTO alunos_diario (id_diario, id_turma, numero_chamada, matricula, nome) VALUES (?, ?, ?, ?, ?)",
                ("", id_turma, idx, aluno_info["matricula"], aluno_info["nome"])
            )

        # Salva JSON único: alunos_turma_389.json
        caminho_json = f"alunos_turma_{id_turma}.json"
        with open(caminho_json, "w", encoding="utf-8") as f:
            json.dump(alunos_turma, f, ensure_ascii=False, indent=4)

        print(f" → salvo {caminho_json}")
        time.sleep(0.15)

    con.commit()
    con.close()

    # Conta total
    con2 = obter_conexao_banco()
    total = con2.execute("SELECT COUNT(*) FROM alunos_diario").fetchone()[0]
    con2.close()

    print(f"\n[Aulio Data] Banco atualizado! {total} entradas em {len(turmas_unicas)} turmas.")
    return True


if __name__ == "__main__":
    reconstruir_mapa_diarios()
    atualizar_cache_alunos()
