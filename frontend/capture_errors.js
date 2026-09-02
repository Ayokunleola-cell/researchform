const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: "new" });
  const page = await browser.newPage();
  
  // Set localStorage dummy user
  await page.evaluateOnNewDocument(() => {
    localStorage.setItem('rf_token', 'dummy');
    localStorage.setItem('rf_user', JSON.stringify({
      id: "1",
      email: "demo@researchform.app",
      full_name: "Demo User",
      role: "student"
    }));
  });

  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log('BROWSER ERROR:', msg.text());
    }
  });
  page.on('pageerror', err => {
    console.log('PAGE ERROR:', err.message);
  });

  try {
    await page.goto('http://localhost:3000/dashboard', { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 2000));
    console.log("Finished capturing.");
  } catch (err) {
    console.log('Navigation error:', err.message);
  } finally {
    await browser.close();
  }
})();
