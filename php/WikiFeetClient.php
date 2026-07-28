<?php

namespace WikiFeetSDK;

use WikiFeetSDK\Models\Gallery;
use WikiFeetSDK\Models\Comment;
use WikiFeetSDK\Models\Photo;
use WikiFeetSDK\Models\HandPhoto;
use WikiFeetSDK\Models\Guild;
use WikiFeetSDK\Models\GuildMessage;
use WikiFeetSDK\Models\Inbox;
use WikiFeetSDK\Models\MessageThread;
use WikiFeetSDK\Models\PhotoTags;
use WikiFeetSDK\Exceptions\WikiFeetException;
use WikiFeetSDK\Exceptions\AuthenticationException;
use WikiFeetSDK\Exceptions\APIException;
use WikiFeetSDK\Exceptions\ReportException;
use InvalidArgumentException;
use CURLFile;

/**
 * Main PHP SDK Client for WikiFeet.
 */
class WikiFeetClient
{
    public ?string $email;
    public ?string $password;
    public string $domain;
    public string $userAgent;
    public bool $isGuest;
    private bool $loggedIn = false;
    private ?string $proxy = null;
    private string $cookieJar;

    public const DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36";

    public function __construct(
        ?string $email = null,
        ?string $password = null,
        string $domain = "wikifeet.com",
        ?string $proxy = null,
        string $userAgent = self::DEFAULT_USER_AGENT,
        bool $isGuest = false
    ) {
        $this->email = $email;
        $this->password = $password;
        $this->domain = self::normalizeDomain($domain);
        $this->userAgent = $userAgent;
        $this->isGuest = $isGuest || (!$email && !$password);
        $this->proxy = $proxy;

        $this->cookieJar = sys_get_temp_dir() . '/wf_cookie_' . md5(uniqid(rand(), true)) . '.txt';
    }

    public function __destruct()
    {
        if (file_exists($this->cookieJar)) {
            @unlink($this->cookieJar);
        }
    }

    public static function normalizeDomain(string $domain): string
    {
        $d = trim($domain);
        if (str_contains($d, '://')) {
            $parts = explode('://', $d, 2);
            $d = $parts[1];
        }
        $parts = explode('/', $d);
        return $parts[0] ?: "wikifeet.com";
    }

    public static function asGuest(
        string $domain = "wikifeet.com",
        ?string $proxy = null,
        string $userAgent = self::DEFAULT_USER_AGENT
    ): self {
        return new self(null, null, $domain, $proxy, $userAgent, true);
    }

    public static function asUser(
        string $email,
        string $password,
        string $domain = "wikifeet.com",
        ?string $proxy = null,
        string $userAgent = self::DEFAULT_USER_AGENT
    ): self {
        return new self($email, $password, $domain, $proxy, $userAgent, false);
    }

    public function setProxy(?string $proxyUrl): void
    {
        $this->proxy = $proxyUrl;
    }

    public function getProxy(): ?string
    {
        return $this->proxy;
    }

    public function isLoggedIn(): bool
    {
        return $this->loggedIn && !$this->isGuest;
    }

    private function request(string $method, string $url, array $postFields = [], array $headers = []): array
    {
        $ch = curl_init();

        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, 30);
        curl_setopt($ch, CURLOPT_USERAGENT, $this->userAgent);
        curl_setopt($ch, CURLOPT_COOKIEJAR, $this->cookieJar);
        curl_setopt($ch, CURLOPT_COOKIEFILE, $this->cookieJar);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, 0);

        $defaultHeaders = [
            "Accept: */*",
            "Accept-Language: en-US,en;q=0.9",
            'Sec-Ch-Ua: "Not?A_Brand";v="99", "Chromium";v="130", "Google Chrome";v="130"',
            "Sec-Ch-Ua-Mobile: ?0",
            'Sec-Ch-Ua-Platform: "Windows"',
            "Sec-Fetch-Dest: empty",
            "Sec-Fetch-Mode: cors",
            "Sec-Fetch-Site: same-origin"
        ];
        curl_setopt($ch, CURLOPT_HTTPHEADER, array_merge($defaultHeaders, $headers));

        if ($this->proxy) {
            curl_setopt($ch, CURLOPT_PROXY, $this->proxy);
        }

        if (strtoupper($method) === 'POST') {
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, $postFields);
        }

        $response = curl_exec($ch);
        $statusCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        @curl_close($ch);

        if ($response === false) {
            throw new APIException("cURL error: {$error}", 0);
        }

        return ['body' => $response, 'status' => $statusCode];
    }

    private function verifyApiResponse(array $res, string $actionName = "API action"): mixed
    {
        if ($res['status'] >= 400) {
            throw new APIException("{$actionName} failed with HTTP status {$res['status']}", $res['status']);
        }

        $data = json_decode($res['body'], true);
        if ($data === null && json_last_error() !== JSON_ERROR_NONE) {
            throw new APIException("{$actionName} failed to return valid JSON response: {$res['body']}");
        }

        if (is_array($data)) {
            // List error pattern
            if (array_is_list($data)) {
                foreach ($data as $item) {
                    if (is_array($item) && isset($item[0]) && $item[0] === 'error') {
                        $errMsg = $item[1] ?? 'Unknown error';
                        throw new ReportException("{$actionName} failed: {$errMsg}", $res['status'], $data);
                    }
                }
            } else {
                // Dict error patterns
                if (!empty($data['error'])) {
                    throw new ReportException("{$actionName} failed: {$data['error']}", $res['status'], $data);
                }
                if (isset($data['status']) && $data['status'] === 'error') {
                    $errMsg = $data['message'] ?? $data['error'] ?? 'Unknown error';
                    throw new ReportException("{$actionName} failed: {$errMsg}", $res['status'], $data);
                }
                if (isset($data['process']) && is_array($data['process']) && count($data['process']) >= 2) {
                    $procType = strtolower(trim((string)$data['process'][0]));
                    $msg = trim((string)$data['process'][1]);
                    if (in_array($procType, ['dialog', 'error', 'warning', 'fail'], true)) {
                        throw new ReportException("{$actionName} failed: {$msg}", $res['status'], $data);
                    }
                }
            }
        }

        return $data;
    }

    public function gallery(string $celebritySlug): Gallery
    {
        if (str_starts_with($celebritySlug, "http://") || str_starts_with($celebritySlug, "https://")) {
            $url = $celebritySlug;
        } else {
            $slug = ltrim($celebritySlug, "/");
            $url = "https://{$this->domain}/{$slug}";
        }

        $res = $this->request('GET', $url);
        if ($res['status'] >= 400) {
            throw new APIException("Failed to fetch gallery for {$celebritySlug}", $res['status']);
        }

        if (preg_match('/tdata\s*=\s*({.*?});/s', $res['body'], $match) || preg_match('/tdata\s*=\s*({[\s\S]*?});/', $res['body'], $match)) {
            $tdata = json_decode($match[1], true);
            return new Gallery($tdata ?: [], $this);
        }

        throw new APIException("Could not find tdata payload on celebrity page.");
    }

    public function search(string $query): array
    {
        if (empty(trim($query))) {
            return [];
        }

        $url = "https://{$this->domain}/api/suggest";
        $res = $this->request('POST', $url, ['query' => trim($query)]);
        $data = json_decode($res['body'], true);

        $results = [];
        if (is_array($data)) {
            foreach ($data as $item) {
                if (is_array($item) && count($item) >= 2 && $item[0] === 'tdata') {
                    $results = $item[1]['searchresults'] ?? [];
                    break;
                }
            }
        }

        return is_array($results) ? $results : [];
    }

    public function rateCelebrity(mixed $cidOrGallery, int $rank): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Rating celebrities requires an authenticated User session.");
        }
        if ($rank < 1 || $rank > 5) {
            throw new InvalidArgumentException("Star rank must be between 1 and 5 (got {$rank}).");
        }

        $cid = ($cidOrGallery instanceof Gallery) ? $cidOrGallery->cid : $cidOrGallery;
        $url = "https://{$this->domain}/api/rateceleb";
        $res = $this->request('POST', $url, ['cid' => (string)$cid, 'rank' => (string)$rank]);
        return $this->verifyApiResponse($res, "Rating celebrity CID {$cid}");
    }

    public function toggleFavorite(mixed $cidOrGallery): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Favoriting celebrities requires an authenticated User session.");
        }
        $cid = ($cidOrGallery instanceof Gallery) ? $cidOrGallery->cid : $cidOrGallery;
        $url = "https://{$this->domain}/api/fav";
        $res = $this->request('POST', $url, ['cid' => (string)$cid]);
        return $this->verifyApiResponse($res, "Favoriting celebrity CID {$cid}");
    }

    public function ignoreCelebrity(mixed $cidOrGallery): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Ignoring celebrities requires an authenticated User session.");
        }
        $cid = ($cidOrGallery instanceof Gallery) ? $cidOrGallery->cid : $cidOrGallery;
        $url = "https://{$this->domain}/api/ignoreceleb";
        $res = $this->request('POST', $url, ['cid' => (string)$cid]);
        return $this->verifyApiResponse($res, "Ignoring celebrity CID {$cid}");
    }

    public function fetchExtendedDetails(mixed $pidOrPhoto): array
    {
        $pid = ($pidOrPhoto instanceof Photo) ? $pidOrPhoto->pid : $pidOrPhoto;
        $url = "https://{$this->domain}/api/extended";
        $res = $this->request('POST', $url, ['pid' => (string)$pid]);

        $uploadedBy = null;
        $uploadDate = null;
        $reportedBy = null;

        if ($res['status'] === 200) {
            $body = $res['body'];
            if (preg_match('/(?:Added|Uploaded) by["\'\s]*\],\s*\[["\'\s]*span["\'\s]*,\s*"([^"]+)"/i', $body, $m) || preg_match('/(?:Added|Uploaded) by:?\s*([a-zA-Z0-9_\-]+)/i', $body, $m)) {
                $uploadedBy = trim($m[1]);
            }
            if (preg_match('/\b(\d{4}-\d{2}-\d{2})\b/', $body, $m)) {
                $uploadDate = trim($m[1]);
            }
            if (preg_match('/Reported by["\'\s]*\],\s*\[["\'\s]*span["\'\s]*,\s*"([^"]+)"/i', $body, $m) || preg_match('/Reported by:?\s*([a-zA-Z0-9_\-]+)/i', $body, $m)) {
                $reportedBy = trim($m[1]);
            }
        }

        return ['uploaded_by' => $uploadedBy, 'upload_date' => $uploadDate, 'reported_by' => $reportedBy];
    }

    public function fetchMoreComments(Gallery $gallery, int $maxPages = 1): array
    {
        if (!$gallery->hasMoreComments || empty($gallery->comments)) {
            return [];
        }

        $url = "https://{$this->domain}/api/comments";
        $newComments = [];
        $pageCount = 0;

        while ($gallery->hasMoreComments && $pageCount < $maxPages) {
            $lastMidx = end($gallery->comments)->midx;
            if (!$lastMidx || !$gallery->cid) {
                break;
            }

            $res = $this->request('POST', $url, ['cid' => (string)$gallery->cid, 'last' => (string)$lastMidx]);
            $data = json_decode($res['body'], true);

            $rawThreads = $data['threads'] ?? [];
            $gallery->hasMoreComments = !empty($data['more']);

            if (empty($rawThreads)) {
                $gallery->hasMoreComments = false;
                break;
            }

            foreach ($rawThreads as $t) {
                if (is_array($t)) {
                    $cObj = new Comment($t, $this);
                    $gallery->comments[] = $cObj;
                    $newComments[] = $cObj;
                }
            }
            $pageCount++;
        }

        return $newComments;
    }

    public function voteComment(mixed $commentOrCidx, int $state): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Voting on comments requires an authenticated User session.");
        }
        $cidx = ($commentOrCidx instanceof Comment) ? $commentOrCidx->idx : $commentOrCidx;
        $url = "https://{$this->domain}/api/like";
        $res = $this->request('POST', $url, ['cidx' => (string)$cidx, 'state' => (string)$state]);
        $data = $this->verifyApiResponse($res, "Voting comment CIDX {$cidx}");

        if ($commentOrCidx instanceof Comment) {
            if (isset($data['likes'])) {
                $commentOrCidx->likes = (int)$data['likes'];
                $commentOrCidx->likeCount = $commentOrCidx->likes;
            }
            if (isset($data['likepart'])) {
                $commentOrCidx->userVote = ($data['likepart'] !== null) ? (int)$data['likepart'] : null;
            }
        }

        return $data;
    }

    public function likeComment(mixed $commentOrCidx): array
    {
        return $this->voteComment($commentOrCidx, 1);
    }

    public function dislikeComment(mixed $commentOrCidx): array
    {
        return $this->voteComment($commentOrCidx, 0);
    }

    public function retractCommentVote(mixed $commentOrCidx): array
    {
        return $this->voteComment($commentOrCidx, 2);
    }

    public function tagPhoto(mixed $pidOrPhoto, string $tag, int $value = 1): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Tagging photos requires an authenticated User session.");
        }
        $tagCode = PhotoTags::normalizeTag($tag);
        $pid = ($pidOrPhoto instanceof Photo) ? $pidOrPhoto->pid : $pidOrPhoto;
        $url = "https://{$this->domain}/api/tagphoto";

        $res = $this->request('POST', $url, ['pid' => (string)$pid, 'tag' => $tagCode, 'value' => (string)$value]);
        $data = $this->verifyApiResponse($res, "Tagging photo PID {$pid}");

        if ($pidOrPhoto instanceof Photo && isset($data['tags'])) {
            $pidOrPhoto->tags->rawString = (string)$data['tags'];
        }

        return $data;
    }

    public function untagPhoto(mixed $pidOrPhoto, string $tag): array
    {
        return $this->tagPhoto($pidOrPhoto, $tag, 0);
    }

    public function likePhoto(mixed $pidOrPhoto, int $value = 1): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Liking photos requires an authenticated User session.");
        }
        $pid = ($pidOrPhoto instanceof Photo) ? $pidOrPhoto->pid : $pidOrPhoto;
        $url = "https://{$this->domain}/api/topphoto";

        $res = $this->request('POST', $url, ['pid' => (string)$pid, 'value' => (string)$value]);
        $data = $this->verifyApiResponse($res, "Liking photo PID {$pid}");

        if ($pidOrPhoto instanceof Photo) {
            $pidOrPhoto->best = (int)($data['value'] ?? $value);
        }

        return $data;
    }

    public function unlikePhoto(mixed $pidOrPhoto): array
    {
        return $this->likePhoto($pidOrPhoto, 0);
    }

    public function getHands(mixed $cidOrGallery): array
    {
        $cid = ($cidOrGallery instanceof Gallery) ? $cidOrGallery->cid : $cidOrGallery;
        $url = "https://{$this->domain}/api/hands";

        $res = $this->request('POST', $url, ['cid' => (string)$cid]);
        $data = json_decode($res['body'], true);

        $rawHands = [];
        if (is_array($data)) {
            foreach ($data as $item) {
                if (is_array($item) && count($item) >= 2 && $item[0] === 'tdata') {
                    $rawHands = $item[1]['hands'] ?? [];
                    break;
                }
            }
        }

        $list = [];
        if (is_array($rawHands)) {
            foreach ($rawHands as $h) {
                if (is_array($h)) {
                    $list[] = new HandPhoto($h, $this);
                }
            }
        }

        return $list;
    }

    public function fetchHandExtendedDetails(mixed $hidOrPhoto): array
    {
        $hid = ($hidOrPhoto instanceof HandPhoto) ? $hidOrPhoto->pid : $hidOrPhoto;
        $url = "https://{$this->domain}/api/hextended";
        $res = $this->request('POST', $url, ['hid' => (string)$hid]);

        $uploadedBy = null;
        $uploadDate = null;
        $reportedBy = null;

        if ($res['status'] === 200) {
            $body = $res['body'];
            if (preg_match('/(?:Added|Uploaded) by["\'\s]*\],\s*\[["\'\s]*span["\'\s]*,\s*"([^"]+)"/i', $body, $m) || preg_match('/(?:Added|Uploaded) by:?\s*([a-zA-Z0-9_\-]+)/i', $body, $m)) {
                $uploadedBy = trim($m[1]);
            }
            if (preg_match('/\b(\d{4}-\d{2}-\d{2})\b/', $body, $m)) {
                $uploadDate = trim($m[1]);
            }
            if (preg_match('/Reported by["\'\s]*\],\s*\[["\'\s]*span["\'\s]*,\s*"([^"]+)"/i', $body, $m) || preg_match('/Reported by:?\s*([a-zA-Z0-9_\-]+)/i', $body, $m)) {
                $reportedBy = trim($m[1]);
            }
        }

        return ['uploaded_by' => $uploadedBy, 'upload_date' => $uploadDate, 'reported_by' => $reportedBy];
    }

    public function reportPhoto(mixed $pidOrPhoto, string $reportType = "NO_FEET", mixed $targetPid = null): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Reporting photos requires an authenticated User session.");
        }

        $map = [
            "NO_FEET" => "N", "N" => "N",
            "WRONG_PERSON" => "W", "W" => "W",
            "FAKE" => "F", "F" => "F",
            "ILLEGAL" => "I", "I" => "I",
            "LOW_QUALITY" => "P", "P" => "P",
            "UNDERAGE" => "U", "U" => "U",
            "ADULT_CONTENT" => "A", "A" => "A",
            "OVERLIMIT" => "O", "O" => "O",
            "DUPLICATE" => "D", "D" => "D",
            "UNREPORT" => "0", "0" => "0",
        ];

        $key = strtoupper(trim($reportType));
        if (!isset($map[$key])) {
            throw new InvalidArgumentException("Unknown reportType '{$reportType}'.");
        }

        $rtype = $map[$key];
        $repVal = "0";

        $tgtPid = ($targetPid instanceof Photo) ? $targetPid->pid : $targetPid;
        if ($rtype === 'D') {
            if ($tgtPid === null) {
                throw new InvalidArgumentException("targetPid is required when reporting a photo as Duplicate ('D').");
            }
            $repVal = (string)$tgtPid;
        } elseif ($tgtPid !== null) {
            $repVal = (string)$tgtPid;
        }

        $pid = ($pidOrPhoto instanceof Photo) ? $pidOrPhoto->pid : $pidOrPhoto;
        $url = "https://{$this->domain}/api/reportphoto";
        $res = $this->request('POST', $url, ['idx' => (string)$pid, 'type' => $rtype, 'rep' => $repVal]);
        $data = $this->verifyApiResponse($res, "Reporting photo PID {$pid}");

        if ($pidOrPhoto instanceof Photo) {
            $pidOrPhoto->reported = $rtype;
        }

        return $data;
    }

    public function reportHandPhoto(mixed $hidOrPhoto, string $reason): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Reporting hand photos requires an authenticated User session.");
        }
        if (empty(trim($reason))) {
            throw new InvalidArgumentException("A reason string is required when reporting a hand photo.");
        }

        $hid = ($hidOrPhoto instanceof HandPhoto) ? $hidOrPhoto->pid : $hidOrPhoto;
        $url = "https://{$this->domain}/api/reporthand";
        $res = $this->request('POST', $url, ['idx' => (string)$hid, 'reason' => trim($reason)]);
        return $this->verifyApiResponse($res, "Reporting hand photo HID {$hid}");
    }

    public function guild(): Guild
    {
        $url = "https://{$this->domain}/guild";
        $res = $this->request('GET', $url);

        if (preg_match('/tdata\s*=\s*({.*?});/s', $res['body'], $match) || preg_match('/tdata\s*=\s*({[\s\S]*?});/', $res['body'], $match)) {
            $tdata = json_decode($match[1], true);
            return new Guild($tdata ?: [], $this);
        }

        return new Guild([], $this);
    }

    public function joinGuild(): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Joining the Guild requires an authenticated User session.");
        }
        $url = "https://{$this->domain}/api/joinguild";
        $res = $this->request('POST', $url);
        return $this->verifyApiResponse($res, "Joining Guild");
    }

    public function leaveGuild(): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Leaving the Guild requires an authenticated User session.");
        }
        $url = "https://{$this->domain}/api/quitguild";
        $res = $this->request('POST', $url);
        return $this->verifyApiResponse($res, "Leaving Guild");
    }

    public function quitGuild(): array
    {
        return $this->leaveGuild();
    }

    public function getGuildChat(int $lastIdx = 0): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Fetching Guild chat requires an authenticated User session.");
        }
        $url = "https://{$this->domain}/api/guildchat";
        $res = $this->request('POST', $url, ['idx' => (string)$lastIdx]);
        $data = $this->verifyApiResponse($res, "Fetching Guild chat");

        $rawChat = is_array($data) ? ($data['chat'] ?? $data) : [];
        $msgs = [];
        if (is_array($rawChat)) {
            foreach ($rawChat as $m) {
                if (is_array($m)) {
                    $msgs[] = new GuildMessage($m);
                }
            }
        }
        return $msgs;
    }

    private function getGenderCode(): string
    {
        $dom = strtolower($this->domain);
        if (str_contains($dom, 'men.wikifeet')) return "1";
        if (str_contains($dom, 'wikifeetx')) return "2";
        return "0";
    }

    public function getGuildPhotoBacklog(): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Viewing Guild photo backlog requires an authenticated User session.");
        }
        $url = "https://{$this->domain}/api/guildphotos";
        $res = $this->request('POST', $url, ['gender' => $this->getGenderCode()]);
        $data = $this->verifyApiResponse($res, "Fetching Guild photo backlog");

        $backlog = [];
        if (is_array($data)) {
            foreach ($data as $action) {
                if (is_array($action) && count($action) >= 3 && $action[0] === 'render' && $action[1] === 'backdiv') {
                    $content = $action[2];
                    if (is_array($content) && count($content) >= 2) {
                        $backlog = $content[1];
                        break;
                    }
                }
            }
        }
        return is_array($backlog) ? $backlog : [];
    }

    public function getGuildCommentBacklog(): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Viewing Guild comment backlog requires an authenticated User session.");
        }
        $url = "https://{$this->domain}/api/guildcomments";
        $res = $this->request('POST', $url, ['gender' => $this->getGenderCode()]);
        $data = $this->verifyApiResponse($res, "Fetching Guild comment backlog");

        $backlog = [];
        if (is_array($data)) {
            foreach ($data as $action) {
                if (is_array($action) && count($action) >= 3 && $action[0] === 'render' && $action[1] === 'backdiv') {
                    $content = $action[2];
                    if (is_array($content) && count($content) >= 2) {
                        $backlog = $content[1];
                        break;
                    }
                }
            }
        }
        return is_array($backlog) ? $backlog : [];
    }

    public function inbox(): Inbox
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Viewing private messages requires an authenticated User session.");
        }
        $url = "https://{$this->domain}/messages";
        $res = $this->request('GET', $url);

        if (preg_match('/tdata\s*=\s*({.*?});/s', $res['body'], $match) || preg_match('/tdata\s*=\s*({[\s\S]*?});/', $res['body'], $match)) {
            $tdata = json_decode($match[1], true);
            return new Inbox($tdata ?: [], $this);
        }

        return new Inbox([], $this);
    }

    public function getMessageThread(mixed $partnerUid): MessageThread
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Viewing message thread requires an authenticated User session.");
        }
        $url = "https://{$this->domain}/messages/{$partnerUid}";
        $res = $this->request('GET', $url);

        if (preg_match('/tdata\s*=\s*({.*?});/s', $res['body'], $match) || preg_match('/tdata\s*=\s*({[\s\S]*?});/', $res['body'], $match)) {
            $tdata = json_decode($match[1], true);
            return new MessageThread($tdata ?: [], $this);
        }

        return new MessageThread([], $this);
    }

    public function sendPrivateMessage(mixed $toUid, string $text): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Sending private messages requires an authenticated User session.");
        }
        if (empty(trim($text))) {
            throw new InvalidArgumentException("Message text cannot be empty.");
        }

        $url = "https://{$this->domain}/api/compose";
        $res = $this->request('POST', $url, ['to' => (string)$toUid, 'message' => trim($text)]);
        return $this->verifyApiResponse($res, "Sending PM to UID {$toUid}");
    }

    public function archiveAllMessages(): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Archiving messages requires an authenticated User session.");
        }
        $url = "https://{$this->domain}/api/archiveall";
        $res = $this->request('POST', $url);
        return $this->verifyApiResponse($res, "Archiving all messages");
    }

    public function blacklistUser(mixed $uid): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Blacklisting users requires an authenticated User session.");
        }
        $url = "https://{$this->domain}/api/userlists";
        $res = $this->request('POST', $url, ['bladd' => (string)$uid]);
        return $this->verifyApiResponse($res, "Blacklisting user UID {$uid}");
    }

    public function unblacklistUser(mixed $uid): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Unblacklisting users requires an authenticated User session.");
        }
        $url = "https://{$this->domain}/api/userlists";
        $res = $this->request('POST', $url, ['blremove' => (string)$uid]);
        return $this->verifyApiResponse($res, "Unblacklisting user UID {$uid}");
    }

    public function setCelebrityAlerts(mixed $cidOrGallery, bool $subPhotos = true, bool $subThreads = true): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Configuring celebrity alerts requires an authenticated User session.");
        }
        $cid = ($cidOrGallery instanceof Gallery) ? $cidOrGallery->cid : $cidOrGallery;
        $url = "https://{$this->domain}/api/alertset";
        $res = $this->request('POST', $url, [
            'cid' => (string)$cid,
            'sub_photos' => $subPhotos ? "1" : "0",
            'sub_threads' => $subThreads ? "1" : "0"
        ]);
        return $this->verifyApiResponse($res, "Configuring alerts for CID {$cid}");
    }

    public function postComment(mixed $cnameOrCid, string $message, mixed $photoPid = null): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Posting comments requires an authenticated User session.");
        }
        if (empty(trim($message))) {
            throw new InvalidArgumentException("Comment message cannot be empty.");
        }

        $cname = ($cnameOrCid instanceof Gallery) ? $cnameOrCid->cname : (string)$cnameOrCid;
        $url = "https://{$this->domain}/api/wsubmit";
        $fields = ['cname' => $cname, 'message' => trim($message)];

        if ($photoPid !== null) {
            $pidVal = ($photoPid instanceof Photo) ? $photoPid->pid : $photoPid;
            $fields['attachment'] = (string)$pidVal;
        }

        $res = $this->request('POST', $url, $fields);
        return $this->verifyApiResponse($res, "Posting comment to '{$cname}'");
    }

    public function reportComment(mixed $commentOrCidx, string $reason = ""): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Reporting comments requires an authenticated User session.");
        }
        $cidx = ($commentOrCidx instanceof Comment) ? $commentOrCidx->idx : $commentOrCidx;
        $url = "https://{$this->domain}/api/reportcomment";
        $res = $this->request('POST', $url, ['idx' => (string)$cidx, 'reason' => trim($reason)]);
        return $this->verifyApiResponse($res, "Reporting comment CIDX {$cidx}");
    }

    public function flagComment(mixed $commentOrCidx): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Flagging comments requires an authenticated User session.");
        }
        $cidx = ($commentOrCidx instanceof Comment) ? $commentOrCidx->idx : $commentOrCidx;
        $url = "https://{$this->domain}/api/wflag";
        $res = $this->request('POST', $url, ['idx' => (string)$cidx]);
        return $this->verifyApiResponse($res, "Flagging comment CIDX {$cidx}");
    }

    public function retractComment(mixed $tidxOrCidx): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Retracting comments requires an authenticated User session.");
        }
        $idx = ($tidxOrCidx instanceof Comment) ? $tidxOrCidx->idx : $tidxOrCidx;
        $url = "https://{$this->domain}/api/wretract";
        $res = $this->request('POST', $url, ['idx' => (string)$idx]);
        return $this->verifyApiResponse($res, "Retracting comment ID {$idx}");
    }

    public function reviewComment(mixed $tidx, bool $approve = true): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Reviewing comments requires an authenticated User session.");
        }
        $url = "https://{$this->domain}/api/wreview";
        $res = $this->request('POST', $url, ['tidx' => (string)$tidx, 'approve' => $approve ? "1" : "0"]);
        return $this->verifyApiResponse($res, "Reviewing comment TIDX {$tidx}");
    }

    public function voteGuildPoll(mixed $pollId, mixed $choice): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Voting in Guild poll requires an authenticated User session.");
        }
        $url = "https://{$this->domain}/api/guildpollvote";
        $res = $this->request('POST', $url, ['pid' => (string)$pollId, 'choice' => (string)$choice]);
        return $this->verifyApiResponse($res, "Voting in Guild poll PID {$pollId}");
    }

    public function createGuildPoll(string $title, array $options): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Creating Guild poll requires an authenticated User session.");
        }
        $url = "https://{$this->domain}/api/guildpollmake";
        $res = $this->request('POST', $url, ['title' => $title, 'options' => json_encode($options)]);
        return $this->verifyApiResponse($res, "Creating Guild poll");
    }

    public function createGuildAnnouncement(string $title, string $text): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Creating Guild announcement requires an authenticated User session.");
        }
        $url = "https://{$this->domain}/api/guildannouncementmake";
        $res = $this->request('POST', $url, ['title' => $title, 'text' => $text]);
        return $this->verifyApiResponse($res, "Creating Guild announcement");
    }

    public function findDuplicatePhotos(mixed $pidOrPhoto): array
    {
        $pid = ($pidOrPhoto instanceof Photo) ? $pidOrPhoto->pid : $pidOrPhoto;
        $url = "https://{$this->domain}/api/similars";

        $res = $this->request('POST', $url, ['pid' => (string)$pid]);
        $data = json_decode($res['body'], true);

        $matches = [];
        if (is_array($data)) {
            if (array_is_list($data)) {
                foreach ($data as $item) {
                    if (is_array($item) && count($item) >= 2 && $item[0] === 'tdata') {
                        $matches = $item[1]['duplicates'] ?? [];
                        break;
                    }
                }
            } else {
                $matches = $data['duplicates'] ?? [];
            }
        }

        return is_array($matches) ? $matches : [];
    }

    public function fetchImdbData(mixed $imdbIdOrCid): array
    {
        $url = "https://{$this->domain}/api/imdb_fetch";
        $res = $this->request('POST', $url, ['cid' => (string)$imdbIdOrCid]);
        return json_decode($res['body'], true) ?: [];
    }

    public function closeAccount(bool $confirm = false): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Closing account requires an authenticated User session.");
        }
        if (!$confirm) {
            throw new InvalidArgumentException("Must explicitly pass confirm=true to close account.");
        }

        $url = "https://{$this->domain}/api/closeaccount";
        $res = $this->request('POST', $url);
        return $this->verifyApiResponse($res, "Closing account");
    }

    public function uploadPhoto(mixed $cidOrGallery, mixed $filePathOrBytes, ?string $fileName = null): array
    {
        if ($this->isGuest) {
            throw new AuthenticationException("Uploading photos requires an authenticated User session.");
        }
        $cid = ($cidOrGallery instanceof Gallery) ? $cidOrGallery->cid : $cidOrGallery;
        $url = "https://{$this->domain}/api/upload";

        $fields = ['cid' => (string)$cid];
        if (is_string($filePathOrBytes) && file_exists($filePathOrBytes)) {
            $fname = $fileName ?? basename($filePathOrBytes);
            $fields['file'] = new CURLFile($filePathOrBytes, 'image/jpeg', $fname);
        } else {
            $tmpFile = sys_get_temp_dir() . '/upload_' . md5(uniqid(rand(), true)) . '.jpg';
            file_put_contents($tmpFile, $filePathOrBytes);
            $fname = $fileName ?? 'upload.jpg';
            $fields['file'] = new CURLFile($tmpFile, 'image/jpeg', $fname);
        }

        $res = $this->request('POST', $url, $fields);
        return $this->verifyApiResponse($res, "Uploading photo for CID {$cid}");
    }

    public function uploadHandPhoto(
        mixed $cidOrGallery,
        mixed $filePathOrBytes,
        string $source = "social",
        string $sourceInfo = "Social media post source",
        ?string $fileName = null
    ): array {
        if ($this->isGuest) {
            throw new AuthenticationException("Uploading hand photos requires an authenticated User session.");
        }

        $validSources = ["social", "video", "stock", "artist", "celeb", "other"];
        $srcClean = strtolower(trim($source));
        if (!in_array($srcClean, $validSources, true)) {
            throw new InvalidArgumentException("Invalid hand upload source '{$source}'.");
        }
        if (strlen(trim($sourceInfo)) < 10) {
            throw new InvalidArgumentException("sourceInfo description must be at least 10 characters long.");
        }

        $cid = ($cidOrGallery instanceof Gallery) ? $cidOrGallery->cid : $cidOrGallery;
        $url = "https://{$this->domain}/api/handupload";

        $fields = [
            'cid' => (string)$cid,
            'source' => $srcClean,
            'sinfo' => trim($sourceInfo)
        ];

        if (is_string($filePathOrBytes) && file_exists($filePathOrBytes)) {
            $fname = $fileName ?? basename($filePathOrBytes);
            $fields['file'] = new CURLFile($filePathOrBytes, 'image/jpeg', $fname);
        } else {
            $tmpFile = sys_get_temp_dir() . '/handupload_' . md5(uniqid(rand(), true)) . '.jpg';
            file_put_contents($tmpFile, $filePathOrBytes);
            $fname = $fileName ?? 'handupload.jpg';
            $fields['file'] = new CURLFile($tmpFile, 'image/jpeg', $fname);
        }

        $res = $this->request('POST', $url, $fields);
        return $this->verifyApiResponse($res, "Uploading hand photo for CID {$cid}");
    }
}
