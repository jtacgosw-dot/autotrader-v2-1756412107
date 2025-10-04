import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test('viewer can login and navigate but not access Risk page', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('lastSeenVersion', '2.1.0')
    })

    await page.route('**/api/login', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ role: 'viewer' })
      })
    })
    
    await page.route('**/api/auth/whoami', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: 'viewer', role: 'viewer' })
      })
    })
    
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
    await page.addInitScript(() => {
      localStorage.setItem('lastSeenVersion', '2.1.0')
    })

    await page.route('**/api/login', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ role: 'controller' })
      })
    })
    
    await page.route('**/api/auth/whoami', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: 'controller', role: 'controller' })
      })
    })
    
    await page.route('**/api/pause', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'paused' })
      })
    })
    
    await page.route('**/api/resume', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'resumed' })
      })
    })
    
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
