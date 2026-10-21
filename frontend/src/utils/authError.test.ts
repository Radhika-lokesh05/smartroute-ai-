import { describe, it, expect } from 'vitest';
import { formatAuthError } from './authError';

describe('formatAuthError', () => {
  it('returns backend error string when detail is a string', () => {
    const err = { response: { data: { detail: 'Invalid email or password' } } };
    expect(formatAuthError(err, 'Fallback')).toBe('Invalid email or password');
  });

  it('joins array details when detail is a validation error array', () => {
    const err = {
      response: {
        data: {
          detail: [
            { loc: ['body', 'password'], msg: 'Password must be at least 8 characters' },
            { loc: ['body', 'email'], msg: 'value is not a valid email address' },
          ],
        },
      },
    };
    expect(formatAuthError(err, 'Fallback')).toBe(
      'Password must be at least 8 characters, value is not a valid email address'
    );
  });

  it('returns connection helpful message when network error occurs', () => {
    const networkErr = { code: 'ERR_NETWORK', message: 'Network Error' };
    expect(formatAuthError(networkErr, 'Fallback')).toContain('Cannot connect to backend server');
  });

  it('returns connection message when response is missing', () => {
    const noRespErr = new Error('Failed to fetch');
    expect(formatAuthError(noRespErr, 'Fallback')).toContain('Cannot connect to backend server');
  });

  it('returns fallback message when no detail and not network error', () => {
    const err = { response: { status: 500, data: {} } };
    expect(formatAuthError(err, 'Default fallback')).toBe('Default fallback');
  });
});
