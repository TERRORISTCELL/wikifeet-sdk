"""
Object-Oriented models for WikiFeetSDK representing tdata structures.
"""

import json
import re
from typing import Dict, List, Optional, Any, Union


def parse_extended_details(data_or_text: Any) -> Dict[str, Optional[str]]:
    """Helper to parse uploader, upload date, and reporter from POST /api/extended response."""
    text = json.dumps(data_or_text) if not isinstance(data_or_text, str) else data_or_text

    uploaded_by = None
    upload_date = None
    reported_by = None

    up_match = re.search(r'(?:Added|Uploaded) by["\'\s]*\],\s*\[["\'\s]*span["\'\s]*,\s*"([^"]+)"', text, re.I)
    if not up_match:
        up_match = re.search(r'(?:Added|Uploaded) by:?\s*([a-zA-Z0-9_\-]+)', text, re.I)
    if up_match:
        uploaded_by = up_match.group(1).strip()

    dt_match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', text)
    if dt_match:
        upload_date = dt_match.group(1).strip()

    rep_match = re.search(r'Reported by["\'\s]*\],\s*\[["\'\s]*span["\'\s]*,\s*"([^"]+)"', text, re.I)
    if not rep_match:
        rep_match = re.search(r'Reported by:?\s*([a-zA-Z0-9_\-]+)', text, re.I)
    if rep_match:
        reported_by = rep_match.group(1).strip()

    return {
        "uploaded_by": uploaded_by,
        "upload_date": upload_date,
        "reported_by": reported_by
    }


TAG_MAPPING: Dict[str, str] = {
    "C": "close_up",
    "N": "nylons",
    "S": "soles",
    "B": "barefoot",
    "T": "toes",
    "A": "arches",
}

TAG_NAME_TO_CODE: Dict[str, str] = {
    "c": "C", "close_up": "C", "close-up": "C", "closeup": "C", "close": "C",
    "n": "N", "nylons": "N", "nylon": "N",
    "s": "S", "soles": "S", "sole": "S",
    "b": "B", "barefoot": "B",
    "t": "T", "toes": "T", "toe": "T",
    "a": "A", "arches": "A", "arch": "A"
}


def normalize_tag(tag: str) -> str:
    """Normalizes a tag name or code to uppercase single character WikiFeet tag code."""
    cleaned = str(tag).strip().lower()
    if cleaned in TAG_NAME_TO_CODE:
        return TAG_NAME_TO_CODE[cleaned]
    upper = str(tag).strip().upper()
    if upper in TAG_MAPPING:
        return upper
    raise ValueError(f"Unknown tag '{tag}'. Valid tag names: {list(TAG_MAPPING.values())} (or codes {list(TAG_MAPPING.keys())})")


class TagState:
    """Represents a single tag state on a photo with chainable callable syntax."""

    def __init__(self, manager: "PhotoTags", code: str, name: str) -> None:
        self._manager: "PhotoTags" = manager
        self._code: str = code
        self._name: str = name

    def __call__(self, value: bool = True) -> "PhotoTags":
        """Queues a tag modification and returns the manager for chaining."""
        self._manager._set_pending(self._code, bool(value))
        return self._manager

    def __bool__(self) -> bool:
        """Evaluates to True if tag is active (including any uncommitted changes)."""
        return self._manager._is_active(self._code)

    def __eq__(self, other: Any) -> bool:
        return bool(self) == bool(other)

    def __repr__(self) -> str:
        return f"{bool(self)}"


class PhotoTags:
    """
    Fluent tag manager for Photo objects.
    """

    def __init__(self, photo: Any, raw_tags: str = "", client: Any = None) -> None:
        self._photo: Any = photo
        self._client: Any = client
        self.raw_string: str = raw_tags
        self._pending: Dict[str, bool] = {}

    def _is_active(self, code: str) -> bool:
        if code in self._pending:
            return self._pending[code]
        return code in self.raw_string

    def _set_pending(self, code: str, value: bool) -> None:
        self._pending[code] = value

    @property
    def close_up(self) -> TagState:
        return TagState(self, "C", "close_up")

    @property
    def nylons(self) -> TagState:
        return TagState(self, "N", "nylons")

    @property
    def soles(self) -> TagState:
        return TagState(self, "S", "soles")

    @property
    def barefoot(self) -> TagState:
        return TagState(self, "B", "barefoot")

    @property
    def toes(self) -> TagState:
        return TagState(self, "T", "toes")

    @property
    def arches(self) -> TagState:
        return TagState(self, "A", "arches")

    @property
    def raw(self) -> str:
        """Returns active raw tag string code (e.g. 'BTA')."""
        active_codes = [code for code in "CNSTBA" if self._is_active(code)]
        return "".join(active_codes)

    def list(self) -> List[str]:
        """Returns list of active human-readable tag names."""
        return [TAG_MAPPING[code] for code in "CNSBTA" if self._is_active(code) and code in TAG_MAPPING]

    def has(self, tag: str) -> bool:
        """Checks if a tag is active by name or code."""
        code = normalize_tag(tag)
        return self._is_active(code)

    def commit(self, client: Any = None) -> Dict[str, Any]:
        """Commits all queued tag modifications to WikiFeet."""
        active_client = client or self._client or getattr(self._photo, "_client", None)
        if not active_client:
            raise ValueError("An authenticated client session is required to commit tag changes.")

        if not self._pending:
            return {"pid": self._photo.pid, "tags": self.raw_string, "updated": 0}

        results = {}
        for code, value in list(self._pending.items()):
            val_int = 1 if value else 0
            res = active_client.tag_photo(self._photo, tag=code, value=val_int)
            results[code] = res

        self._pending.clear()
        return {"pid": self._photo.pid, "tags": self.raw_string, "updated": len(results)}

    def __contains__(self, item: str) -> bool:
        return self.has(item)

    def __repr__(self) -> str:
        pending_str = f" pending={self._pending}" if self._pending else ""
        return f"<PhotoTags active={self.list()}{pending_str}>"


class Photo:
    """Represents an individual photo in a celebrity gallery."""

    def __init__(self, data: Dict[str, Any], client: Any = None) -> None:
        self._data: Dict[str, Any] = data
        self._client: Any = client
        self._extended_details: Optional[Dict[str, Optional[str]]] = None

        self.pid: int = int(data.get("pid", 0))
        self.width: int = int(data.get("pw", 0))
        self.height: int = int(data.get("ph", 0))
        self.gid: int = int(data.get("gid", 0))
        self.best: int = int(data.get("best", 0))
        
        raw_tags_str = str(data.get("tags", ""))
        self.tags: PhotoTags = PhotoTags(self, raw_tags=raw_tags_str, client=client)

        self.reported: str = str(data.get("reported", "0"))
        self.removed: int = int(data.get("removed", 0))
        self.similarity: Optional[int] = data.get("similarity")

    @property
    def image_url(self) -> str:
        """Constructs the standard image URL for this photo PID."""
        return f"https://pics.wikifeet.com/{self.pid}.jpg"

    @property
    def is_liked(self) -> bool:
        """Returns True if this photo is marked as liked."""
        return self.best > 0

    def like(self, client: Any = None) -> Dict[str, Any]:
        """Likes this photo via POST /api/topphoto using the client session."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to like a photo.")
        return active_client.like_photo(self)

    def unlike(self, client: Any = None) -> Dict[str, Any]:
        """Retracts like from this photo via POST /api/topphoto using the client session."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to retract a photo like.")
        return active_client.unlike_photo(self)

    def report(
        self,
        client: Any = None,
        report_type: str = "NO_FEET",
        target_pid: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Submits a photo report via POST /api/reportphoto."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to report a photo.")
        return active_client.report_photo(self, report_type=report_type, target_pid=target_pid)

    def unreport(self, client: Any = None) -> Dict[str, Any]:
        """Retracts/unreports this photo via POST /api/reportphoto."""
        return self.report(client=client, report_type="UNREPORT")

    def report_no_feet(self, client: Any = None) -> Dict[str, Any]:
        """Reports photo as 'NO_FEET' ('N')."""
        return self.report(client=client, report_type="NO_FEET")

    def report_duplicate(self, target_pid: Any, client: Any = None) -> Dict[str, Any]:
        """Reports photo as 'DUPLICATE' ('D') pointing to target duplicate PID."""
        return self.report(client=client, report_type="DUPLICATE", target_pid=target_pid)

    def report_wrong_person(self, client: Any = None) -> Dict[str, Any]:
        """Reports photo as 'WRONG_PERSON' ('W')."""
        return self.report(client=client, report_type="WRONG_PERSON")

    def report_low_quality(self, client: Any = None) -> Dict[str, Any]:
        """Reports photo as 'LOW_QUALITY' ('P')."""
        return self.report(client=client, report_type="LOW_QUALITY")

    def report_fake(self, client: Any = None) -> Dict[str, Any]:
        """Reports photo as 'FAKE' ('F')."""
        return self.report(client=client, report_type="FAKE")

    def report_underage(self, client: Any = None) -> Dict[str, Any]:
        """Reports photo as 'UNDERAGE' ('U')."""
        return self.report(client=client, report_type="UNDERAGE")

    def report_adult_content(self, client: Any = None) -> Dict[str, Any]:
        """Reports photo as 'ADULT_CONTENT' ('A')."""
        return self.report(client=client, report_type="ADULT_CONTENT")

    def scan_duplicates(self, client: Any = None) -> List[Dict[str, Any]]:
        """Scans for duplicate photos across WikiFeet database via POST /api/similars."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("A client session is required to scan for duplicate photos.")
        return active_client.find_duplicate_photos(self)

    def fetch_details(self, client: Any = None) -> Dict[str, Optional[str]]:
        """
        Fetches extended uploader, upload date, and reporter details via POST /api/extended.
        Results are cached on this Photo instance.
        """
        if self._extended_details is not None:
            return self._extended_details

        active_client = client or self._client
        if not active_client:
            return {"uploaded_by": None, "upload_date": None, "reported_by": None}

        details = active_client.fetch_extended_details(self.pid)
        self._extended_details = details
        return details

    @property
    def uploaded_by(self) -> Optional[str]:
        """Uploader username (automatically loaded on access)."""
        return self.fetch_details().get("uploaded_by")

    @property
    def upload_date(self) -> Optional[str]:
        """Upload date (automatically loaded on access)."""
        return self.fetch_details().get("upload_date")

    @property
    def reported_by(self) -> Optional[str]:
        """Reporter username if reported (automatically loaded on access)."""
        return self.fetch_details().get("reported_by")

    def __repr__(self) -> str:
        return f"<Photo PID={self.pid} size={self.width}x{self.height} best={self.best}>"


class HandPhoto:
    """Represents a hand photo in a celebrity's hands gallery."""

    def __init__(self, data: Dict[str, Any], client: Any = None) -> None:
        self._data: Dict[str, Any] = data
        self._client: Any = client
        self._extended_details: Optional[Dict[str, Optional[str]]] = None

        self.pid: int = int(data.get("pid", 0))
        self.width: int = int(data.get("pw", 0))
        self.height: int = int(data.get("ph", 0))
        self.gid: int = int(data.get("gid", 0))
        self.best: int = int(data.get("best", 0))
        
        raw_tags_str = str(data.get("tags", ""))
        self.tags: PhotoTags = PhotoTags(self, raw_tags=raw_tags_str, client=client)

        self.reported: str = str(data.get("reported", "0"))
        self.removed: int = int(data.get("removed", 0))

    @property
    def image_url(self) -> str:
        """Constructs the standard image URL for this hand photo PID."""
        return f"https://pics.wikifeet.com/{self.pid}.jpg"

    def fetch_details(self, client: Any = None) -> Dict[str, Optional[str]]:
        """
        Fetches extended uploader, upload date, and reporter details via POST /api/hextended.
        Results are cached on this HandPhoto instance.
        """
        if self._extended_details is not None:
            return self._extended_details

        active_client = client or self._client
        if not active_client:
            return {"uploaded_by": None, "upload_date": None, "reported_by": None}

        details = active_client.fetch_hand_extended_details(self.pid)
        self._extended_details = details
        return details

    @property
    def uploaded_by(self) -> Optional[str]:
        """Uploader username (automatically loaded on access)."""
        return self.fetch_details().get("uploaded_by")

    @property
    def upload_date(self) -> Optional[str]:
        """Upload date (automatically loaded on access)."""
        return self.fetch_details().get("upload_date")

    @property
    def reported_by(self) -> Optional[str]:
        """Reporter username if reported (automatically loaded on access)."""
        return self.fetch_details().get("reported_by")

    def report(self, client: Any = None, reason: str = "") -> Dict[str, Any]:
        """Submits a report for this hand photo via POST /api/reporthand."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to report a hand photo.")
        return active_client.report_hand_photo(self, reason=reason)

    def __repr__(self) -> str:
        return f"<HandPhoto PID={self.pid} size={self.width}x{self.height}>"


class Comment:
    """Represents a single comment thread and nested replies."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data: Dict[str, Any] = data
        self.idx: int = int(data.get("idx", 0))
        self.midx: int = int(data.get("midx", 0))
        self.text: str = str(data.get("comment", ""))
        self.author: str = str(data.get("nickname", "N/A"))
        self.user_title: str = str(data.get("title", ""))
        self.user_id: int = int(data.get("uid", 0))
        self.status: int = int(data.get("status", 0))
        self.likes: int = int(data.get("likes", 0))
        self.like_count: int = self.likes
        
        # User vote state: 1 (Upvoted/Liked), -1 (Downvoted/Disliked), None (No vote)
        raw_vote = data.get("likepart")
        self.user_vote: Optional[int] = int(raw_vote) if raw_vote is not None else None
        self.timestamp: str = str(data.get("timestamp", ""))

        # Target photo PID if attached to a specific photo
        val = data.get("value")
        self.photo_pid: Optional[int] = int(val) if val is not None and str(val).isdigit() else None

        # Nested replies
        raw_replies = data.get("replies", [])
        self.replies: List["Comment"] = [
            Comment(r) for r in raw_replies if isinstance(r, dict)
        ]

    @property
    def is_approved(self) -> bool:
        return self.status == 1

    @property
    def is_pending(self) -> bool:
        return self.status == 0

    @property
    def is_liked_by_user(self) -> bool:
        """Returns True if current user has upvoted/liked this comment."""
        return self.user_vote == 1

    @property
    def is_disliked_by_user(self) -> bool:
        """Returns True if current user has downvoted/disliked this comment."""
        return self.user_vote == -1

    def like(self, client: Any) -> Dict[str, Any]:
        """Likes / upvotes this comment using the client session."""
        return client.like_comment(self)

    def dislike(self, client: Any) -> Dict[str, Any]:
        """Dislikes / downvotes this comment using the client session."""
        return client.dislike_comment(self)

    def retract_vote(self, client: Any) -> Dict[str, Any]:
        """Retracts vote from this comment using the client session."""
        return client.retract_comment_vote(self)

    def report(self, reason: str = "", client: Any = None) -> Dict[str, Any]:
        """Reports this comment via POST /api/reportcomment."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to report a comment.")
        return active_client.report_comment(self, reason=reason)

    def flag(self, client: Any = None) -> Dict[str, Any]:
        """Flags this comment via POST /api/wflag."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to flag a comment.")
        return active_client.flag_comment(self)

    def __repr__(self) -> str:
        snippet = self.text[:30] + "..." if len(self.text) > 30 else self.text
        return f"<Comment ID={self.idx} author='{self.author}' likes={self.like_count} text='{snippet}'>"


class RatingBreakdown:
    """Represents the rating score and detailed star vote counts."""

    def __init__(self, score: float, edata: Optional[Dict[str, Any]] = None) -> None:
        self.score: float = float(score)
        self.stats: Dict[str, int] = {}
        
        if edata and isinstance(edata, dict) and "stats" in edata:
            raw_stats = edata.get("stats", {})
            if isinstance(raw_stats, dict):
                self.stats = {str(k): int(v) for k, v in raw_stats.items()}

    @property
    def one_star(self) -> int:
        return self.stats.get("1", 0)

    @property
    def two_star(self) -> int:
        return self.stats.get("2", 0)

    @property
    def three_star(self) -> int:
        return self.stats.get("3", 0)

    @property
    def four_star(self) -> int:
        return self.stats.get("4", 0)

    @property
    def five_star(self) -> int:
        return self.stats.get("5", 0)

    @property
    def total_votes(self) -> int:
        """Returns total sum of all votes cast across 1 to 5 stars."""
        return sum(self.stats.values())

    def __repr__(self) -> str:
        return (
            f"<RatingBreakdown score={self.score} total_votes={self.total_votes} "
            f"stars=[1:{self.one_star}, 2:{self.two_star}, 3:{self.three_star}, 4:{self.four_star}, 5:{self.five_star}]>"
        )


class Gallery:
    """
    Object-oriented wrapper around WikiFeet celebrity `tdata`.
    """

    def __init__(self, tdata: Dict[str, Any], client: Any = None) -> None:
        self._tdata: Dict[str, Any] = tdata
        self._client: Any = client
        self._hands_cache: Optional[List[HandPhoto]] = None

        self.cname: str = tdata.get("cname", "")
        self.cid: int = int(tdata.get("cid", 0))
        self.gender: int = int(tdata.get("gender", 0))
        self.birth_place: Optional[str] = tdata.get("bplace")
        self.birth_date: Optional[str] = tdata.get("bdate")
        self.height_us: Optional[str] = tdata.get("height_us")
        self.shoe_size: Optional[Any] = tdata.get("ssize")
        self.score: float = float(tdata.get("score", 0.0))

        # Rating stats & vote calculation
        self.rating_breakdown: RatingBreakdown = RatingBreakdown(
            score=self.score, edata=tdata.get("edata")
        )

        # Photos list
        raw_gallery = tdata.get("gallery", [])
        self.photos: List[Photo] = [
            Photo(item, client=client) for item in raw_gallery if isinstance(item, dict)
        ]

        # Comments parsing
        raw_comments_obj = tdata.get("comments", {})
        if isinstance(raw_comments_obj, dict):
            raw_threads = raw_comments_obj.get("threads", [])
            self.has_more_comments: bool = bool(raw_comments_obj.get("more", 0))
        elif isinstance(raw_comments_obj, list):
            raw_threads = raw_comments_obj
            self.has_more_comments = False
        else:
            raw_threads = []
            self.has_more_comments = False

        self.comments: List[Comment] = [
            Comment(t) for t in raw_threads if isinstance(t, dict)
        ]

        # Reports & Theme
        self.reports: Dict[str, Any] = tdata.get("reports", {})
        self.theme: Dict[str, Any] = tdata.get("theme", {})

    @property
    def has_hands(self) -> bool:
        """Returns True if hands gallery is available for this celebrity."""
        return bool(self._tdata.get("hashands", False))

    def get_hands(self, client: Any = None) -> List[HandPhoto]:
        """
        Fetches and returns the list of HandPhoto objects for this celebrity.
        Results are cached on this Gallery instance.
        """
        if self._hands_cache is not None:
            return self._hands_cache

        active_client = client or self._client
        if not active_client:
            raise ValueError("A client session is required to fetch hands gallery.")

        hands_list = active_client.get_hands(self.cid)
        self._hands_cache = hands_list
        return hands_list

    def rate(self, rank: int, client: Any = None) -> Dict[str, Any]:
        """Rates this celebrity with star rank (1 to 5) via POST /api/rateceleb."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to rate a celebrity.")
        return active_client.rate_celebrity(self, rank=rank)

    def favorite(self, client: Any = None) -> Dict[str, Any]:
        """Toggles favorite status on this celebrity via POST /api/fav."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to favorite a celebrity.")
        return active_client.toggle_favorite(self)

    def ignore(self, client: Any = None) -> Dict[str, Any]:
        """Ignores / hides this celebrity via POST /api/ignoreceleb."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to ignore a celebrity.")
        return active_client.ignore_celebrity(self)

    def set_alerts(self, sub_photos: bool = True, sub_threads: bool = True, client: Any = None) -> Dict[str, Any]:
        """Configures notification alert subscriptions for this celebrity via POST /api/alertset."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to set alert subscriptions.")
        return active_client.set_celebrity_alerts(self, sub_photos=sub_photos, sub_threads=sub_threads)

    def post_comment(self, message: str, photo_pid: Optional[Any] = None, client: Any = None) -> Dict[str, Any]:
        """Posts a new comment to this celebrity gallery via POST /api/wsubmit."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to post a comment.")
        return active_client.post_comment(self.cname, message=message, photo_pid=photo_pid)

    def upload_photo(
        self,
        file_path_or_bytes: Union[str, bytes],
        file_name: Optional[str] = None,
        client: Any = None
    ) -> Dict[str, Any]:
        """Uploads a new photo to this celebrity gallery via POST /api/upload."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to upload photos.")
        return active_client.upload_photo(self, file_path_or_bytes=file_path_or_bytes, file_name=file_name)

    def upload_hand_photo(
        self,
        file_path_or_bytes: Union[str, bytes],
        source: str = "social",
        source_info: str = "Social media post source",
        file_name: Optional[str] = None,
        client: Any = None
    ) -> Dict[str, Any]:
        """Uploads a new hand photo to this celebrity's hands gallery via POST /api/handupload."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to upload hand photos.")
        return active_client.upload_hand_photo(self, file_path_or_bytes=file_path_or_bytes, source=source, source_info=source_info, file_name=file_name)

    @property
    def total_votes(self) -> int:
        """Convenience property for total votes."""
        return self.rating_breakdown.total_votes

    @property
    def photo_count(self) -> int:
        """Returns total number of photos in gallery."""
        return len(self.photos)

    def __getitem__(self, item: str) -> Any:
        """Enables dict-like access if needed."""
        if hasattr(self, item):
            return getattr(self, item)
        return self._tdata[item]

    def __repr__(self) -> str:
        return (
            f"<Gallery cname='{self.cname}' cid={self.cid} score={self.score} "
            f"total_votes={self.total_votes} photo_count={self.photo_count} "
            f"has_hands={self.has_hands} comment_count={len(self.comments)}>"
        )


class GuildMessage:
    """Represents a chat message in the WikiFeet Guild chat."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data: Dict[str, Any] = data
        self.idx: int = int(data.get("idx", 0))
        self.user_id: int = int(data.get("uid", 0))
        self.author: str = str(data.get("nickname") or data.get("author", "Anonymous"))
        self.text: str = str(data.get("message") or data.get("comment", ""))
        self.avatar_id: int = int(data.get("avatar", 0))
        self.secago: int = int(data.get("secago", 0))
        self.timestamp: str = str(data.get("timestamp", ""))
        self.user_title: str = str(data.get("title", ""))
        self.badge: Optional[str] = data.get("badge")

    @property
    def avatar_url(self) -> Optional[str]:
        """Returns standard avatar URL or None if user has no avatar set."""
        if self.avatar_id > 0:
            return f"https://wikifeet.com/avatars/{self.avatar_id}.jpg"
        return None

    @property
    def formatted_time(self) -> str:
        """Returns relative human-readable time string (e.g. '5 mins ago')."""
        if self.secago <= 0:
            return self.timestamp or "Just now"
        s = self.secago
        if s < 60:
            return f"{s}s ago"
        elif s < 3600:
            return f"{s // 60}m ago"
        elif s < 86400:
            return f"{s // 3600}h ago"
        else:
            return f"{s // 86400}d ago"

    def __repr__(self) -> str:
        snippet = self.text[:30] + "..." if len(self.text) > 30 else self.text
        return f"<GuildMessage ID={self.idx} author='{self.author}' time='{self.formatted_time}' text='{snippet}'>"


class Guild:
    """Represents the WikiFeet Guild environment and chat hub."""

    def __init__(self, tdata: Dict[str, Any], client: Any = None) -> None:
        self._tdata: Dict[str, Any] = tdata
        self._client: Any = client

        self.is_member: bool = bool(tdata.get("guild", False))
        self.unread_count: int = int(tdata.get("unread", 0))

        raw_messages = tdata.get("chat", [])
        if not isinstance(raw_messages, list):
            raw_messages = []

        self.messages: List[GuildMessage] = [
            GuildMessage(m) for m in raw_messages if isinstance(m, dict)
        ]

    def join(self, client: Any = None) -> Dict[str, Any]:
        """Joins the WikiFeet Guild via POST /api/joinguild."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to join the Guild.")
        res = active_client.join_guild()
        self.is_member = True
        return res

    def leave(self, client: Any = None) -> Dict[str, Any]:
        """Leaves the WikiFeet Guild via POST /api/quitguild."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to leave the Guild.")
        res = active_client.leave_guild()
        self.is_member = False
        return res

    def quit(self, client: Any = None) -> Dict[str, Any]:
        """Alias for leave()."""
        return self.leave(client=client)

    def get_chat(self, last_idx: Optional[int] = None, client: Any = None) -> List[GuildMessage]:
        """
        Polls for new Guild chat messages via POST /api/guildchat.
        Appends newly fetched messages to `self.messages`.

        :param last_idx: Last seen message ID (defaults to last message ID in `self.messages` or 0).
        :return: List of newly received GuildMessage objects.
        """
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to fetch Guild chat.")

        if last_idx is None:
            last_idx = self.messages[-1].idx if self.messages else 0

        new_msgs = active_client.get_guild_chat(last_idx=last_idx)
        if new_msgs:
            self.messages.extend(new_msgs)
        return new_msgs

    def get_photo_backlog(self, client: Any = None) -> List[Dict[str, Any]]:
        """Fetches pending Guild photo reports backlog via POST /api/guildphotos."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to view photo backlog.")
        return active_client.get_guild_photo_backlog()

    def get_comment_backlog(self, client: Any = None) -> List[Dict[str, Any]]:
        """Fetches pending Guild comment reports backlog via POST /api/guildcomments."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to view comment backlog.")
        return active_client.get_guild_comment_backlog()

    def vote_poll(self, poll_id: Union[int, str], choice: Union[int, str], client: Any = None) -> Dict[str, Any]:
        """Votes in a Guild poll via POST /api/guildpollvote."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to vote in a Guild poll.")
        return active_client.vote_guild_poll(poll_id=poll_id, choice=choice)

    def create_poll(self, title: str, options: List[str], client: Any = None) -> Dict[str, Any]:
        """Creates a new Guild poll via POST /api/guildpollmake."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to create a Guild poll.")
        return active_client.create_guild_poll(title=title, options=options)

    def create_announcement(self, title: str, text: str, client: Any = None) -> Dict[str, Any]:
        """Creates a Guild announcement via POST /api/guildannouncementmake."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to create a Guild announcement.")
        return active_client.create_guild_announcement(title=title, text=text)

    def __repr__(self) -> str:
        return f"<Guild is_member={self.is_member} messages_loaded={len(self.messages)}>"


class PrivateMessage:
    """Represents a single private message."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data: Dict[str, Any] = data
        self.idx: int = int(data.get("idx", 0))
        self.sender_uid: int = int(data.get("uid", 0))
        self.author: str = str(data.get("nickname") or data.get("author", "Anonymous"))
        self.text: str = str(data.get("message") or data.get("comment", ""))
        self.timestamp: str = str(data.get("timestamp", ""))

    def __repr__(self) -> str:
        snippet = self.text[:30] + "..." if len(self.text) > 30 else self.text
        return f"<PrivateMessage ID={self.idx} from='{self.author}' text='{snippet}'>"


class MessageThread:
    """Represents a private message conversation thread with a partner user."""

    def __init__(self, data: Dict[str, Any], client: Any = None) -> None:
        self._data: Dict[str, Any] = data
        self._client: Any = client

        self.partner_uid: int = int(data.get("uid", 0))
        self.partner_name: str = str(data.get("nickname", "Anonymous"))
        self.unread_count: int = int(data.get("unread", 0))
        self.last_message: str = str(data.get("message", ""))
        self.last_timestamp: str = str(data.get("timestamp", ""))

        raw_msgs = data.get("messages") or data.get("chat") or []
        if not isinstance(raw_msgs, list):
            raw_msgs = []

        self.messages: List[PrivateMessage] = [
            PrivateMessage(m) for m in raw_msgs if isinstance(m, dict)
        ]

    def send(self, text: str, client: Any = None) -> Dict[str, Any]:
        """Sends a private message reply to this partner user."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to send private messages.")
        return active_client.send_private_message(to_uid=self.partner_uid, text=text)

    def fetch_messages(self, client: Any = None) -> List[PrivateMessage]:
        """Fetches full message history thread for this conversation."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to fetch message thread.")

        thread_obj = active_client.get_message_thread(self.partner_uid)
        self.messages = thread_obj.messages
        return self.messages

    def __repr__(self) -> str:
        return f"<MessageThread partner='{self.partner_name}' (uid={self.partner_uid}) unread={self.unread_count}>"


class Inbox:
    """Represents the User's private message inbox and archived conversations."""

    def __init__(self, tdata: Dict[str, Any], client: Any = None) -> None:
        self._tdata: Dict[str, Any] = tdata
        self._client: Any = client

        raw_inbox = tdata.get("inbox", [])
        if not isinstance(raw_inbox, list):
            raw_inbox = []

        self.threads: List[MessageThread] = [
            MessageThread(item, client=client) for item in raw_inbox if isinstance(item, dict)
        ]

        raw_archived = tdata.get("archived", [])
        if not isinstance(raw_archived, list):
            raw_archived = []

        self.archived: List[MessageThread] = [
            MessageThread(item, client=client) for item in raw_archived if isinstance(item, dict)
        ]

    def send_message(self, to_uid: Union[int, str], text: str, client: Any = None) -> Dict[str, Any]:
        """Sends a private message to a specific user UID."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to send private messages.")
        return active_client.send_private_message(to_uid=to_uid, text=text)

    def archive_all(self, client: Any = None) -> Dict[str, Any]:
        """Archives all inbox message threads via POST /api/archiveall."""
        active_client = client or self._client
        if not active_client:
            raise ValueError("An authenticated client session is required to archive messages.")
        return active_client.archive_all_messages()

    def __repr__(self) -> str:
        return f"<Inbox active_threads={len(self.threads)} archived_threads={len(self.archived)}>"
