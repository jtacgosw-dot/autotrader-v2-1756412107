import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test('viewer can login and navigate but not access Risk page', async ({ page }) => {
    await page.goto('/login')
    
    await page.fill('input[id="username"]', 'viewer')
    await page.fill('input[id="password"]', 'ViewerPass123!')
    await page.click('button[type="submit"]')
    
    await expect(page).toHaveURL('/overview')
    await expect(page.locator('div.inline-flex:has-text("viewer")')).toBeVisible()
    
    await page.click('text=Venues & Latency')
    await expect(page).toHaveURL('/venues')
    
    await page.click('text=Orders & Positions')
    await expect(page).toHaveURL('/orders')
    
    await page.click('text=Alerts')
    await expect(page).toHaveURL('/alerts')
    
    await expect(page.locator('text=Risk & Controls')).not.toBeVisible()
    
    await page.goto('/risk')
    await expect(page).toHaveURL('/login')
  })

  test('controller can login and access all pages including Risk', async ({ page }) => {
    await page.goto('/login')
    
    await page.fill('input[id="username"]', 'controller')
    await page.fill('input[id="password"]', 'ControllerPass456!')
    await page.click('button[type="submit"]')
    
    await expect(page).toHaveURL('/overview')
    await expect(page.locator('div.inline-flex:has-text("controller")')).toBeVisible()
    
    await page.click('text=Risk & Controls')
    await expect(page).toHaveURL('/risk')
    await expect(page.locator('text=Bot Controls')).toBeVisible()
    
    const pauseButton = page.locator('button:has-text("Pause")')
    await expect(pauseButton).toBeVisible()
  })

})
