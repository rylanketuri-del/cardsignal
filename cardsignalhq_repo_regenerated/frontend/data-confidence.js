/**
 * Data Confidence Layer — UI helpers (Sprint 10.0)
 * Evidence quality is independent of BUY/HOLD/SELL recommendations.
 */
(function (global) {
  const EVIDENCE_LEVELS = ["VERY_HIGH", "HIGH", "MEDIUM", "LOW", "INSUFFICIENT"];
  const FRESHNESS_BUCKETS = ["LIVE", "RECENT", "CURRENT", "STALE", "UNKNOWN"];

  function dcNormalizeLevel(level) {
    const key = String(level || "").toUpperCase();
    return EVIDENCE_LEVELS.includes(key) ? key : "INSUFFICIENT";
  }

  function dcNormalizeFreshness(bucket) {
    const key = String(bucket || "").toUpperCase();
    return FRESHNESS_BUCKETS.includes(key) ? key : "UNKNOWN";
  }

  function dcEvidenceClass(level) {
    const key = dcNormalizeLevel(level);
    if (key === "VERY_HIGH" || key === "HIGH") return "dc-badge--evidence-high";
    if (key === "MEDIUM") return "dc-badge--evidence-medium";
    if (key === "LOW") return "dc-badge--evidence-low";
    return "dc-badge--evidence-insufficient";
  }

  function dcFreshnessClass(bucket) {
    const key = dcNormalizeFreshness(bucket);
    if (key === "LIVE") return "dc-badge--freshness-live";
    if (key === "RECENT") return "dc-badge--freshness-recent";
    if (key === "CURRENT") return "dc-badge--freshness-current";
    if (key === "STALE") return "dc-badge--freshness-stale";
    return "dc-badge--freshness-unknown";
  }

  function dcFormatEvidenceLabel(level) {
    return dcNormalizeLevel(level);
  }

  function dcFormatFreshnessLabel(bucket) {
    return dcNormalizeFreshness(bucket);
  }

  function dcFormatRelativeTime(minutes) {
    const n = Number(minutes);
    if (!Number.isFinite(n) || n < 0) return null;
    if (n < 60) return `${Math.round(n)} minute${n === 1 ? "" : "s"} ago`;
    if (n < 24 * 60) {
      const hours = Math.floor(n / 60);
      return `${hours} hour${hours === 1 ? "" : "s"} ago`;
    }
    const days = Math.floor(n / (24 * 60));
    return `${days} day${days === 1 ? "" : "s"} ago`;
  }

  function dcRenderBadge(label, value, className) {
    return `
      <div class="dc-badge-wrap">
        <span class="dc-badge-label">${label}</span>
        <span class="dc-badge ${className}">${value}</span>
      </div>`;
  }

  function dcRenderHeaderBadges(confidencePayload) {
    if (!confidencePayload) return "";
    const conf = confidencePayload.confidence || {};
    const freshness = confidencePayload.freshness || {};
    const evidenceLevel = conf.confidence_level || conf.evidence_level;
    const freshnessBucket = freshness.bucket || conf.freshness_bucket;

    return `
      <div class="dc-header-badges">
        ${dcRenderBadge("Evidence", dcFormatEvidenceLabel(evidenceLevel), dcEvidenceClass(evidenceLevel))}
        ${dcRenderBadge("Freshness", dcFormatFreshnessLabel(freshnessBucket), dcFreshnessClass(freshnessBucket))}
      </div>`;
  }

  function dcRenderTrustSection(confidencePayload) {
    if (!confidencePayload) {
      return `
        <details class="dc-trust">
          <summary class="dc-trust-summary">Why this report?</summary>
          <p class="dc-trust-pending">Evidence summary pending.</p>
        </details>`;
    }

    const trust = confidencePayload.trust_summary || {};
    const verified = trust.verified_using || [];
    const missing = confidencePayload.missing_inputs || [];
    const latestUpdate = trust.latest_update
      || dcFormatRelativeTime(confidencePayload.freshness?.freshness_minutes)
      || "Unknown";

    const verifiedHtml = verified.length
      ? `<ul class="dc-trust-list">${verified.map((item) => `<li><span class="dc-trust-check" aria-hidden="true">✓</span> ${item}</li>`).join("")}</ul>`
      : `<p class="dc-trust-pending">Stored evidence is still building for this report.</p>`;

    const missingHtml = missing.length
      ? `<div class="dc-trust-missing"><p class="dc-trust-missing-label">Evidence gaps</p><ul class="dc-trust-missing-list">${missing.map((m) => `<li>${m}</li>`).join("")}</ul></div>`
      : "";

    return `
      <details class="dc-trust">
        <summary class="dc-trust-summary">Why this report?</summary>
        <div class="dc-trust-body">
          <p class="dc-trust-lead">Verified using:</p>
          ${verifiedHtml}
          <p class="dc-trust-meta"><span class="dc-trust-meta-label">Latest update:</span> ${latestUpdate}</p>
          <p class="dc-trust-meta"><span class="dc-trust-meta-label">Model:</span> ${trust.model || "—"}</p>
          ${missingHtml}
        </div>
      </details>`;
  }

  function dcRenderCardHeaderBadges(confidencePayload) {
    return dcRenderHeaderBadges(confidencePayload);
  }

  global.DataConfidence = {
    dcNormalizeLevel,
    dcNormalizeFreshness,
    dcEvidenceClass,
    dcFreshnessClass,
    dcFormatEvidenceLabel,
    dcFormatFreshnessLabel,
    dcFormatRelativeTime,
    dcRenderBadge,
    dcRenderHeaderBadges,
    dcRenderTrustSection,
    dcRenderCardHeaderBadges,
  };
})(typeof window !== "undefined" ? window : globalThis);
