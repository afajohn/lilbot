const fs = require('fs');
const path = require('path');

describe('PageSpeed URL Analysis', () => {
  let testUrl;
  let results = {
    url: '',
    timestamp: new Date().toISOString(),
    mobile: {},
    desktop: {}
  };

  before(() => {
    testUrl = Cypress.env('TEST_URL');
    
    if (!testUrl) {
      throw new Error('CYPRESS_TEST_URL environment variable is not set');
    }
    
    results.url = testUrl;
  });

  it('should analyze URL on PageSpeed Insights for Mobile and Desktop', () => {
    cy.visit('/');
    
    cy.get('input[name="url"]', { timeout: 10000 }).should('be.visible').clear().type(testUrl);
    
    cy.get('button[type="submit"]').click();
    
    cy.wait(15000);
    
    cy.get('.lh-exp-gauge__arc', { timeout: 60000 }).should('exist');
    
    cy.get('button').contains('Mobile', { matchCase: false }).click();
    
    cy.wait(2000);
    
    cy.get('.lh-exp-gauge__arc').first().invoke('attr', 'stroke-dasharray').then((dashArray) => {
      const score = parseFloat(dashArray.split(',')[0]) / 352 * 100;
      results.mobile.score = Math.round(score);
      
      if (results.mobile.score < 80) {
        cy.url().then((url) => {
          results.mobile.reportUrl = url;
        });
      }
    });
    
    cy.get('button').contains('Desktop', { matchCase: false }).click();
    
    cy.wait(2000);
    
    cy.get('.lh-exp-gauge__arc').first().invoke('attr', 'stroke-dasharray').then((dashArray) => {
      const score = parseFloat(dashArray.split(',')[0]) / 352 * 100;
      results.desktop.score = Math.round(score);
      
      if (results.desktop.score < 80) {
        cy.url().then((url) => {
          results.desktop.reportUrl = url;
        });
      }
    });
  });

  after(() => {
    const resultsDir = path.join(process.cwd(), 'cypress', 'results');
    
    if (!fs.existsSync(resultsDir)) {
      fs.mkdirSync(resultsDir, { recursive: true });
    }
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `pagespeed-results-${timestamp}.json`;
    const filepath = path.join(resultsDir, filename);
    
    fs.writeFileSync(filepath, JSON.stringify(results, null, 2));
    
    cy.log(`Results written to ${filename}`);
  });
});
