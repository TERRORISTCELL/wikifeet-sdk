<?php

namespace WikiFeetSDK\Models;

use WikiFeetSDK\WikiFeetClient;
use InvalidArgumentException;

/**
 * Fluent tag manager for Photo objects.
 */
class PhotoTags
{
    private mixed $photo;
    private ?WikiFeetClient $client;
    public string $rawString;
    private array $pending = [];

    public const TAG_MAPPING = [
        'C' => 'close_up',
        'N' => 'nylons',
        'S' => 'soles',
        'B' => 'barefoot',
        'T' => 'toes',
        'A' => 'arches',
    ];

    public const TAG_NAME_TO_CODE = [
        'c' => 'C', 'close_up' => 'C', 'close-up' => 'C', 'closeup' => 'C', 'close' => 'C',
        'n' => 'N', 'nylons' => 'N', 'nylon' => 'N',
        's' => 'S', 'soles' => 'S', 'sole' => 'S',
        'b' => 'B', 'barefoot' => 'B',
        't' => 'T', 'toes' => 'T', 'toe' => 'T',
        'a' => 'A', 'arches' => 'A', 'arch' => 'A'
    ];

    public function __construct(mixed $photo, string $rawTags = '', ?WikiFeetClient $client = null)
    {
        $this->photo = $photo;
        $this->rawString = $rawTags;
        $this->client = $client;
    }

    public function isActiveCode(string $code): bool
    {
        if (array_key_exists($code, $this->pending)) {
            return (bool)$this->pending[$code];
        }
        return str_contains($this->rawString, $code);
    }

    public function setPending(string $code, bool $value): void
    {
        $this->pending[$code] = $value;
    }

    public function closeUp(bool $value = true): self
    {
        $this->setPending('C', $value);
        return $this;
    }

    public function nylons(bool $value = true): self
    {
        $this->setPending('N', $value);
        return $this;
    }

    public function soles(bool $value = true): self
    {
        $this->setPending('S', $value);
        return $this;
    }

    public function barefoot(bool $value = true): self
    {
        $this->setPending('B', $value);
        return $this;
    }

    public function toes(bool $value = true): self
    {
        $this->setPending('T', $value);
        return $this;
    }

    public function arches(bool $value = true): self
    {
        $this->setPending('A', $value);
        return $this;
    }

    public function raw(): string
    {
        $activeCodes = [];
        foreach (['C', 'N', 'S', 'B', 'T', 'A'] as $code) {
            if ($this->isActiveCode($code)) {
                $activeCodes[] = $code;
            }
        }
        return implode('', $activeCodes);
    }

    public function list(): array
    {
        $active = [];
        foreach (['C', 'N', 'S', 'B', 'T', 'A'] as $code) {
            if ($this->isActiveCode($code) && isset(self::TAG_MAPPING[$code])) {
                $active[] = self::TAG_MAPPING[$code];
            }
        }
        return $active;
    }

    public static function normalizeTag(string $tag): string
    {
        $cleaned = strtolower(trim($tag));
        if (isset(self::TAG_NAME_TO_CODE[$cleaned])) {
            return self::TAG_NAME_TO_CODE[$cleaned];
        }
        $upper = strtoupper(trim($tag));
        if (isset(self::TAG_MAPPING[$upper])) {
            return $upper;
        }
        throw new InvalidArgumentException("Unknown tag '{$tag}'.");
    }

    public function has(string $tag): bool
    {
        $code = self::normalizeTag($tag);
        return $this->isActiveCode($code);
    }

    public function commit(?WikiFeetClient $client = null): array
    {
        $activeClient = $client ?? $this->client ?? $this->photo->getClient();
        if (!$activeClient) {
            throw new InvalidArgumentException("An authenticated client session is required to commit tag changes.");
        }

        if (empty($this->pending)) {
            return ['pid' => $this->photo->pid, 'tags' => $this->rawString, 'updated' => 0];
        }

        $results = [];
        foreach ($this->pending as $code => $value) {
            $valInt = $value ? 1 : 0;
            $res = $activeClient->tagPhoto($this->photo, $code, $valInt);
            $results[$code] = $res;
        }

        $this->pending = [];
        return ['pid' => $this->photo->pid, 'tags' => $this->rawString, 'updated' => count($results)];
    }
}
