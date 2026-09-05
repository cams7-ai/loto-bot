# Arquitetura

LotoBot usa Clean Architecture para manter o domínio independente de frameworks.

## Camadas

`domain`

Entidades, value objects e exceções. Não importa FastAPI, Playwright, `httpx` ou configurações de ambiente.

`application`

Casos de uso e portas. Orquestra o fluxo de aposta, controle de sessão, autorização explícita de pagamento e notificação de falhas.

`infrastructure`

Adapters concretos:

- `browser`: automação Playwright com perfil persistente.
- `clients`: integrações HTTP com Gmail Reader, Mail Sender e WhatsApp Notify.
- `config`: carregamento com `pydantic-settings`.
- `selectors`: seletores centralizados do portal.
- `logging`: formato de log com operação, processo e thread.

`api`

FastAPI, rotas, schemas, tratamento padronizado de erros e composição de dependências.

## Fluxo Principal

`POST /api/v1/bets/run` chama `RunBetFlowUseCase`, que:

1. inicia sessão caso necessário;
2. acessa o portal;
3. aceita termos;
4. autentica com CPF, código e senha;
5. seleciona modalidade;
6. completa jogo e adiciona ao carrinho;
7. seleciona pagamento;
8. exige `CONFIRM_PAYMENT=true`;
9. confirma pagamento;
10. valida finalização;
11. encerra recursos.

Em qualquer falha, o caso de uso registra o erro, aciona notificações e encerra a sessão.

## Conferência de Resultados

`POST /api/v1/bets/check_draws` valida o corpo integralmente na fronteira da API e entrega filtros tipados a `CheckBetDrawsUseCase`. O caso de uso compõe `ListPlacedBetsUseCase` e `ListPortalBetsUseCase`, correlaciona os DTOs em memória e usa `NotificationPort` sem acessar MongoDB, Playwright ou clients HTTP diretamente.

A chave de correlação preserva modalidade canônica, ordem dos números e número textual do concurso. Se não houver histórico, o portal não é consultado; se não houver correspondência, nenhum canal de notificação é acionado. Havendo correspondências, uma única mensagem consolidada usa WhatsApp como canal primário e e-mail exclusivamente como fallback.

O adapter Playwright continua sendo o responsável por timezone e normalização dos rótulos conhecidos do portal. O caso de uso preserva a sessão aberta após sucesso e não usa o tratamento de falha do fluxo de compra, evitando uma segunda notificação ou o fechamento indevido dos recursos persistentes.

## Segurança

- Segredos entram apenas por variáveis de ambiente.
- `.env` é ignorado pelo Git.
- `.env.example` contém placeholders.
- Logs devem mascarar valores sensíveis.
- A confirmação real de pagamento é bloqueada por padrão.

## Testabilidade

Casos de uso dependem de portas. Testes substituem navegador, e-mail, WhatsApp e Gmail por fakes ou transports mockados, garantindo execução local determinística e sem acesso ao portal real.
