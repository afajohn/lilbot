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

  const validateUrlAccessibility = (url) => {
    return cy.request({
      url: url,
      failOnStatusCode: false,
      timeout: 30000,
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; PageSpeedAudit/1.0)'
      }
    }).then((response) => {
      if (response.status >= 200 && response.status < 400) {
        cy.log(`URL is accessible: ${url} (Status: ${response.status})`);
        return true;
      } else {
        throw new Error(`URL is not accessible: ${url} (Status: ${response.status})`);
      }
    });
  };

  const smartWaitForScores = (maxWaitTime = 120000, pollInterval = 2000) => {
    const startTime = Date.now();
    
    const checkScores = () => {
      return cy.get('body').then(($body) => {
        const scoreElements = $body.find('.lh-exp-gauge__percentage, [data-testid="score-gauge"], .lh-gauge__percentage');
        
        if (scoreElements.length > 0) {
          return cy.wrap(true);
        }
        
        const elapsed = Date.now() - startTime;
        if (elapsed >= maxWaitTime) {
          throw new Error(`Score elements not found after ${maxWaitTime}ms`);
        }
        
        return cy.wait(pollInterval).then(() => checkScores());
      });
    };
    
    return checkScores();
  };

  const detectViewportResize = () => {
    return cy.window().then((win) => {
      const viewport = {
        width: win.innerWidth,
        height: win.innerHeight,
        isMobile: win.innerWidth < 768,
        isTablet: win.innerWidth >= 768 && win.innerWidth < 1024,
        isDesktop: win.innerWidth >= 1024
      };
      cy.log(`Viewport detected: ${viewport.width}x${viewport.height} (${viewport.isMobile ? 'Mobile' : viewport.isTablet ? 'Tablet' : 'Desktop'})`);
      return viewport;
    });
  };

  const getScoreElement = () => {
    return cy.get('body').then(($body) => {
      const selectors = [
        '[data-testid="score-gauge"]',
        '.lh-exp-gauge__percentage',
        '.lh-gauge__percentage'
      ];
      
      for (const selector of selectors) {
        const elements = $body.find(selector);
        if (elements.length > 0) {
          return cy.get(selector).first();
        }
      }
      
      throw new Error('No score element found with available selectors');
    });
  };

  const findButton = (textPattern) => {
    return cy.get('body').then(($body) => {
      const dataTestIdSelectors = [
        `[data-testid*="analyze"]`,
        `[data-testid*="mobile"]`,
        `[data-testid*="desktop"]`
      ];
      
      for (const selector of dataTestIdSelectors) {
        const elements = $body.find(selector);
        if (elements.length > 0) {
          const matchingElement = elements.filter((i, el) => {
            return textPattern.test(Cypress.$(el).text());
          });
          if (matchingElement.length > 0) {
            return cy.wrap(matchingElement.first());
          }
        }
      }
      
      return cy.get('button').contains(textPattern, { timeout: 10000 });
    });
  };

  it('should analyze URL on PageSpeed Insights for Mobile and Desktop in parallel', () => {
    validateUrlAccessibility(testUrl);
    
    detectViewportResize();
    
    cy.visit('/');
    
    cy.get('[data-testid="url-input"], input[name="url"]', { timeout: 10000 })
      .should('be.visible')
      .clear()
      .type(testUrl);
    
    findButton(/analyze/i).should('be.visible').click();
    
    smartWaitForScores(120000, 2000);
    
    cy.wait(2000);
    
    detectViewportResize();
    
    findButton(/mobile/i).should('be.visible').then(($btn) => {
      const isActive = $btn.hasClass('active') || 
                       $btn.attr('aria-selected') === 'true' || 
                       $btn.attr('aria-pressed') === 'true';
      
      if (!isActive) {
        cy.wrap($btn).click();
        cy.wait(2000);
      }
    });
    
    getScoreElement().invoke('text').then((text) => {
      const score = parseInt(text.trim());
      results.mobile.score = score;
      cy.log(`Mobile score: ${score}`);
      
      if (results.mobile.score < 80) {
        cy.url().then((url) => {
          results.mobile.reportUrl = url;
        });
      }
    });
    
    findButton(/desktop/i).should('be.visible').click();
    
    cy.wait(2000);
    
    getScoreElement().invoke('text').then((text) => {
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

  afterEach(function() {
    if (this.currentTest.state === 'failed') {
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const testName = this.currentTest.title.replace(/[^a-z0-9]/gi, '_').toLowerCase();
      cy.screenshot(`failure-${testName}-${timestamp}`, {
        capture: 'fullPage',
        overwrite: true
      });
    }
  });

  after(() => {
    cy.task('writeResults', results).then((fileInfo) => {
      cy.log(`Results written to ${fileInfo.filename}`);
    });
  });
});
