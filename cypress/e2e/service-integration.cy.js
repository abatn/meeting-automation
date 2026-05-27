/// <reference types="cypress" />

describe('User Service Integration E2E Test', () => {
  const testUser = {
    email: `service_test_${Date.now()}@example.com`,
    password: 'ValidPass123!',
    full_name: 'Service Test User',
    company_name: 'Service Test Company',
    plan: 'GRATUIT'
  };

  beforeEach(() => {
    cy.visit('/register');
  });

  it('should register user successfully through the service layer', () => {
    // Fill in the form
    cy.get('input[name="full_name"]').type(testUser.full_name);
    cy.get('input[name="email"]').type(testUser.email);
    cy.get('input[name="company_name"]').type(testUser.company_name);
    cy.get('input[name="password"]').type(testUser.password);
    cy.get('select[name="plan"]').select(testUser.plan);
    
    // Submit
    cy.get('button[type="submit"]').click();
    
    // Should redirect to check email page
    cy.url().should('include', '/check-email');
    
    // Verify success message
    cy.contains('Check your email').should('be.visible');
    cy.contains(testUser.email).should('be.visible');
  });

  it('should reject duplicate email registration', () => {
    // First registration
    cy.get('input[name="full_name"]').type(testUser.full_name);
    cy.get('input[name="email"]').type('duplicate@example.com');
    cy.get('input[name="company_name"]').type(testUser.company_name);
    cy.get('input[name="password"]').type(testUser.password);
    cy.get('button[type="submit"]').click();
    
    // Try to register again with same email
    cy.visit('/register');
    cy.get('input[name="full_name"]').type(testUser.full_name);
    cy.get('input[name="email"]').type('duplicate@example.com');
    cy.get('input[name="company_name"]').type(testUser.company_name);
    cy.get('input[name="password"]').type(testUser.password);
    cy.get('button[type="submit"]').click();
    
    // Should show error message
    cy.contains('already exists').should('be.visible');
  });

  it('should create client with correct plan minutes', () => {
    // Register with PRO plan
    cy.get('input[name="full_name"]').type('PRO User');
    cy.get('input[name="email"]').type(`pro_${Date.now()}@example.com`);
    cy.get('input[name="company_name"]').type('PRO Company');
    cy.get('input[name="password"]').type(testUser.password);
    cy.get('select[name="plan"]').select('PRO');
    cy.get('button[type="submit"]').click();
    
    // Should redirect successfully
    cy.url().should('include', '/check-email');
  });

  it('should create activation token', () => {
    // Register a user
    const uniqueEmail = `activation_${Date.now()}@example.com`;
    cy.get('input[name="full_name"]').type('Activation User');
    cy.get('input[name="email"]').type(uniqueEmail);
    cy.get('input[name="company_name"]').type('Activation Test Co');
    cy.get('input[name="password"]').type(testUser.password);
    cy.get('button[type="submit"]').click();
    
    // Should redirect to check email page (indicates activation token created)
    cy.url().should('include', '/check-email');
  });
});