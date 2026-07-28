<?php

namespace WikiFeetSDK\Models;

use WikiFeetSDK\WikiFeetClient;
use InvalidArgumentException;

/**
 * Represents a hand photo in a celebrity's hands gallery.
 */
class HandPhoto
{
    private array $data;
    private ?WikiFeetClient $client;
    private ?array $extendedDetails = null;

    public int $pid;
    public int $width;
    public int $height;
    public int $gid;
    public int $best;
    public PhotoTags $tags;
    public string $reported;
    public int $removed;

    public function __construct(array $data, ?WikiFeetClient $client = null)
    {
        $this->data = $data;
        $this->client = $client;

        $this->pid = (int)($data['pid'] ?? 0);
        $this->width = (int)($data['pw'] ?? 0);
        $this->height = (int)($data['ph'] ?? 0);
        $this->gid = (int)($data['gid'] ?? 0);
        $this->best = (int)($data['best'] ?? 0);

        $rawTags = (string)($data['tags'] ?? '');
        $this->tags = new PhotoTags($this, $rawTags, $client);

        $this->reported = (string)($data['reported'] ?? '0');
        $this->removed = (int)($data['removed'] ?? 0);
    }

    public function getClient(): ?WikiFeetClient
    {
        return $this->client;
    }

    public function getImageUrl(): string
    {
        return "https://pics.wikifeet.com/{$this->pid}.jpg";
    }

    public function fetchDetails(?WikiFeetClient $client = null): array
    {
        if ($this->extendedDetails !== null) {
            return $this->extendedDetails;
        }

        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            return ['uploaded_by' => null, 'upload_date' => null, 'reported_by' => null];
        }

        $details = $activeClient->fetchHandExtendedDetails($this->pid);
        $this->extendedDetails = $details;
        return $details;
    }

    public function getUploadedBy(?WikiFeetClient $client = null): ?string
    {
        return $this->fetchDetails($client)['uploaded_by'] ?? null;
    }

    public function getUploadDate(?WikiFeetClient $client = null): ?string
    {
        return $this->fetchDetails($client)['upload_date'] ?? null;
    }

    public function getReportedBy(?WikiFeetClient $client = null): ?string
    {
        return $this->fetchDetails($client)['reported_by'] ?? null;
    }

    public function report(?WikiFeetClient $client = null, string $reason = ""): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to report a hand photo.");
        }
        return $activeClient->reportHandPhoto($this, $reason);
    }
}
