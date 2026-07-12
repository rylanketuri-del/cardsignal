// Frontend universal search registry tests.

import { readFileSync } from "node:fs";
import { test } from "node:test";
import assert from "node:assert/strict";

const appJs = readFileSync(new URL("../frontend/app.js", import.meta.url), "utf8");

test("frontend loads registered leagues from API", () => {
  assert.match(appJs, /fetchRegisteredLeagues/);
  assert.match(appJs, /\/api\/leagues/);
});

test("frontend uses generalized player search endpoint", () => {
  assert.match(appJs, /\/api\/players\/search/);
  assert.doesNotMatch(appJs, /\/api\/players\/search\?q=\$\{encodeURIComponent\(query\)\}&league=MLB/);
});

test("frontend routes cs player ids by league", () => {
  assert.match(appJs, /entry\.league/);
  assert.match(appJs, /data-league/);
});

test("frontend safe MLB fallback when leagues API fails", () => {
  assert.match(appJs, /live_status: 'live'/);
});
