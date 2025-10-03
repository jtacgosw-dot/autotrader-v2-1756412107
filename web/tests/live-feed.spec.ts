import { test, expect } from '@playwright/test'

test.describe('Live Feed', () => {
  test('Live page is accessible after login', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[id="username"]', 'viewer')
    await page.fill('input[id="password"]', 'ViewerPass123!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL('/overview')
    
    await page.click('text=Live Feed')
    await expect(page).toHaveURL('/live')
    await expect(page.locator('h1:has-text("Live Feed")')).toBeVisible()
  })
})
