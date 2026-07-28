"""
WikiFeetSDK Python Package.
"""

from .client import WikiFeetClient
from .models import (
    Gallery,
    Photo,
    HandPhoto,
    Comment,
    PhotoTags,
    TagState,
    RatingBreakdown,
    Guild,
    GuildMessage,
    PrivateMessage,
    MessageThread,
    Inbox,
)
from .exceptions import (
    WikiFeetError,
    AuthenticationError,
    APIError,
    ReportError,
)

__version__ = "0.1.0"

__all__ = [
    "WikiFeetClient",
    "Gallery",
    "Photo",
    "HandPhoto",
    "Comment",
    "PhotoTags",
    "TagState",
    "RatingBreakdown",
    "Guild",
    "GuildMessage",
    "PrivateMessage",
    "MessageThread",
    "Inbox",
    "WikiFeetError",
    "AuthenticationError",
    "APIError",
    "ReportError",
]
