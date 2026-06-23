from infrastructure.logging.logging_config import configure_logging
from infrastructure.logging.playwright_error_message_builder import PlaywrightErrorMessageBuilder

playwright_error_message = PlaywrightErrorMessageBuilder.build_error_message

__all__ = ["configure_logging", "playwright_error_message"]
