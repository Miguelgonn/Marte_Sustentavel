# 🚀 SIFSM — Sistema Integrado de Futuro Sustentável em Marte
### Uma solução computacional para gerenciamento inteligente, sustentabilidade e autonomia da colônia Aurora Siger.

## 👥 Equipe

| Nome | RM |
|------|----|
| Ana Gabriela | rm571312 |
| Kaique | rm570533 |
| Miguel Antunes | rm573643 |
| Miguel Gonçalves | rm573793 |

# O que o sistema faz

- Guarda módulos e leituras em um banco SQLite
- CRUD das leituras (cadastrar, listar, alterar e excluir)
- Desfazer a última ação (usando uma pilha)
- Regras booleanas para gerar alertas e liberar irrigação
- Simulação do estado de carga da bateria em 24 horas
- Regressão linear múltipla para estimar o consumo
- Chat com agentes de IA simulados (sem LLM de verdade)
- Textos explicando a arquitetura computacional e o impacto socioambiental
- Uma opção que junta tudo e dá uma recomendação final (opção 12)

## Como rodar


```
pip install numpy matplotlib
python codigo_fonte.py
```

O `numpy` é obrigatório. 

## Arquivos do projeto

`codigo_fonte.py` 
`script_banco.sql` 
`dados_aurora_siger.csv`  
`circuito_logico.pdf`
`simulacao_computacional.py`  
`relatorio_tecnico.pdf`  
`link_video.txt`  
`graficos_ou_imagens/` 

## Menu

```
===== SIFSM - Aurora Siger =====
 1. Cadastrar leitura          7. Simulacao da bateria
 2. Listar leituras            8. Modelo linear (regressao)
 3. Alterar leitura            9. Chat com agentes de IA
 4. Excluir leitura           10. Arquitetura computacional
 5. Desfazer ultima acao      11. Impacto socioambiental
 6. Regras logicas            12. ANALISAR SUSTENTABILIDADE
 0. Sair
```



### Tratamento de erros

Todas as funções do CRUD usam `try / except / else / finally`

- Se o usuário digita texto onde era número, ou um valor fora do limite, o `ler_numero()` avisa e pergunta de novo
- Se o módulo ou a leitura não existe, aparece uma mensagem de erro
- Se der erro no banco, o programa faz `rollback`
- O `else` confirma a operação e salva no histórico

## Estruturas de dados

| Estrutura | Como foi feita | Para que serve no sistema |
|---|---|---|
| Fila (FIFO) | `deque` | Alertas atendidos na ordem em que aparecem |
| Pilha (LIFO) | lista do Python | Histórico das ações, para a função desfazer |
| Tabela hash | `dict` | Achar um módulo rápido pelo código |
| Grafo | dicionário de listas de adjacência + BFS | Dependência entre módulos: mostra o que para se a energia falhar |
| Lista / vetor | `list` e arrays do numpy | Guardar leituras e dados da simulação |

## Regra booleana e circuito lógico

A regra de alerta que usamos é:

```python
alerta = consumo > limite and critico
```

Ou seja, ALERTA = A · B, onde A é "consumo alto" (acima do limite do módulo) e B é "módulo crítico".

| A | B | ALERTA |
|---|---|---|
| 0 | 0 | 0 |
| 0 | 1 | 0 |
| 1 | 0 | 0 |
| 1 | 1 | 1 |

Também tem a regra da irrigação: só libera se o módulo agrícola estiver ativo **e** a umidade for menor que 40%.

No circuito, A e B são duas chaves ligadas em uma porta AND, e a saída acende um LED. Dá para montar no Tinkercad com o CI 7408 e um resistor de 220 ohms no LED, ou com Arduino. O arquivo do circuito está na pasta do projeto. O resultado é o mesmo no Python e no circuito.

## Simulação da bateria

A simulação calcula o estado de carga (SoC) da bateria durante 24 horas e compara dois cenários: consumo normal e modo economia (20% a menos).

- Geração solar: `330 * sin(pi * (h - 6) / 12)` kW, só entre 6h e 18h
- Capacidade da bateria: 2000 kWh, começando em 80%
- A cada hora: `SoC = SoC + (geração - consumo) / capacidade * 100`, sempre entre 0 e 100%
- A energia gerada e consumida é calculada por integração numérica (regra do trapézio)

O gráfico fica salvo em `graficos_ou_imagens/simulacao_bateria.png`.

Limitações: não considera perdas na carga e descarga, desgaste da bateria, tempestade de poeira nem mudança de estação, e os dados são inventados.

## Regressão linear

O modelo é `consumo = b0 + b1 * temperatura + b2 * tripulantes`, feito com `numpy` (`np.linalg.lstsq`). O programa mostra a análise exploratória (média, desvio e correlações), os coeficientes, o R² e o RMSE, e ainda faz uma previsão para um caso (25 °C e 6 tripulantes).

Como interpretar: b1 é quanto o consumo sobe (em kWh) a cada grau a mais, b2 é quanto sobe a cada tripulante a mais e b0 é o consumo base. Também verificamos a correlação entre temperatura e tripulantes para ver se tem multicolinearidade.

## Agentes de IA (simulado)

Não usamos nenhum LLM de verdade, é uma simulação com regras simples em Python para mostrar como seria a arquitetura.

- **Agente triador**: lê a mensagem e passa para o agente certo (handoff)
- **Agente de energia**: consulta o consumo médio no banco
- **Agente ambiental**: informa temperatura e umidade médias
- **Agente de manutenção**: consulta a fila de alertas
- **Guardrail**: bloqueia pedidos perigosos, como desligar o suporte de vida ou o oxigênio
- **Sessão**: guarda as mensagens da conversa

Os agentes só usam funções que consultam o banco, então não inventam número. Se o pedido não for entendido, ele vai para um operador humano. A IA só sugere, quem decide é a pessoa.

## Arquitetura computacional

- A **CPU** cuida do menu, do banco, do CRUD e das regras, que são tarefas de controle
- Uma **GPU** ajudaria se tivesse milhares de sensores e simulações grandes (aqui o numpy já vetoriza na CPU)
- Uma **NPU/TPU** rodaria o modelo de IA gastando pouca energia, o que importa muito em Marte
- Na **computação heterogênea** cada tarefa vai para a unidade mais adequada
- Sobre **memória**: mover dado gasta mais tempo e energia que calcular, por isso usamos `AVG` e `SUM` direto no banco em vez de puxar tudo para o Python
- Processar localmente (na própria colônia) reduz transmissão e economiza energia

## Sustentabilidade e cidadania digital

- A simulação mostra, antes de agir, se reduzir o consumo evita a bateria acabar
- Testar cenários no software evita desperdício na colônia de verdade
- O grafo mostra o efeito em cascata de uma falha de energia, o que ajuda na resiliência
- O sistema só guarda dados operacionais e não identifica tripulantes. Dados pessoais só poderiam ser coletados com consentimento e uma finalidade clara
- Guardrails e validação humana evitam que a IA tome decisões críticas sozinha
- Escolhemos modelos simples e processamento local para gastar menos energia

## Exemplos de execução

Listar leituras (opção 2):

```
 ID | Modulo | Ciclo | Temp | Umid | Trip | Consumo
  60 | COM-01 |    10 | 19.4 | 65.1 |    4 |  14.21
  59 | COM-01 |     9 | 28.2 | 28.1 |    2 |  15.57
  58 | COM-01 |     8 | 19.9 | 68.2 |    2 |  13.11
```

Erros tratados (módulo inexistente e consumo inválido):

```
Codigo do modulo: abc
  [Erro] Modulo 'ABC' nao existe.
  (operacao finalizada)

Novo consumo (kWh): -5
  [Erro] Valor fora do intervalo (0 a None).
Novo consumo (kWh): abc
  [Erro] Digite um numero valido.
```

Desfazer (opção 5):

```
  Acao desfeita: UPDATE
```

Chat com os agentes (opção 9):

```
Tripulante: desligar suporte de vida
[Guardrail] Pedido bloqueado: acao critica exige validacao humana.
Tripulante: qual o consumo de energia?
[Triador -> Energia] [Agente Energia] Consumo medio total: 100.9 kW.
```

Análise de sustentabilidade (opção 12), com os dados iniciais:

```
  ALERTA: ENE-01 (Energia): 20.12 kWh > limite 20.0
  ALERTA: HAB-01 (Habitacao): 19.03 kWh > limite 18.0
  ALERTA: MED-01 (Suporte medico): 17.7 kWh > limite 15.0
Se ENE-01 falhar, afetados: AGR-01, COM-01, HAB-01, LAB-01, MED-01

SoC minimo - cenario normal:  46.4%
SoC minimo - cenario economia (-20%): 53.5%

Registros: 60 | consumo medio: 17.02 kWh | desvio: 2.96
b0 (intercepto) = 5.608
b1 (temperatura) = 0.309 kWh por grau extra
b2 (tripulantes) = 1.030 kWh por tripulante extra
R2 = 0.787 | RMSE = 1.369 kWh
Estimativa para temp=25C e 6 tripulantes: 19.51 kWh

RECOMENDACAO TECNICA:
  Bateria segura no cenario atual; manter monitoramento.
  Decisao final deve ser validada por um responsavel humano.
```

<img width="910" height="315" alt="image" src="https://github.com/user-attachments/assets/b7ecae03-50ef-4084-a21b-ce5b9a818ea0" />
<img width="910" height="502" alt="image" src="https://github.com/user-attachments/assets/18213717-e4b7-4f13-ad4c-3f526cf95ffd" />
<img width="960" height="480" alt="image" src="https://github.com/user-attachments/assets/1375ec8b-2a62-472a-8360-a16da9dfdb5c" />


