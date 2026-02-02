const { defineConfig } = require('cypress');
const fs = require('fs');
const path = require('path');

module.exports = defineConfig({
  e2e: {
    baseUrl: 'https://pagespeed.web.dev',
    video: false,
    screenshotOnRunFailure: false,
    viewportWidth: 1280,
    viewportHeight: 720,
    defaultCommandTimeout: 10000,
    pageLoadTimeout: 120000,
    requestTimeout: 60000,
    responseTimeout: 60000,
    experimentalStudio: false,
    experimentalWebKitSupport: false,
    setupNodeEvents(on, config) {
      on('task', {
        writeResults(results) {
          const resultsDir = path.join(process.cwd(), 'cypress', 'results');
          
          if (!fs.existsSync(resultsDir)) {
            fs.mkdirSync(resultsDir, { recursive: true });
          }
          
          const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
          const filename = `pagespeed-results-${timestamp}.json`;
          const filepath = path.join(resultsDir, filename);
          
          fs.writeFileSync(filepath, JSON.stringify(results, null, 2));
          
          return { filename, filepath };
        }
      });
      
      return config;
    },
    reporter: 'json',
    reporterOptions: {
      output: 'cypress/results/test-results.json',
      overwrite: true,
      html: false,
      json: true
    }
  },
  chromeWebSecurity: false,
  retries: {
    runMode: 2,
    openMode: 0
  }
});
