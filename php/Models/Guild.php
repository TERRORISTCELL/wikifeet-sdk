<?php

namespace WikiFeetSDK\Models;

use WikiFeetSDK\WikiFeetClient;
use InvalidArgumentException;

/**
 * Represents the WikiFeet Guild environment and chat hub.
 */
class Guild
{
    private array $tdata;
    private ?WikiFeetClient $client;

    public bool $isMember;
    public int $unreadCount;
    public array $messages = [];

    public function __construct(array $tdata, ?WikiFeetClient $client = null)
    {
        $this->tdata = $tdata;
        $this->client = $client;

        $this->isMember = !empty($tdata['guild']);
        $this->unreadCount = (int)($tdata['unread'] ?? 0);

        $rawMessages = $tdata['chat'] ?? [];
        if (is_array($rawMessages)) {
            foreach ($rawMessages as $m) {
                if (is_array($m)) {
                    $this->messages[] = new GuildMessage($m);
                }
            }
        }
    }

    public function join(?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to join the Guild.");
        }
        $res = $activeClient->joinGuild();
        $this->isMember = true;
        return $res;
    }

    public function leave(?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to leave the Guild.");
        }
        $res = $activeClient->leaveGuild();
        $this->isMember = false;
        return $res;
    }

    public function quit(?WikiFeetClient $client = null): array
    {
        return $this->leave($client);
    }

    public function getChat(?int $lastIdx = null, ?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to fetch Guild chat.");
        }

        if ($lastIdx === null) {
            $lastIdx = !empty($this->messages) ? end($this->messages)->idx : 0;
        }

        $newMsgs = $activeClient->getGuildChat($lastIdx);
        foreach ($newMsgs as $msg) {
            $this->messages[] = $msg;
        }
        return $newMsgs;
    }

    public function getPhotoBacklog(?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to view photo backlog.");
        }
        return $activeClient->getGuildPhotoBacklog();
    }

    public function getCommentBacklog(?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to view comment backlog.");
        }
        return $activeClient->getGuildCommentBacklog();
    }

    public function votePoll(mixed $pollId, mixed $choice, ?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to vote in a Guild poll.");
        }
        return $activeClient->voteGuildPoll($pollId, $choice);
    }

    public function createPoll(string $title, array $options, ?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to create a Guild poll.");
        }
        return $activeClient->createGuildPoll($title, $options);
    }

    public function createAnnouncement(string $title, string $text, ?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to create a Guild announcement.");
        }
        return $activeClient->createGuildAnnouncement($title, $text);
    }
}
