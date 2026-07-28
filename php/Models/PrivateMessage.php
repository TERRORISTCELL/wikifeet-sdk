<?php

namespace WikiFeetSDK\Models;

/**
 * Represents a single private message.
 */
class PrivateMessage
{
    public int $idx;
    public int $senderUid;
    public string $author;
    public string $text;
    public string $timestamp;

    public function __construct(array $data)
    {
        $this->idx = (int)($data['idx'] ?? 0);
        $this->senderUid = (int)($data['uid'] ?? 0);
        $this->author = (string)($data['nickname'] ?? $data['author'] ?? 'Anonymous');
        $this->text = (string)($data['message'] ?? $data['comment'] ?? '');
        $this->timestamp = (string)($data['timestamp'] ?? '');
    }
}
