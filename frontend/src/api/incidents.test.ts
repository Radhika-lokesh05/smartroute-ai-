import { describe, it, expect } from 'vitest';
import { mapIncidentError } from './incidents';
import { AxiosError, AxiosHeaders, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

function createMockAxiosError(status: number, data: unknown, headers: Record<string, string> = {}): AxiosError {
  const axiosHeaders = new AxiosHeaders(headers);
  const response: AxiosResponse = {
    data,
    status,
    statusText: 'Error',
    headers: headers,
    config: { headers: axiosHeaders } as InternalAxiosRequestConfig,
  };
  const err = new AxiosError('Request failed', 'ERR_BAD_REQUEST', undefined, undefined, response);
  err.response = response;
  return err;
}

describe('Incident API Error Mapping', () => {
  it('maps 409 already reported or already voted', () => {
    const errDup = createMockAxiosError(409, { detail: 'You have already reported an active incident at this location.' });
    expect(mapIncidentError(errDup)).toBe('You have already reported an active incident at this location.');

    const errVote = createMockAxiosError(409, { detail: 'You have already voted on this incident.' });
    expect(mapIncidentError(errVote)).toBe('You have already voted on this incident.');
  });

  it('maps 400/422 distance radius violations to friendly message', () => {
    const errRadius = createMockAxiosError(400, { detail: 'Voter location exceeds allowable radius (1000m) from incident.' });
    expect(mapIncidentError(errRadius)).toBe('You must be within 1 km of the incident to verify or vote.');
  });

  it('maps 403 resolve permission denial', () => {
    const errResolve = createMockAxiosError(403, {
      detail: 'Resolution requires admin role, verified ambulance credentials, or original reporter identity.',
    });
    expect(mapIncidentError(errResolve)).toBe(
      'Only the original reporter, verified ambulance operators, or admins can resolve this incident.'
    );
  });

  it('maps 429 rate limits with Retry-After header', () => {
    const errRate = createMockAxiosError(429, { detail: 'Too many requests' }, { 'retry-after': '42' });
    expect(mapIncidentError(errRate)).toBe('Rate limit exceeded. Please wait 42 seconds before trying again.');

    const errRateNoHeader = createMockAxiosError(429, { detail: 'Too many requests' });
    expect(mapIncidentError(errRateNoHeader)).toBe('Too many requests. Please wait a moment before trying again.');
  });

  it('maps 404/410 expired or not found', () => {
    const err404 = createMockAxiosError(404, { detail: 'Incident not found' });
    expect(mapIncidentError(err404)).toBe('This incident has expired or no longer exists.');

    const err410 = createMockAxiosError(410, { detail: 'Incident expired' });
    expect(mapIncidentError(err410)).toBe('This incident has expired or no longer exists.');
  });

  it('handles standard Error instances and unknown errors', () => {
    expect(mapIncidentError(new Error('Connection timed out'))).toBe('Connection timed out');
    expect(mapIncidentError(null)).toBe('An unexpected network error occurred. Please try again.');
  });
});
