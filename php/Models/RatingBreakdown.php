<?php

namespace WikiFeetSDK\Models;

/**
 * Represents rating score and star vote distributions.
 */
class RatingBreakdown
{
    public float $score;
    public array $stats = [];

    public function __construct(float $score, ?array $edata = null)
    {
        $this->score = $score;
        if ($edata && isset($edata['stats']) && is_array($edata['stats'])) {
            foreach ($edata['stats'] as $k => $v) {
                $this->stats[(string)$k] = (int)$v;
            }
        }
    }

    public function getOneStar(): int
    {
        return $this->stats['1'] ?? 0;
    }

    public function getTwoStar(): int
    {
        return $this->stats['2'] ?? 0;
    }

    public function getThreeStar(): int
    {
        return $this->stats['3'] ?? 0;
    }

    public function getFourStar(): int
    {
        return $this->stats['4'] ?? 0;
    }

    public function getFiveStar(): int
    {
        return $this->stats['5'] ?? 0;
    }

    public function getTotalVotes(): int
    {
        return array_sum($this->stats);
    }
}
