<?php

namespace WikiFeetSDK\Models;

use WikiFeetSDK\WikiFeetClient;
use InvalidArgumentException;

/**
 * Represents a private message conversation thread.
 */
class MessageThread
{
    private array $data;
    private ?WikiFeetClient $client;

    public int $partnerUid;
    public string $partnerName;
    public int $unreadCount;
    public string $lastMessage;
    public string $lastTimestamp;
    public array $messages = [];

    public function __construct(array $data, ?WikiFeetClient $client = null)
    {
        $this->data = $data;
        $this->client = $client;

        $this->partnerUid = (int)($data['uid'] ?? 0);
        $this->partnerName = (string)($data['nickname'] ?? 'Anonymous');
        $this->unreadCount = (int)($data['unread'] ?? 0);
        $this->lastMessage = (string)($data['message'] ?? '');
        $this->lastTimestamp = (string)($data['timestamp'] ?? '');

        $rawMsgs = $data['messages'] ?? $data['chat'] ?? [];
        if (is_array($rawMsgs)) {
            foreach ($rawMsgs as $m) {
                if (is_array($m)) {
                    $this->messages[] = new PrivateMessage($m);
                }
            }
        }
    }

    public function send(string $text, ?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to send private messages.");
        }
        return $activeClient->sendPrivateMessage($this->partnerUid, $text);
    }

    public function fetchMessages(?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to fetch message thread.");
        }

        $threadObj = $activeClient->getMessageThread($this->partnerUid);
        $this->messages = $threadObj->messages;
        return $this->messages;
    }
}
