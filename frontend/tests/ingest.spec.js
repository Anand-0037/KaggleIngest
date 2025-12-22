import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('http://localhost:5173/');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/KaggleIngest/);
});

test('can start ingestion from quick start', async ({ page }) => {
  await page.goto('http://localhost:5173/');

  // Click on a Quick Start pill
  await page.getByRole('button', { name: 'Titanic' }).click();

  // Expect URL input to be filled
  await expect(page.getByPlaceholder('Paste Kaggle URL (Competition or Dataset)...')).toHaveValue('https://www.kaggle.com/competitions/titanic');
});

test('shows error for invalid URL', async ({ page }) => {
  await page.goto('http://localhost:5173/');

  // Fill invalid URL
  await page.getByPlaceholder('Paste Kaggle URL (Competition or Dataset)...').fill('https://google.com');
  await page.getByRole('button', { name: 'Ingest Context' }).click();

  // Expect error message
  await expect(page.getByText('Please enter a valid Kaggle Competition, Dataset, or Notebook URL.')).toBeVisible();
});
