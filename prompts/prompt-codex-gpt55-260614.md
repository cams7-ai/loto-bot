# Prompt para Codex GPT-5.5: LotoBot

Você é um Arquiteto de Software Sênior, especialista em Python 3.12, FastAPI, Playwright, Clean Architecture, automação web, testes automatizados e engenharia de requisitos.

Sua missão é projetar e implementar a aplicação **LotoBot**, uma API REST em Python para controlar uma sessão autenticada no portal **Loterias Online CAIXA** e executar o fluxo de aposta online de forma automatizada, observável, testável e segura.

Toda a lógica interna do código deve ser escrita em inglês, incluindo nomes de classes, funções, métodos, módulos, variáveis e objetos de domínio. Comentários no código, mensagens de erro, logs personalizados, documentação técnica, README e demais textos direcionados ao usuário ou mantenedor devem ser escritos em **português do Brasil**.

> Importante: credenciais, CPF, dados de cartão, códigos de segurança e demais dados sensíveis devem ser tratados como segredos. Não grave valores reais diretamente no código, em testes ou na documentação. Use variáveis de ambiente e placeholders nos arquivos versionáveis.

---

## 1. Objetivo

Construir uma API REST chamada **LotoBot** que permita iniciar, controlar e encerrar uma automação do portal Loterias Online CAIXA, realizando o caso de uso **Realizar Aposta Online**.

A aplicação deve:

- Usar **FastAPI** para expor endpoints de controle da automação.
- Usar **Playwright** com perfil persistente do Chromium.
- Seguir **Clean Architecture**, separando API, aplicação, domínio e infraestrutura.
- Integrar com serviços locais para leitura de e-mail, envio de e-mail e notificação via WhatsApp Web.
- Gerar logs estruturados com rastreabilidade suficiente para auditoria e diagnóstico.
- Ter testes automatizados com cobertura de 100%.
- Garantir que os testes nunca acessem a URL real do portal Loterias Online CAIXA.
- Manter a confirmação real de pagamento protegida por flag explícita.

---

## 2. Caso de Uso

### 2.1 Identificação

| Campo | Descrição |
|---|---|
| Nome | Realizar aposta online |
| Ator principal | Apostador |
| Sistema externo | Loterias Online CAIXA |
| Aplicação | LotoBot |
| Objetivo | Permitir que o usuário escolha uma modalidade de loteria, selecione números, adicione a aposta ao carrinho e finalize o pagamento conforme configuração autorizada. |

### 2.2 Pré-condições

O usuário deve:

- Ter CPF cadastrado no ecossistema CAIXA.
- Ter acesso ao portal Loterias Online CAIXA.
- Estar apto a autenticar-se no sistema.
- Ter idade mínima permitida para realizar apostas.
- Possuir forma de pagamento válida.
- Ter autorizado explicitamente a execução do pagamento quando aplicável.

### 2.3 Pós-condições

Ao final do caso de uso bem-sucedido:

- A aposta fica registrada no sistema da Loterias Online CAIXA.
- O pagamento é confirmado.
- O comprovante da aposta é gerado.
- O usuário pode consultar a aposta posteriormente.
- A sessão automatizada é encerrada de forma controlada.

### 2.4 Resultado esperado

O usuário consegue realizar uma aposta válida no site Loterias Online CAIXA e recebe confirmação da aposta com sucesso. Em caso de falha, a aplicação registra o erro, envia notificação conforme disponibilidade dos canais configurados e encerra a sessão.

---

## 3. Diagrama Textual do Fluxo do Caso de Uso

```text
Apostador/LotoBot
    |
    v
[CP 1.1] Acessar Loterias Online CAIXA
    |
    v
[CP 1.2] Aceitar termos de uso
    |
    v
[CP 1.3] Acessar Home
    |
    v
[CP 1.4] Informar CPF
    |
    v
[CP 1.5] Solicitar código de acesso
    |
    +--> [CP 11.1] Buscar código no Gmail Reader
    |        |
    |        +--> Falha: [EX 10.2] Notificar e encerrar sessão
    |
    v
[CP 1.6] Informar código recebido
    |
    v
[CP 1.7] Informar senha
    |
    v
[CP 2.1] Selecionar modalidade
    |
    +--> Se houver modal: [CA 2.1.1] Fechar modal de notificação
    |
    v
[CP 3.1] Escolher números aleatórios da aposta
    |
    v
[CP 4.1] Adicionar aposta ao carrinho
    |
    v
[CP 5.1] Confirmar compra
    |
    v
[CP 6.1] Selecionar forma de pagamento
    |
    v
[CP 7.1] Confirmar pagamento
    |
    +--> Se CONFIRMA_PAGAMENTO != true:
    |        [EX 10.2] Notificar e encerrar sessão
    |
    v
[CP 8.1] Finalizar aposta e validar comprovante
    |
    v
[CP 10.1] Fechar sessão e navegador
    |
    +--> [CP 10.4] Encerrar sessão do WhatsApp Web
    |
    v
Fim

Fluxo de exceção global:
Qualquer tela não carregada, elemento indisponível, falha de API ou erro de automação
    -> [EX 10.2] Gerar log de erro
    -> [CP 10.5] Enviar notificação por WhatsApp, quando disponível
    -> [CP 10.6] Enviar e-mail como fallback
    -> [CP 10.1] Fechar sessão
```

---

## 4. Fluxo Principal Resumido

| Etapa | Ação do ator | Resposta esperada do sistema |
|---:|---|---|
| 1 | Acessa o site Loterias Online CAIXA | Exibe a tela inicial |
| 2 | Aceita os termos de uso | Libera o acesso ao portal |
| 3 | Informa o CPF | Solicita autenticação |
| 4 | Solicita o código de acesso | Envia código para o canal cadastrado |
| 5 | Informa o código recebido | Valida o código |
| 6 | Informa a senha | Autentica o usuário |
| 7 | Seleciona uma modalidade, por exemplo Mega-Sena | Exibe a tela de apostas |
| 8 | Escolhe os números da aposta | Valida a quantidade de números |
| 9 | Adiciona a aposta ao carrinho | Atualiza o carrinho |
| 10 | Confirma a compra | Exibe formas de pagamento |
| 11 | Seleciona PIX ou cartão | Solicita dados de pagamento |
| 12 | Confirma o pagamento | Processa a transação |
| 13 | Finaliza a aposta | Exibe comprovante da aposta |

---

## 5. Legenda de Cenários

- **CP**: Cenário Principal
- **CA**: Cenário Alternativo
- **EX**: Fluxo de Exceção
- **RN**: Regra de Negócio

---

## 6. Configurações e Variáveis de Ambiente

Crie os arquivos `.env` e `.env.example`. O arquivo `.env.example` deve conter placeholders seguros. O arquivo `.env` deve ser usado apenas localmente.

```env
CPF="<CPF_DO_APOSTADOR>"
SENHA="<SENHA_DO_APOSTADOR>"

URL_LOTERIAS_ONLINE="https://www.loteriasonline.caixa.gov.br"
URL_TERMO_DE_USO="${URL_LOTERIAS_ONLINE}/silce-web/#/termos-de-uso"
URL_HOME="${URL_LOTERIAS_ONLINE}/silce-web/#/home"
CLIENT_ID="cli-web-lce"
URL_LOGIN_CAIXA="https://login.caixa.gov.br"
EXECUTION="<EXECUTION_ID_DA_SESSAO>"

URL_GMAIL_READER="http://localhost:8001"
URL_MAIL_SENDER="http://localhost:8002"
URL_WHATSAPP_NOTIFY="http://localhost:8003"

VALIDATION_CODE_WAIT_TIMEOUT_SECONDS=30
WHATSAPP_HEADLESS=true
WHATSAPP_TIMEOUT_SECONDS=60
WHATSAPP_CONTACT="Notificação via App"

MAIL_TO="<EMAIL_DESTINATARIO>"
MAIL_TYPE="HTML"

MODALIDADE_SELECIONADA="mega-sena"
URL_ESCOLHE_NUMEROS_APOSTA="${URL_LOTERIAS_ONLINE}/silce-web/#/${MODALIDADE_SELECIONADA}"
URL_SELECIONA_PIX_OU_CARTAO="${URL_LOTERIAS_ONLINE}/silce-web/#/carrinho/pagamento#container-meio-pagamento"

FINAL_CARTAO_CREDITO="<ULTIMOS_4_DIGITOS_DO_CARTAO>"
CODIGO_DE_SEGURANCA_DO_CARTAO_DE_CREDITO="<CVV>"
CONFIRMA_PAGAMENTO=false

URL_FINALIZA_A_APOSTA_PROCESSANDO="${URL_LOTERIAS_ONLINE}/silce-web/#/carrinho/processamento"
```

### Observações sobre segurança

- `CONFIRMA_PAGAMENTO` deve permanecer `false` por padrão.
- O fluxo de confirmação real de pagamento só pode ser executado quando `CONFIRMA_PAGAMENTO=true`.
- Testes automatizados devem usar mocks, fakes ou servidores locais simulados.
- Nenhum teste pode abrir `URL_LOTERIAS_ONLINE`.
- Dados sensíveis devem ser mascarados nos logs.

---

## 7. Seletores da Interface

Centralize os seletores em um módulo de infraestrutura, evitando espalhá-los pela lógica de aplicação.

```env
TERMO_USO_BOTAO_SIM="//*[@id='botaosim']"
HOME_BOTAO_ACESSAR="//*[@id='btnLogin']/span"
INFORME_CPF_CAMPO_CPF="//*[@id='username']"
INFORME_CPF_BOTAO_PROXIMO="//*[@id='button-submit']"
RECEBE_CODIGO_BOTAO_RECEBER_CODIGO="//*[@id='form-login']//button[text()='Receber código']"
INFORME_CODIGO_CAMPO_CODIGO="//*[@id='codigo']"
INFORME_CODIGO_BOTAO_ENVIAR="//*[@id='form-login']//button[text()='Enviar']"
INFORME_SENHA_CAMPO_SENHA="//*[@id='password']"
INFORME_SENHA_BOTAO_ENTRAR="//*[@id='template-section']//button[text()='Entrar']"
HOME_POPUPNOTIFICAO_FECHAR="//*[@id='HeaderView.html']//button[text()='Fechar']"
HOME_BOTAO_SELECIONAR_MODALIDADE="//h2[normalize-space()='${MODALIDADE_SELECIONADA}']/ancestor::div[contains(@class,'new-card-modalidades')]//button[.//p[normalize-space()='Aposte']]"
MODALIDADE_BOTAO_COMPLETE_O_JOGO="//*[@id='completeojogo']"
MODALIDADE_BOTAO_COLOCAR_NO_CARRINHO="//*[@id='colocarnocarrinho']"
MODALIDADE_BOTAO_IR_PARA_PAGAMENTO="//*[@id='irparapagamento']"
MODALIDADE_BOTAO_CONFIRMA_PAGAMENTO="//span[contains(.,'O Valor total da sua compra é de') and contains(.,'Confirma?')]/ancestor::div[contains(@class,'modal-content')]//button[@id='confirma']"
SELECIONA_PIX_OU_CARTAO_SELECIONAR_CARTAO="//h4[.//img[@alt='Mercado Pago'] and contains(normalize-space(.),'${FINAL_CARTAO_CREDITO}')]"
SELECIONA_PIX_OU_CARTAO_BOTAO_CONTINUAR="//label[normalize-space()='Informe os dados do seu cartão de crédito:']/ancestor::div[contains(@class,'jumbotron')]//button[@id='pay']"
SELECIONA_PIX_OU_CARTAO_CAMPO_CODIGO_DE_SEGURANCA="//p[contains(normalize-space(.),'Digite o código de Segurança do seu cartão')]/ancestor::div[contains(@class,'modal-content')]//input[@id='securityCode']"
SELECIONA_PIX_OU_CARTAO_BOTAO_CONFIRMAR="//p[contains(normalize-space(.),'Digite o código de Segurança do seu cartão')]/ancestor::div[contains(@class,'modal-content')]//button[@id='confirmarModalConfirmacao']"
FINALIZA_A_APOSTA_PEDIDO_REALIZADO="//div[@id='containerProcessamento']//h3[contains(.,'Seu pedido foi realizado')]"
FINALIZA_A_APOSTA_BOTAO_MINHA_CONTA="//a[@id='suaconta']//span[normalize-space()='Minha Conta']"
FINALIZA_A_APOSTA_BOTAO_SAIR="//*[@id='sair']"
```

---

## 8. Estado da Automação

Modele o estado da automação de forma explícita, preferencialmente por meio de entidades, value objects ou DTOs da camada de aplicação.

| Variável | Descrição |
|---|---|
| `state` | UUID gerado por sessão pelo sistema da Loterias Online, no formato 8-4-4-4-12. |
| `nonce` | UUID gerado por sessão pelo sistema da Loterias Online, no formato 8-4-4-4-12. |
| `url_informe_cpf` | URL de autenticação OpenID Connect montada com `CLIENT_ID`, `URL_HOME`, `state` e `nonce`. |
| `tab_id` | Sequência alfanumérica curta gerada por sessão. |
| `executed_operation` | Nome da operação atualmente executada. |
| `valid_code` | Código de validação retornado pela API Gmail Reader. |
| `whatsapp_status` | Status retornado pela API de sessão do WhatsApp. |
| `whatsapp_message` | Mensagem enviada via API WhatsApp Notify. |
| `whatsapp_status_message` | Status de envio retornado pela API WhatsApp Notify. |
| `whatsapp_error_code` | Código de erro retornado pelas APIs do WhatsApp Notify. |
| `whatsapp_enabled` | Flag que indica se a sessão do WhatsApp Web foi inicializada. |
| `mail_subject` | Assunto enviado para a API Mail Sender. |
| `mail_body` | Corpo HTML enviado para a API Mail Sender. |
| `codigo_acompanhamento` | Código numérico gerado por aposta pelo sistema Loterias Online. |

URLs derivadas:

```text
url_autenticacao="${URL_LOGIN_CAIXA}/auth/realms/internet/login-actions/authenticate?execution=${EXECUTION}&client_id=${CLIENT_ID}&tab_id=${tab_id}"
url_recebe_codigo="${url_autenticacao}"
url_informe_codigo="${url_autenticacao}"
url_informe_senha="${url_autenticacao}"
url_finaliza_a_aposta_acompanhamento="${URL_LOTERIAS_ONLINE}/silce-web/#/carrinho/acompanhamento/${codigo_acompanhamento}"
```

---

## 9. Cenários Funcionais Detalhados

### CP 1.1 - Acessar o site Loterias Online CAIXA

1. Definir `executed_operation` como `"Acessa o site Loterias Online CAIXA"`.
2. Executar `CP 10.3`.
3. Acessar `URL_LOTERIAS_ONLINE`.
4. Aguardar redirecionamento para `CP 1.2`.
5. Gerar log `INFO` conforme `CP 14.1`.

**CA 1.1.1 - Tela de termos de uso não carregada**

Se a tela de termos de uso não for carregada, executar `EX 10.2`.

### CP 1.2 - Aceitar termos de uso

1. Definir `executed_operation` como `"Aceita os termos de uso"`.
2. Aguardar carregamento de `URL_TERMO_DE_USO`.
3. Clicar em `TERMO_USO_BOTAO_SIM`.
4. Aguardar redirecionamento para `CP 1.3`.
5. Gerar log `INFO` conforme `CP 14.1`.

**CA 1.2.1 - Home não carregada**

Se a Home não for carregada, executar `EX 10.2`.

### CP 1.3 - Home

1. Definir `executed_operation` como `"Home"`.
2. Aguardar carregamento de `URL_HOME`.
3. Clicar em `HOME_BOTAO_ACESSAR`.
4. Aguardar redirecionamento para `CP 1.4`.
5. Gerar log `INFO` conforme `CP 14.1`.

**CA 1.3.1 - Tela de CPF não carregada**

Se a tela de CPF não for carregada, executar `EX 10.2`.

### CP 1.4 - Informar CPF

1. Definir `executed_operation` como `"Informa o CPF"`.
2. Aguardar carregamento de `url_informe_cpf`.
3. Preencher `CPF` em `INFORME_CPF_CAMPO_CPF`.
4. Clicar em `INFORME_CPF_BOTAO_PROXIMO`.
5. Aguardar redirecionamento para `CP 1.5`.
6. Gerar log `INFO` conforme `CP 14.1`.

**CA 1.4.1 - Tela de solicitação de código não carregada**

Se a tela de solicitação de código não for carregada, executar `EX 10.2`.

### CP 1.5 - Solicitar código de acesso

1. Definir `executed_operation` como `"Solicita o código de acesso"`.
2. Executar `CP 11.1`.
3. Aguardar carregamento de `url_recebe_codigo`.
4. Clicar em `RECEBE_CODIGO_BOTAO_RECEBER_CODIGO`.
5. Aguardar redirecionamento para `CP 1.6`.
6. Gerar log `INFO` conforme `CP 14.1`.

**CA 1.5.1 - Erro ao buscar código de validação**

Se ocorrer `CA 11.1.1`, executar `EX 10.2`.

**CA 1.5.2 - Tela de código recebido não carregada**

Se a tela de código recebido não for carregada, executar `EX 10.2`.

### CP 1.6 - Informar código recebido

1. Definir `executed_operation` como `"Informa o código recebido"`.
2. Aguardar carregamento de `url_informe_codigo`.
3. Preencher `valid_code` em `INFORME_CODIGO_CAMPO_CODIGO`.
4. Clicar em `INFORME_CODIGO_BOTAO_ENVIAR`.
5. Aguardar redirecionamento para `CP 1.7`.
6. Gerar log `INFO` conforme `CP 14.1`.

**CA 1.6.1 - Tela de senha não carregada**

Se a tela de senha não for carregada, executar `EX 10.2`.

### CP 1.7 - Informar senha

1. Definir `executed_operation` como `"Informa a senha"`.
2. Aguardar carregamento de `url_informe_senha`.
3. Preencher `SENHA` em `INFORME_SENHA_CAMPO_SENHA`.
4. Clicar em `INFORME_SENHA_BOTAO_ENTRAR`.
5. Aguardar redirecionamento para `CP 2.1`.
6. Gerar log `INFO` conforme `CP 14.1`.

**CA 1.7.1 - Tela de seleção de modalidade não carregada**

Se a tela de seleção de modalidade não for carregada, executar `EX 10.2`.

### CP 2.1 - Selecionar modalidade

1. Definir `executed_operation` como `"Seleciona uma modalidade"`.
2. Aguardar carregamento de `URL_HOME`.
3. Se `HOME_POPUPNOTIFICAO_FECHAR` estiver visível, executar `CA 2.1.1`.
4. Clicar em `HOME_BOTAO_SELECIONAR_MODALIDADE`.
5. Aguardar redirecionamento para `CP 3.1`.
6. Gerar log `INFO` conforme `CP 14.1`.

**CA 2.1.1 - Fechar modal de notificação**

Se o elemento `HOME_POPUPNOTIFICAO_FECHAR` for exibido, clicar no botão correspondente.

**CA 2.1.2 - Tela de escolha de números não carregada**

Se a tela de escolha de números não for carregada, executar `EX 10.2`.

### CP 3.1 - Escolher números aleatórios da aposta

1. Definir `executed_operation` como `"Escolhe os números da aposta"`.
2. Aguardar carregamento de `URL_ESCOLHE_NUMEROS_APOSTA`.
3. Clicar em `MODALIDADE_BOTAO_COMPLETE_O_JOGO`.
4. Executar `CP 4.1`.
5. Gerar log `INFO` conforme `CP 14.1`.

### CP 4.1 - Adicionar aposta ao carrinho

1. Definir `executed_operation` como `"Adiciona a aposta ao carrinho"`.
2. Clicar em `MODALIDADE_BOTAO_COLOCAR_NO_CARRINHO`.
3. Executar `CP 5.1`.
4. Gerar log `INFO` conforme `CP 14.1`.

### CP 5.1 - Confirmar compra

1. Definir `executed_operation` como `"Confirma a compra"`.
2. Clicar em `MODALIDADE_BOTAO_IR_PARA_PAGAMENTO`.
3. Clicar em `MODALIDADE_BOTAO_CONFIRMA_PAGAMENTO`.
4. Aguardar redirecionamento para `CP 6.1`.
5. Gerar log `INFO` conforme `CP 14.1`.

**CA 5.1.1 - Tela de pagamento não carregada**

Se a tela de pagamento não for carregada, executar `EX 10.2`.

### CP 6.1 - Selecionar PIX ou cartão

1. Definir `executed_operation` como `"Seleciona PIX ou cartão"`.
2. Aguardar carregamento de `URL_SELECIONA_PIX_OU_CARTAO`.
3. Clicar em `SELECIONA_PIX_OU_CARTAO_SELECIONAR_CARTAO`.
4. Executar `CP 7.1`.
5. Gerar log `INFO` conforme `CP 14.1`.

### CP 7.1 - Confirmar pagamento

1. Definir `executed_operation` como `"Confirma o pagamento"`.
2. Validar que `CONFIRMA_PAGAMENTO=true`.
3. Clicar em `SELECIONA_PIX_OU_CARTAO_BOTAO_CONTINUAR`.
4. Preencher `CODIGO_DE_SEGURANCA_DO_CARTAO_DE_CREDITO` em `SELECIONA_PIX_OU_CARTAO_CAMPO_CODIGO_DE_SEGURANCA`.
5. Clicar em `SELECIONA_PIX_OU_CARTAO_BOTAO_CONFIRMAR`.
6. Aguardar redirecionamento para `CP 8.1`.
7. Gerar log `INFO` conforme `CP 14.1`.

**CA 7.1.1 - Confirmação de pagamento desabilitada**

Se `CONFIRMA_PAGAMENTO` for diferente de `true`, executar `EX 10.2`.

**CA 7.1.2 - Tela de finalização não carregada**

Se a tela de finalização não for carregada, executar `EX 10.2`.

### CP 8.1 - Finalizar aposta

1. Definir `executed_operation` como `"Finaliza a aposta"`.
2. Aguardar carregamento de `URL_FINALIZA_A_APOSTA_PROCESSANDO`.
3. Aguardar carregamento de `url_finaliza_a_aposta_acompanhamento`.
4. Validar presença de `FINALIZA_A_APOSTA_PEDIDO_REALIZADO`.
5. Clicar em `FINALIZA_A_APOSTA_BOTAO_MINHA_CONTA`.
6. Clicar em `FINALIZA_A_APOSTA_BOTAO_SAIR`.
7. Gerar log `INFO` conforme `CP 14.1`.
8. Executar `CP 10.1`.

**CA 8.1.1 - Tela de acompanhamento não carregada**

Se a tela de acompanhamento não for carregada, executar `EX 10.2`.

**CA 8.1.2 - Pedido não realizado**

Se o comprovante não for encontrado, executar `EX 10.2`.

---

## 10. Encerramento, Notificações e Integrações Auxiliares

### CP 10.1 - Fechar sessão

1. Fechar a sessão ativa e o navegador associado.
2. Executar `CP 10.4`.
3. Gerar log `INFO` conforme `CP 14.1`.

**CA 10.1.1 - Erro ao fechar sessão**

Se ocorrer erro ao fechar a sessão, gerar log `ERROR` conforme `CP 14.2`.

### EX 10.2 - Enviar notificação e fechar sessão

1. Gerar log `ERROR` conforme `CP 14.2`.
2. Criar mensagem de notificação.
3. Executar `CP 10.5`.
4. Executar `CP 10.1`.

### CP 10.3 - Iniciar sessão do WhatsApp Web

1. Executar `CP 13.2`.
2. Definir `whatsapp_enabled=true`.
3. Gerar log `INFO` conforme `CP 14.1`.

**CA 10.3.1 - Sessão do WhatsApp Web não inicializada**

Se ocorrer `CA 13.2.1`, gerar log `WARNING` conforme `CP 14.3`.

**CA 10.3.2 - Sessão do WhatsApp Web não está aberta**

Se ocorrer `CA 10.3.1` e `whatsapp_error_code` for diferente de `"SESSAO_ABERTA"`, criar assunto e mensagem de e-mail e executar `CP 10.6`.

### CP 10.4 - Encerrar sessão do WhatsApp Web

1. Executar `CP 13.5`.
2. Definir `whatsapp_enabled=false`.
3. Gerar log `INFO` conforme `CP 14.1`.

**CA 10.4.1 - Sessão do WhatsApp Web não encerrada**

Se ocorrer `CA 13.5.1`, gerar log `WARNING` conforme `CP 14.3`.

**CA 10.4.2 - Sessão do WhatsApp Web não está fechada**

Se ocorrer `CA 10.4.1` e `whatsapp_error_code` for diferente de `"SESSAO_FECHADA"`, criar assunto e mensagem de e-mail e executar `CP 10.6`.

### CP 10.5 - Enviar notificação pelo WhatsApp Web

1. Se `whatsapp_enabled=false`, executar `CA 10.5.1`.
2. Executar `CP 13.1`.
3. Se `whatsapp_status` for diferente de `"SESSAO_ABERTA"`, executar `CA 10.5.2`.
4. Definir `whatsapp_message` com a mensagem de notificação.
5. Executar `CP 13.4`.
6. Se `whatsapp_status_message` for diferente de `"enviado"`, executar `CA 10.5.3`.
7. Gerar log `INFO` conforme `CP 14.1`.

**RN 10.5 - Mensagem de WhatsApp**

- A mensagem deve estar em português do Brasil.
- A mensagem pode informar `executed_operation`, quando relevante.
- A mensagem deve ser formatada de forma adequada para WhatsApp.
- Dados sensíveis devem ser mascarados.

**CA 10.5.1 - WhatsApp desabilitado**

Se `whatsapp_enabled=false`, gerar log `WARNING`, criar e-mail de fallback e executar `CP 10.6`.

**CA 10.5.2 - Sessão do WhatsApp não aberta**

Se `whatsapp_status` for diferente de `"SESSAO_ABERTA"`, gerar log `WARNING`, criar e-mail de fallback e executar `CP 10.6`.

**CA 10.5.3 - Mensagem não enviada**

Se `whatsapp_status_message` for diferente de `"enviado"`, gerar log `WARNING`, criar e-mail de fallback e executar `CP 10.6`.

**CA 10.5.4 - Erro ao enviar WhatsApp**

Se ocorrer `CA 13.4.1`, gerar log `WARNING`, criar e-mail de fallback e executar `CP 10.6`.

### CP 10.6 - Enviar e-mail

1. Definir `mail_subject`.
2. Definir `mail_body` em HTML.
3. Executar `CP 12.1`.
4. Gerar log `INFO` conforme `CP 14.1`.

**RN 10.6 - Mensagem de e-mail**

- A mensagem deve estar em português do Brasil.
- A mensagem deve estar em HTML.
- A mensagem deve informar `executed_operation`.
- A mensagem deve informar data, hora e timezone.
- Dados sensíveis devem ser mascarados.

**CA 10.6.1 - Erro ao enviar e-mail**

Se ocorrer `CA 12.1.1`, gerar log `ERROR` conforme `CP 14.2`.

---

## 11. APIs Externas

### CP 11.1 - Gmail Reader: buscar código de validação

```http
GET ${URL_GMAIL_READER}/api/v1/validation-code?waitTimeoutSeconds=${VALIDATION_CODE_WAIT_TIMEOUT_SECONDS}
```

Resposta esperada:

```json
{
  "code": "${valid_code}",
  "message": "string"
}
```

Em caso de sucesso, incluir `code` mascarado e `message` no log `INFO`.

**CA 11.1.1 - Erro ao buscar código de validação**

Resposta de erro esperada:

```json
{
  "error": {
    "code": "string",
    "error": "string",
    "message": "string"
  }
}
```

Em caso de erro, incluir `error.code`, `error.message` e `error.error`, quando existir, no log `ERROR`.

### CP 12.1 - Mail Sender: enviar e-mail

```http
POST ${URL_MAIL_SENDER}/api/v1/mail/send
Content-Type: application/json
```

Payload:

```json
{
  "to": "${MAIL_TO}",
  "subject": "${mail_subject}",
  "body": "${mail_body}",
  "message_type": "${MAIL_TYPE}"
}
```

Resposta esperada:

```json
{
  "message": "string"
}
```

**CA 12.1.1 - Erro ao enviar e-mail**

Resposta de erro esperada:

```json
{
  "error": {
    "code": "string",
    "message": "string"
  }
}
```

### CP 13.1 - WhatsApp Notify: consultar status da sessão

```http
GET ${URL_WHATSAPP_NOTIFY}/whatsapp/session/status
```

Resposta esperada:

```json
{
  "status": "${whatsapp_status}",
  "message": "string",
  "isOpen": true
}
```

Status possíveis:

- `INICIANDO_SESSAO`
- `AGUARDANDO_AUTENTICACAO`
- `CARREGANDO_CONVERSAS`
- `SESSAO_ABERTA`
- `SESSAO_FECHADA`

### CP 13.2 - WhatsApp Notify: iniciar sessão

```http
GET ${URL_WHATSAPP_NOTIFY}/whatsapp/session/start?headless=${WHATSAPP_HEADLESS}&timeoutInSeconds=${WHATSAPP_TIMEOUT_SECONDS}
```

Resposta esperada:

```json
{
  "status": "string",
  "message": "string"
}
```

### CP 13.3 - WhatsApp Notify: capturar QR Code

```http
GET ${URL_WHATSAPP_NOTIFY}/whatsapp/session/qrcode
Accept: image/png
```

Resposta esperada:

```text
Content-Type: image/png
Status: 200
```

### CP 13.4 - WhatsApp Notify: enviar mensagem

```http
POST ${URL_WHATSAPP_NOTIFY}/whatsapp/messages/send
Content-Type: application/json
```

Payload:

```json
{
  "contact": "${WHATSAPP_CONTACT}",
  "message": "${whatsapp_message}"
}
```

Resposta esperada:

```json
{
  "status": "${whatsapp_status_message}",
  "message": "string",
  "contact": "string",
  "elapsedTimeInSeconds": 1.0
}
```

### CP 13.5 - WhatsApp Notify: encerrar sessão

```http
GET ${URL_WHATSAPP_NOTIFY}/whatsapp/session/stop
```

Resposta esperada:

```json
{
  "status": "string",
  "message": "string"
}
```

Para todas as APIs do WhatsApp, erros devem seguir o formato:

```json
{
  "error": {
    "code": "${whatsapp_error_code}",
    "message": "string"
  }
}
```

---

## 12. Logs da Aplicação

### CP 14.1 - Log INFO

O nível do log deve ser `INFO`.

### CP 14.2 - Log ERROR

O nível do log deve ser `ERROR`.

### CP 14.3 - Log WARNING

O nível do log deve ser `WARNING`.

### CP 14.4 - Log DEBUG

O nível do log deve ser `DEBUG`.

### RN 14 - Estrutura obrigatória dos logs

Cada mensagem de log deve conter:

- Nível do log.
- Timestamp em ISO 8601 com timezone.
- Path ou URL da página do Loterias Online relacionada ao evento, quando aplicável.
- Classe e função responsáveis pelo evento.
- Thread e processo.
- Nome da operação em `executed_operation`.
- Dados de diagnóstico relevantes.

Dados sensíveis como CPF, senha, CVV, token, código de validação e dados de cartão devem ser mascarados.

---

## 13. Regras de Negócio

- Apenas usuários autenticados podem apostar.
- O usuário deve ser maior de idade.
- A aposta só é registrada após confirmação do pagamento.
- Cada modalidade possui quantidade mínima e máxima de números.
- O valor da aposta depende da modalidade e da quantidade de números escolhidos.
- A confirmação de pagamento só pode ocorrer quando `CONFIRMA_PAGAMENTO=true`.
- A aplicação deve encerrar a sessão e notificar o usuário em qualquer falha operacional relevante.
- O fluxo deve ser idempotente nos endpoints de controle sempre que possível.

---

## 14. Requisitos Não Funcionais

- Nome da aplicação: **LotoBot**.
- Linguagem: Python 3.12.
- Framework HTTP: FastAPI.
- Automação web: Playwright.
- Navegador: Chromium com perfil persistente.
- Arquitetura: Clean Architecture.
- Swagger UI, ReDoc e OpenAPI JSON devem estar habilitados.
- O arquivo `pyproject.toml` deve ficar na raiz do projeto.
- As pastas `src` e `tests` devem ficar na raiz do projeto.
- Todo o código da aplicação deve ficar em `src`.
- Todos os testes devem ficar em `tests`.
- O arquivo `src/main.py` deve inicializar a aplicação.
- As camadas da Clean Architecture devem ser criadas dentro de `src`.
- Criar `ARCHITECTURE.md` na raiz do projeto com a documentação arquitetural.
- Criar `DEVELOPMENT.md` na raiz do projeto com o guia de desenvolvimento.
- Criar ou atualizar `README.md` na raiz do projeto com visão geral, instalação, execução, testes e variáveis de ambiente.
- A cobertura de testes deve ser 100%.
- Durante os testes, a aplicação nunca deve acessar `URL_LOTERIAS_ONLINE`.
- Erros devem ser tratados com exceções específicas e respostas HTTP padronizadas.
- Integrações externas devem ser encapsuladas por gateways ou clients de infraestrutura.
- O domínio não deve depender de FastAPI, Playwright, requests/httpx ou frameworks externos.

---

## 15. Estrutura Esperada do Projeto

Crie uma estrutura compatível com Clean Architecture. Sugestão:

```text
.
├── pyproject.toml
├── .env
├── .env.example
├── README.md
├── ARCHITECTURE.md
├── DEVELOPMENT.md
├── src
│   ├── main.py
│   ├── api
│   │   ├── routes
│   │   ├── schemas
│   │   └── dependencies.py
│   ├── application
│   │   ├── use_cases
│   │   ├── dto
│   │   └── ports
│   ├── domain
│   │   ├── entities
│   │   ├── value_objects
│   │   ├── exceptions
│   │   └── services
│   ├── infrastructure
│   │   ├── browser
│   │   ├── clients
│   │   ├── config
│   │   ├── logging
│   │   └── selectors
│   └── shared
└── tests
    ├── unit
    ├── integration
    └── e2e
```

Adapte os nomes e módulos conforme necessário, desde que a separação de responsabilidades permaneça clara.

---

## 16. Endpoints Esperados

Implemente endpoints mínimos para controle da automação:

- `GET /health`: verificar disponibilidade da API.
- `GET /api/v1/bets/run`: iniciar o fluxo completo de aposta.
- `GET /api/v1/sessions/start`: iniciar sessão de navegador.
- `GET /api/v1/sessions/stop`: encerrar sessão de navegador.
- `GET /api/v1/sessions/status`: consultar estado da sessão.

Os schemas de entrada e saída devem ser tipados com Pydantic.

---

## 17. Critérios de Aceite

A entrega será considerada concluída quando:

- A aplicação FastAPI iniciar corretamente por `src/main.py`.
- A documentação automática do FastAPI estiver disponível.
- O projeto seguir a estrutura de Clean Architecture.
- O fluxo principal do caso de uso estiver implementado por use cases claros.
- Playwright estiver encapsulado na infraestrutura.
- Seletores, URLs e configurações estiverem centralizados.
- `.env.example` estiver completo e sem valores sensíveis reais.
- Logs estiverem estruturados e em português do Brasil.
- Notificações por WhatsApp e e-mail estiverem encapsuladas por clients testáveis.
- Testes cobrirem o domínio, use cases, API e infraestrutura mockada.
- A cobertura de testes for 100%.
- Nenhum teste acessar `URL_LOTERIAS_ONLINE`.
- `README.md`, `ARCHITECTURE.md` e `DEVELOPMENT.md` forem criados ou atualizados.

---

## 18. Diretrizes de Implementação

- Leia o código existente antes de alterar a estrutura.
- Faça mudanças incrementais, mantendo o projeto executável.
- Não grave credenciais reais no repositório.
- Prefira `httpx` para clients HTTP.
- Prefira `pydantic-settings` para configuração.
- Use `pytest`, `pytest-cov` e mocks/fakes para testes.
- Use Playwright apenas na camada de infraestrutura.
- A lógica de negócio deve ser testável sem navegador.
- Não implemente regras de negócio diretamente nos handlers FastAPI.
- Não exponha detalhes sensíveis em respostas HTTP.
- Garanta encerramento de recursos mesmo em caso de exceção.

