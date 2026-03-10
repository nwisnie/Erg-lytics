const { test, expect } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;

const BASE_URL = process.env.A11Y_BASE_URL || "";
const PAGES = ["/", "/signin"];

function summarizeViolations(violations) {
  return violations
    .map((violation) => {
      const nodes = violation.nodes
        .map((node) => node.target.join(" "))
        .slice(0, 3)
        .join(" | ");
      return `${violation.id} (${violation.impact}): ${nodes}`;
    })
    .join("\n");
}

test.describe("Axe accessibility baseline", () => {
  test.skip(!BASE_URL, "Set A11Y_BASE_URL to run accessibility checks.");

  for (const path of PAGES) {
    test(`no serious/critical violations on ${path}`, async ({ page }) => {
      await page.goto(`${BASE_URL}${path}`, { waitUntil: "networkidle" });

      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa"])
        .analyze();

      const seriousOrCritical = results.violations.filter((violation) =>
        ["serious", "critical"].includes(violation.impact)
      );

      expect(
        seriousOrCritical,
        `A11Y violations on ${path}:\n${summarizeViolations(seriousOrCritical)}`
      ).toEqual([]);
    });
  }
});
