<?php

namespace WikiFeetSDK\Models;

/**
 * Represents a chat message in the WikiFeet Guild chat.
 */
class GuildMessage
{
    public int $idx;
    public int $userId;
    public string $author;
    public string $text;
    public int $avatarId;
    public int $secago;
    public string $timestamp;
    public string $userTitle;
    public ?string $badge;

    public function __construct(array $data)
    {
        $this->idx = (int)($data['idx'] ?? 0);
        $this->userId = (int)($data['uid'] ?? 0);
        $this->author = (string)($data['nickname'] ?? $data['author'] ?? 'Anonymous');
        $this->text = (string)($data['message'] ?? $data['comment'] ?? '');
        $this->avatarId = (int)($data['avatar'] ?? 0);
        $this->secago = (int)($data['secago'] ?? 0);
        $this->timestamp = (string)($data['timestamp'] ?? '');
        $this->userTitle = (string)($data['title'] ?? '');
        $this->badge = $data['badge'] ?? null;
    }

    public function getAvatarUrl(): ?string
    {
        if ($this->avatarId > 0) {
            return "https://wikifeet.com/avatars/{$this->avatarId}.jpg";
        }
        return null;
    }

    public function getFormattedTime(): string
    {
        if ($this->secago <= 0) {
            return !empty($this->timestamp) ? $this->timestamp : "Just now";
        }
        $s = $this->secago;
        if ($s < 60) {
            return "{$s}s ago";
        } elseif ($s < 3600) {
            $m = floor($s / 60);
            return "{$m}m ago";
        } elseif ($s < 86400) {
            $h = floor($s / 3600);
            return "{$h}h ago";
        } else {
            $d = floor($s / 86400);
            return "{$d}d ago";
        }
    }
}
