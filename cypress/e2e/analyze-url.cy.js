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
    
    cy.get('input[name="url"]', { timeout: 30000 }).should('be.visible').clear().type(testUrl);
    
    cy.get('button').contains(/analyze/i, { timeout: 30000 }).should('be.visible').click();
    
    cy.wait(15000);
    
    cy.get('.lh-exp-gauge__percentage', { timeout: 180000 }).should('exist');
    
    cy.get('button').contains('Mobile', { matchCase: false, timeout: 30000 }).click();
    
    cy.wait(5000);
    
    cy.get('.lh-exp-gauge__percentage', { timeout: 30000 }).first().invoke('text').then((text) => {
      const score = parseInt(text.trim());
      results.mobile.score = score;
      
      if (results.mobile.score < 80) {
        cy.url().then((url) => {
          results.mobile.reportUrl = url;
        });
      }
    });
    
    cy.get('button').contains('Desktop', { matchCase: false, timeout: 30000 }).click();
    
    cy.wait(5000);
    
    cy.get('.lh-exp-gauge__percentage', { timeout: 30000 }).first().invoke('text').then((text) => {
      const score = parseInt(text.trim());
      results.desktop.score = score;
      
      if (results.desktop.score < 80) {
        cy.url().then((url) => {
          results.desktop.reportUrl = url;
        });
      }
    });
  });

  after(() => {
    cy.task('writeResults', results).then((fileInfo) => {
      cy.log(`Results written to ${fileInfo.filename}`);
    });
  });
});
