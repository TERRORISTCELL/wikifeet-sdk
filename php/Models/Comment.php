<?php

namespace WikiFeetSDK\Models;

use WikiFeetSDK\WikiFeetClient;
use InvalidArgumentException;

/**
 * Represents a comment thread and nested replies.
 */
class Comment
{
    private array $data;
    private ?WikiFeetClient $client;

    public int $idx;
    public int $midx;
    public string $text;
    public string $author;
    public string $userTitle;
    public int $userId;
    public int $status;
    public int $likes;
    public int $likeCount;
    public ?int $userVote = null;
    public string $timestamp;
    public ?int $photoPid = null;
    public array $replies = [];

    public function __construct(array $data, ?WikiFeetClient $client = null)
    {
        $this->data = $data;
        $this->client = $client;

        $this->idx = (int)($data['idx'] ?? 0);
        $this->midx = (int)($data['midx'] ?? 0);
        $this->text = (string)($data['comment'] ?? '');
        $this->author = (string)($data['nickname'] ?? 'N/A');
        $this->userTitle = (string)($data['title'] ?? '');
        $this->userId = (int)($data['uid'] ?? 0);
        $this->status = (int)($data['status'] ?? 0);
        $this->likes = (int)($data['likes'] ?? 0);
        $this->likeCount = $this->likes;

        if (isset($data['likepart']) && $data['likepart'] !== null) {
            $this->userVote = (int)$data['likepart'];
        }

        $this->timestamp = (string)($data['timestamp'] ?? '');

        if (isset($data['value']) && is_numeric($data['value'])) {
            $this->photoPid = (int)$data['value'];
        }

        $rawReplies = $data['replies'] ?? [];
        if (is_array($rawReplies)) {
            foreach ($rawReplies as $r) {
                if (is_array($r)) {
                    $this->replies[] = new self($r, $client);
                }
            }
        }
    }

    public function isApproved(): bool
    {
        return $this->status === 1;
    }

    public function isPending(): bool
    {
        return $this->status === 0;
    }

    public function isLikedByUser(): bool
    {
        return $this->userVote === 1;
    }

    public function isDislikedByUser(): bool
    {
        return $this->userVote === -1;
    }

    public function like(WikiFeetClient $client): array
    {
        return $client->likeComment($this);
    }

    public function dislike(WikiFeetClient $client): array
    {
        return $client->dislikeComment($this);
    }

    public function retractVote(WikiFeetClient $client): array
    {
        return $client->retractCommentVote($this);
    }

    public function report(?WikiFeetClient $client = null, string $reason = ""): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to report a comment.");
        }
        return $activeClient->reportComment($this, $reason);
    }

    public function flag(?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to flag a comment.");
        }
        return $activeClient->flagComment($this);
    }
}
