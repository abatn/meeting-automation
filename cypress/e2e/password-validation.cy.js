/// <reference types="cypress" />

describe('Password Validation E2E Test', () => {
  const baseUser = {
    email: `test_${Date.now()}@example.com`,
    full_name: 'Test User',
    company_name: 'Test Company',
    plan: 'GRATUIT'
  };

  beforeEach(() => {
    // Visit the register page
    cy.visit('/register');
  });

  it('should reject passwords that are too short', () => {
    const testData = {
      ...baseUser,
      password: 'Ab1' // Too short (3 chars)
    };
    
    fillAndSubmitForm(testData);
    
    // Should show password validation error
    cy.contains('Must be at least 8 characters long').should('be.visible');
    cy.get('button[type="submit"]').should('be.disabled');
  });

  it('should reject passwords without uppercase letter', () => {
    const testData = {
      ...baseUser,
      password: 'abcdef12' // No uppercase
    };
    
    fillAndSubmitForm(testData);
    
    // Should show password validation error
    cy.contains('Must contain at least one uppercase letter').should('be.visible');
    cy.get('button[type="submit"]').should('be.disabled');
  });

  it('should reject passwords without lowercase letter', () => {
    const testData = {
      ...baseUser,
      password: 'ABCDEF12' // No lowercase
    };
    
    fillAndSubmitForm(testData);
    
    // Should show password validation error
    cy.contains('Must contain at least one lowercase letter').should('be.visible');
    cy.get('button[type="submit"]').should('be.disabled');
  });

  it('should reject passwords without numbers', () => {
    const testData = {
      ...baseUser,
      password: 'Abcdefgh' // No numbers
    };
    
    fillAndSubmitForm(testData);
    
    // Should show password validation error
    cy.contains('Must contain at least one number').should('be.visible');
    cy.get('button[type="submit"]').should('be.disabled');
  });

  it('should accept valid password', () => {
    const testData = {
      ...baseUser,
      password: 'ValidPass123!' // Valid password
    };
    
    fillAndSubmitForm(testData);
    
    // Should show password strength indicator as strong
    cy.contains('Strong').should('be.visible');
    
    // Submit button should be enabled
    cy.get('button[type="submit"]').should('not.be.disabled');
    
    // Submit the form
    cy.get('button[type="submit"]').contains('Create Account').click();
    
    // Should redirect to check email page
    cy.url().should('include', '/check-email');
  });

  it('should show real-time password validation as user types', () => {
    // Start typing a weak password
    cy.get('input[name="password"]').type('weak');
    
    // Should show multiple errors
    cy.contains('Must be at least 8 characters long').should('be.visible');
    cy.contains('Must contain at least one uppercase letter').should('be.visible');
    cy.contains('Must contain at least one number').should('be.visible');
    
    // Continue typing to make it stronger
    cy.get('input[name="password"]').clear().type('WeakPass1');
    
    // Should still show errors (too short, no lowercase actually it has lowercase)
    // Actually "WeakPass1" has: W (upper), eak (lower), ass (lower), P (upper), ass (lower), 1 (number)
    // Length: 9 - good
    // Has uppercase: W, P - good
    // Has lowercase: e,a,k,a,s,s,s - good  
    // Has number: 1 - good
    // So it should be valid!
    
    // Let's test with a truly weak one
    cy.get('input[name="password"]').clear().type('123');
    
    cy.contains('Must be at least 8 characters long').should('be.visible');
    cy.contains('Must contain at least one uppercase letter').should('be.visible');
    cy.contains('Must contain at least one lowercase letter').should('be.visible');
  });
});

function fillAndSubmitForm(userData) {
  // Fill in the form
  cy.get('input[name="full_name"]').type(userData.full_name);
  cy.get('input[name="email"]').type(userData.email);
  cy.get('input[name="company_name"]').type(userData.company_name);
  cy.get('input[name="password"]').type(userData.password);
  
  // Select plan
  cy.get('select[name="plan"]').select(userData.plan);
}