# LotoBot — Chromium na EC2 usando a conexão local como Proxy SOCKS5

> Guia passo a passo para implementar, testar localmente e preparar para AWS a arquitetura em que o **LotoBot + Playwright + Chromium** executam na EC2, enquanto o **PC Windows local fornece apenas a saída de rede** por meio de um túnel SSH com proxy SOCKS5.
---

## 1. Objetivo

A arquitetura final será:

```text
                         AWS
                ┌──────────────────────┐
                │ EC2                  │
                │                      │
                │ LotoBot / FastAPI    │
                │ Playwright           │
                │ Chromium             │
                │      │               │
                │      ▼               │
                │ SOCKS5               │
                │ 127.0.0.1:1080       │
                └────────┬─────────────┘
                         │
                         │ túnel SSH
                         │ iniciado pelo PC
                         ▼
                ┌──────────────────────┐
                │ PC Windows local     │
                │ OpenSSH Client       │
                └────────┬─────────────┘
                         │
                         ▼
                     Internet
```

O ponto principal é:

- o **LotoBot continua rodando junto com Playwright e Chromium**;
- o código de automação do navegador continua praticamente inalterado;
- somente o tráfego do Chromium é enviado ao proxy;
- o backend, FastAPI, MongoDB e demais clientes continuam usando a rede normal da EC2;
- o PC local inicia a conexão SSH com a EC2;
- não é necessário abrir uma porta de proxy no roteador residencial;
- o SOCKS5 fica acessível somente em `127.0.0.1:1080` dentro da EC2;
- se o túnel cair, o navegador deve falhar em vez de sair silenciosamente pelo IP da AWS.

---

# 2. Por que essa estratégia exige pouca refatoração

O LotoBot atual já centraliza as configurações em:

```text
src/infrastructure/config/settings.py
```

e inicializa o Chromium em:

```text
src/infrastructure/browser/session_control_browser.py
```

Atualmente o contexto persistente é criado aproximadamente assim:

```python
self._context = self._playwright.chromium.launch_persistent_context(
    user_data_dir=str(self._settings.browser_profile_dir),
    headless=self._settings.browser_headless,
    viewport=viewport,
    args=self._launch_args(self._settings.browser_headless),
    user_agent=self._user_agent(),
    locale="pt-BR",
)
```

O Playwright aceita configuração `proxy` diretamente em `launch_persistent_context`.

Portanto, não é necessário alterar:

```text
domain
application/use_cases
application/ports
selectors
fluxo de autenticação
fluxo de apostas
controle do carrinho
pagamento
persistência
API FastAPI
```

A alteração fica concentrada em infraestrutura/configuração.

---

# 3. Arquivos que serão alterados

A implementação mínima envolve:

```text
.env.example
src/infrastructure/config/settings.py
src/infrastructure/browser/session_control_browser.py
tests/unit/test_browser_coverage.py
```

Opcionalmente será criado:

```text
scripts/test_browser_proxy.py
```

Esse script serve apenas para validar o proxy sem executar uma aposta.

---

# 4. Pré-requisitos locais

O projeto atual requer Python 3.12.

No PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install -e ".[dev]"
python -m playwright install chromium
```

Execute a suíte antes de qualquer modificação:

```powershell
python -m pytest
```

E valide a cobertura:

```powershell
python -m pytest --cov=src --cov-report=term-missing
```

O projeto está configurado com:

```toml
fail_under = 100
```

Portanto, qualquer novo código precisa ter cobertura de testes.

---

# 5. Adicionar configuração do proxy

Arquivo:

```text
src/infrastructure/config/settings.py
```

Adicione `browser_proxy_server`:

```python
browser_profile_dir: Path = Field(default=Path(".lotobot-profile"), alias="BROWSER_PROFILE_DIR")
browser_headless: bool = Field(default=True, alias="BROWSER_HEADLESS")
browser_timeout_seconds: int = Field(default=5, alias="BROWSER_TIMEOUT_SECONDS")
browser_proxy_server: str | None = Field(default=None, alias="BROWSER_PROXY_SERVER")
```

---

# 6. Atualizar `.env.example`

Arquivo:

```text
.env.example
```

Altere para:

```env
BROWSER_PROFILE_DIR=.lotobot-profile
BROWSER_HEADLESS=true
BROWSER_TIMEOUT_SECONDS=5
BROWSER_PROXY_SERVER=
```

A configuração vazia significa:

```text
Chromium sem proxy
```

Na EC2 será usado:

```env
BROWSER_PROXY_SERVER=socks5://127.0.0.1:1080
```

---

# 7. Alterar a inicialização do Chromium

Arquivo:

```text
src/infrastructure/browser/session_control_browser.py
```

Altere para:

```python
proxy = None

if self._settings.browser_proxy_server:
    proxy = {
        "server": self._settings.browser_proxy_server,
    }

self._context = self._playwright.chromium.launch_persistent_context(
    user_data_dir=str(self._settings.browser_profile_dir),
    headless=self._settings.browser_headless,
    viewport=viewport,
    args=self._launch_args(self._settings.browser_headless),
    user_agent=self._user_agent(),
    locale="pt-BR",
    proxy=proxy,
)
```

A configuração fica explícita, tipada pela API do Playwright e não interfere na lista atual de argumentos Chromium.

---

# 8. Não configurar fallback para conexão direta

Não use uma configuração equivalente a:

```text
proxy -> direct
```

A intenção é:

```text
Túnel disponível
    ↓
Chromium funciona

Túnel indisponível
    ↓
Chromium falha
```

e não:

```text
Túnel indisponível
    ↓
Chromium passa a sair pelo IP AWS
```

Isso evita mudança silenciosa do IP de saída.

---

# 9. Adicionar testes de configuração

A configuração deve funcionar com e sem proxy.

Exemplo de teste:

```python
def test_browser_proxy_settings():
    settings = Settings(
        BROWSER_PROXY_SERVER="socks5://127.0.0.1:1080",
    )

    assert settings.browser_proxy_server == "socks5://127.0.0.1:1080"
```

E sem configuração:

```python
def test_browser_proxy_settings_default():
    settings = Settings()

    assert settings.browser_proxy_server is None
```

Esses testes podem ser colocados em:

```text
tests/unit/test_edges.py
```

ou em outro teste de `Settings` já existente.

---

# 10. Adicionar teste do `launch_persistent_context`

O projeto já possui testes extensivos de `SessionControlBrowserMixin` em:

```text
tests/unit/test_browser_coverage.py
```

Adicione um teste equivalente ao seguinte:

```python
def test_session_browser_start_with_proxy(monkeypatch, tmp_path):
    page = Page()

    context = SimpleNamespace(
        pages=[page],
        set_default_timeout=Mock(),
        add_init_script=Mock(),
        new_page=Mock(return_value=page),
        close=Mock(),
    )

    chromium = SimpleNamespace(
        launch_persistent_context=Mock(return_value=context),
    )

    playwright = SimpleNamespace(
        chromium=chromium,
        stop=Mock(),
    )

    starter = SimpleNamespace(
        start=Mock(return_value=playwright),
    )

    import infrastructure.browser.playwright_browser as playwright_browser

    monkeypatch.setattr(
        playwright_browser,
        "sync_playwright",
        Mock(return_value=starter),
    )

    settings = Settings(
        BROWSER_PROFILE_DIR=tmp_path,
        BROWSER_PROXY_SERVER="socks5://127.0.0.1:1080",
        BROWSER_TIMEOUT_SECONDS=1,
    )

    browser = SessionControlBrowserMixin(settings)

    browser._start(AutomationSession())

    chromium.launch_persistent_context.assert_called_once()

    kwargs = chromium.launch_persistent_context.call_args.kwargs

    assert kwargs["proxy"] == {
        "server": "socks5://127.0.0.1:1080",
    }

    browser._stop()
```

Também é recomendável validar a ausência do proxy:

```python
def test_session_browser_start_without_proxy(monkeypatch, tmp_path):
    page = Page()

    context = SimpleNamespace(
        pages=[page],
        set_default_timeout=Mock(),
        add_init_script=Mock(),
        new_page=Mock(return_value=page),
        close=Mock(),
    )

    chromium = SimpleNamespace(
        launch_persistent_context=Mock(return_value=context),
    )

    playwright = SimpleNamespace(
        chromium=chromium,
        stop=Mock(),
    )

    starter = SimpleNamespace(
        start=Mock(return_value=playwright),
    )

    import infrastructure.browser.playwright_browser as playwright_browser

    monkeypatch.setattr(
        playwright_browser,
        "sync_playwright",
        Mock(return_value=starter),
    )

    settings = Settings(
        BROWSER_PROFILE_DIR=tmp_path,
        BROWSER_TIMEOUT_SECONDS=1,
    )

    browser = SessionControlBrowserMixin(settings)

    browser._start(AutomationSession())

    kwargs = chromium.launch_persistent_context.call_args.kwargs

    assert kwargs["proxy"] is None

    browser._stop()
```

Se preferir reduzir duplicação, transforme a criação dos mocks em fixture.

---

# 11. Executar testes unitários

No PowerShell:

```powershell
python -m pytest
```

Depois:

```powershell
python -m pytest --cov=src --cov-report=term-missing
```

O resultado esperado é:

```text
100% coverage
```

Também valide o lint:

```powershell
python -m ruff check .
```

E a formatação:

```powershell
python -m ruff format --check .
```

Caso precise corrigir:

```powershell
python -m ruff check . --fix
python -m ruff format .
```

---

# 12. Criar um teste funcional isolado do proxy

Antes de testar o LotoBot inteiro, é melhor validar apenas:

```text
Playwright
    ↓
SOCKS5
    ↓
Internet
```

Crie:

```text
scripts/test_browser_proxy.py
```

Conteúdo:

```python
from __future__ import annotations

import os
import tempfile
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

TERMS_OF_USE_URL = "https://www.loteriasonline.caixa.gov.br/silce-web/#/termos-de-uso"
EXPECTED_HOST = "www.loteriasonline.caixa.gov.br"
EXPECTED_PATH = "/silce-web/"
EXPECTED_FRAGMENT = "/termos-de-uso"
NAVIGATION_SETTLE_MS = 5_000


def main() -> None:
    proxy_server = os.getenv("BROWSER_PROXY_SERVER")

    if not proxy_server:
        raise RuntimeError("BROWSER_PROXY_SERVER não configurado")

    with tempfile.TemporaryDirectory(prefix="lotobot-proxy-test-") as profile_dir, sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            proxy={
                "server": proxy_server,
            },
        )

        try:
            page = context.pages[0] if context.pages else context.new_page()

            response = page.goto(
                TERMS_OF_USE_URL,
                wait_until="commit",
                timeout=30_000,
            )

            if response is None or not response.ok:
                status = "sem resposta" if response is None else str(response.status)
                raise RuntimeError(f"A página da CAIXA retornou um status inválido: {status}")

            # DOMContentLoaded pode não ocorrer enquanto o portal processa scripts
            # e desafios de proteção. Aguarde os redirecionamentos sem vincular o
            # teste a esse evento global da página.
            page.wait_for_timeout(NAVIGATION_SETTLE_MS)

            current_url = urlsplit(page.url)
            if (
                current_url.hostname != EXPECTED_HOST
                or current_url.path != EXPECTED_PATH
                or current_url.fragment != EXPECTED_FRAGMENT
            ):
                raise RuntimeError(f"O Chromium terminou em uma URL inesperada: {page.url}")

            body = page.locator("body")
            body.wait_for(state="attached", timeout=30_000)
            if not body.inner_html().strip():
                raise RuntimeError("A página da CAIXA retornou um documento sem conteúdo")

            print("Teste CAIXA via Chromium: OK")
            print(f"Status HTTP CAIXA: {response.status}")
            print(f"URL final CAIXA: {page.url}")
            print(f"Título da página CAIXA: {page.title()}")
        finally:
            context.close()


if __name__ == "__main__":
    main()
```

Esse script:

- não usa o perfil real do LotoBot;
- não acessa o portal da CAIXA;
- não executa autenticação;
- não realiza aposta;
- testa somente o caminho de rede do Chromium.

---

# 13. Teste local sem proxy

Primeiro confirme que o script funciona sem a alteração de rede.

Você pode criar temporariamente uma versão do script sem `proxy`, ou simplesmente abrir:

```text
https://api.ipify.org
```

pelo navegador normal e anotar o IP público atual.

No PowerShell:

```powershell
curl.exe https://api.ipify.org
```

Exemplo:

```text
200.100.50.25
```

Anote esse endereço como:

```text
IP_LOCAL
```

---

# 14. Testar SOCKS5 localmente no Windows

Para validar o suporte do LotoBot/Playwright ao SOCKS5 antes de criar a EC2, uma maneira prática é usar o próprio OpenSSH do Windows.

## 14.1 Verificar o OpenSSH Client

No PowerShell:

```powershell
ssh -V
```

Deve aparecer algo semelhante a:

```text
OpenSSH_for_Windows_...
```

Caso o comando não exista:

```powershell
Get-WindowsCapability -Online |
    Where-Object Name -like 'OpenSSH.Client*'
```

Instalação, se necessária:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
```

---

# 15. Opção de teste local com OpenSSH Server

Essa etapa é somente para simular um SOCKS5 local antes da AWS.

Verifique:

```powershell
Get-WindowsCapability -Online |
    Where-Object Name -like 'OpenSSH.Server*'
```

Se não estiver instalado:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
```

Inicie:

```powershell
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
```

Confirme:

```powershell
Get-Service sshd
```

---

# 16. Criar SOCKS5 local para teste

Abra um PowerShell separado:

```powershell
ssh -N -D 127.0.0.1:1080 localhost
```

Significado:

```text
-D
    cria um SOCKS dinâmico

127.0.0.1:1080
    aceita conexões apenas da própria máquina

-N
    não abre um shell remoto
```

Mantenha esse terminal aberto.

---

# 17. Testar o SOCKS com `curl`

Em outro PowerShell:

```powershell
curl.exe `
  --socks5-hostname 127.0.0.1:1080 `
  https://api.ipify.org
```

O IP retornado deverá ser o IP público da sua conexão local.

Compare:

```powershell
curl.exe https://api.ipify.org
```

com:

```powershell
curl.exe `
  --socks5-hostname 127.0.0.1:1080 `
  https://api.ipify.org
```

Como os dois caminhos terminam na mesma máquina nesse teste, os IPs devem ser iguais.

O objetivo aqui não é mudar o IP, e sim validar:

```text
SOCKS5 funcionando
```

---

# 18. Executar o teste Playwright pelo SOCKS

No terminal onde o ambiente virtual está ativado:

```powershell
$env:BROWSER_PROXY_SERVER="socks5://127.0.0.1:1080"
python .\scripts\test_browser_proxy.py
```

Resultado esperado:

```text
IP público observado pelo Chromium: <SEU_IP_LOCAL>
```

Isso comprova:

```text
Playwright
   ↓
Chromium
   ↓
SOCKS5
   ↓
SSH
   ↓
Internet
```

---

# 19. Testar comportamento de falha

Esse teste é importante.

Pare o terminal do SSH com:

```text
Ctrl+C
```

Não altere:

```powershell
$env:BROWSER_PROXY_SERVER
```

Execute novamente:

```powershell
python .\scripts\test_browser_proxy.py
```

O esperado é uma falha de conexão/proxy.

O navegador **não deve navegar normalmente**.

Isso comprova que não existe fallback silencioso para a conexão direta.

---

# 20. Testar o LotoBot local sem proxy

No `.env` local:

```env
BROWSER_PROXY_SERVER=
```

Inicie:

```powershell
python -m uvicorn api.server:app --app-dir src --reload
```

Execute os fluxos que não efetuem pagamento real.

Mantenha obrigatoriamente:

```env
CONFIRM_PAYMENT=false
```

O objetivo desse teste é confirmar que a nova configuração é retrocompatível.

---

# 21. Testar o LotoBot local com SOCKS5

Suba novamente:

```powershell
ssh -N -D 127.0.0.1:1080 localhost
```

Configure:

```env
BROWSER_PROXY_SERVER=socks5://127.0.0.1:1080
```

Inicie a API:

```powershell
python -m uvicorn api.server:app --app-dir src --reload
```

Teste a abertura da sessão/navegação.

Nesse momento ainda não existe diferença de IP, porque o SOCKS termina na própria máquina.

O que está sendo validado é:

```text
LotoBot
    ↓
SessionControlBrowserMixin
    ↓
launch_persistent_context(proxy=...)
    ↓
Chromium
    ↓
SOCKS5
```

---

# 22. Teste descartável na AWS com AWS CLI

---

## 22.1 Testar `socks5` em uma EC2 descartável

O roteiro abaixo cria uma infraestrutura isolada apenas para validar o caminho:

```text
curl na EC2
    → SOCKS5 127.0.0.1:1080
    → túnel SSH reverso
    → Windows
    → Internet
```

Ele cria VPC, Internet Gateway, tabela de rotas, subnet pública, Security Group,
par de chaves e uma EC2 Ubuntu. O script de inicialização registra em um arquivo
JSON o estado necessário para que um segundo script remova os recursos, mesmo se
a criação ou a validação falhar.

Este teste AWS é exclusivamente de conectividade. Ele não instala nem executa
Chromium, Playwright ou LotoBot. A validação usa somente `curl` na EC2 para
comparar a saída direta com a saída pelo SOCKS5, inclusive ao consultar a página
de termos de uso do portal da CAIXA.

> O teste pode gerar cobrança de EC2, EBS, transferência e IPv4 público enquanto
> estiver em execução. Confirme a elegibilidade do tipo de instância na sua conta
> e execute o script de limpeza assim que concluir a validação.

### 22.1.1 Pré-requisitos e permissões

Execute em um PowerShell com `aws`, `ssh` e `curl.exe` disponíveis:

```powershell
aws --version
ssh -V
curl.exe --version
aws sts get-caller-identity --profile <perfil>
```

A identidade usada precisa poder consultar o SSM Parameter Store e criar,
descrever, marcar e excluir os recursos EC2 usados no script. Isso inclui as
ações equivalentes a `ssm:GetParameter` e às operações de VPC, subnet, Internet
Gateway, route table, Security Group, key pair, `RunInstances` e
`TerminateInstances`.

O teste não cria IAM role, Elastic IP, NAT Gateway, endpoint VPC, S3 ou Secrets
Manager. Portanto, não há recursos desses tipos para limpar.

### 22.1.2 Criação, teste e limpeza com os scripts do repositório

Os scripts usados neste procedimento já estão no diretório `scripts`:

- `start-socks5-ipv4-aws.ps1` cria os recursos, testa o túnel e grava o estado;
- `stop-socks5-ipv4-aws.ps1` lê esse estado, encerra o túnel e remove os recursos.

Abra o PowerShell e entre no diretório dos scripts. Substitua `$YourDir` pelo
diretório que contém o repositório `loto-bot`:

```powershell
cd $YourDir\loto-bot\scripts

Unblock-File -LiteralPath .\start-socks5-ipv4-aws.ps1
Unblock-File -LiteralPath .\stop-socks5-ipv4-aws.ps1
```

Inicie o teste informando o perfil, a região e o tipo da instância. O exemplo
abaixo usa o perfil `<perfil>`, a região `us-east-1` e uma `t3.small`:

```powershell
.\start-socks5-ipv4-aws.ps1 -AwsProfile "<perfil>" -AwsRegion "us-east-1" -InstanceType "t3.small"
```

O script cria, no mesmo diretório, o arquivo padrão
`socks5-ipv4-aws-state.json`. Ele contém os IDs dos recursos, o perfil e a região
necessários à limpeza. O arquivo não contém a chave privada, mas não deve ser
editado nem removido manualmente antes da limpeza.

O teste aprovado deve mostrar:

- listener exatamente em `127.0.0.1:1080`;
- IP direto diferente do IP do SOCKS5, salvo quando a rede AWS e a local
  excepcionalmente compartilham a mesma saída;
- IP do SOCKS5 igual ao IP público observado no Windows antes do teste;
- os códigos HTTP obtidos no acesso direto e pelo SOCKS5 ao portal da CAIXA;
- falha do `curl --socks5-hostname` depois que o túnel é encerrado.

Mesmo após um teste aprovado, os recursos AWS permanecem ativos e podem gerar
cobrança. Remova-os assim que terminar:

```powershell
.\stop-socks5-ipv4-aws.ps1
```

O script de limpeza recupera o perfil e a região do arquivo de estado, termina a
instância, remove os demais recursos e executa uma auditoria final. Quando a
limpeza termina sem pendências, ele também exclui o arquivo de estado local.

Para escolher explicitamente outro arquivo de estado, passe o mesmo caminho aos
dois scripts. Por exemplo:

```powershell
.\start-socks5-ipv4-aws.ps1 -AwsProfile "<perfil>" -AwsRegion "us-east-1" -InstanceType "t3.small" -StateFile ".\socks5-ipv4-aws-state.json"
.\stop-socks5-ipv4-aws.ps1 -StateFile ".\socks5-ipv4-aws-state.json"
```

Como `socks5-ipv4-aws-state.json` já é o padrão, também é válido iniciar o segundo
teste solicitado apenas com o parâmetro explícito abaixo; perfil, região e tipo
de instância assumirão os padrões definidos no script (`<perfil>`, `us-east-1` e
`t3.micro`). Na prática, informe `-AwsProfile` sempre que não tiver substituído o
placeholder no script:

```powershell
.\start-socks5-ipv4-aws.ps1 -StateFile "socks5-ipv4-aws-state.json"
.\stop-socks5-ipv4-aws.ps1 -StateFile "socks5-ipv4-aws-state.json"
```

Não inicie outro teste usando o mesmo arquivo enquanto ele existir. Primeiro
execute a limpeza ou escolha outro `-StateFile`. Se a inicialização falhar, o
estado parcial é preservado; execute o comando de parada com o mesmo arquivo
para tentar remover tudo o que já tiver sido criado.

### 22.1.3 Limpeza de contingência

Se a limpeza terminar com pendências, o script preserva o arquivo de estado para
uma nova tentativa. Corrija a causa indicada na saída e execute novamente:

```powershell
.\stop-socks5-ipv4-aws.ps1 -StateFile ".\socks5-ipv4-aws-state.json"
```

Se for necessário substituir o perfil ou a região gravados no JSON, o script de
parada também aceita esses parâmetros:

```powershell
.\stop-socks5-ipv4-aws.ps1 -StateFile ".\socks5-ipv4-aws-state.json" -AwsProfile "<perfil>" -AwsRegion "us-east-1"
```

Confira a auditoria exibida ao final: nenhuma VPC do teste deve ser retornada e
somente a instância terminada deve permanecer no histórico do EC2. O volume raiz
usa `DeleteOnTermination=true`, portanto é removido com a instância. O IPv4
público é atribuído automaticamente, não é um Elastic IP e é liberado quando a
instância é terminada.

## 22.2 Testar `test_browser_proxy.py` em uma EC2 descartável

O script `start-browser-socks5-ipv4-aws.ps1` cria a mesma infraestrutura descartável
do teste anterior, estabelece o túnel SSH reverso e executa
`scripts/test_browser_proxy.py` na EC2. Ele prepara automaticamente a instância
com Python, ambiente virtual, Playwright, Chromium e Xvfb. A execução remota usa
`xvfb-run`, embora o Chromium seja iniciado com `headless=True`.

O procedimento valida que:

- o listener SOCKS5 existe em `127.0.0.1:1080` na EC2;
- o Chromium usa `socks5://127.0.0.1:1080` para abrir a página de Termos de Uso
  das Loterias Online CAIXA;
- a navegação recebe uma resposta HTTP bem-sucedida, termina com o host
  `www.loteriasonline.caixa.gov.br`, o caminho `/silce-web/` e o fragmento
  `/termos-de-uso`, e retorna um documento com conteúdo;
- o orquestrador recebe a confirmação `Teste CAIXA via Chromium: OK`;
- depois que o túnel é encerrado, uma nova execução do teste falha em vez de
  usar diretamente a saída da EC2.

Abra o PowerShell no diretório dos scripts e desbloqueie os arquivos baixados,
caso necessário:

```powershell
cd $YourDir\loto-bot\scripts

Unblock-File -LiteralPath .\start-browser-socks5-ipv4-aws.ps1
Unblock-File -LiteralPath .\stop-socks5-ipv4-aws.ps1
```

Execute o teste. Uma `t3.micro` é usada no exemplo para dar mais folga à
instalação e à inicialização do Chromium:

```powershell
.\start-browser-socks5-ipv4-aws.ps1 `
  -AwsProfile "<perfil>" `
  -AwsRegion "us-east-1" `
  -InstanceType "t3.micro" `
  -StateFile ".\browser-socks5-ipv4-aws-state.json"
```

Por padrão, o arquivo Python enviado à EC2 é o
`test_browser_proxy.py` localizado no mesmo diretório do script PowerShell. Para
testar outra cópia, informe seu caminho com `-BrowserTestScript`.

A preparação da instância pode levar alguns minutos porque baixa o Chromium e
suas dependências. O resultado aprovado contém linhas semelhantes a:

```text
Listener: 127.0.0.1:1080
Teste CAIXA via Chromium: OK
Status HTTP CAIXA: 200
URL final CAIXA: https://www.loteriasonline.caixa.gov.br/silce-web/#/termos-de-uso
Título da página CAIXA: <título-retornado-pelo-portal>
Falha sem fallback confirmada após encerrar o túnel.
Teste aprovado: a página de Termos de Uso da CAIXA abriu pelo SOCKS5 e falhou sem fallback.
```

O status HTTP e o título mostrados acima são ilustrativos; o critério do script
é que a resposta seja bem-sucedida, que o host, o caminho e o fragmento da URL
final sejam os esperados e que o `body` não esteja vazio. Como a navegação pode
continuar processando scripts e desafios de proteção do portal, o teste aguarda
o início da resposta
(`wait_until="commit"`) e mais cinco segundos para os redirecionamentos, sem
depender do evento global `DOMContentLoaded`.

Os scripts normalizam as terminações de linha antes de entregar comandos ao Bash
remoto. Isso é necessário no Windows PowerShell para impedir que o `CR` de `CRLF`
seja anexado ao último argumento, transformando, por exemplo, `chromium` em
`chromium\r` e fazendo o Playwright rejeitar o nome do navegador.

O script encerra o túnel ao concluir a validação, mas mantém a EC2 e os demais
recursos ativos para permitir auditoria. A finalização continua sendo feita pelo
mesmo `stop-socks5-ipv4-aws.ps1`; use exatamente o arquivo de estado informado na
inicialização:

```powershell
.\stop-socks5-ipv4-aws.ps1 -StateFile ".\browser-socks5-ipv4-aws-state.json"
```

Execute a finalização mesmo quando o teste falhar. O estado parcial é salvo no
JSON para que o script de parada possa remover os recursos que já tiverem sido
criados. Se a limpeza reportar pendências, corrija o erro e repita o mesmo
comando antes de excluir o arquivo de estado manualmente.

---

# 23. Checklist local

- [ ] `browser_proxy_server` adicionado em `Settings`.
- [ ] `BROWSER_PROXY_SERVER=` adicionado em `.env.example`.
- [ ] `proxy=` adicionado ao `launch_persistent_context`.
- [ ] Teste de configuração criado.
- [ ] Teste de inicialização com proxy criado.
- [ ] Teste sem proxy criado.
- [ ] `python -m pytest` passa.
- [ ] Cobertura permanece em 100%.
- [ ] Ruff passa.
- [ ] SOCKS5 local funciona.
- [ ] `scripts/test_browser_proxy.py` funciona.
- [ ] Desligar SOCKS faz o navegador falhar.
- [ ] LotoBot funciona sem proxy.
- [ ] LotoBot funciona com proxy.
- [ ] `CONFIRM_PAYMENT=false`.

---

# 24. Checklist AWS

- [ ] EC2 criada.
- [ ] Python 3.12 instalado.
- [ ] Chromium do Playwright instalado.
- [ ] SSH permitido somente das origens necessárias.
- [ ] Porta 1080 não exposta.
- [ ] Túnel Windows → EC2 estabelecido.
- [ ] EC2 possui `127.0.0.1:1080`.
- [ ] `curl` direto mostra IP AWS.
- [ ] `curl --socks5-hostname` mostra IP local.
- [ ] Chromium mostra IP local.
- [ ] Demais conexões continuam usando IP AWS.
- [ ] Queda do túnel provoca falha do Chromium.
- [ ] Túnel consegue reconectar.

---

# 25. Fluxo final

```text
┌─────────────────────────────────────────────┐
│                   AWS EC2                   │
│                                             │
│  FastAPI                                    │
│     │                                       │
│  Use Cases                                  │
│     │                                       │
│  SessionControlBrowserMixin                 │
│     │                                       │
│  Playwright                                 │
│     │                                       │
│  Chromium                                   │
│     │                                       │
│     ▼                                       │
│  SOCKS5 127.0.0.1:1080                     │
└───────────────┬─────────────────────────────┘
                │
                │ SSH Reverse Dynamic Forward
                │
                ▼
┌─────────────────────────────────────────────┐
│                Windows local                │
│                                             │
│  OpenSSH Client                             │
│       │                                     │
│       ▼                                     │
│  conexão local                              │
└───────────────┬─────────────────────────────┘
                │
                ▼
             Internet
```