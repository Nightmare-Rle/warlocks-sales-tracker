<?php
/**
 * Shared helpers: JSON responses, input parsing, auth, hashing.
 */
require_once __DIR__ . '/db.php';

/** Send a JSON response and stop. */
function respond(int $status, $data): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

/** Respond 500 with a stable message (log real error to server log). */
function respond_error(Throwable $e): void
{
    error_log('[sales-tracker] ' . $e->getMessage());
    respond(500, ['error' => 'Server error', 'detail' => $e->getMessage()]);
}

/** Read JSON body (or form data). */
function body(): array
{
    $raw = file_get_contents('php://input');
    $json = json_decode($raw, true);
    if (is_array($json)) {
        return $json;
    }
    return $_POST;
}

/** Merkle root over a list of leaf hashes. */
function merkle_root(array $hashes): string
{
    $n = count($hashes);
    if ($n === 0) {
        return '';
    }
    if ($n === 1) {
        return $hashes[0];
    }
    $next = [];
    for ($i = 0; $i < $n; $i += 2) {
        $a = $hashes[$i];
        $b = $hashes[$i + 1] ?? $a; // duplicate last for odd counts
        $next[] = hash('sha256', $a . $b);
    }
    return merkle_root($next);
}

/** Canonical sale line fingerprint used for transparency (all-integer). */
function hash_sale_line(string $receipt_no, ?int $product_id, string $product_name,
                        int $price_cents, int $quantity, int $subtotal_cents,
                        string $sale_time, ?int $cashier_id, int $sale_id): string
{
    $canonical = implode('|', [
        $receipt_no,
        $product_id === null ? '' : (string)$product_id,
        strtoupper($product_name),
        (string)$price_cents,
        (string)$quantity,
        (string)$subtotal_cents,
        $sale_time,
        $cashier_id === null ? '' : (string)$cashier_id,
        (string)$sale_id,
    ]);
    return hash('sha256', $canonical);
}

/* ------------------------------------------------------------------ */
/* Money: pesos <-> integer centavos (no floats, no rounding drift)     */
/* ------------------------------------------------------------------ */

/** "30.00" | 30 | "30.5" | 55.50 -> integer centavos. */
function peso_to_cents($value): int
{
    if (is_int($value)) {
        return $value * 100;
    }
    $s = trim((string)$value);
    if ($s === '') {
        return 0;
    }
    $neg = (strncmp($s, '-', 1) === 0);
    if ($neg) {
        $s = substr($s, 1);
    }
    if (!preg_match('/^\d+(\.\d{1,2})?$/', $s)) {
        // Unusual input: normalise via decimal formatting, still exact to 2dp.
        $s = number_format((float)$s, 2, '.', '');
    }
    $parts = array_pad(explode('.', $s, 2), 2, '');
    $frac = str_pad(substr($parts[1], 0, 2), 2, '0');
    $cents = (int)$parts[0] * 100 + (int)$frac;
    return $neg ? -$cents : $cents;
}

/** integer centavos -> "30.00" (string, never a float). */
function cents_to_peso(int $cents): string
{
    $neg = $cents < 0;
    $c = abs($cents);
    return ($neg ? '-' : '') . intdiv($c, 100) . '.' . str_pad((string)($c % 100), 2, '0', STR_PAD_LEFT);
}

/**
 * Atomically reserve the next receipt sequence for a day.
 * Must be called inside the sale transaction so a rollback also rolls back
 * the counter (no gaps). Returns the new sequence number.
 */
function receipt_next_seq(PDO $pdo, string $day): int
{
    $st = $pdo->prepare(
        'INSERT INTO receipt_counters (day, seq) VALUES (?, LAST_INSERT_ID(1))
         ON DUPLICATE KEY UPDATE seq = LAST_INSERT_ID(seq + 1)'
    );
    $st->execute([$day]);
    return (int)$pdo->lastInsertId();
}

/* ------------------------------------------------------------------ */
/* Auth                                                                */
/* ------------------------------------------------------------------ */

/** Resolve the current user from the Bearer token, or null. */
function current_user(): ?array
{
    static $user = false;
    if ($user !== false) {
        return $user;
    }

    $auth = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
    $token = null;
    if (preg_match('/^Bearer\s+([a-f0-9]{64})$/i', trim($auth), $m)) {
        $token = $m[1];
    } elseif (!empty($_GET['token'])) {
        $token = preg_replace('/[^a-f0-9]/i', '', (string)$_GET['token']);
    }

    if (!$token) {
        $user = null;
        return null;
    }

    $pdo = db();
    $st = $pdo->prepare(
        'SELECT u.id, u.username, u.role FROM sessions s
         JOIN users u ON u.id = s.user_id
         WHERE s.token = :t AND s.expires_at > NOW() LIMIT 1'
    );
    $st->execute([':t' => $token]);
    $user = $st->fetch() ?: null;
    return $user;
}

/** Require an authenticated user; returns it. */
function require_login(): array
{
    $u = current_user();
    if (!$u) {
        respond(401, ['error' => 'Not authenticated']);
    }
    return $u;
}

/** Require the owner role. */
function require_owner(): array
{
    $u = require_login();
    if ($u['role'] !== 'owner') {
        respond(403, ['error' => 'Owner access required']);
    }
    return $u;
}

/** Check ANCHOR_SECRET for the cron worker confirmation call. */
function require_anchor_secret(): void
{
    $given = $_SERVER['HTTP_X_ANCHOR_SECRET'] ?? ($_GET['secret'] ?? null);
    if (!$given || !hash_equals(ANCHOR_SECRET, (string)$given)) {
        respond(403, ['error' => 'Invalid anchor secret']);
    }
}

function login_user(int $userId): string
{
    $pdo = db();
    $token = bin2hex(random_bytes(32));
    $expires = date('Y-m-d H:i:s', time() + SESSION_TTL_HOURS * 3600);
    $st = $pdo->prepare('INSERT INTO sessions (user_id, token, expires_at) VALUES (?,?,?)');
    $st->execute([$userId, $token, $expires]);
    return $token;
}

function logout_token(string $token): void
{
    $pdo = db();
    $st = $pdo->prepare('DELETE FROM sessions WHERE token = ?');
    $st->execute([$token]);
}