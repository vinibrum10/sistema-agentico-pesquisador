# agent_experiment

Quarto agente (opcional): melhora, por rodadas, o código de um experimento. Serve a qualquer tese e
área: o que ele precisa é de um script que imprima uma métrica numérica. O modelo propõe uma mudança
por rodada; **quem roda e decide se melhorou é o código**, pelo número. Acesso: menu principal →
[6] Experimentos.

## Etapas

| # | Etapa | Quem decide | Onde | Saída |
|---|---|---|---|---|
| 1 | Define o experimento: nome, objetivo (uma frase), pasta do código base, comando, pasta de dados (opcional), métrica e se maior ou menor é melhor, máximo de rodadas (3) e tempo por rodada (10 min). Mostra o resumo e só grava depois de confirmado | pesquisador | `experimento.py` (`definir_experimento`) | `experimento.json`, `base/` |
| 2 | Rodada 0: roda o código base e guarda a métrica de referência | código | `rodadas.py` (`rodar_rodadas`) | `rodada_00/` |
| 3 | Cada rodada parte da **melhor versão**: o modelo propõe UMA mudança (arquivos `.py` completos e um motivo); o código roda no Docker, lê a métrica e decide se melhorou. Se der erro, o erro volta ao modelo (até 2 correções na mesma rodada) | modelo propõe; código decide | `rodadas.py`, `executor.py` | `rodada_NN/` |
| 4 | Relatório: tabela de rodadas, a melhor versão e a diferença em relação ao código base. Sai mesmo se algo interromper | código | `rodadas.py` (`gerar_relatorio`) | `relatorio.md` |

Tudo fica em `data/active_research/experimentos/<nome>/`: `experimento.json`, `base/` (cópia do código, sem
`.git`, `.venv` e `__pycache__`) e uma pasta `execucao_<data>/` por execução, com `rodada_NN/` (o código da
rodada e `saida.txt`), `experimentos.csv` (`;`) e `relatorio.md`. **O seu código original nunca é
alterado**: para usar a melhor versão, copie os arquivos da rodada indicada no relatório.

## Contrato da métrica

O código imprime uma linha `METRICA nome=valor` (valor numérico finito). Vale a última linha com o nome da
métrica. Rodada sem essa linha, com erro ou com tempo estourado conta como erro.

## Isolamento (Docker)

O código gerado por modelo nunca roda direto na sua máquina. Cada rodada roda num container:

- sem rede (`--network none`); memória de 4 GB e 2 CPUs (`MEMORIA` e `CPUS` em `executor.py`);
- raiz somente leitura; só a pasta da rodada (`/exp`) é gravável; dados em `/dados`, somente leitura;
- sem privilégios extras; o container é morto se o tempo da rodada estourar.

As dependências vêm do `requirements.txt` da pasta do código base: a imagem é montada uma vez (cacheada
pelo conteúdo do arquivo) e a rede só é usada nessa montagem. Sem o arquivo, roda `python:3.12-slim`.
Exige o Docker Desktop aberto. A GPU não está no V1.

## Regras

- Para depois de `max_rodadas`, de 2 rodadas seguidas sem melhora ou do teto de gasto da camada de modelos.
- O modelo só pode criar ou alterar arquivos `.py` dentro da pasta da rodada (caminho relativo, sem `..`).
- Modelo: tarefa `codigo_experimento` em `config/modelos.json`, padrão `qwen2.5-coder:7b` (local, sem custo).
  No teste de brinquedo (3 rodadas, uma execução por modelo) ele foi de 0,858 para 0,866; o `deepseek-flash`
  ficou em 0,858 (cerca de US$ 0,001). Amostra pequena.
- Lê e grava só em `data/active_research/experimentos/` e usa `core/`; não importa outros agentes.

## Limites conhecidos

- **O modelo pode alterar o código de avaliação** e inflar a métrica. Revise a diferença em
  `relatorio.md` antes de confiar no número.
- Só edita arquivos `.py`; os `.py` do código base somam no máximo 24 KB (precisam caber no prompt).
- Não usa o corpus de trechos para sugerir mudanças.
- A correção de erros dentro da rodada foi testada com falhas simuladas, não com falhas reais do modelo.
