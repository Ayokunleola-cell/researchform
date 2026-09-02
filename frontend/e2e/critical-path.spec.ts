import { test, expect } from '@playwright/test';

test.describe('Critical Path: Survey Creation & Marketplace', () => {
  test('should login, create a survey, and navigate to marketplace', async ({ page }) => {
    // 1. Login using demo bypass
    await page.goto('/login');
    await page.fill('input[type="email"]', 'demo@researchform.app');
    await page.click('button:has-text("Continue")');
    await page.fill('input[type="password"]', 'demo1234');
    await page.click('button:has-text("Sign in securely")');
    
    // Expect to be on dashboard
    await expect(page).toHaveURL(/\/dashboard/);
    
    // 2. Go to Surveys
    await page.click('text="Surveys"');
    await expect(page).toHaveURL(/\/surveys/);
    
    // 3. Create a Survey
    await page.click('text="New Survey"');
    await page.fill('input[placeholder="e.g. Employee Satisfaction 2024"]', 'E2E Test Survey');
    await page.fill('textarea[placeholder="What is this survey about?"]', 'Automated E2E testing.');
    await page.click('button:has-text("Create & Continue")');
    
    // Should be in builder
    await expect(page).toHaveURL(/\/surveys\/[a-z0-9-]+\/build/);
    
    // 4. Check Marketplace Listing (Sell Data)
    await page.click('text="Sell Data"');
    await expect(page).toHaveURL(/\/marketplace\/sell/);
    
    // Check KYC status logic is present
    await expect(page.locator('text="Payout Verification"').or(page.locator('text="Sell a Dataset"'))).toBeVisible();
  });
});
