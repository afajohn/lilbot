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

  it('should analyze URL on PageSpeed Insights for Mobile and Desktop in parallel', () => {
    cy.visit('/');
    
    cy.get('input[name="url"]', { timeout: 10000 }).should('be.visible').clear().type(testUrl);
    
    cy.get('button').contains(/analyze/i, { timeout: 10000 }).should('be.visible').click();
    
    cy.get('.lh-exp-gauge__percentage', { timeout: 120000 }).should('have.length.at.least', 1);
    
    cy.wait(2000);
    
    cy.get('button').contains('Mobile', { matchCase: false, timeout: 10000 }).should('be.visible').then(($btn) => {
      if (!$btn.hasClass('active') && !$btn.attr('aria-selected')) {
        cy.wrap($btn).click();
        cy.wait(2000);
      }
    });
    
    cy.get('.lh-exp-gauge__percentage', { timeout: 10000 }).first().invoke('text').then((text) => {
      const score = parseInt(text.trim());
      results.mobile.score = score;
      cy.log(`Mobile score: ${score}`);
      
      if (results.mobile.score < 80) {
        cy.url().then((url) => {
          results.mobile.reportUrl = url;
        });
      }
    });
    
    cy.get('button').contains('Desktop', { matchCase: false, timeout: 10000 }).should('be.visible').click();
    
    cy.wait(2000);
    
    cy.get('.lh-exp-gauge__percentage', { timeout: 10000 }).first().invoke('text').then((text) => {
      const score = parseInt(text.trim());
      results.desktop.score = score;
      cy.log(`Desktop score: ${score}`);
      
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
