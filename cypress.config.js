const { defineConfig } = require('cypress');

module.exports = defineConfig({
  e2e: {
    baseUrl: 'https://pagespeed.web.dev',
    video: false,
    screenshotOnRunFailure: true,
    viewportWidth: 1280,
    viewportHeight: 720,
    defaultCommandTimeout: 10000,
    pageLoadTimeout: 60000,
    requestTimeout: 30000,
    responseTimeout: 30000,
    experimentalStudio: false,
    experimentalWebKitSupport: false,
    setupNodeEvents(on, config) {
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
