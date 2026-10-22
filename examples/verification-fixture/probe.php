<?php
declare(strict_types=1);

if (!extension_loaded('json')) {
    exit(1);
}

echo json_encode(['answer' => 42], JSON_THROW_ON_ERROR), "\n";
