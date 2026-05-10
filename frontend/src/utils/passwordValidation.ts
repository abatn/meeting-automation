export interface PasswordValidation {
  isValid: boolean;
  errors: string[];
  strength: 'weak' | 'medium' | 'strong';
}

/**
 * Validates password strength
 * @param password - The password to validate
 * @returns Validation result with errors and strength indicator
 */
export const validatePassword = (password: string): PasswordValidation => {
  const errors: string[] = [];
  
  // Minimum length check
  if (password.length < 8) {
    errors.push('Must be at least 8 characters long');
  }
  
  // Uppercase check
  if (!/[A-Z]/.test(password)) {
    errors.push('Must contain at least one uppercase letter');
  }
  
  // Lowercase check
  if (!/[a-z]/.test(password)) {
    errors.push('Must contain at least one lowercase letter');
  }
  
  // Number check
  if (!/[0-9]/.test(password)) {
    errors.push('Must contain at least one number');
  }
  
  // Special character check (optional but recommended)
  // if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) {
  //   errors.push('Must contain at least one special character');
  // }
  
  // Calculate strength based on number of missing requirements
  const missingChecks = errors.length;
  let strength: 'weak' | 'medium' | 'strong' = 'strong';
  
  if (missingChecks >= 3) {
    strength = 'weak';
  } else if (missingChecks >= 1) {
    strength = 'medium';
  }
  
  return {
    isValid: errors.length === 0,
    errors,
    strength
  };
};