# Desenvolvimento

## Ambiente

Use Python 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

## Organização

- Código da aplicação: `src`.
- Testes: `tests`.
- Rotas HTTP: `src/api/routes`.
- Casos de uso: `src/application/use_cases`.
- Portas: `src/application/ports`.
- Adapters externos: `src/infrastructure`.

Nomes de módulos, classes, funções e variáveis ficam em inglês. Textos para usuário, logs e documentação ficam em português do Brasil.

## Rodando a API

```powershell
python -m uvicorn api.server:app --app-dir src --reload
```

## Chromium Persistente

`LOTTOBOT_BROWSER_PROFILE_DIR` define o perfil persistente do Chromium e é criado automaticamente pelo adapter Playwright. `LOTTOBOT_BROWSER_HEADLESS` aceita `true/false`, `yes/no`, `sim/não` e `1/0`. `LOTTOBOT_BROWSER_TIMEOUT_SECONDS` precisa ser maior que zero e é aplicado como timeout padrão do contexto Playwright e nas navegações.

## Rodando testes

```powershell
python -m pytest
python -m pytest --cov=src --cov-report=term-missing
```

Os testes não devem usar Playwright real nem acessar `https://www.loteriasonline.caixa.gov.br`.

## Regras Para Mudanças

- Não colocar regras de negócio em handlers FastAPI.
- Não espalhar seletores fora de `infrastructure/selectors`.
- Não expor CPF, senha, CVV, código de validação ou cartão em logs.
- Manter `CONFIRMA_PAGAMENTO=false` por padrão.
- Encerrar navegador e WhatsApp Web em fluxos de erro.
