<?php

namespace WikiFeetSDK\Models;

use WikiFeetSDK\WikiFeetClient;
use InvalidArgumentException;

/**
 * Represents User private message inbox and archived threads.
 */
class Inbox
{
    private array $tdata;
    private ?WikiFeetClient $client;

    public array $threads = [];
    public array $archived = [];

    public function __construct(array $tdata, ?WikiFeetClient $client = null)
    {
        $this->tdata = $tdata;
        $this->client = $client;

        $rawInbox = $tdata['inbox'] ?? [];
        if (is_array($rawInbox)) {
            foreach ($rawInbox as $item) {
                if (is_array($item)) {
                    $this->threads[] = new MessageThread($item, $client);
                }
            }
        }

        $rawArchived = $tdata['archived'] ?? [];
        if (is_array($rawArchived)) {
            foreach ($rawArchived as $item) {
                if (is_array($item)) {
                    $this->archived[] = new MessageThread($item, $client);
                }
            }
        }
    }

    public function sendMessage(mixed $toUid, string $text, ?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to send private messages.");
        }
        return $activeClient->sendPrivateMessage($toUid, $text);
    }

    public function archiveAll(?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to archive messages.");
        }
        return $activeClient->archiveAllMessages();
    }
}
