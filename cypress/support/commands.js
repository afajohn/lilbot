Cypress.Commands.add('submitToPageSpeed', (url) => {
  cy.visit('/', { timeout: 30000 });
  
  cy.get('input[type="url"]', { timeout: 10000 })
    .should('be.visible')
    .clear()
    .type(url, { delay: 50 });
  
  cy.get('button[type="submit"]', { timeout: 10000 })
    .should('be.visible')
    .should('not.be.disabled')
    .click();
  
  cy.log(`Submitted URL: ${url} for PageSpeed analysis`);
});

Cypress.Commands.add('waitForAnalysis', () => {
  cy.log('Waiting for PageSpeed analysis to complete...');
  
  cy.get('.lh-scores-container', { timeout: 120000 })
    .should('be.visible');
  
  cy.get('.lh-gauge__percentage', { timeout: 10000 })
    .should('be.visible')
    .should('have.length.greaterThan', 0);
  
  cy.wait(2000);
  
  cy.get('.lh-gauge__percentage').each(($el) => {
    cy.wrap($el).should('not.be.empty');
  });
  
  cy.log('PageSpeed analysis completed successfully');
});

Cypress.Commands.add('getDeviceScore', (device) => {
  cy.log(`Getting score for device: ${device}`);
  
  const deviceSelector = device.toLowerCase() === 'mobile' 
    ? '[data-device="mobile"]' 
    : '[data-device="desktop"]';
  
  cy.get(deviceSelector, { timeout: 10000 })
    .should('exist');
  
  cy.get(deviceSelector)
    .click({ force: true });
  
  cy.wait(1000);
  
  cy.get('.lh-scores-container', { timeout: 10000 })
    .should('be.visible');
  
  return cy.get('.lh-gauge__percentage').first().then(($score) => {
    const scoreText = $score.text().trim();
    const scoreValue = parseInt(scoreText, 10);
    
    cy.log(`${device} score: ${scoreValue}`);
    
    return cy.wrap(scoreValue);
  });
});
