<?php

namespace WikiFeetSDK\Exceptions;

/**
 * Raised when a WikiFeet API request fails.
 */
class APIException extends WikiFeetException
{
    public ?int $statusCode;
    public mixed $responseData;

    public function __construct(string $message, ?int $statusCode = null, mixed $responseData = null)
    {
        parent::__construct($message);
        $this->statusCode = $statusCode;
        $this->responseData = $responseData;
    }
}
