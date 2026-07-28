<?php

namespace WikiFeetSDK\Models;

use WikiFeetSDK\WikiFeetClient;
use InvalidArgumentException;

/**
 * Represents an individual photo in a celebrity gallery.
 */
class Photo
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
    public ?int $similarity;

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
        $this->similarity = isset($data['similarity']) ? (int)$data['similarity'] : null;
    }

    public function getClient(): ?WikiFeetClient
    {
        return $this->client;
    }

    public function getImageUrl(): string
    {
        return "https://pics.wikifeet.com/{$this->pid}.jpg";
    }

    public function isLiked(): bool
    {
        return $this->best > 0;
    }

    public function like(?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to like a photo.");
        }
        return $activeClient->likePhoto($this);
    }

    public function unlike(?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to retract a photo like.");
        }
        return $activeClient->unlikePhoto($this);
    }

    public function report(?WikiFeetClient $client = null, string $reportType = "NO_FEET", mixed $targetPid = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to report a photo.");
        }
        return $activeClient->reportPhoto($this, $reportType, $targetPid);
    }

    public function unreport(?WikiFeetClient $client = null): array
    {
        return $this->report($client, "UNREPORT");
    }

    public function reportNoFeet(?WikiFeetClient $client = null): array
    {
        return $this->report($client, "NO_FEET");
    }

    public function reportDuplicate(mixed $targetPid, ?WikiFeetClient $client = null): array
    {
        return $this->report($client, "DUPLICATE", $targetPid);
    }

    public function reportWrongPerson(?WikiFeetClient $client = null): array
    {
        return $this->report($client, "WRONG_PERSON");
    }

    public function reportLowQuality(?WikiFeetClient $client = null): array
    {
        return $this->report($client, "LOW_QUALITY");
    }

    public function reportFake(?WikiFeetClient $client = null): array
    {
        return $this->report($client, "FAKE");
    }

    public function reportUnderage(?WikiFeetClient $client = null): array
    {
        return $this->report($client, "UNDERAGE");
    }

    public function reportAdultContent(?WikiFeetClient $client = null): array
    {
        return $this->report($client, "ADULT_CONTENT");
    }

    public function scanDuplicates(?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("A client session is required to scan for duplicate photos.");
        }
        return $activeClient->findDuplicatePhotos($this);
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

        $details = $activeClient->fetchExtendedDetails($this->pid);
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
}
