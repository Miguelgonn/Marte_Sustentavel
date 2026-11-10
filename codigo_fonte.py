"""
SIFSM - Sistema Integrado de Futuro Sustentavel em Marte
Projeto: Aurora Siger

Dependencias: Python 3.9+, numpy (obrigatoria), matplotlib (opcional, para graficos)
Banco de dados: SQLite (equivalente ao Oracle, ja vem com o Python)
Dados: dados_aurora_siger.json (carregado no banco; pode ser exportado/importado pelo menu)
Execucao: python codigo_fonte.py
"""

import sqlite3
import json
import os
import random
import itertools
from collections import deque
import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")  # salva grafico em arquivo, sem abrir janela
    import matplotlib.pyplot as plt
    TEM_MATPLOTLIB = True
except ImportError:
    TEM_MATPLOTLIB = False

ARQUIVO_BANCO = "banco_aurora_siger.db"
ARQUIVO_JSON = "dados_aurora_siger.json"  # base de dados simulada (arquivo estruturado)

# ============================================================
# 1. BANCO DE DADOS (tabelas, campos, registros)
# ============================================================

def conectar():
    """Abre a conexao com o banco e ativa chaves estrangeiras."""
    conn = sqlite3.connect(ARQUIVO_BANCO)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def criar_banco(conn):
    """Cria as duas tabelas: modulos e leituras (relacionadas por codigo)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS modulos (
            codigo TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            critico INTEGER NOT NULL CHECK (critico IN (0,1)),
            ativo INTEGER NOT NULL CHECK (ativo IN (0,1)),
            limite_consumo REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS leituras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modulo_codigo TEXT NOT NULL REFERENCES modulos(codigo),
            ciclo INTEGER NOT NULL,
            temperatura REAL NOT NULL,
            umidade REAL NOT NULL,
            tripulantes INTEGER NOT NULL,
            consumo_kwh REAL NOT NULL
        );
    """)
    conn.commit()


def gerar_dados_simulados():
    """Gera a base simulada (semente fixa = reproduzivel) como dicionario no formato do JSON."""
    modulos = [
        {"codigo": "ENE-01", "nome": "Energia", "critico": 1, "ativo": 1, "limite_consumo": 20.0},
        {"codigo": "HAB-01", "nome": "Habitacao", "critico": 1, "ativo": 1, "limite_consumo": 18.0},
        {"codigo": "AGR-01", "nome": "Agricultura", "critico": 0, "ativo": 1, "limite_consumo": 16.0},
        {"codigo": "LAB-01", "nome": "Laboratorio", "critico": 0, "ativo": 1, "limite_consumo": 17.0},
        {"codigo": "MED-01", "nome": "Suporte medico", "critico": 1, "ativo": 1, "limite_consumo": 15.0},
        {"codigo": "COM-01", "nome": "Comunicacao", "critico": 0, "ativo": 1, "limite_consumo": 14.0},
    ]
    random.seed(42)
    leituras = []
    for m in modulos:
        for ciclo in range(1, 11):
            temp = round(random.uniform(18, 30), 1)
            umid = round(random.uniform(25, 70), 1)
            trip = random.randint(1, 8)
            # consumo depende de temperatura e tripulantes (+ ruido) -> base da regressao
            cons = round(4 + 0.35 * temp + 1.1 * trip + random.gauss(0, 1.5), 2)
            leituras.append({"modulo_codigo": m["codigo"], "ciclo": ciclo, "temperatura": temp,
                             "umidade": umid, "tripulantes": trip, "consumo_kwh": cons})
    return {"modulos": modulos, "leituras": leituras}


def exportar_json(conn, caminho=ARQUIVO_JSON):
    """Salva o conteudo atual do banco em um arquivo JSON."""
    try:
        cur = conn.execute("SELECT codigo,nome,critico,ativo,limite_consumo FROM modulos")
        modulos = [dict(zip(["codigo", "nome", "critico", "ativo", "limite_consumo"], l)) for l in cur]
        cur = conn.execute("SELECT modulo_codigo,ciclo,temperatura,umidade,tripulantes,consumo_kwh "
                           "FROM leituras ORDER BY id")
        cols = ["modulo_codigo", "ciclo", "temperatura", "umidade", "tripulantes", "consumo_kwh"]
        leituras = [dict(zip(cols, l)) for l in cur]
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump({"modulos": modulos, "leituras": leituras}, f, indent=2, ensure_ascii=False)
    except (OSError, sqlite3.Error) as e:
        print(f"  [Erro] Nao foi possivel exportar: {e}")
        return False
    else:
        print(f"  {len(modulos)} modulos e {len(leituras)} leituras exportados para {caminho}")
        return True


def importar_json(conn, caminho=ARQUIVO_JSON, substituir=False):
    """
    Le o JSON e grava no banco. Se substituir=True, apaga as leituras atuais antes.
    Valida o arquivo: erros de leitura, formato ou campos faltando sao tratados.
    """
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
        modulos = dados["modulos"]
        leituras = dados["leituras"]
        if substituir:
            conn.execute("DELETE FROM leituras")
            conn.execute("DELETE FROM sqlite_sequence WHERE name='leituras'")  # reinicia os IDs
        for m in modulos:
            conn.execute("INSERT OR IGNORE INTO modulos VALUES (?,?,?,?,?)",
                         (m["codigo"], m["nome"], int(m["critico"]), int(m["ativo"]),
                          float(m["limite_consumo"])))
        for l in leituras:
            conn.execute("INSERT INTO leituras (modulo_codigo,ciclo,temperatura,umidade,tripulantes,"
                         "consumo_kwh) VALUES (?,?,?,?,?,?)",
                         (l["modulo_codigo"], int(l["ciclo"]), float(l["temperatura"]),
                          float(l["umidade"]), int(l["tripulantes"]), float(l["consumo_kwh"])))
        conn.commit()
    except FileNotFoundError:
        print(f"  [Erro] Arquivo {caminho} nao encontrado.")
    except json.JSONDecodeError as e:
        conn.rollback()
        print(f"  [Erro] JSON invalido: {e}")
    except (KeyError, ValueError, TypeError) as e:
        conn.rollback()
        print(f"  [Erro] Dados do JSON com formato incorreto: {e}")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"  [Erro de banco] {e}")
    else:
        pilha_historico.clear()  # ids mudaram: o historico de desfazer nao vale mais
        print(f"  Importados {len(modulos)} modulos e {len(leituras)} leituras de {caminho}")
        return True
    return False


def popular_dados_iniciais(conn):
    """
    Primeira execucao (banco vazio): carrega os dados do JSON.
    Se o JSON nao existir, gera a base simulada, salva o JSON e carrega.
    """
    if conn.execute("SELECT COUNT(*) FROM modulos").fetchone()[0] > 0:
        return
    if not os.path.exists(ARQUIVO_JSON):
        with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
            json.dump(gerar_dados_simulados(), f, indent=2, ensure_ascii=False)
        print(f"  Base simulada criada em {ARQUIVO_JSON}")
    importar_json(conn, ARQUIVO_JSON)


# ============================================================
# 2. ENTRADA SEGURA (tratamento de erros)
# ============================================================

def ler_numero(msg, tipo=float, minimo=None, maximo=None):
    """Repete a pergunta ate o usuario digitar um numero valido."""
    while True:
        try:
            valor = tipo(input(msg).replace(",", "."))
        except ValueError:
            print("  [Erro] Digite um numero valido.")
            continue
        if (minimo is not None and valor < minimo) or (maximo is not None and valor > maximo):
            print(f"  [Erro] Valor fora do intervalo ({minimo} a {maximo}).")
            continue
        return valor


# ============================================================
# 3. ESTRUTURAS DE DADOS
# ============================================================

fila_alertas = deque()   # FILA (FIFO): alertas sao atendidos na ordem de chegada
pilha_historico = []     # PILHA (LIFO): permite desfazer a ultima acao


def montar_hash_modulos(conn):
    """TABELA HASH (dict): busca O(1) de um modulo pelo codigo."""
    cur = conn.execute("SELECT codigo,nome,critico,ativo,limite_consumo FROM modulos")
    return {c: {"nome": n, "critico": bool(k), "ativo": bool(a), "limite": l}
            for c, n, k, a, l in cur}


# GRAFO (lista de adjacencia): quem depende de quem (energia alimenta os demais)
GRAFO_DEPENDENCIAS = {
    "ENE-01": ["HAB-01", "AGR-01", "LAB-01", "MED-01", "COM-01"],
    "COM-01": ["LAB-01"],
    "AGR-01": ["HAB-01"],
    "HAB-01": [], "LAB-01": [], "MED-01": [],
}


def modulos_afetados(origem):
    """Busca em largura (BFS): quais modulos param se 'origem' falhar."""
    visitados, fila = set(), deque([origem])
    while fila:
        atual = fila.popleft()
        for vizinho in GRAFO_DEPENDENCIAS.get(atual, []):
            if vizinho not in visitados:
                visitados.add(vizinho)
                fila.append(vizinho)
    return sorted(visitados)


# ============================================================
# 4. REGRAS BOOLEANAS (decisao por software e por logica digital)
# ============================================================

def regra_alerta(consumo, limite, critico):
    """ALERTA = (consumo alto) AND (modulo critico)  -> porta AND"""
    return consumo > limite and critico


def regra_irrigacao(modulo_ativo, umidade):
    """IRRIGAR = (modulo agricola ativo) AND (umidade baixa < 40%)"""
    return modulo_ativo and umidade < 40


def mostrar_tabela_verdade():
    print("\nTabela verdade da regra: ALERTA = CONSUMO_ALTO AND CRITICO")
    print("Circuito: duas entradas digitais (A=consumo alto, B=critico) -> porta AND -> LED de alerta")
    print(" A | B | LED")
    for a, b in itertools.product([0, 1], repeat=2):
        print(f" {a} | {b} |  {int(a and b)}")


# ============================================================
# 5. CRUD
# ============================================================

def cadastrar_leitura(conn, hash_mod):
    try:
        cod = input("Codigo do modulo: ").strip().upper()
        if cod not in hash_mod:  # busca rapida na tabela hash
            raise KeyError(cod)
        ciclo = ler_numero("Ciclo: ", int, 1)
        temp = ler_numero("Temperatura (C): ", float, -80, 60)
        umid = ler_numero("Umidade (%): ", float, 0, 100)
        trip = ler_numero("Tripulantes ativos: ", int, 0, 50)
        cons = ler_numero("Consumo (kWh): ", float, 0)
        cur = conn.execute(
            "INSERT INTO leituras (modulo_codigo,ciclo,temperatura,umidade,tripulantes,consumo_kwh)"
            " VALUES (?,?,?,?,?,?)", (cod, ciclo, temp, umid, trip, cons))
        conn.commit()
    except KeyError as e:
        print(f"  [Erro] Modulo {e} nao existe.")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"  [Erro de banco] {e}")
    else:
        pilha_historico.append(("INSERT", cur.lastrowid))
        print(f"  Leitura {cur.lastrowid} cadastrada.")
        # aplica a regra booleana e enfileira alerta se necessario
        m = hash_mod[cod]
        if regra_alerta(cons, m["limite"], m["critico"]):
            fila_alertas.append(f"Consumo alto no modulo critico {cod} ({cons} kWh)")
            print("  ALERTA gerado e colocado na fila!")
    finally:
        print("  (operacao finalizada)")


def listar_leituras(conn, limite=15):
    cur = conn.execute("SELECT id,modulo_codigo,ciclo,temperatura,umidade,tripulantes,consumo_kwh"
                       " FROM leituras ORDER BY id DESC LIMIT ?", (limite,))
    print("\n ID | Modulo | Ciclo | Temp | Umid | Trip | Consumo")
    for linha in cur:
        print(" {:>3} | {:<6} | {:>5} | {:>4} | {:>4} | {:>4} | {:>6}".format(*linha))


def alterar_leitura(conn):
    try:
        id_ = ler_numero("ID da leitura a alterar: ", int, 1)
        novo = ler_numero("Novo consumo (kWh): ", float, 0)
        antigo = conn.execute("SELECT consumo_kwh FROM leituras WHERE id=?", (id_,)).fetchone()
        if antigo is None:
            raise LookupError(id_)
        conn.execute("UPDATE leituras SET consumo_kwh=? WHERE id=?", (novo, id_))
        conn.commit()
    except LookupError as e:
        print(f"  [Erro] Leitura {e} nao encontrada.")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"  [Erro de banco] {e}")
    else:
        pilha_historico.append(("UPDATE", id_, antigo[0]))
        print("  Leitura alterada.")


def excluir_leitura(conn):
    try:
        id_ = ler_numero("ID da leitura a excluir: ", int, 1)
        linha = conn.execute("SELECT * FROM leituras WHERE id=?", (id_,)).fetchone()
        if linha is None:
            raise LookupError(id_)
        conn.execute("DELETE FROM leituras WHERE id=?", (id_,))
        conn.commit()
    except LookupError as e:
        print(f"  [Erro] Leitura {e} nao encontrada.")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"  [Erro de banco] {e}")
    else:
        pilha_historico.append(("DELETE", linha))
        print("  Leitura excluida.")


def desfazer(conn):
    """Usa a PILHA para desfazer a ultima acao (INSERT, UPDATE ou DELETE)."""
    if not pilha_historico:
        print("  Nada para desfazer.")
        return
    acao = pilha_historico.pop()
    if acao[0] == "INSERT":
        conn.execute("DELETE FROM leituras WHERE id=?", (acao[1],))
    elif acao[0] == "UPDATE":
        conn.execute("UPDATE leituras SET consumo_kwh=? WHERE id=?", (acao[2], acao[1]))
    elif acao[0] == "DELETE":
        conn.execute("INSERT INTO leituras VALUES (?,?,?,?,?,?,?)", acao[1])
    conn.commit()
    print(f"  Acao desfeita: {acao[0]}")


# ============================================================
# 6. SIMULACAO COMPUTACIONAL (estado de carga da bateria)
# ============================================================

def integral_trapezio(y, dt=1.0):
    """Integracao numerica (regra do trapezio): area sob a curva."""
    return float(np.sum((y[:-1] + y[1:]) / 2.0) * dt)


def simular_bateria(consumo_medio_kw, fator=1.0, capacidade_kwh=2000.0, soc_inicial=80.0):
    """
    Simula 24 h. Geracao solar = max(0, 330*sin(pi*(h-6)/12)) kW (dia de 6h as 18h).
    SoC(t+1) = SoC(t) + (geracao - consumo) * dt / capacidade * 100, limitado entre 0 e 100%.
    """
    horas = np.arange(0, 25)
    geracao = np.maximum(0, 330 * np.sin(np.pi * (horas - 6) / 12))
    consumo = np.full(len(horas), consumo_medio_kw * fator)
    soc = [soc_inicial]
    for h in range(24):
        energia = (geracao[h] + geracao[h + 1]) / 2 - (consumo[h] + consumo[h + 1]) / 2
        soc.append(min(100, max(0, soc[-1] + energia / capacidade_kwh * 100)))
    return horas, geracao, consumo, np.array(soc)


def executar_simulacao(conn):
    # consumo total medio da colonia (soma das medias por modulo)
    total = conn.execute("SELECT SUM(m) FROM (SELECT AVG(consumo_kwh) m FROM leituras "
                         "GROUP BY modulo_codigo)").fetchone()[0] or 0
    print(f"\nConsumo medio total da colonia: {total:.1f} kW")
    h, ger, cons, soc_normal = simular_bateria(total)
    _, _, _, soc_eco = simular_bateria(total, fator=0.8)
    print(f"Energia gerada no dia (integral trapezio): {integral_trapezio(ger):.1f} kWh")
    print(f"Energia consumida no dia: {integral_trapezio(cons):.1f} kWh")
    print(f"SoC minimo - cenario normal:  {soc_normal.min():.1f}%")
    print(f"SoC minimo - cenario economia (-20%): {soc_eco.min():.1f}%")
    if soc_normal.min() <= 0:
        print("  >> Cenario normal esgota a bateria: reduzir consumo e necessario.")
    if TEM_MATPLOTLIB:
        import os
        os.makedirs("graficos_ou_imagens", exist_ok=True)
        plt.figure(figsize=(8, 4))
        plt.plot(h, soc_normal, label="Normal")
        plt.plot(h, soc_eco, label="Economia (-20%)")
        plt.xlabel("Hora"); plt.ylabel("Estado de carga (%)")
        plt.title("Simulacao da bateria - Aurora Siger"); plt.legend(); plt.grid(True)
        plt.savefig("graficos_ou_imagens/simulacao_bateria.png", dpi=120)
        plt.close()
        print("  Grafico salvo em graficos_ou_imagens/simulacao_bateria.png")
    return soc_normal.min(), soc_eco.min()


# ============================================================
# 7. MODELO LINEAR (regressao multipla com numpy)
# ============================================================

def modelo_linear(conn, prever=None):
    """consumo = b0 + b1*temperatura + b2*tripulantes"""
    dados = np.array(conn.execute(
        "SELECT temperatura, tripulantes, consumo_kwh FROM leituras").fetchall(), dtype=float)
    if len(dados) < 5:
        print("  Dados insuficientes para o modelo.")
        return None
    X = np.column_stack([np.ones(len(dados)), dados[:, 0], dados[:, 1]])
    y = dados[:, 2]
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ beta
    ss_res = np.sum((y - pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot
    rmse = np.sqrt(ss_res / len(y))
    corr = np.corrcoef(dados.T)
    print("\n--- Analise exploratoria ---")
    print(f"Registros: {len(y)} | consumo medio: {y.mean():.2f} kWh | desvio: {y.std():.2f}")
    print(f"Correlacao consumo x temperatura: {corr[0, 2]:.2f}")
    print(f"Correlacao consumo x tripulantes: {corr[1, 2]:.2f}")
    print(f"Correlacao temperatura x tripulantes (multicolinearidade): {corr[0, 1]:.2f}")
    print("\n--- Modelo: consumo = b0 + b1*temp + b2*tripulantes ---")
    print(f"b0 (intercepto) = {beta[0]:.3f}")
    print(f"b1 (temperatura) = {beta[1]:.3f} kWh por grau extra")
    print(f"b2 (tripulantes) = {beta[2]:.3f} kWh por tripulante extra")
    print(f"R2 = {r2:.3f} | RMSE = {rmse:.3f} kWh")
    if prever:
        est = beta[0] + beta[1] * prever[0] + beta[2] * prever[1]
        print(f"Estimativa para temp={prever[0]}C e {prever[1]} tripulantes: {est:.2f} kWh")
    return beta, r2


# ============================================================
# 8. IA: SISTEMA MULTIAGENTE SIMULADO (deterministico)
# ============================================================

historico_sessao = []  # memoria da conversa (sessao)
PALAVRAS_PROIBIDAS = ["desligar suporte", "apagar tudo", "desativar oxigenio", "desligar oxigenio"]


def guardrail(msg):
    """Bloqueia pedidos inseguros: IA nao executa acoes criticas sozinha."""
    return not any(p in msg.lower() for p in PALAVRAS_PROIBIDAS)


def agente_energia(conn):
    total = conn.execute("SELECT SUM(m) FROM (SELECT AVG(consumo_kwh) m FROM leituras "
                         "GROUP BY modulo_codigo)").fetchone()[0]
    return f"[Agente Energia] Consumo medio total: {total:.1f} kW."


def agente_ambiental(conn):
    t, u = conn.execute("SELECT AVG(temperatura), AVG(umidade) FROM leituras").fetchone()
    return f"[Agente Ambiental] Temperatura media {t:.1f}C, umidade media {u:.1f}%."


def agente_manutencao(conn):
    if not fila_alertas:
        return "[Agente Manutencao] Nenhum alerta pendente."
    return f"[Agente Manutencao] {len(fila_alertas)} alerta(s) pendente(s). Proximo: {fila_alertas[0]}"


def agente_triador(msg, conn):
    """Triador: le a solicitacao e faz HANDOFF para o agente especialista."""
    historico_sessao.append(msg)
    if not guardrail(msg):
        return "[Guardrail] Pedido bloqueado: acao critica exige validacao humana."
    m = msg.lower()
    if any(p in m for p in ["energia", "bateria", "consumo"]):
        return "[Triador -> Energia] " + agente_energia(conn)
    if any(p in m for p in ["temperatura", "umidade", "ambiente"]):
        return "[Triador -> Ambiental] " + agente_ambiental(conn)
    if any(p in m for p in ["manutencao", "alerta", "falha"]):
        return "[Triador -> Manutencao] " + agente_manutencao(conn)
    return "[Triador] Nao entendi. Fora do escopo; encaminhando para um operador humano."


def menu_ia(conn):
    print("\nChat com agentes (digite 'sair' para voltar)")
    while True:
        msg = input("Tripulante: ").strip()
        if msg.lower() == "sair":
            break
        print(agente_triador(msg, conn))
    print(f"(Sessao registrou {len(historico_sessao)} mensagem(ns))")


# ============================================================
# 9. TEXTOS EXPLICATIVOS (arquitetura e impacto)
# ============================================================

def explicar_arquitetura():
    print("""
ARQUITETURA COMPUTACIONAL DO SIFSM
- CPU: banco de dados, menu, regras booleanas e CRUD (tarefas sequenciais e de controle).
- GPU/NPU (conceitual): se houvesse milhares de sensores, regressao e simulacoes em lote
  ganhariam com paralelismo; uma NPU executaria o modelo de IA com baixo consumo.
- Computacao heterogenea: cada tarefa roda na unidade mais eficiente.
- Memoria: a tabela hash mantem modulos em memoria rapida; o banco fica em armazenamento.
  Mover dados e mais caro (tempo e energia) que calcular: por isso agregamos no banco (AVG, SUM)
  em vez de trazer tudo para o Python.
- Sustentabilidade: execucao local (edge) na colonia reduz transmissao e consumo energetico.""")


def explicar_impacto():
    print("""
IMPACTO SOCIOAMBIENTAL E CIDADANIA DIGITAL
1. Uso responsavel de recursos: a simulacao da bateria mostra, antes de agir, se cortar 20% do
   consumo evita o esgotamento da energia.
2. Simulacao reduz desperdicio: cenarios sao testados no software, nao na colonia real.
3. Resiliencia: o grafo de dependencias mostra o efeito de uma falha de energia nos demais modulos.
4. Privacidade e economia dos dados: o sistema guarda apenas dados operacionais (sem identificar
   tripulantes); dados pessoais seriam coletados com consentimento e finalidade clara.
5. IA com responsabilidade humana: guardrails bloqueiam acoes criticas; um humano valida decisoes.
6. Impacto ambiental da computacao: IA e processamento intensivo gastam energia; priorizamos
   modelos simples e processamento local.""")


# ============================================================
# 10. ANALISE FINAL INTEGRADA
# ============================================================

def analisar_sustentabilidade(conn, hash_mod):
    print("\n===== ANALISE DE SUSTENTABILIDADE DA COLONIA =====")
    # 1) ultima leitura de cada modulo + regra booleana + fila de alertas
    fila_alertas.clear()
    for cod, m in hash_mod.items():
        linha = conn.execute("SELECT consumo_kwh, umidade FROM leituras WHERE modulo_codigo=? "
                             "ORDER BY id DESC LIMIT 1", (cod,)).fetchone()
        if not linha:
            continue
        cons, umid = linha
        if regra_alerta(cons, m["limite"], m["critico"]):
            fila_alertas.append(f"{cod} ({m['nome']}): {cons} kWh > limite {m['limite']}")
        if cod == "AGR-01" and regra_irrigacao(m["ativo"], umid):
            print(f"  Irrigacao liberada em {cod} (umidade {umid}%)")
    print(f"Alertas na fila: {len(fila_alertas)}")
    while fila_alertas:
        print("  ALERTA:", fila_alertas.popleft())
    # 2) impacto de falha de energia (grafo)
    print("Se ENE-01 falhar, afetados:", ", ".join(modulos_afetados("ENE-01")))
    # 3) simulacao e regressao
    minimo_normal, minimo_eco = executar_simulacao(conn)
    modelo_linear(conn, prever=(25, 6))
    # 4) recomendacao
    print("\nRECOMENDACAO TECNICA:")
    if minimo_normal < 30:
        print(f"  Adotar modo economia (-20%): SoC minimo passa de {minimo_normal:.0f}% para {minimo_eco:.0f}%.")
    else:
        print("  Bateria segura no cenario atual; manter monitoramento.")
    print("  Decisao final deve ser validada por um responsavel humano.")
    print("LIMITACOES: dados simulados, modelo linear simples, geracao solar idealizada,")
    print("            sem tempestades de poeira e sem degradacao da bateria.")


# ============================================================
# 11. MENU PRINCIPAL
# ============================================================

def menu():
    conn = conectar()
    criar_banco(conn)
    popular_dados_iniciais(conn)
    while True:
        hash_mod = montar_hash_modulos(conn)
        print("""
===== SIFSM - Aurora Siger =====
 1. Cadastrar leitura          7. Simulacao da bateria
 2. Listar leituras            8. Modelo linear (regressao)
 3. Alterar leitura            9. Chat com agentes de IA
 4. Excluir leitura           10. Arquitetura computacional
 5. Desfazer ultima acao      11. Impacto socioambiental
 6. Regras logicas            12. ANALISAR SUSTENTABILIDADE
13. Exportar banco -> JSON    14. Importar JSON -> banco
 0. Sair""")
        op = input("Escolha: ").strip()
        if op == "1": cadastrar_leitura(conn, hash_mod)
        elif op == "2": listar_leituras(conn)
        elif op == "3": alterar_leitura(conn)
        elif op == "4": excluir_leitura(conn)
        elif op == "5": desfazer(conn)
        elif op == "6":
            mostrar_tabela_verdade()
            print("Teste: consumo 22, limite 20, critico ->", regra_alerta(22, 20, True))
            print("Irrigacao: ativo e umidade 30% ->", regra_irrigacao(True, 30))
        elif op == "7": executar_simulacao(conn)
        elif op == "8": modelo_linear(conn, prever=(25, 6))
        elif op == "9": menu_ia(conn)
        elif op == "10": explicar_arquitetura()
        elif op == "11": explicar_impacto()
        elif op == "12": analisar_sustentabilidade(conn, hash_mod)
        elif op == "13": exportar_json(conn)
        elif op == "14":
            r = input("Substituir as leituras atuais pelas do JSON? (s/n): ").strip().lower()
            importar_json(conn, substituir=(r == "s"))
        elif op == "0":
            break
        else:
            print("  Opcao invalida.")
    conn.close()
    print("Encerrando o SIFSM. Ate logo!")


if __name__ == "__main__":
    menu()
