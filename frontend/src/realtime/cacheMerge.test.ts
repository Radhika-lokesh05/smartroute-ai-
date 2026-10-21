import { describe, it, expect } from 'vitest';
import { mergeIncidentIntoCache, sortIncidentsByDistance } from './cacheMerge';
import { Incident, IncidentBroadcastData } from '@/types/incident';

describe('cacheMerge Utilities', () => {
  const baseIncident: Incident = {
    id: 'inc-1',
    incident_type: 'accident',
    status: 'pending',
    lat: 12.9716,
    lng: 77.5946,
    confirmations: 1,
    rejections: 0,
    trust_score: 1.0,
    created_at: '2026-10-19T01:00:00Z',
    expires_at: '2026-10-19T01:45:00Z',
    seconds_remaining: 2700,
    note: 'Minor bumper tap',
    user_voted: true,
    user_vote: 'confirm',
    distance_m: 500,
  };

  it('adds a new incident and computes its distance from user', () => {
    const newBroadcast: IncidentBroadcastData = {
      id: 'inc-2',
      incident_type: 'hazard',
      status: 'pending',
      lat: 12.9816,
      lng: 77.5946,
      confirmations: 1,
      rejections: 0,
      trust_score: 1.0,
      created_at: '2026-10-19T01:05:00Z',
      expires_at: '2026-10-19T01:50:00Z',
      seconds_remaining: 2700,
      note: 'Pothole',
    };

    const userLoc = { lat: 12.9716, lng: 77.5946 };
    const result = mergeIncidentIntoCache([baseIncident], 'incident.created', newBroadcast, userLoc);

    expect(result).toHaveLength(2);
    const added = result.find((i) => i.id === 'inc-2');
    expect(added).toBeDefined();
    expect(added?.user_voted).toBe(false);
    expect(added?.distance_m).toBeGreaterThan(1000);
  });

  it('updates existing incident while preserving user_voted and user_vote', () => {
    const updateBroadcast: IncidentBroadcastData = {
      id: 'inc-1',
      incident_type: 'accident',
      status: 'validated',
      lat: 12.9716,
      lng: 77.5946,
      confirmations: 3,
      rejections: 0,
      trust_score: 3.0,
      created_at: '2026-10-19T01:00:00Z',
      expires_at: '2026-10-19T01:45:00Z',
      seconds_remaining: 2500,
      note: 'Minor bumper tap - 3 cars',
    };

    const result = mergeIncidentIntoCache([baseIncident], 'incident.validated', updateBroadcast);
    expect(result).toHaveLength(1);
    expect(result[0].status).toBe('validated');
    expect(result[0].confirmations).toBe(3);
    expect(result[0].note).toBe('Minor bumper tap - 3 cars');
    // Crucial: local user voting state was preserved!
    expect(result[0].user_voted).toBe(true);
    expect(result[0].user_vote).toBe('confirm');
  });

  it('removes incident from cache when resolved or expired', () => {
    const resolvedBroadcast: IncidentBroadcastData = {
      id: 'inc-1',
      incident_type: 'accident',
      status: 'resolved',
      lat: 12.9716,
      lng: 77.5946,
      confirmations: 3,
      rejections: 0,
      trust_score: 3.0,
      created_at: '2026-10-19T01:00:00Z',
      expires_at: '2026-10-19T01:45:00Z',
      seconds_remaining: 0,
    };

    const result = mergeIncidentIntoCache([baseIncident], 'incident.resolved', resolvedBroadcast);
    expect(result).toHaveLength(0);
  });

  it('is strictly idempotent when called multiple times with identical broadcast', () => {
    const updateBroadcast: IncidentBroadcastData = {
      id: 'inc-1',
      incident_type: 'accident',
      status: 'pending',
      lat: 12.9716,
      lng: 77.5946,
      confirmations: 2,
      rejections: 0,
      trust_score: 2.0,
      created_at: '2026-10-19T01:00:00Z',
      expires_at: '2026-10-19T01:45:00Z',
      seconds_remaining: 2600,
    };

    const pass1 = mergeIncidentIntoCache([baseIncident], 'incident.updated', updateBroadcast);
    const pass2 = mergeIncidentIntoCache(pass1, 'incident.updated', updateBroadcast);

    expect(pass2).toEqual(pass1);
    expect(pass2).toHaveLength(1);
    expect(pass2[0].confirmations).toBe(2);
  });

  it('ignores older out-of-order updates', () => {
    const validatedIncident: Incident = {
      ...baseIncident,
      status: 'validated',
      confirmations: 4,
      trust_score: 4.0,
    };

    const staleBroadcast: IncidentBroadcastData = {
      id: 'inc-1',
      incident_type: 'accident',
      status: 'pending',
      lat: 12.9716,
      lng: 77.5946,
      confirmations: 2, // stale count
      rejections: 0,
      trust_score: 2.0,
      created_at: '2026-10-19T01:00:00Z',
      expires_at: '2026-10-19T01:45:00Z',
      seconds_remaining: 2600,
    };

    const result = mergeIncidentIntoCache([validatedIncident], 'incident.updated', staleBroadcast);
    expect(result[0].confirmations).toBe(4);
    expect(result[0].status).toBe('validated');
  });

  it('sorts incidents by distance ascending', () => {
    const incFar: Incident = { ...baseIncident, id: 'far', distance_m: 2500 };
    const incNear: Incident = { ...baseIncident, id: 'near', distance_m: 350 };
    const incMid: Incident = { ...baseIncident, id: 'mid', distance_m: 1200 };

    const sorted = sortIncidentsByDistance([incFar, incNear, incMid]);
    expect(sorted.map((i) => i.id)).toEqual(['near', 'mid', 'far']);
  });
});
