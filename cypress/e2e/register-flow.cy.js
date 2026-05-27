/// <reference types="cypress" />

describe('Registration Flow E2E Test', () => {
  const testUser = {
    email: `test_${Date.now()}@example.com`,
    password: 'TestPass123!',
    full_name: 'Test User',
    company_name: 'Test Company',
    plan: 'GRATUIT'
  };

  beforeEach(() => {
    // Visit the landing page first
    cy.visit('/');
    // Click on register button/link
    cy.contains('Start Free Trial').click();
    // Should be on register page
    cy.url().should('include', '/register');
  });

  it('should register a new user and redirect to check email page', () => {
    // Fill in the registration form
    cy.get('input[name="full_name"]').type(testUser.full_name);
    cy.get('input[name="email"]').type(testUser.email);
    cy.get('input[name="company_name"]').type(testUser.company_name);
    cy.get('input[name="password"]').type(testUser.password);
    
    // Select plan (should already be GRATUIT)
    cy.get('select[name="plan"]').select('GRATUIT');
    
    // Submit the form
    cy.get('button[type="submit"]').contains('Create Account').click();
    
    // Should redirect to check email page
    cy.url().should('include', '/check-email');
    
    // Check that the email is displayed
    cy.contains(testUser.email).should('be.visible');
    
    // Check for success message or resend button
    cy.contains('Resend activation link').should('be.visible');
  });

  it('should show validation errors for invalid input', () => {
    // Try to submit empty form
    cy.get('button[type="submit"]').contains('Create Account').click();
    
    // Check for validation errors
    cy.contains('Nom complet est requis').should('be.visible');
    cy.contains('Adresse Email est requise').should('be.visible');
    cy.contains('Mot de passe est requis').should('be.visible');
    cy.contains('Nom de l\'entreprise est requis').should('be.visible');
    
    // Fill in only email and password
    cy.get('input[name="email"]').type(testUser.email);
    cy.get('input[name="password"]').type(testUser.password);
    
    // Submit again
    cy.get('button[type="submit"]').contains('Create Account').click();
    
    // Should still show errors for missing fields
    cy.contains('Nom complet est requis').should('be.visible');
    cy.contains('Nom de l\'entreprise est requise').should('be.visible');
  });

  it('should navigate to login page from check email page', () => {
    // First register a user
    cy.get('input[name="full_name"]').type(testUser.full_name);
    cy.get('input[name="email"]').type(testUser.email);
    cy.get('input[name="company_name"]').type(testUser.company_name);
    cy.get('input[name="password"]').type(testUser.password);
    cy.get('button[type="submit"]').contains('Create Account').click();
    
    // Should be on check email page
    cy.url().should('include', '/check-email');
    
    // Click back to login link
    cy.contains('Se connecter').click();
    
    // Should be on login page
    cy.url().should('include', '/login');
  });
});