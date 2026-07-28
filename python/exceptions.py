"""
Custom exception hierarchy for WikiFeetSDK.
"""

from typing import Optional, Any


class WikiFeetError(Exception):
    """Base exception for all WikiFeetSDK errors."""
    pass


class AuthenticationError(WikiFeetError, PermissionError):
    """Raised when an action requiring a logged-in User is called in Guest mode or auth fails."""
    pass


class APIError(WikiFeetError):
    """Raised when a WikiFeet API request fails (HTTP error, API error message, or network timeout)."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Any] = None
    ) -> None:
        super().__init__(message)
        self.message: str = message
        self.status_code: Optional[int] = status_code
        self.response_data: Optional[Any] = response_data

    def __repr__(self) -> str:
        return f"<APIError status_code={self.status_code} message='{self.message}'>"


class ReportError(APIError):
    """Raised specifically when a photo, hand photo, or comment report action fails."""
    pass
