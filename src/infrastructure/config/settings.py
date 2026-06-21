"""Configurações carregadas do ambiente."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    cpf: str = Field(default="<CPF_DO_APOSTADOR>", alias="CPF")
    senha: str = Field(default="<SENHA_DO_APOSTADOR>", alias="SENHA")
    url_loterias_online: str = Field(default="https://www.loteriasonline.caixa.gov.br", alias="URL_LOTERIAS_ONLINE")
    url_termo_de_uso: str = Field(default="https://www.loteriasonline.caixa.gov.br/silce-web/#/termos-de-uso", alias="URL_TERMO_DE_USO")
    url_home: str = Field(default="https://www.loteriasonline.caixa.gov.br/silce-web/#/home", alias="URL_HOME")
    client_id: str = Field(default="cli-web-lce", alias="CLIENT_ID")
    url_login_caixa: str = Field(default="https://login.caixa.gov.br", alias="URL_LOGIN_CAIXA")
    execution: str = Field(default="<EXECUTION_ID_DA_SESSAO>", alias="EXECUTION")

    url_gmail_reader: str = Field(default="http://localhost:8001", alias="URL_GMAIL_READER")
    url_mail_sender: str = Field(default="http://localhost:8002", alias="URL_MAIL_SENDER")
    url_whatsapp_notify: str = Field(default="http://localhost:8003", alias="URL_WHATSAPP_NOTIFY")

    validation_code_wait_timeout_seconds: int = Field(default=30, alias="VALIDATION_CODE_WAIT_TIMEOUT_SECONDS")
    whatsapp_headless: bool = Field(default=True, alias="WHATSAPP_HEADLESS")
    whatsapp_enabled: bool = Field(default=False, alias="WHATSAPP_ENABLED")
    whatsapp_timeout_seconds: int = Field(default=10, alias="WHATSAPP_TIMEOUT_SECONDS")
    whatsapp_contact: str = Field(default="Notificação via App", alias="WHATSAPP_CONTACT")
    mail_to: str = Field(default="<EMAIL_DESTINATARIO>", alias="MAIL_TO")
    mail_type: str = Field(default="HTML", alias="MAIL_TYPE")

    modalidade_selecionada: str = Field(default="mega-sena", alias="MODALIDADE_SELECIONADA")
    url_escolhe_numeros_aposta: str = Field(default="https://www.loteriasonline.caixa.gov.br/silce-web/#/mega-sena", alias="URL_ESCOLHE_NUMEROS_APOSTA")
    url_seleciona_pix_ou_cartao: str = Field(default="https://www.loteriasonline.caixa.gov.br/silce-web/#/carrinho/pagamento#container-meio-pagamento", alias="URL_SELECIONA_PIX_OU_CARTAO")
    final_cartao_credito: str = Field(default="<ULTIMOS_4_DIGITOS_DO_CARTAO>", alias="FINAL_CARTAO_CREDITO")
    codigo_de_seguranca_do_cartao_de_credito: str = Field(default="<CVV>", alias="CODIGO_DE_SEGURANCA_DO_CARTAO_DE_CREDITO")
    confirma_pagamento: bool = Field(default=False, alias="CONFIRMA_PAGAMENTO")
    url_finaliza_a_aposta_processando: str = Field(default="https://www.loteriasonline.caixa.gov.br/silce-web/#/carrinho/processamento", alias="URL_FINALIZA_A_APOSTA_PROCESSANDO")

    browser_profile_dir: Path = Field(default=Path(".lotobot-profile"), alias="LOTTOBOT_BROWSER_PROFILE_DIR")
    browser_headless: bool = Field(default=True, alias="LOTTOBOT_BROWSER_HEADLESS")
    browser_timeout_seconds: int = Field(default=5, alias="LOTTOBOT_BROWSER_TIMEOUT_SECONDS")

    @field_validator("whatsapp_headless", "whatsapp_enabled", "confirma_pagamento", "browser_headless", mode="before")
    @classmethod
    def parse_browser_headless(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        normalized = value.strip().lower()
        if not normalized:
            return False
        if normalized in {"1", "true", "yes", "y", "sim", "s"}:
            return True
        if normalized in {"0", "false", "no", "n", "nao", "não"}:
            return False
        raise ValueError("Valor booleano inválido. Use um dos seguintes: 1, 0, true, false, yes, no, y, n, sim, nao.")

    @field_validator("validation_code_wait_timeout_seconds", "whatsapp_timeout_seconds", "browser_timeout_seconds")
    @classmethod
    def validate_browser_timeout_seconds(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("O valor deve ser um inteiro positivo.")
        return value

    @model_validator(mode="after")
    def resolve_browser_profile_dir(self) -> "Settings":
        profile_dir = self.browser_profile_dir
        if not profile_dir.is_absolute():
            base_dir = ENV_FILE.parent if ENV_FILE.exists() else Path.cwd()
            self.browser_profile_dir = (base_dir / profile_dir).resolve()
        return self

    def authentication_url(self, tab_id: str, execution: str | None = None) -> str:
        execution_id = execution or self.execution
        return (
            f"{self.url_login_caixa}/auth/realms/internet/login-actions/authenticate"
            f"?execution={execution_id}&client_id={self.client_id}&tab_id={tab_id}"
        )

    def cpf_url(self, state: str, nonce: str) -> str:
        return (
            f"{self.url_login_caixa}/auth/realms/internet/protocol/openid-connect/auth"
            f"?response_type=code&client_id={self.client_id}&redirect_uri={self.url_home}"
            f"&state={state}&nonce={nonce}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
