<?php

namespace WikiFeetSDK\Models;

use WikiFeetSDK\WikiFeetClient;
use InvalidArgumentException;

/**
 * Object-oriented wrapper around WikiFeet celebrity tdata.
 */
class Gallery
{
    private array $tdata;
    private ?WikiFeetClient $client;
    private ?array $handsCache = null;

    public string $cname;
    public int $cid;
    public int $gender;
    public ?string $birthPlace;
    public ?string $birthDate;
    public ?string $heightUs;
    public mixed $shoeSize;
    public float $score;
    public RatingBreakdown $ratingBreakdown;
    public array $photos = [];
    public array $comments = [];
    public bool $hasMoreComments = false;
    public array $reports = [];
    public array $theme = [];

    public function __construct(array $tdata, ?WikiFeetClient $client = null)
    {
        $this->tdata = $tdata;
        $this->client = $client;

        $this->cname = (string)($tdata['cname'] ?? '');
        $this->cid = (int)($tdata['cid'] ?? 0);
        $this->gender = (int)($tdata['gender'] ?? 0);
        $this->birthPlace = $tdata['bplace'] ?? null;
        $this->birthDate = $tdata['bdate'] ?? null;
        $this->heightUs = $tdata['height_us'] ?? null;
        $this->shoeSize = $tdata['ssize'] ?? null;
        $this->score = (float)($tdata['score'] ?? 0.0);

        $this->ratingBreakdown = new RatingBreakdown($this->score, $tdata['edata'] ?? null);

        $rawGallery = $tdata['gallery'] ?? [];
        if (is_array($rawGallery)) {
            foreach ($rawGallery as $item) {
                if (is_array($item)) {
                    $this->photos[] = new Photo($item, $client);
                }
            }
        }

        $rawCommentsObj = $tdata['comments'] ?? [];
        if (is_array($rawCommentsObj) && isset($rawCommentsObj['threads'])) {
            $rawThreads = $rawCommentsObj['threads'];
            $this->hasMoreComments = !empty($rawCommentsObj['more']);
        } elseif (is_array($rawCommentsObj)) {
            $rawThreads = $rawCommentsObj;
            $this->hasMoreComments = false;
        } else {
            $rawThreads = [];
            $this->hasMoreComments = false;
        }

        if (is_array($rawThreads)) {
            foreach ($rawThreads as $t) {
                if (is_array($t)) {
                    $this->comments[] = new Comment($t, $client);
                }
            }
        }

        $this->reports = $tdata['reports'] ?? [];
        $this->theme = $tdata['theme'] ?? [];
    }

    public function hasHands(): bool
    {
        return !empty($this->tdata['hashands']);
    }

    public function getHands(?WikiFeetClient $client = null): array
    {
        if ($this->handsCache !== null) {
            return $this->handsCache;
        }

        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("A client session is required to fetch hands gallery.");
        }

        $handsList = $activeClient->getHands($this->cid);
        $this->handsCache = $handsList;
        return $handsList;
    }

    public function rate(int $rank, ?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to rate a celebrity.");
        }
        return $activeClient->rateCelebrity($this, $rank);
    }

    public function favorite(?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to favorite a celebrity.");
        }
        return $activeClient->toggleFavorite($this);
    }

    public function ignore(?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to ignore a celebrity.");
        }
        return $activeClient->ignoreCelebrity($this);
    }

    public function setAlerts(bool $subPhotos = true, bool $subThreads = true, ?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to set alert subscriptions.");
        }
        return $activeClient->setCelebrityAlerts($this, $subPhotos, $subThreads);
    }

    public function postComment(string $message, mixed $photoPid = null, ?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to post a comment.");
        }
        return $activeClient->postComment($this->cname, $message, $photoPid);
    }

    public function uploadPhoto(mixed $filePathOrBytes, ?string $fileName = null, ?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to upload photos.");
        }
        return $activeClient->uploadPhoto($this, $filePathOrBytes, $fileName);
    }

    public function uploadHandPhoto(
        mixed $filePathOrBytes,
        string $source = "social",
        string $sourceInfo = "Social media post source",
        ?string $fileName = null,
        ?WikiFeetClient $client = null
    ): array {
        $activeClient = $client ?? $this->client;
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to upload hand photos.");
        }
        return $activeClient->uploadHandPhoto($this, $filePathOrBytes, $source, $sourceInfo, $fileName);
    }

    public function getTotalVotes(): int
    {
        return $this->ratingBreakdown->getTotalVotes();
    }

    public function getPhotoCount(): int
    {
        return count($this->photos);
    }
}
