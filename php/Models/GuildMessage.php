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
    public string $timestamp;
    public string $userTitle;

    public function __construct(array $data)
    {
        $this->idx = (int)($data['idx'] ?? 0);
        $this->userId = (int)($data['uid'] ?? 0);
        $this->author = (string)($data['nickname'] ?? $data['author'] ?? 'Anonymous');
        $this->text = (string)($data['message'] ?? $data['comment'] ?? '');
        $this->timestamp = (string)($data['timestamp'] ?? '');
        $this->userTitle = (string)($data['title'] ?? '');
    }
}
