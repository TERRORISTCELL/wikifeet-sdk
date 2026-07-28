"""
WikiFeetSDK Client implementation supporting authenticated user sessions and guest sessions.
"""

import json
import re
import requests
from typing import Optional, Dict, Any, List, Union
from .models import Gallery, Comment, Photo, HandPhoto, Guild, GuildMessage, PrivateMessage, MessageThread, Inbox, parse_extended_details, normalize_tag
from .exceptions import AuthenticationError, APIError, ReportError


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def normalize_domain(domain: str) -> str:
    """Strips http/https protocols and trailing paths from a domain string."""
    d = str(domain).strip()
    if "://" in d:
        d = d.split("://")[1]
    return d.split("/")[0] or "wikifeet.com"


class WikiFeetClient:
    """
    Main SDK Client for WikiFeet.
    Binds a fixed domain (e.g. 'wikifeet.com', 'men.wikifeet.com', 'wikifeetx.com') on creation.
    Can operate in authenticated mode (User) or unauthenticated mode (Guest).
    """

    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        domain: str = "wikifeet.com",
        proxy: Optional[str] = None,
        user_agent: str = DEFAULT_USER_AGENT,
        is_guest: bool = False
    ) -> None:
        self.email: Optional[str] = email
        self.password: Optional[str] = password
        self.domain: str = normalize_domain(domain)
        self.user_agent: str = user_agent
        self.is_guest: bool = is_guest or (not email and not password)
        self._logged_in: bool = False
        self._proxy: Optional[str] = None

        self.session: requests.Session = requests.Session()
        self._configure_session()

        if proxy:
            self.set_proxy(proxy)

        if not self.is_guest and self.email and self.password:
            try:
                self.login()
            except Exception:
                pass

    def _configure_session(self) -> None:
        """Sets default browser-like headers on the requests session."""
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Not?A_Brand";v="99", "Chromium";v="130", "Google Chrome";v="130"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        })

    @classmethod
    def as_guest(
        cls,
        domain: str = "wikifeet.com",
        proxy: Optional[str] = None,
        user_agent: str = DEFAULT_USER_AGENT
    ) -> "WikiFeetClient":
        """Factory method to create an unauthenticated Guest client bound to a specific domain."""
        return cls(domain=domain, proxy=proxy, user_agent=user_agent, is_guest=True)

    @classmethod
    def as_user(
        cls,
        email: str,
        password: str,
        domain: str = "wikifeet.com",
        proxy: Optional[str] = None,
        user_agent: str = DEFAULT_USER_AGENT
    ) -> "WikiFeetClient":
        """Factory method to create an authenticated User client bound to a specific domain."""
        client = cls(email=email, password=password, domain=domain, proxy=proxy, user_agent=user_agent, is_guest=False)
        if not client.is_logged_in:
            client.login()
        return client

    @property
    def proxy(self) -> Optional[str]:
        return self._proxy

    @proxy.setter
    def proxy(self, proxy_url: Optional[str]) -> None:
        self.set_proxy(proxy_url)

    def set_proxy(self, proxy_url: Optional[str]) -> None:
        """Sets or removes proxy configuration for this client session."""
        self._proxy = proxy_url
        if proxy_url:
            self.session.proxies = {
                "http": proxy_url,
                "https": proxy_url
            }
        else:
            self.session.proxies = {}

    @property
    def is_logged_in(self) -> bool:
        """Returns True if the client is authenticated as a User."""
        return self._logged_in and not self.is_guest

    def login(self, email: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
        """
        Authenticates session as a registered User via POST /api/signin.

        :param email: User email address (defaults to self.email).
        :param password: User password (defaults to self.password).
        :return: Response JSON containing session details.
        """
        user_email = email or self.email
        user_pass = password or self.password

        if not user_email or not user_pass:
            raise ValueError("Email and password are required to login.")

        url = f"https://{self.domain}/api/signin"
        files = {
            "stype": (None, "0"),
            "email": (None, str(user_email).strip()),
            "password": (None, str(user_pass))
        }

        resp = self.session.post(url, files=files, timeout=15)
        data = self._verify_api_response(resp, action_name="User signin")

        # Check render error pattern or session token payload
        sess_token = None
        if isinstance(data, list):
            for item in data:
                if isinstance(item, list):
                    if len(item) >= 3 and item[0] == "render" and item[1] == "errorlabel":
                        raise AuthenticationError(f"Login failed: {item[2]}")
                    elif len(item) >= 2 and item[0] == "session":
                        sess_token = item[1]
                elif item == "errorlabel" and len(data) >= 3:
                    raise AuthenticationError(f"Login failed: {data[2]}")

        if sess_token:
            self.session.cookies.set("session", sess_token, domain=self.domain)
            if "wikifeet.com" in self.domain:
                self.session.cookies.set("session", sess_token, domain=".wikifeet.com")

        self.email = user_email
        self.password = user_pass
        self.is_guest = False
        self._logged_in = True

        return data

    def __repr__(self) -> str:
        mode = "Guest" if self.is_guest else f"User({self.email})"
        return f"<WikiFeetClient domain='{self.domain}' mode={mode} logged_in={self.is_logged_in}>"

    def gallery(self, celebrity_slug: str) -> Gallery:
        """
        Fetches the celebrity page and returns parsed `tdata` as a Gallery instance.

        :param celebrity_slug: Celebrity slug (e.g. 'Yurina_Hirate') or full URL.
        :return: Gallery object
        """
        if celebrity_slug.startswith("http://") or celebrity_slug.startswith("https://"):
            url = celebrity_slug
        else:
            slug = celebrity_slug.lstrip("/").strip().replace(" ", "_")
            url = f"https://{self.domain}/{slug}"

        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()

        match = re.search(r'tdata\s*=\s*({.*?});', resp.text, re.DOTALL)
        if not match:
            match = re.search(r'tdata\s*=\s*({[\s\S]*?});', resp.text)

        tdata = json.loads(match.group(1))
        return Gallery(tdata, client=self)

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Performs instant search for celebrities via POST /api/suggest.

        :param query: Search query string (e.g. 'Yurina').
        :return: List of matching celebrity dicts containing 'cid', 'name', 'fetchname', 'pcount', 'gender'.
        """
        if not query or not str(query).strip():
            return []

        url = f"https://{self.domain}/api/suggest"
        files = {"query": (None, str(query).strip())}

        resp = self.session.post(url, files=files, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        results: List[Dict[str, Any]] = []

        if isinstance(data, list):
            for item in data:
                if isinstance(item, list) and len(item) >= 2 and item[0] == "tdata":
                    results = item[1].get("searchresults", [])
                    break

        return [r for r in results if isinstance(r, dict)]

    def rate_celebrity(self, cid_or_gallery: Union[int, str, Gallery], rank: int) -> Dict[str, Any]:
        """
        Rates a celebrity with star rank (1 to 5) via POST /api/rateceleb.

        :param cid_or_gallery: Celebrity ID integer/string or Gallery object.
        :param rank: Star rating integer (1 to 5).
        :return: Response JSON.
        """
        if self.is_guest:
            raise AuthenticationError("Rating celebrities requires an authenticated User session.")

        if rank < 1 or rank > 5:
            raise ValueError(f"Star rank must be between 1 and 5 (got {rank}).")

        cid = cid_or_gallery.cid if isinstance(cid_or_gallery, Gallery) else cid_or_gallery
        url = f"https://{self.domain}/api/rateceleb"
        files = {
            "cid": (None, str(cid)),
            "rank": (None, str(rank))
        }

        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name=f"Rating celebrity CID {cid}")

    def toggle_favorite(self, cid_or_gallery: Union[int, str, Gallery]) -> Dict[str, Any]:
        """
        Toggles favorite status on a celebrity via POST /api/fav.
        """
        if self.is_guest:
            raise AuthenticationError("Favoriting celebrities requires an authenticated User session.")

        cid = cid_or_gallery.cid if isinstance(cid_or_gallery, Gallery) else cid_or_gallery
        url = f"https://{self.domain}/api/fav"
        files = {"cid": (None, str(cid))}

        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name=f"Favoriting celebrity CID {cid}")

    def ignore_celebrity(self, cid_or_gallery: Union[int, str, Gallery]) -> Dict[str, Any]:
        """
        Ignores / hides a celebrity via POST /api/ignoreceleb.
        """
        if self.is_guest:
            raise AuthenticationError("Ignoring celebrities requires an authenticated User session.")

        cid = cid_or_gallery.cid if isinstance(cid_or_gallery, Gallery) else cid_or_gallery
        url = f"https://{self.domain}/api/ignoreceleb"
        files = {"cid": (None, str(cid))}

        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name=f"Ignoring celebrity CID {cid}")

    def _verify_api_response(
        self,
        resp: requests.Response,
        action_name: str = "API action"
    ) -> Any:
        """
        Verifies HTTP status and parses API JSON response, checking for WikiFeet error structures.
        """
        try:
            resp.raise_for_status()
            data = resp.json()
        except requests.HTTPError as e:
            raise APIError(
                f"{action_name} failed with HTTP status {resp.status_code}: {resp.text}",
                status_code=resp.status_code
            ) from e
        except Exception as e:
            raise APIError(f"{action_name} failed to return valid JSON response: {resp.text}") from e

        # Check list error patterns (e.g. [["error", "Reason"]] or ["error", "Reason"])
        if isinstance(data, list):
            for item in data:
                if isinstance(item, list) and len(item) > 0 and item[0] == "error":
                    err_msg = item[1] if len(item) > 1 else "Unknown error"
                    raise ReportError(f"{action_name} failed: {err_msg}", response_data=data)
                elif item == "error":
                    err_msg = data[1] if len(data) > 1 else "Unknown error"
                    raise ReportError(f"{action_name} failed: {err_msg}", response_data=data)

        # Check dict error & process dialog patterns
        if isinstance(data, dict):
            if "error" in data and data["error"]:
                raise ReportError(f"{action_name} failed: {data['error']}", response_data=data)
            if data.get("status") == "error":
                err_msg = data.get("message") or data.get("error") or "Unknown error"
                raise ReportError(f"{action_name} failed: {err_msg}", response_data=data)

            # Check WikiFeet process dialog errors (e.g. {"process": ["dialog", "Action not allowed..."]})
            proc = data.get("process")
            if isinstance(proc, list) and len(proc) >= 2:
                proc_type = str(proc[0]).strip().lower()
                msg = str(proc[1]).strip()
                if proc_type in ("dialog", "error", "warning", "fail"):
                    raise ReportError(f"{action_name} failed: {msg}", response_data=data)

        return data

    def fetch_extended_details(
        self,
        pid_or_photo: Union[int, str, Photo]
    ) -> Dict[str, Optional[str]]:
        """
        Fetches uploader, upload date, and reporter details via POST /api/extended.

        :param pid_or_photo: Photo object or PID integer/string.
        :return: Dict containing 'uploaded_by', 'upload_date', 'reported_by'
        """
        pid = pid_or_photo.pid if isinstance(pid_or_photo, Photo) else pid_or_photo
        url = f"https://{self.domain}/api/extended"
        files = {"pid": (None, str(pid))}

        try:
            resp = self.session.post(url, files=files, timeout=10)
            resp.raise_for_status()
            return parse_extended_details(resp.json())
        except Exception:
            return {"uploaded_by": None, "upload_date": None, "reported_by": None}

    def fetch_more_comments(self, gallery: Gallery, max_pages: int = 1) -> List[Comment]:
        """
        Fetches next page(s) of comments for a given Gallery via POST /api/comments API.
        Appends newly fetched comments directly to `gallery.comments`.

        :param gallery: Target Gallery instance
        :param max_pages: Max number of pagination pages to request (default: 1)
        :return: List of newly fetched Comment objects
        """
        if not gallery.has_more_comments or not gallery.comments:
            return []

        url = f"https://{self.domain}/api/comments"
        new_comments: List[Comment] = []
        page_count = 0

        while gallery.has_more_comments and page_count < max_pages:
            last_midx = gallery.comments[-1].midx
            if not last_midx or not gallery.cid:
                break

            files = {
                "cid": (None, str(gallery.cid)),
                "last": (None, str(last_midx))
            }

            resp = self.session.post(url, files=files, timeout=10)
            resp.raise_for_status()

            data = resp.json()
            raw_threads = data.get("threads", [])
            gallery.has_more_comments = bool(data.get("more", 0))

            if not raw_threads:
                gallery.has_more_comments = False
                break

            fetched_objs = [Comment(t) for t in raw_threads if isinstance(t, dict)]
            gallery.comments.extend(fetched_objs)
            new_comments.extend(fetched_objs)
            page_count += 1

        return new_comments

    def vote_comment(
        self,
        comment_or_cidx: Union[int, str, Comment],
        state: int
    ) -> Dict[str, Any]:
        """
        Submits a vote state for a comment via POST /api/like.

        :param comment_or_cidx: Comment object or comment index ID (cidx).
        :param state: Vote action state (1 = Like/Upvote, 0 = Dislike/Downvote, 2 = Retract/Neutral).
        :return: Response JSON containing updated cidx, likes, likepart, state.
        """
        if self.is_guest:
            raise AuthenticationError("Voting on comments requires an authenticated User session.")

        cidx = comment_or_cidx.idx if isinstance(comment_or_cidx, Comment) else comment_or_cidx

        url = f"https://{self.domain}/api/like"
        files = {
            "cidx": (None, str(cidx)),
            "state": (None, str(state))
        }

        resp = self.session.post(url, files=files, timeout=10)
        data = self._verify_api_response(resp, action_name=f"Voting comment CIDX {cidx}")

        if isinstance(comment_or_cidx, Comment):
            if "likes" in data:
                comment_or_cidx.likes = int(data["likes"])
                comment_or_cidx.like_count = comment_or_cidx.likes
            if "likepart" in data:
                comment_or_cidx.user_vote = int(data["likepart"]) if data["likepart"] is not None else None

        return data

    def like_comment(self, comment_or_cidx: Union[int, str, Comment]) -> Dict[str, Any]:
        """Likes / upvotes a comment (state=1)."""
        return self.vote_comment(comment_or_cidx, state=1)

    def dislike_comment(self, comment_or_cidx: Union[int, str, Comment]) -> Dict[str, Any]:
        """Dislikes / downvotes a comment (state=0)."""
        return self.vote_comment(comment_or_cidx, state=0)

    def retract_comment_vote(self, comment_or_cidx: Union[int, str, Comment]) -> Dict[str, Any]:
        """Retracts / removes like or dislike vote from a comment (state=2)."""
        return self.vote_comment(comment_or_cidx, state=2)

    def tag_photo(
        self,
        pid_or_photo: Union[int, str, Photo],
        tag: str,
        value: int = 1
    ) -> Dict[str, Any]:
        """
        Tags or untags a photo via POST /api/tagphoto.

        :param pid_or_photo: Photo object or PID integer/string.
        :param tag: Tag name or code (e.g. 'arches', 'A', 'soles', 'S', 'close_up', 'C').
        :param value: 1 to add tag, 0 to remove tag.
        :return: Response JSON containing updated pid and tags string.
        """
        if self.is_guest:
            raise AuthenticationError("Tagging photos requires an authenticated User session.")

        tag_code = normalize_tag(tag)
        pid = pid_or_photo.pid if isinstance(pid_or_photo, Photo) else pid_or_photo

        url = f"https://{self.domain}/api/tagphoto"
        files = {
            "pid": (None, str(pid)),
            "tag": (None, str(tag_code)),
            "value": (None, str(value))
        }

        resp = self.session.post(url, files=files, timeout=10)
        data = self._verify_api_response(resp, action_name=f"Tagging photo PID {pid}")

        if isinstance(pid_or_photo, Photo) and "tags" in data:
            pid_or_photo.tags.raw_string = str(data["tags"])

        return data

    def untag_photo(
        self,
        pid_or_photo: Union[int, str, Photo],
        tag: str
    ) -> Dict[str, Any]:
        """Removes a tag from a photo (value=0)."""
        return self.tag_photo(pid_or_photo, tag=tag, value=0)

    def like_photo(
        self,
        pid_or_photo: Union[int, str, Photo],
        value: int = 1
    ) -> Dict[str, Any]:
        """
        Likes or retracts like from a photo via POST /api/topphoto.

        :param pid_or_photo: Photo object or PID integer/string.
        :param value: 1 to like photo, 0 to retract like.
        :return: Response JSON containing pid, value, pb, and process status.
        """
        if self.is_guest:
            raise AuthenticationError("Liking photos requires an authenticated User session.")

        pid = pid_or_photo.pid if isinstance(pid_or_photo, Photo) else pid_or_photo

        url = f"https://{self.domain}/api/topphoto"
        files = {
            "pid": (None, str(pid)),
            "value": (None, str(value))
        }

        resp = self.session.post(url, files=files, timeout=10)
        data = self._verify_api_response(resp, action_name=f"Liking photo PID {pid}")

        if isinstance(pid_or_photo, Photo):
            val = int(data.get("value", value))
            pid_or_photo.best = val

        return data

    def unlike_photo(self, pid_or_photo: Union[int, str, Photo]) -> Dict[str, Any]:
        """Retracts like from a photo (value=0)."""
        return self.like_photo(pid_or_photo, value=0)

    def get_hands(self, cid_or_gallery: Union[int, str, Gallery]) -> List[HandPhoto]:
        """
        Fetches hands gallery for a celebrity via POST /api/hands.

        :param cid_or_gallery: Celebrity ID integer/string or Gallery object.
        :return: List of HandPhoto objects
        """
        cid = cid_or_gallery.cid if isinstance(cid_or_gallery, Gallery) else cid_or_gallery
        url = f"https://{self.domain}/api/hands"
        files = {"cid": (None, str(cid))}

        resp = self.session.post(url, files=files, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        raw_hands = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, list) and len(item) >= 2 and item[0] == "tdata":
                    raw_hands = item[1].get("hands", [])
                    break

        return [HandPhoto(h, client=self) for h in raw_hands if isinstance(h, dict)]

    def fetch_hand_extended_details(self, hid_or_photo: Union[int, str, HandPhoto]) -> Dict[str, Optional[str]]:
        """
        Fetches uploader, upload date, and reporter details for a hand photo via POST /api/hextended.
        """
        hid = hid_or_photo.pid if isinstance(hid_or_photo, HandPhoto) else hid_or_photo
        url = f"https://{self.domain}/api/hextended"
        files = {"hid": (None, str(hid))}

        try:
            resp = self.session.post(url, files=files, timeout=10)
            resp.raise_for_status()
            return parse_extended_details(resp.json())
        except Exception:
            return {"uploaded_by": None, "upload_date": None, "reported_by": None}

    def report_photo(
        self,
        pid_or_photo: Union[int, str, Photo],
        report_type: str = "NO_FEET",
        target_pid: Optional[Union[int, str, Photo]] = None
    ) -> Dict[str, Any]:
        """
        Reports a photo via POST /api/reportphoto.

        :param pid_or_photo: Target photo ID or Photo object.
        :param report_type: Type of report (e.g. 'NO_FEET', 'DUPLICATE', 'LOW_QUALITY', 'UNDERAGE', 'FAKE').
        :param target_pid: Required when report_type is 'DUPLICATE' ('D').
        :return: Response dict containing status and result details.
        """
        if self.is_guest:
            raise AuthenticationError("Reporting photos requires an authenticated User session.")

        REPORT_TYPE_MAP = {
            "NO_FEET": "N", "N": "N",
            "WRONG_PERSON": "W", "W": "W",
            "FAKE": "F", "F": "F",
            "ILLEGAL": "I", "I": "I",
            "LOW_QUALITY": "P", "P": "P",
            "UNDERAGE": "U", "U": "U",
            "ADULT_CONTENT": "A", "A": "A",
            "OVERLIMIT": "O", "O": "O",
            "DUPLICATE": "D", "D": "D",
            "UNREPORT": "0", "0": "0",
            "RETRACT": "0"
        }

        pid = pid_or_photo.pid if isinstance(pid_or_photo, Photo) else pid_or_photo
        rtype_key = str(report_type).strip().upper()
        if rtype_key not in REPORT_TYPE_MAP:
            raise ValueError(f"Unknown report_type '{report_type}'. Valid types: {list(REPORT_TYPE_MAP.keys())}")

        rtype = REPORT_TYPE_MAP[rtype_key]
        rep_val = "0"

        tgt_pid = target_pid.pid if isinstance(target_pid, Photo) else target_pid
        if rtype == "D":
            if tgt_pid is None:
                raise ValueError("target_pid is required when reporting a photo as Duplicate ('DUPLICATE' / 'D').")
            rep_val = str(tgt_pid)
        elif tgt_pid is not None:
            rep_val = str(tgt_pid)

        url = f"https://{self.domain}/api/reportphoto"
        files = {
            "idx": (None, str(pid)),
            "type": (None, rtype),
            "rep": (None, rep_val)
        }

        resp = self.session.post(url, files=files, timeout=10)
        data = self._verify_api_response(resp, action_name=f"Reporting photo PID {pid}")

        if isinstance(pid_or_photo, Photo):
            pid_or_photo.reported = rtype

        return data

    def report_hand_photo(
        self,
        hid_or_photo: Union[int, str, HandPhoto],
        reason: str
    ) -> Dict[str, Any]:
        """
        Reports a hand photo via POST /api/reporthand.

        :param hid_or_photo: Hand photo ID or HandPhoto object.
        :param reason: Reason string (e.g. 'not a close up').
        :return: Response JSON containing status message.
        """
        if self.is_guest:
            raise AuthenticationError("Reporting hand photos requires an authenticated User session.")

        if not reason or not str(reason).strip():
            raise ValueError("A reason string is required when reporting a hand photo.")

        hid = hid_or_photo.pid if isinstance(hid_or_photo, HandPhoto) else hid_or_photo
        url = f"https://{self.domain}/api/reporthand"
        files = {
            "idx": (None, str(hid)),
            "reason": (None, str(reason))
        }

        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name=f"Reporting hand photo HID {hid}")

    def guild(self) -> Guild:
        """
        Fetches the Guild page (/guild), parses embedded `tdata`, and returns a Guild instance.
        """
        url = f"https://{self.domain}/guild"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()

        match = re.search(r'tdata\s*=\s*({.*?});', resp.text, re.DOTALL)
        if not match:
            match = re.search(r'tdata\s*=\s*({[\s\S]*?});', resp.text)

        tdata = json.loads(match.group(1)) if match else {}
        return Guild(tdata, client=self)

    def join_guild(self) -> Dict[str, Any]:
        """
        Joins the WikiFeet Guild via POST /api/joinguild.
        """
        if self.is_guest:
            raise AuthenticationError("Joining the Guild requires an authenticated User session.")

        url = f"https://{self.domain}/api/joinguild"
        resp = self.session.post(url, files={}, timeout=10)
        return self._verify_api_response(resp, action_name="Joining Guild")

    def leave_guild(self) -> Dict[str, Any]:
        """
        Leaves the WikiFeet Guild via POST /api/quitguild.
        """
        if self.is_guest:
            raise AuthenticationError("Leaving the Guild requires an authenticated User session.")

        url = f"https://{self.domain}/api/quitguild"
        resp = self.session.post(url, files={}, timeout=10)
        return self._verify_api_response(resp, action_name="Leaving Guild")

    def quit_guild(self) -> Dict[str, Any]:
        """Alias for leave_guild()."""
        return self.leave_guild()

    def get_guild_chat(self, last_idx: int = 0) -> List[GuildMessage]:
        """
        Fetches new Guild chat messages via POST /api/guildchat.

        :param last_idx: Last seen message ID integer.
        :return: List of GuildMessage objects.
        """
        if self.is_guest:
            raise AuthenticationError("Fetching Guild chat requires an authenticated User session.")

        url = f"https://{self.domain}/api/guildchat"
        files = {
            "idx": (None, str(last_idx))
        }

        resp = self.session.post(url, files=files, timeout=10)
        data = self._verify_api_response(resp, action_name="Fetching Guild chat")

        raw_chat = []
        if isinstance(data, dict):
            raw_chat = data.get("chat", [])
        elif isinstance(data, list):
            raw_chat = data

        return [GuildMessage(m) for m in raw_chat if isinstance(m, dict)]

    def _get_gender_code(self) -> str:
        """Returns gender string parameter for backlog calls based on client domain."""
        dom = self.domain.lower()
        if "men.wikifeet" in dom:
            return "1"
        elif "wikifeetx" in dom:
            return "2"
        return "0"

    def get_guild_photo_backlog(self) -> List[Dict[str, Any]]:
        """
        Fetches pending Guild photo reports backlog via POST /api/guildphotos.
        """
        if self.is_guest:
            raise AuthenticationError("Viewing Guild photo backlog requires an authenticated User session.")

        url = f"https://{self.domain}/api/guildphotos"
        files = {"gender": (None, self._get_gender_code())}

        resp = self.session.post(url, files=files, timeout=10)
        data = self._verify_api_response(resp, action_name="Fetching Guild photo backlog")

        backlog: List[Dict[str, Any]] = []
        if isinstance(data, list):
            for action in data:
                if isinstance(action, list) and len(action) >= 3 and action[0] == "render" and action[1] == "backdiv":
                    content = action[2]
                    if isinstance(content, list) and len(content) >= 2:
                        backlog = content[1]
                        break

        return backlog

    def get_guild_comment_backlog(self) -> List[Dict[str, Any]]:
        """
        Fetches pending Guild comment reports backlog via POST /api/guildcomments.
        """
        if self.is_guest:
            raise AuthenticationError("Viewing Guild comment backlog requires an authenticated User session.")

        url = f"https://{self.domain}/api/guildcomments"
        files = {"gender": (None, self._get_gender_code())}

        resp = self.session.post(url, files=files, timeout=10)
        data = self._verify_api_response(resp, action_name="Fetching Guild comment backlog")

        backlog: List[Dict[str, Any]] = []
        if isinstance(data, list):
            for action in data:
                if isinstance(action, list) and len(action) >= 3 and action[0] == "render" and action[1] == "backdiv":
                    content = action[2]
                    if isinstance(content, list) and len(content) >= 2:
                        backlog = content[1]
                        break

        return backlog

    def inbox(self) -> Inbox:
        """
        Fetches the private messaging inbox (/messages), parses embedded `tdata`, and returns an Inbox instance.
        """
        if self.is_guest:
            raise AuthenticationError("Viewing private messages requires an authenticated User session.")

        url = f"https://{self.domain}/messages"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()

        match = re.search(r'tdata\s*=\s*({.*?});', resp.text, re.DOTALL)
        if not match:
            match = re.search(r'tdata\s*=\s*({[\s\S]*?});', resp.text)

        tdata = json.loads(match.group(1)) if match else {}
        return Inbox(tdata, client=self)

    def get_message_thread(self, partner_uid: Union[int, str]) -> MessageThread:
        """
        Fetches a specific private message conversation thread (/messages/{partner_uid}).

        :param partner_uid: Partner user ID integer or string.
        :return: MessageThread object containing full conversation history.
        """
        if self.is_guest:
            raise AuthenticationError("Viewing message thread requires an authenticated User session.")

        url = f"https://{self.domain}/messages/{partner_uid}"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()

        match = re.search(r'tdata\s*=\s*({.*?});', resp.text, re.DOTALL)
        if not match:
            match = re.search(r'tdata\s*=\s*({[\s\S]*?});', resp.text)

        tdata = json.loads(match.group(1)) if match else {}
        return MessageThread(tdata, client=self)

    def send_private_message(self, to_uid: Union[int, str], text: str) -> Dict[str, Any]:
        """
        Sends a private message to a specific user UID via POST /api/compose.

        :param to_uid: Target recipient user UID.
        :param text: Message text.
        :return: Response JSON containing process status.
        """
        if self.is_guest:
            raise AuthenticationError("Sending private messages requires an authenticated User session.")

        if not text or not str(text).strip():
            raise ValueError("Message text cannot be empty.")

        url = f"https://{self.domain}/api/compose"
        files = {
            "to": (None, str(to_uid)),
            "message": (None, str(text))
        }

        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name=f"Sending PM to UID {to_uid}")

    def archive_all_messages(self) -> Dict[str, Any]:
        """
        Archives all private message threads via POST /api/archiveall.
        """
        if self.is_guest:
            raise AuthenticationError("Archiving messages requires an authenticated User session.")

        url = f"https://{self.domain}/api/archiveall"
        resp = self.session.post(url, files={}, timeout=10)
        return self._verify_api_response(resp, action_name="Archiving all messages")

    def blacklist_user(self, uid: Union[int, str]) -> Dict[str, Any]:
        """
        Adds a user to your personal blacklist via POST /api/userlists (bladd).
        """
        if self.is_guest:
            raise AuthenticationError("Blacklisting users requires an authenticated User session.")

        url = f"https://{self.domain}/api/userlists"
        files = {"bladd": (None, str(uid))}
        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name=f"Blacklisting user UID {uid}")

    def unblacklist_user(self, uid: Union[int, str]) -> Dict[str, Any]:
        """
        Removes a user from your personal blacklist via POST /api/userlists (blremove).
        """
        if self.is_guest:
            raise AuthenticationError("Unblacklisting users requires an authenticated User session.")

        url = f"https://{self.domain}/api/userlists"
        files = {"blremove": (None, str(uid))}
        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name=f"Unblacklisting user UID {uid}")

    def set_celebrity_alerts(
        self,
        cid_or_gallery: Union[int, str, Gallery],
        sub_photos: bool = True,
        sub_threads: bool = True
    ) -> Dict[str, Any]:
        """
        Sets notification subscriptions for a celebrity via POST /api/alertset.
        """
        if self.is_guest:
            raise AuthenticationError("Configuring celebrity alerts requires an authenticated User session.")

        cid = cid_or_gallery.cid if isinstance(cid_or_gallery, Gallery) else cid_or_gallery
        url = f"https://{self.domain}/api/alertset"
        files = {
            "cid": (None, str(cid)),
            "sub_photos": (None, "1" if sub_photos else "0"),
            "sub_threads": (None, "1" if sub_threads else "0")
        }

        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name=f"Configuring alerts for CID {cid}")

    def post_comment(
        self,
        cname_or_cid: Union[int, str, Gallery],
        message: str,
        photo_pid: Optional[Union[int, str, Photo]] = None
    ) -> Dict[str, Any]:
        """
        Posts a new comment to a celebrity page or photo PID via POST /api/wsubmit.
        """
        if self.is_guest:
            raise AuthenticationError("Posting comments requires an authenticated User session.")

        if not message or not str(message).strip():
            raise ValueError("Comment message cannot be empty.")

        cname = cname_or_cid.cname if isinstance(cname_or_cid, Gallery) else str(cname_or_cid)

        url = f"https://{self.domain}/api/wsubmit"
        files = {
            "cname": (None, cname),
            "message": (None, str(message))
        }

        if photo_pid is not None:
            pid_val = photo_pid.pid if isinstance(photo_pid, Photo) else photo_pid
            files["attachment"] = (None, str(pid_val))

        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name=f"Posting comment to '{cname}'")

    def report_comment(
        self,
        comment_or_cidx: Union[int, str, Comment],
        reason: str = ""
    ) -> Dict[str, Any]:
        """
        Reports a comment via POST /api/reportcomment.
        """
        if self.is_guest:
            raise AuthenticationError("Reporting comments requires an authenticated User session.")

        cidx = comment_or_cidx.idx if isinstance(comment_or_cidx, Comment) else comment_or_cidx

        url = f"https://{self.domain}/api/reportcomment"
        files = {
            "idx": (None, str(cidx)),
            "reason": (None, str(reason))
        }

        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name=f"Reporting comment CIDX {cidx}")

    def flag_comment(self, comment_or_cidx: Union[int, str, Comment]) -> Dict[str, Any]:
        """
        Flags a comment via POST /api/wflag.
        """
        if self.is_guest:
            raise AuthenticationError("Flagging comments requires an authenticated User session.")

        cidx = comment_or_cidx.idx if isinstance(comment_or_cidx, Comment) else comment_or_cidx

        url = f"https://{self.domain}/api/wflag"
        files = {"idx": (None, str(cidx))}

        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name=f"Flagging comment CIDX {cidx}")

    def retract_comment(self, tidx_or_cidx: Union[int, str, Comment]) -> Dict[str, Any]:
        """
        Retracts a submitted comment via POST /api/wretract.
        """
        if self.is_guest:
            raise AuthenticationError("Retracting comments requires an authenticated User session.")

        idx = tidx_or_cidx.idx if isinstance(tidx_or_cidx, Comment) else tidx_or_cidx

        url = f"https://{self.domain}/api/wretract"
        files = {"idx": (None, str(idx))}

        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name=f"Retracting comment ID {idx}")

    def review_comment(self, tidx: Union[int, str], approve: bool = True) -> Dict[str, Any]:
        """
        Moderates a pending comment via POST /api/wreview.
        """
        if self.is_guest:
            raise AuthenticationError("Reviewing comments requires an authenticated User session.")

        url = f"https://{self.domain}/api/wreview"
        files = {
            "tidx": (None, str(tidx)),
            "approve": (None, "1" if approve else "0")
        }

        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name=f"Reviewing comment TIDX {tidx}")

    def vote_guild_poll(self, poll_id: Union[int, str], choice: Union[int, str]) -> Dict[str, Any]:
        """
        Votes in a Guild poll via POST /api/guildpollvote.
        """
        if self.is_guest:
            raise AuthenticationError("Voting in Guild poll requires an authenticated User session.")

        url = f"https://{self.domain}/api/guildpollvote"
        files = {
            "pid": (None, str(poll_id)),
            "choice": (None, str(choice))
        }

        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name=f"Voting in Guild poll PID {poll_id}")

    def create_guild_poll(self, title: str, options: List[str]) -> Dict[str, Any]:
        """
        Creates a new Guild poll via POST /api/guildpollmake.
        """
        if self.is_guest:
            raise AuthenticationError("Creating Guild poll requires an authenticated User session.")

        url = f"https://{self.domain}/api/guildpollmake"
        files = {
            "title": (None, str(title)),
            "options": (None, json.dumps(options))
        }

        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name="Creating Guild poll")

    def create_guild_announcement(self, title: str, text: str) -> Dict[str, Any]:
        """
        Creates a Guild announcement via POST /api/guildannouncementmake.
        """
        if self.is_guest:
            raise AuthenticationError("Creating Guild announcement requires an authenticated User session.")

        url = f"https://{self.domain}/api/guildannouncementmake"
        files = {
            "title": (None, str(title)),
            "text": (None, str(text))
        }

        resp = self.session.post(url, files=files, timeout=10)
        return self._verify_api_response(resp, action_name="Creating Guild announcement")

    def find_duplicate_photos(self, pid_or_photo: Union[int, str, Photo]) -> List[Dict[str, Any]]:
        """
        Scans for duplicate photo matches across WikiFeet database via POST /api/similars.
        """
        pid = pid_or_photo.pid if isinstance(pid_or_photo, Photo) else pid_or_photo

        url = f"https://{self.domain}/api/similars"
        files = {"pid": (None, str(pid))}

        resp = self.session.post(url, files=files, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        matches: List[Dict[str, Any]] = []

        if isinstance(data, list):
            for item in data:
                if isinstance(item, list) and len(item) >= 2 and item[0] == "tdata":
                    matches = item[1].get("duplicates", [])
                    break
        elif isinstance(data, dict):
            matches = data.get("duplicates", [])

        return [m for m in matches if isinstance(m, dict)]

    def fetch_imdb_data(self, imdb_id_or_cid: Union[int, str]) -> Dict[str, Any]:
        """
        Fetches IMDb metadata via POST /api/imdb_fetch.
        """
        url = f"https://{self.domain}/api/imdb_fetch"
        files = {"cid": (None, str(imdb_id_or_cid))}

        resp = self.session.post(url, files=files, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def close_account(self, confirm: bool = False) -> Dict[str, Any]:
        """
        Closes / deletes the authenticated user account via POST /api/closeaccount.
        """
        if self.is_guest:
            raise AuthenticationError("Closing account requires an authenticated User session.")

        if not confirm:
            raise ValueError("Must explicitly pass confirm=True to close account.")

        url = f"https://{self.domain}/api/closeaccount"
        resp = self.session.post(url, files={}, timeout=10)
        return self._verify_api_response(resp, action_name="Closing account")

    def upload_photo(
        self,
        cid_or_gallery: Union[int, str, Gallery],
        file_path_or_bytes: Union[str, bytes],
        file_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uploads a new photo to a celebrity gallery via POST /api/upload.

        :param cid_or_gallery: Celebrity ID integer/string or Gallery object.
        :param file_path_or_bytes: File path string or raw image bytes.
        :param file_name: Optional file name string (defaults to filename or 'upload.jpg').
        :return: Response JSON containing uploaded photo PID or process status.
        """
        if self.is_guest:
            raise AuthenticationError("Uploading photos requires an authenticated User session.")

        cid = cid_or_gallery.cid if isinstance(cid_or_gallery, Gallery) else cid_or_gallery
        url = f"https://{self.domain}/api/upload"

        if isinstance(file_path_or_bytes, str):
            with open(file_path_or_bytes, "rb") as f:
                content = f.read()
            fname = file_name or file_path_or_bytes.replace("\\", "/").split("/")[-1]
        else:
            content = file_path_or_bytes
            fname = file_name or "upload.jpg"

        files = {
            "cid": (None, str(cid)),
            "file": (fname, content, "image/jpeg")
        }

        resp = self.session.post(url, files=files, timeout=30)
        return self._verify_api_response(resp, action_name=f"Uploading photo for CID {cid}")

    def upload_hand_photo(
        self,
        cid_or_gallery: Union[int, str, Gallery],
        file_path_or_bytes: Union[str, bytes],
        source: str = "social",
        source_info: str = "Social media post source",
        file_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uploads a new hand photo to a celebrity's hands gallery via POST /api/handupload.

        :param cid_or_gallery: Celebrity ID integer/string or Gallery object.
        :param file_path_or_bytes: File path string or raw image bytes.
        :param source: Source type ('social', 'video', 'stock', 'artist', 'celeb', 'other').
        :param source_info: Source description string (minimum 10 characters).
        :param file_name: Optional file name string.
        :return: Response JSON containing process status.
        """
        if self.is_guest:
            raise AuthenticationError("Uploading hand photos requires an authenticated User session.")

        VALID_SOURCES = ("social", "video", "stock", "artist", "celeb", "other")
        src_clean = str(source).strip().lower()
        if src_clean not in VALID_SOURCES:
            raise ValueError(f"Invalid hand upload source '{source}'. Must be one of: {list(VALID_SOURCES)}")

        if not source_info or len(str(source_info).strip()) < 10:
            raise ValueError("source_info description must be at least 10 characters long.")

        cid = cid_or_gallery.cid if isinstance(cid_or_gallery, Gallery) else cid_or_gallery
        url = f"https://{self.domain}/api/handupload"

        if isinstance(file_path_or_bytes, str):
            with open(file_path_or_bytes, "rb") as f:
                content = f.read()
            fname = file_name or file_path_or_bytes.replace("\\", "/").split("/")[-1]
        else:
            content = file_path_or_bytes
            fname = file_name or "handupload.jpg"

        files = {
            "cid": (None, str(cid)),
            "source": (None, src_clean),
            "sinfo": (None, str(source_info).strip()),
            "file": (fname, content, "image/jpeg")
        }

        resp = self.session.post(url, files=files, timeout=30)
        return self._verify_api_response(resp, action_name=f"Uploading hand photo for CID {cid}")
