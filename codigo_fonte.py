"""
SIFSM - Sistema Integrado de Futuro Sustentavel em Marte
Projeto: Aurora Siger

Dependencias: Python 3.9+, numpy (obrigatoria), matplotlib (opcional, para graficos)
Banco de dados: SQLite (equivalente ao Oracle, ja vem com o Python)
Execucao: python codigo_fonte.py
"""

import sqlite3
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


def popular_dados_iniciais(conn):
    """Insere dados simulados na primeira execucao (semente fixa = reproduzivel)."""
    if conn.execute("SELECT COUNT(*) FROM modulos").fetchone()[0] > 0:
        return
    modulos = [
        ("ENE-01", "Energia", 1, 1, 20.0),
        ("HAB-01", "Habitacao", 1, 1, 18.0),
        ("AGR-01", "Agricultura", 0, 1, 16.0),
        ("LAB-01", "Laboratorio", 0, 1, 17.0),
        ("MED-01", "Suporte medico", 1, 1, 15.0),
        ("COM-01", "Comunicacao", 0, 1, 14.0),
    ]
    conn.executemany("INSERT INTO modulos VALUES (?,?,?,?,?)", modulos)
    random.seed(42)
    for cod, *_ in modulos:
        for ciclo in range(1, 11):
            temp = round(random.uniform(18, 30), 1)
            umid = round(random.uniform(25, 70), 1)
            trip = random.randint(1, 8)
            # consumo depende de temperatura e tripulantes (+ ruido) -> base da regressao
            cons = round(4 + 0.35 * temp + 1.1 * trip + random.gauss(0, 1.5), 2)
            conn.execute(
                "INSERT INTO leituras (modulo_codigo,ciclo,temperatura,umidade,tripulantes,consumo_kwh)"
                " VALUES (?,?,?,?,?,?)", (cod, ciclo, temp, umid, trip, cons))
    conn.commit()


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
        elif op == "0":
            break
        else:
            print("  Opcao invalida.")
    conn.close()
    print("Encerrando o SIFSM. Ate logo!")


if __name__ == "__main__":
    menu()
