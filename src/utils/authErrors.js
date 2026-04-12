/**
 * Maps AWS Cognito error codes to user-friendly messages
 * Prevents exposure of raw Cognito error details to users
 */

export const getCognitoErrorMessage = (error) => {
  // Handle error object
  const errorCode = error?.code || error?.name || '';
  const errorMessage = error?.message || '';

  // Map specific Cognito error codes
  const errorMap = {
    'UserAlreadyAuthenticatedException': 'A session is already active. Please wait while we refresh your connection.',
    'NotAuthorizedException': 'Invalid username or password. Please try again.',
    'UserNotFoundException': 'User not found. Please check your username and try again.',
    'PasswordResetRequiredException': 'Your password needs to be reset. Please contact support.',
    'TooManyRequestsException': 'Too many login attempts. Please wait a few minutes before trying again.',
    'TooManySignUpAttemptsException': 'Too many signup attempts. Please wait a few minutes before trying again.',
    'InvalidParameterException': 'Invalid input. Please check your credentials and try again.',
    'LimitExceededException': 'Request limit exceeded. Please try again later.',
    'InvalidPasswordException': 'Password does not meet security requirements.',
    'UsernameExistsException': 'Username already exists. Please choose a different username.',
    'CodeMismatchException': 'Verification code is incorrect. Please try again.',
    'ExpiredCodeException': 'Verification code has expired. Please request a new one.',
  };

  // Check if error message contains "already authenticated" or similar
  if (errorMessage?.toLowerCase().includes('already')) {
    return 'A session is already active. Please wait while we refresh your connection.';
  }

  // Return mapped error or generic message
  return errorMap[errorCode] || 'An authentication error occurred. Please try again.';
};

/**
 * Determines if an error indicates an existing session
 * Used to determine if we need to sign out before signing in
 */
export const isExistingSessionError = (error) => {
  const errorCode = error?.code || error?.name || '';
  const errorMessage = error?.message || '';

  return (
    errorCode === 'UserAlreadyAuthenticatedException' ||
    errorMessage?.toLowerCase().includes('already authenticated') ||
    errorMessage?.toLowerCase().includes('already a signed in user')
  );
};
