import { test, expect } from '@playwright/test'

for (const route of ['terminal', 'dev', 'config']) {
  test(`visual-${route}`, async ({ page }) => {
    await page.goto(`/${route}`)
    await page.waitForTimeout(800)
    await expect(page).toHaveScreenshot(`${route}.png`, { fullPage: true })
  })
}
