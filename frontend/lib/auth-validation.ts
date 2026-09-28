export type AuthFieldErrors = Record<string, string>

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

export function validateEmail(email: string): string | undefined {
  if (!EMAIL_PATTERN.test(email.trim())) return 'Enter a valid email address.'
}

export function validateDisplayName(displayName: string): string | undefined {
  const length = displayName.trim().length
  if (length < 1 || length > 80) return 'Display name must contain between 1 and 80 characters.'
}

export function validatePassword(password: string): string | undefined {
  if (password.length < 12) return 'Password must contain at least 12 characters.'
  if (password.length > 1024) return 'Password is too long.'
}

export function validateRegistration(input: {
  displayName: string
  email: string
  password: string
}): AuthFieldErrors {
  const errors: AuthFieldErrors = {}
  const displayNameError = validateDisplayName(input.displayName)
  const emailError = validateEmail(input.email)
  const passwordError = validatePassword(input.password)
  if (displayNameError) errors.displayName = displayNameError
  if (emailError) errors.email = emailError
  if (passwordError) errors.password = passwordError
  return errors
}
