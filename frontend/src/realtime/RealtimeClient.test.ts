import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { RealtimeClient, getWebSocketUrl } from './RealtimeClient';

// Minimal Mock WebSocket
class MockWebSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSING = 2;
  static CLOSED = 3;

  public url: string;
  public readyState: number = MockWebSocket.CONNECTING;
  public sentMessages: string[] = [];

  public onopen: ((event: Event) => void) | null = null;
  public onmessage: ((event: MessageEvent) => void) | null = null;
  public onclose: ((event: CloseEvent) => void) | null = null;
  public onerror: ((event: Event) => void) | null = null;

  static instances: MockWebSocket[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    setTimeout(() => {
      if (this.readyState === MockWebSocket.CONNECTING) {
        this.readyState = MockWebSocket.OPEN;
        this.onopen?.(new Event('open'));
      }
    }, 10);
  }

  send(data: string) {
    this.sentMessages.push(data);
  }

  close(code = 1000, reason = '') {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({ code, reason } as CloseEvent);
  }

  simulateServerMessage(msg: unknown) {
    this.onmessage?.({ data: JSON.stringify(msg) } as MessageEvent);
  }
}

describe('RealtimeClient', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('correctly converts http and https URLs to ws and wss without token in query', () => {
    expect(getWebSocketUrl('http://localhost:8000')).toBe('ws://localhost:8000/ws');
    expect(getWebSocketUrl('https://api.smartroute.ai/')).toBe('wss://api.smartroute.ai/ws');
  });

  it('connects and sends auth message as the very first packet after open', async () => {
    const onStatusChange = vi.fn();
    const client = new RealtimeClient({
      apiBaseUrl: 'http://localhost:8000',
      token: 'test-jwt-token-123',
      onStatusChange,
    });

    client.connect();
    expect(MockWebSocket.instances).toHaveLength(1);
    const ws = MockWebSocket.instances[0];

    // Verify token is NOT in URL query
    expect(ws.url).toBe('ws://localhost:8000/ws');
    expect(ws.url).not.toContain('test-jwt-token-123');

    // Fast-forward connection open
    await vi.advanceTimersByTimeAsync(15);
    expect(ws.sentMessages).toHaveLength(1);
    const firstMsg = JSON.parse(ws.sentMessages[0]);
    expect(firstMsg).toEqual({ type: 'auth', token: 'test-jwt-token-123' });

    // Server responds with auth.success
    ws.simulateServerMessage({ v: 1, type: 'auth.success', user_id: 'user-1' });
    expect(client.getStatus()).toBe('live');

    client.disconnect();
  });

  it('sends subscribe after auth and throttles redundant re-subscriptions', async () => {
    const client = new RealtimeClient({
      apiBaseUrl: 'http://localhost:8000',
      token: 'jwt-token',
    });

    client.subscribe(12.9716, 77.5946, 5000);
    client.connect();

    await vi.advanceTimersByTimeAsync(15);
    const ws = MockWebSocket.instances[0];
    ws.simulateServerMessage({ v: 1, type: 'auth.success', user_id: 'user-1' });

    // Should have sent auth and subscribe
    expect(ws.sentMessages).toHaveLength(2);
    const subMsg = JSON.parse(ws.sentMessages[1]);
    expect(subMsg).toEqual({
      type: 'subscribe',
      lat: 12.9716,
      lng: 77.5946,
      radius_m: 5000,
    });

    // Move only 20 meters: should NOT send another subscribe message
    client.subscribe(12.9717, 77.5946, 5000);
    expect(ws.sentMessages).toHaveLength(2);

    // Move 1500 meters away: should trigger a new subscribe message
    client.subscribe(12.9850, 77.5946, 5000);
    expect(ws.sentMessages).toHaveLength(3);
    const subMsg2 = JSON.parse(ws.sentMessages[2]);
    expect(subMsg2.lat).toBe(12.9850);

    client.disconnect();
  });

  it('stops reconnecting on 4401 unauthorized close and calls onAuthFailed', async () => {
    const onAuthFailed = vi.fn();
    const onStatusChange = vi.fn();

    const client = new RealtimeClient({
      apiBaseUrl: 'http://localhost:8000',
      token: 'bad-token',
      onAuthFailed,
      onStatusChange,
    });

    client.connect();
    await vi.advanceTimersByTimeAsync(15);

    const ws = MockWebSocket.instances[0];
    // Server rejects with close code 4401
    ws.close(4401, 'Unauthorized');

    expect(client.getStatus()).toBe('offline');
    expect(onAuthFailed).toHaveBeenCalledTimes(1);

    // Advance time: should NOT have spawned any new reconnect attempts
    await vi.advanceTimersByTimeAsync(35000);
    expect(MockWebSocket.instances).toHaveLength(1);

    client.disconnect();
  });

  it('schedules exponential backoff reconnect on unexpected close', async () => {
    const onReconnect = vi.fn();
    const client = new RealtimeClient({
      apiBaseUrl: 'http://localhost:8000',
      token: 'valid-token',
      onReconnect,
    });

    client.connect();
    await vi.advanceTimersByTimeAsync(15);
    const ws1 = MockWebSocket.instances[0];
    ws1.simulateServerMessage({ v: 1, type: 'auth.success', user_id: 'user-1' });

    // Unexpected disconnect (network dropped, code 1006)
    ws1.close(1006, 'Abnormal closure');
    expect(client.getStatus()).toBe('reconnecting');

    // Advance through backoff delay
    await vi.advanceTimersByTimeAsync(2000);
    expect(MockWebSocket.instances).toHaveLength(2);

    const ws2 = MockWebSocket.instances[1];
    await vi.advanceTimersByTimeAsync(15);
    ws2.simulateServerMessage({ v: 1, type: 'auth.success', user_id: 'user-1' });

    expect(client.getStatus()).toBe('live');
    expect(onReconnect).toHaveBeenCalledTimes(1);

    client.disconnect();
  });

  it('sends heartbeat ping every 25s and handles pong', async () => {
    const client = new RealtimeClient({
      apiBaseUrl: 'http://localhost:8000',
      token: 'test-token',
    });

    client.connect();
    await vi.advanceTimersByTimeAsync(15);
    const ws = MockWebSocket.instances[0];
    ws.simulateServerMessage({ v: 1, type: 'auth.success', user_id: 'user-1' });

    // Advance 25 seconds
    await vi.advanceTimersByTimeAsync(25000);
    const pingMsg = ws.sentMessages.find((m) => m.includes('"ping"'));
    expect(pingMsg).toBeDefined();

    // Server sends pong
    ws.simulateServerMessage({ v: 1, type: 'pong' });

    client.disconnect();
  });
});
