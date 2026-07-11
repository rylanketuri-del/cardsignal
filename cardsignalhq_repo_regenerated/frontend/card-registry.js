/**
 * Centralized Card Registry — single normalization and formatting path for all card UI.
 *
 * Raw card record → mapCardRecordToIdentity → formatCardIdentityHtml → UI
 */

const CARD_REGISTRY_PENDING = "Registry data pending";

const SUPPORTED_IDENTITY_FIELDS = [
  "year",
  "brand",
  "set",
  "subset",
  "parallel",
  "variation",
  "card_number",
  "grade",
  "grading_company",
  "serial_number",
];

function mapCardRecordToIdentity(card = {}) {
  const source = card.identity || card.registry || card;
  return {
    year: source.card_year ?? source.year ?? null,
    brand: source.brand ?? null,
    set: source.set ?? null,
    subset: source.subset ?? null,
    parallel: source.parallel ?? null,
    variation: source.variation ?? null,
    card_number: source.card_number ?? null,
    grade: source.grade ?? null,
    grading_company: source.grading_company ?? null,
    serial_number: source.serial_number ?? null,
  };
}

function getCardIdentityFields(card = {}) {
  return mapCardRecordToIdentity(card);
}

function hasCardRegistryIdentity(card = {}) {
  const fields = mapCardRecordToIdentity(card);
  return !!(fields.year || fields.brand || fields.set);
}

function formatCardIdentityHtml(card = {}) {
  const fields = mapCardRecordToIdentity(card);
  if (!hasCardRegistryIdentity(card)) return null;

  const titleParts = [fields.year, fields.brand, fields.set].filter((part) => part != null && part !== "");
  const lines = [];

  if (titleParts.length) {
    lines.push(`<p class="sr-card-title">${titleParts.join(" ")}</p>`);
  }
  if (fields.subset) {
    lines.push(`<p class="sr-card-meta">${fields.subset}</p>`);
  }
  if (fields.parallel) {
    lines.push(`<p class="sr-card-meta">${fields.parallel}</p>`);
  }
  if (fields.variation) {
    lines.push(`<p class="sr-card-meta">${fields.variation}</p>`);
  }
  if (fields.card_number) {
    lines.push(`<p class="sr-card-number">#${fields.card_number}</p>`);
  }
  if (fields.grade) {
    const gradeLine = [fields.grading_company, fields.grade].filter(Boolean).join(" ");
    lines.push(`<p class="sr-card-grade">${gradeLine}</p>`);
  } else if (fields.grading_company) {
    lines.push(`<p class="sr-card-grade">${fields.grading_company}</p>`);
  }
  if (fields.serial_number) {
    lines.push(`<p class="sr-card-serial">SN ${fields.serial_number}</p>`);
  }

  return lines.length ? lines.join("") : null;
}

const CardRegistry = {
  CARD_REGISTRY_PENDING,
  SUPPORTED_IDENTITY_FIELDS,
  mapCardRecordToIdentity,
  getCardIdentityFields,
  hasCardRegistryIdentity,
  formatCardIdentityHtml,
};

if (typeof window !== "undefined") {
  window.CardRegistry = CardRegistry;
  window.CARD_REGISTRY_PENDING = CARD_REGISTRY_PENDING;
  window.getCardIdentityFields = getCardIdentityFields;
  window.hasCardRegistryIdentity = hasCardRegistryIdentity;
  window.formatCardIdentityHtml = formatCardIdentityHtml;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = CardRegistry;
}
