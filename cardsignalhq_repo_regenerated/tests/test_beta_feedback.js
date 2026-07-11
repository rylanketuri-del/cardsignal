#!/usr/bin/env node
/**
 * Focused tests for beta feedback client behavior.
 * Run: node tests/test_beta_feedback.js
 */
const assert = require("assert");
const fs = require("fs");
const path = require("path");

const betaFeedbackSrc = fs.readFileSync(
  path.join(__dirname, "..", "frontend", "beta-feedback.js"),
  "utf8"
);
const versionSrc = fs.readFileSync(path.join(__dirname, "..", "frontend", "version.js"), "utf8");
const appSrc = fs.readFileSync(path.join(__dirname, "..", "frontend", "app.js"), "utf8");

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed += 1;
    console.log(`  ok ${name}`);
  } catch (err) {
    failed += 1;
    console.error(`  FAIL ${name}`);
    console.error(`       ${err.message}`);
  }
}

console.log("Beta feedback tests");

test("feedback modal includes required fields", () => {
  assert.ok(betaFeedbackSrc.includes('name="feedback_type"'));
  assert.ok(betaFeedbackSrc.includes('id="beta-feedback-message"'));
  assert.ok(betaFeedbackSrc.includes("Sending feedback"));
  assert.ok(betaFeedbackSrc.includes("Thanks — your feedback was sent."));
  assert.ok(betaFeedbackSrc.includes("We couldn't send your feedback"));
});

test("duplicate submit prevention exists", () => {
  assert.ok(betaFeedbackSrc.includes("isSubmitting"));
  assert.ok(betaFeedbackSrc.includes("submitBtn.disabled = true"));
});

test("supabase unavailable shows safe message", () => {
  assert.ok(betaFeedbackSrc.includes("response.status === 503"));
  assert.ok(betaFeedbackSrc.includes("temporarily unavailable"));
});

test("safe metadata capture without tokens", () => {
  assert.ok(betaFeedbackSrc.includes("browser_summary"));
  assert.ok(betaFeedbackSrc.includes("viewport_width"));
  assert.ok(!betaFeedbackSrc.includes("localStorage"));
  assert.ok(!betaFeedbackSrc.includes("access_token"));
});

test("modal keyboard and focus behavior", () => {
  assert.ok(betaFeedbackSrc.includes('event.key === "Escape"'));
  assert.ok(betaFeedbackSrc.includes("trapFocus"));
  assert.ok(betaFeedbackSrc.includes("lastFocusTarget.focus"));
});

test("version config is centralized", () => {
  assert.ok(versionSrc.includes('appVersion: "0.14.1"'));
  assert.ok(appSrc.includes("CARDSIGNAL_VERSION"));
  assert.ok(appSrc.includes("setupVersionFooter"));
});

test("safe error formatter avoids raw backend output", () => {
  assert.ok(appSrc.includes("function formatSafeError"));
  assert.ok(appSrc.includes("stack|traceback"));
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
