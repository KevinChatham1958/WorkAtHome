<?php
// Comments form handler for sidehustleintel.org/comments/ (added Nov 23, 2026).
// Emails each comment to the site's public contact address and also appends it
// to a backup log OUTSIDE the public web folder (/home/<account>/sidehustle-comments.log),
// so nothing is lost if email delivery fails. Nothing is published on the site.

header('X-Robots-Tag: noindex');
$wantsJson = isset($_SERVER['HTTP_ACCEPT']) && strpos($_SERVER['HTTP_ACCEPT'], 'application/json') !== false;

function reply($ok, $error = '') {
    global $wantsJson;
    if ($wantsJson) {
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode($ok ? array('ok' => true) : array('ok' => false, 'error' => $error));
    } else if ($ok) {
        header('Location: /comments/?sent=1', true, 303);
    } else {
        header('Content-Type: text/html; charset=utf-8');
        echo '<p>' . htmlspecialchars($error) . ' <a href="/comments/">Go back</a></p>';
    }
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') { header('Location: /comments/', true, 303); exit; }

$clean = function ($k, $max) {
    $v = isset($_POST[$k]) ? (string)$_POST[$k] : '';
    $v = str_replace("\0", '', $v);
    return mb_substr(trim($v), 0, $max);
};
$topic   = preg_replace('/[\r\n]+/', ' ', $clean('topic', 60));
$message = $clean('message', 5000);
$name    = preg_replace('/[\r\n]+/', ' ', $clean('name', 100));
$email   = preg_replace('/[\r\n]+/', '', $clean('email', 200));
$suggest = preg_replace('/[\r\n]+/', ' ', $clean('suggest', 300));
$trap    = $clean('website', 200);
$t       = (int)$clean('t', 20);

// Spam checks: hidden field filled, sent within 3 seconds of loading, or full of links.
// Bots get a quiet "ok" so they don't retry.
if ($trap !== '') reply(true);
if ($t > 0 && (microtime(true) * 1000 - $t) < 3000) reply(true);
if (preg_match_all('#https?://#i', $message) > 3) reply(true);

if (mb_strlen($message) < 2 && $suggest === '') reply(false, 'Please write a comment first.');
if ($email !== '' && !filter_var($email, FILTER_VALIDATE_EMAIL)) reply(false, 'That email address doesn\'t look right.');
if ($topic === '') $topic = 'General comment';

$when = gmdate('Y-m-d H:i') . ' UTC';
$body = "Topic: $topic\nName: " . ($name !== '' ? $name : '(not given)') .
        "\nEmail: " . ($email !== '' ? $email : '(not given)') .
        "\nSent: $when\n" .
        ($suggest !== '' ? "Suggested video or creator: $suggest\n" : '') . "\n$message\n";

// Backup log outside the public folder.
$log = dirname(__DIR__, 2) . '/sidehustle-comments.log';
@file_put_contents($log, json_encode(array('when' => $when, 'topic' => $topic, 'name' => $name,
    'email' => $email, 'suggest' => $suggest, 'message' => $message), JSON_UNESCAPED_UNICODE) . "\n", FILE_APPEND | LOCK_EX);

$to = 'website@sidehustleintel.org';
$subject = '=?UTF-8?B?' . base64_encode('Site comment: ' . $topic) . '?=';
$headers = "From: Side Hustle Intel <website@sidehustleintel.org>\r\n" .
           "Content-Type: text/plain; charset=UTF-8\r\n";
if ($email !== '') $headers .= "Reply-To: $email\r\n";
$sent = @mail($to, $subject, $body, $headers, '-fwebsite@sidehustleintel.org');

// If mail failed but the backup log was written, the comment is still saved.
if (!$sent && !is_file($log)) reply(false, 'Sorry, your comment could not be sent.');
reply(true);
