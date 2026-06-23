from application.services.session_failure_handler import SessionFailureHandler

handle_failure = SessionFailureHandler.handle_failure
handle_custom_failure = SessionFailureHandler.handle_custom_failure
close_if_open = SessionFailureHandler.close_if_open

__all__ = ["handle_failure", "handle_custom_failure", "close_if_open"]
