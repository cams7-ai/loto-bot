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

`GET /api/v1/bets/run` chama `RunBetFlowUseCase`, que:

1. inicia sessão caso necessário;
2. acessa o portal;
3. aceita termos;
4. autentica com CPF, código e senha;
5. seleciona modalidade;
6. completa jogo e adiciona ao carrinho;
7. seleciona pagamento;
8. exige `CONFIRMA_PAGAMENTO=true`;
9. confirma pagamento;
10. valida finalização;
11. encerra recursos.

Em qualquer falha, o caso de uso registra o erro, aciona notificações e encerra a sessão.

## Segurança

- Segredos entram apenas por variáveis de ambiente.
- `.env` é ignorado pelo Git.
- `.env.example` contém placeholders.
- Logs devem mascarar valores sensíveis.
- A confirmação real de pagamento é bloqueada por padrão.

## Testabilidade

Casos de uso dependem de portas. Testes substituem navegador, e-mail, WhatsApp e Gmail por fakes ou transports mockados, garantindo execução local determinística e sem acesso ao portal real.
