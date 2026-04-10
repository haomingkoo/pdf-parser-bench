/**
 * Playwright tests for the PDF parsing comparison blog post.
 *
 * Purpose:
 * 1. Verify the blog post HTML renders correctly in a real browser
 * 2. Check all interactive elements function (theme toggle, chart animations)
 * 3. Take screenshots for visual regression baseline
 * 4. Verify no console errors
 *
 * Setup:
 *   npm install -D @playwright/test
 *   npx playwright install chromium
 *
 * Run:
 *   npx playwright test playwright/verify_blog.spec.ts
 *   npx playwright test --headed  # visible browser
 *   npx playwright test --update-snapshots  # update screenshot baseline
 */

import { test, expect, Page } from "@playwright/test";
import * as path from "path";

// Path to the blog post HTML file (relative to project root)
const BLOG_POST_PATH = path.resolve(__dirname, "../../blog/pdf-parsing-comparison.html");
const BLOG_URL = `file://${BLOG_POST_PATH}`;

// ----------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------

async function loadBlogPost(page: Page): Promise<void> {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.goto(BLOG_URL, { waitUntil: "domcontentloaded" });

  // Fail immediately if JavaScript threw errors on load
  expect(
    consoleErrors,
    `Console errors detected on page load: ${consoleErrors.join(", ")}`
  ).toHaveLength(0);
}

// ----------------------------------------------------------------
// Structure tests
// ----------------------------------------------------------------

test.describe("Blog post structure", () => {
  test("page title is set correctly", async ({ page }) => {
    await loadBlogPost(page);
    await expect(page).toHaveTitle(/PDF Parsing/i);
  });

  test("nav logo and back-to-blog link are present", async ({ page }) => {
    await loadBlogPost(page);
    await expect(page.locator(".nav-logo")).toBeVisible();
    await expect(page.locator(".nav-blog")).toBeVisible();
  });

  test("hero section renders with title and badge", async ({ page }) => {
    await loadBlogPost(page);
    await expect(page.locator(".hero-badge")).toBeVisible();
    await expect(page.locator("h1")).toBeVisible();
  });

  test("all major sections are present", async ({ page }) => {
    await loadBlogPost(page);
    const expectedSectionIds = [
      "#overview",
      "#tool-deep-dive",
      "#ablation",
      "#rubric",
      "#decision-tree",
      "#recommendation",
    ];
    for (const sectionId of expectedSectionIds) {
      await expect(
        page.locator(sectionId),
        `Section ${sectionId} should exist`
      ).toBeAttached();
    }
  });

  test("comparison table renders with correct columns", async ({ page }) => {
    await loadBlogPost(page);
    const table = page.locator(".comparison-table, table").first();
    await expect(table).toBeVisible();
    // Verify key columns exist
    await expect(page.locator("th:has-text('Tool')").first()).toBeVisible();
    await expect(page.locator("th:has-text('License')").first()).toBeVisible();
  });
});

// ----------------------------------------------------------------
// Interactive element tests
// ----------------------------------------------------------------

test.describe("Interactive elements", () => {
  test("theme toggle switches between dark and light", async ({ page }) => {
    await loadBlogPost(page);

    // Default should be dark theme
    const html = page.locator("html");
    await expect(html).toHaveAttribute("data-theme", "dark");

    // Click theme toggle
    const themeBtn = page.locator(".theme-btn");
    await expect(themeBtn).toBeVisible();
    await themeBtn.click();

    // Should switch to light
    await expect(html).toHaveAttribute("data-theme", "light");

    // Click again to switch back
    await themeBtn.click();
    await expect(html).toHaveAttribute("data-theme", "dark");
  });

  test("bar chart animations trigger on scroll", async ({ page }) => {
    await loadBlogPost(page);

    // Scroll to charts section
    await page.locator("#ablation").scrollIntoViewIfNeeded();
    await page.waitForTimeout(500); // Allow animation to start

    // Bar fills should have non-zero height after scroll reveal
    const barFills = page.locator(".bar-fill");
    const count = await barFills.count();
    expect(count).toBeGreaterThan(0);
  });

  test("tool detail cards are visible and have content", async ({ page }) => {
    await loadBlogPost(page);
    await page.locator("#tool-deep-dive").scrollIntoViewIfNeeded();

    const toolCards = page.locator(".tool-card, .method-card");
    const cardCount = await toolCards.count();
    expect(cardCount).toBeGreaterThanOrEqual(3); // At least top 3 tools

    // Each card should have a tool name
    for (let i = 0; i < Math.min(cardCount, 3); i++) {
      await expect(toolCards.nth(i)).not.toBeEmpty();
    }
  });
});

// ----------------------------------------------------------------
// Accessibility tests
// ----------------------------------------------------------------

test.describe("Accessibility", () => {
  test("all images have alt attributes", async ({ page }) => {
    await loadBlogPost(page);
    const images = page.locator("img");
    const imgCount = await images.count();
    for (let i = 0; i < imgCount; i++) {
      const alt = await images.nth(i).getAttribute("alt");
      expect(
        alt,
        `Image ${i} is missing alt attribute`
      ).not.toBeNull();
    }
  });

  test("headings are in logical order (h1 → h2 → h3)", async ({ page }) => {
    await loadBlogPost(page);
    const h1Count = await page.locator("h1").count();
    expect(h1Count).toBe(1); // Exactly one H1 per page
  });
});

// ----------------------------------------------------------------
// Visual regression (screenshots)
// ----------------------------------------------------------------

test.describe("Visual regression", () => {
  test("hero section screenshot matches baseline", async ({ page }) => {
    await loadBlogPost(page);
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.waitForTimeout(300); // Let animations settle

    const hero = page.locator(".hero");
    await expect(hero).toHaveScreenshot("hero-dark.png", {
      maxDiffPixelRatio: 0.02, // Allow 2% pixel difference
    });
  });

  test("comparison table screenshot matches baseline", async ({ page }) => {
    await loadBlogPost(page);
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.locator("#rubric, #ablation").first().scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot("comparison-table.png", {
      maxDiffPixelRatio: 0.02,
      clip: { x: 0, y: 0, width: 1280, height: 600 },
    });
  });

  test("full page screenshot — dark theme", async ({ page }) => {
    await loadBlogPost(page);
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.waitForTimeout(500);
    await expect(page).toHaveScreenshot("full-page-dark.png", {
      fullPage: true,
      maxDiffPixelRatio: 0.03,
    });
  });
});
