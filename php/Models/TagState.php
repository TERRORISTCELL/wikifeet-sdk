<?php

namespace WikiFeetSDK\Models;

/**
 * Represents a single tag state on a photo with chainable syntax.
 */
class TagState
{
    private PhotoTags $manager;
    private string $code;
    private string $name;

    public function __construct(PhotoTags $manager, string $code, string $name)
    {
        $this->manager = $manager;
        $this->code = $code;
        $this->name = $name;
    }

    public function __invoke(bool $value = true): PhotoTags
    {
        $this->manager->setPending($this->code, $value);
        return $this->manager;
    }

    public function isActive(): bool
    {
        return $this->manager->isActiveCode($this->code);
    }
}
