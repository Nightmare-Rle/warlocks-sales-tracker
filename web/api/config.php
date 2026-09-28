<?php
/**
 * Warlocks Sales Tracker - API configuration.
 *
 * EDIT THIS FILE with your MonsterASP (or hosting) MySQL credentials
 * after importing schema.sql.
 *
 * SECURITY NOTES:
 *  - Never expose config.php over the web. Keep it in api/ and make sure
 *    your host blocks direct access to *.php config files (or move it
 *    above the public root if possible).
 *  - ANCHOR_SECRET is a shared password that lets the Python signer
 *    worker confirm on-chain anchors. Generate a long random string.
 */

// ---- Database ----
// Environment variables (ST_DB_*) override these - handy for local testing
// and for hosts that let you set env vars instead of editing files.
define('DB_HOST', getenv('ST_DB_HOST') ?: 'localhost');
define('DB_PORT', getenv('ST_DB_PORT') ?: '3306');
define('DB_NAME', getenv('ST_DB_NAME') ?: 'sales_tracker');
define('DB_USER', getenv('ST_DB_USER') ?: 'root');
define('DB_PASS', getenv('ST_DB_PASS') !== false ? getenv('ST_DB_PASS') : '');

// ---- App ----
define('APP_NAME', 'Warlocks Sales Tracker');
// Base URL where the API lives WITHOUT a trailing slash.
// e.g. 'https://yourdomain.com/web/api' or 'https://yourdomain.com/api'
define('APP_BASE_URL', getenv('ST_APP_BASE_URL') ?: 'https://yourdomain.com/web/api');

// ---- Security ---- (see above)
define('ANCHOR_SECRET', getenv('ST_ANCHOR_SECRET') ?: 'CHANGE_ME_to_a_long_random_string');

// Session lifetime in hours
define('SESSION_TTL_HOURS', 12);

// Timezone (Philippines). Keep UTC in DB is fine too, but PHT is simpler
// for a local shop. If you change this, the daily cron anchor boundary
// shifts with it.
date_default_timezone_set('Asia/Manila');

// Force HTTPS for token auth (disable only on a local test box)
define('REQUIRE_HTTPS', false);

if (REQUIRE_HTTPS && (!isset($_SERVER['HTTPS']) || $_SERVER['HTTPS'] !== 'on') && $_SERVER['SERVER_NAME'] !== 'localhost') {
    http_response_code(403);
    exit(json_encode(['error' => 'HTTPS required']));
}