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

    bettor_cpf: str = Field(default="<CPF_DO_APOSTADOR>", alias="BETTOR_CPF")
    bettor_password: str = Field(default="<SENHA_DO_APOSTADOR>", alias="BETTOR_PASSWORD")
    online_lottery_url: str = Field(default="https://www.loteriasonline.caixa.gov.br", alias="ONLINE_LOTTERY_URL")
    terms_of_use_path: str = Field(default="/silce-web/#/termos-de-uso", alias="TERMS_OF_USE_PATH")
    home_path: str = Field(default="/silce-web/#/home", alias="HOME_PATH")
    client_id: str = Field(default="cli-web-lce", alias="CLIENT_ID")
    login_url: str = Field(default="https://login.caixa.gov.br", alias="LOGIN_URL")
    execution_id: str = Field(default="<EXECUTION_ID_DA_SESSAO>", alias="EXECUTION_ID")

    gmail_reader_url: str = Field(default="http://localhost:8001", alias="GMAIL_READER_URL")
    mail_sender_url: str = Field(default="http://localhost:8002", alias="MAIL_SENDER_URL")
    whatsapp_notify_url: str = Field(default="http://localhost:8003", alias="WHATSAPP_NOTIFY_URL")

    validation_code_wait_timeout_seconds: int = Field(default=30, alias="VALIDATION_CODE_WAIT_TIMEOUT_SECONDS")
    whatsapp_headless: bool = Field(default=True, alias="WHATSAPP_HEADLESS")
    whatsapp_enabled: bool = Field(default=False, alias="WHATSAPP_ENABLED")
    whatsapp_timeout_seconds: int = Field(default=10, alias="WHATSAPP_TIMEOUT_SECONDS")
    whatsapp_contact: str = Field(default="Notificação via App", alias="WHATSAPP_CONTACT")
    mail_to: str = Field(default="<EMAIL_DESTINATARIO>", alias="MAIL_TO")
    mail_content_type: str = Field(default="HTML", alias="MAIL_CONTENT_TYPE")

    selected_lottery_modality: str = Field(default="mega-sena", alias="SELECTED_LOTTERY_MODALITY")
    bet_number_selection_path: str = Field(default="/silce-web/#/{lottery_modality}", alias="BET_NUMBER_SELECTION_PATH")
    payment_method_selection_path: str = Field(default="/silce-web/#/carrinho/pagamento#container-meio-pagamento", alias="PAYMENT_METHOD_SELECTION_PATH")
    credit_card_last_digits: str = Field(default="<ULTIMOS_4_DIGITOS_DO_CARTAO>", alias="CREDIT_CARD_LAST_DIGITS")
    credit_card_security_code: str = Field(default="<CVV>", alias="CREDIT_CARD_SECURITY_CODE")
    confirm_payment: bool = Field(default=False, alias="CONFIRM_PAYMENT")
    bet_processing_path: str = Field(default="/silce-web/#/carrinho/processamento", alias="BET_PROCESSING_PATH")

    browser_profile_dir: Path = Field(default=Path(".lotobot-profile"), alias="BROWSER_PROFILE_DIR")
    browser_headless: bool = Field(default=True, alias="BROWSER_HEADLESS")
    browser_timeout_seconds: int = Field(default=5, alias="BROWSER_TIMEOUT_SECONDS")

    @field_validator("whatsapp_headless", "whatsapp_enabled", "confirm_payment", "browser_headless", mode="before")
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

    def authentication_url(self, tab_id: str, execution_id: str | None = None) -> str:
        execution = execution_id or self.execution_id
        return (
            f"{self.login_url}/auth/realms/internet/login-actions/authenticate"
            f"?execution={execution}&client_id={self.client_id}&tab_id={tab_id}"
        )

    def cpf_url(self, state: str, nonce: str) -> str:
        return (
            f"{self.login_url}/auth/realms/internet/protocol/openid-connect/auth"
            f"?response_type=code&client_id={self.client_id}&redirect_uri={self.home_url}"
            f"&state={state}&nonce={nonce}"
        )

    @property
    def terms_of_use_url(self) -> str:
        return f"{self.online_lottery_url}{self.terms_of_use_path}"

    @property
    def home_url(self) -> str:
        return f"{self.online_lottery_url}{self.home_path}"

    @property
    def bet_number_selection_url(self) -> str:
        return f"{self.online_lottery_url}{self.bet_number_selection_path.format(lottery_modality=self.selected_lottery_modality)}"
    
    @property
    def payment_method_selection_url(self) -> str:
        return f"{self.online_lottery_url}{self.payment_method_selection_path}"
    
    @property
    def bet_processing_url(self) -> str:
        return f"{self.online_lottery_url}{self.bet_processing_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
