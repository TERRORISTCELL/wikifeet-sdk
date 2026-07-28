<?php

namespace WikiFeetSDK\Exceptions;

/**
 * Raised when an action requiring a logged-in User is called in Guest mode.
 */
class AuthenticationException extends WikiFeetException {}
