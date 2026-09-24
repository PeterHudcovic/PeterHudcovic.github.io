<?php
declare(strict_types=1);
// Documents, password hashes and rate limits live outside the web root.
const CV_PRIVATE = '/var/tmp/peterhudcovic-cv';
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
header('X-Robots-Tag: noindex, noarchive');
function fail_request(int $status) {
    http_response_code($status);
    if ($status === 429) header('Retry-After: 900');
    exit;
}
if ($_SERVER['REQUEST_METHOD'] !== 'POST') fail_request(404);
if (!in_array($_SERVER['HTTP_ORIGIN'] ?? '', ['https://peterhudcovic.tech', 'https://www.peterhudcovic.tech'], true)) fail_request(403);
if (($_SERVER['CONTENT_TYPE'] ?? '') !== 'application/json') fail_request(400);
if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 1024) fail_request(400);
$input = json_decode(file_get_contents('php://input', false, null, 0, 1025), true);
if (!is_array($input) || !is_string($input['code'] ?? null) || strlen($input['code']) < 1 || strlen($input['code']) > 128) fail_request(400);
$config = @file_get_contents(CV_PRIVATE . '/config.json');
if ($config === false) fail_request(503);
$records = json_decode($config, true);
if (!is_array($records) || count($records) !== 3) fail_request(503);
$lock = @fopen(CV_PRIVATE . '/attempts.json', 'c+');
if (!$lock || !flock($lock, LOCK_EX | LOCK_NB)) fail_request(503);
$attempts = json_decode(stream_get_contents($lock), true) ?: [];
$now = time();
foreach ($attempts as $key => $value) if ($value['start'] < $now - 900) unset($attempts[$key]);
// Use Apache's connection address, never an untrusted forwarding header.
$client = hash('sha256', $_SERVER['REMOTE_ADDR'] ?? 'unknown');
$entry = $attempts[$client] ?? ['start' => $now, 'count' => 0];
if ($entry['count'] >= 10 || count($attempts) >= 10000) fail_request(429);
$entry['count']++;
$attempts[$client] = $entry;
rewind($lock);
ftruncate($lock, 0);
fwrite($lock, json_encode($attempts));
fflush($lock);
$match = null;
foreach ($records as $record) {
    if (password_verify($input['code'], $record['hash'])) $match = $record['file'];
}
flock($lock, LOCK_UN);
fclose($lock);
if ($match === null) fail_request(403);
// Configured filenames are also allowlisted; input never controls a path.
if (!in_array($match, ['document-0.pdf', 'document-1.pdf', 'document-2.pdf'], true)) fail_request(503);
$file = CV_PRIVATE . '/' . $match;
if (!is_readable($file)) fail_request(503);
header('Content-Type: application/pdf');
header('Content-Disposition: attachment; filename="Peter_Hudcovic_CV.pdf"');
header('Content-Length: ' . filesize($file));
readfile($file);
