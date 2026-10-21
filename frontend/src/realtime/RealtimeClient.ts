import {
  RealtimeConnectionStatus,
  WsClientMessage,
  WsIncidentEventMessage,
  WsServerMessage,
} from '@/types/incident';
import {
  WsAmbulanceClearMessage,
  WsAmbulanceNearbyMessage,
  WsDispatchCancelledMessage,
  WsDispatchOfferMessage,
  WsDispatchUpdatedMessage,
  WsHospitalPrealertMessage,
} from '@/types/dispatch';
import { calculateDistanceM } from '@/utils/coordinates';

export interface RealtimeClientOptions {
  apiBaseUrl: string;
  token: string;
  onStatusChange?: (status: RealtimeConnectionStatus) => void;
  onIncidentEvent?: (message: WsIncidentEventMessage) => void;
  onAmbulanceNearby?: (message: WsAmbulanceNearbyMessage) => void;
  onAmbulanceClear?: (message: WsAmbulanceClearMessage) => void;
  onDispatchOffer?: (message: WsDispatchOfferMessage) => void;
  onDispatchUpdated?: (message: WsDispatchUpdatedMessage) => void;
  onDispatchCancelled?: (message: WsDispatchCancelledMessage) => void;
  onHospitalPrealert?: (message: WsHospitalPrealertMessage) => void;
  onAnyMessage?: (message: WsServerMessage) => void;
  onReconnect?: () => void;
  onAuthFailed?: () => void;
}

export function getWebSocketUrl(apiBaseUrl: string): string {
  let url = apiBaseUrl.trim();
  if (!url || url.startsWith('/')) {
    const loc = typeof window !== 'undefined' ? window.location : { protocol: 'http:', host: 'localhost:8000' };
    const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${loc.host}/ws`;
  }
  url = url.replace(/^http:\/\//i, 'ws://').replace(/^https:\/\//i, 'wss://');
  url = url.replace(/\/+$/, '');
  return `${url}/ws`;
}

export class RealtimeClient {
  private ws: WebSocket | null = null;
  private wsUrl: string;
  private token: string;
  private status: RealtimeConnectionStatus = 'offline';

  // Subscription state
  private subLat: number | null = null;
  private subLng: number | null = null;
  private subRadiusM = 5000;
  private lastSubscribedAt = 0;
  private lastSubscribedCoords: { lat: number; lng: number } | null = null;

  // Heartbeat & reconnection
  private pingIntervalId: ReturnType<typeof setInterval> | null = null;
  private pongTimeoutId: ReturnType<typeof setTimeout> | null = null;
  private reconnectTimeoutId: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private isExplicitlyClosed = false;
  private isReconnecting = false;
  private isAuthenticated = false;

  // Callbacks
  private onStatusChange?: (status: RealtimeConnectionStatus) => void;
  private onIncidentEvent?: (message: WsIncidentEventMessage) => void;
  private onAmbulanceNearby?: (message: WsAmbulanceNearbyMessage) => void;
  private onAmbulanceClear?: (message: WsAmbulanceClearMessage) => void;
  private onDispatchOffer?: (message: WsDispatchOfferMessage) => void;
  private onDispatchUpdated?: (message: WsDispatchUpdatedMessage) => void;
  private onDispatchCancelled?: (message: WsDispatchCancelledMessage) => void;
  private onHospitalPrealert?: (message: WsHospitalPrealertMessage) => void;
  private onAnyMessage?: (message: WsServerMessage) => void;
  private onReconnect?: () => void;
  private onAuthFailed?: () => void;
  private listeners: Set<(msg: WsServerMessage) => void> = new Set();

  constructor(options: RealtimeClientOptions) {
    this.wsUrl = getWebSocketUrl(options.apiBaseUrl);
    this.token = options.token;
    this.onStatusChange = options.onStatusChange;
    this.onIncidentEvent = options.onIncidentEvent;
    this.onAmbulanceNearby = options.onAmbulanceNearby;
    this.onAmbulanceClear = options.onAmbulanceClear;
    this.onDispatchOffer = options.onDispatchOffer;
    this.onDispatchUpdated = options.onDispatchUpdated;
    this.onDispatchCancelled = options.onDispatchCancelled;
    this.onHospitalPrealert = options.onHospitalPrealert;
    this.onAnyMessage = options.onAnyMessage;
    this.onReconnect = options.onReconnect;
    this.onAuthFailed = options.onAuthFailed;
  }

  public addListener(listener: (msg: WsServerMessage) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  public sendMessage(msg: WsClientMessage): void {
    this.sendJson(msg);
  }

  public sendLocation(lat: number, lng: number, heading = 0, speed = 0): void {
    this.sendJson({
      type: 'ambulance.location',
      lat,
      lng,
      heading,
      speed,
    });
  }

  public connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isExplicitlyClosed = false;
    this.setStatus(this.isReconnecting ? 'reconnecting' : 'connecting');

    try {
      this.ws = new WebSocket(this.wsUrl);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = this.handleOpen.bind(this);
    this.ws.onmessage = this.handleMessage.bind(this);
    this.ws.onerror = this.handleError.bind(this);
    this.ws.onclose = this.handleClose.bind(this);
  }

  public updateToken(token: string): void {
    this.token = token;
    if (this.status === 'offline') {
      this.connect();
    }
  }

  public subscribe(lat: number, lng: number, radiusM = 5000): void {
    this.subLat = lat;
    this.subLng = lng;
    this.subRadiusM = radiusM;

    // Check throttle rules: only re-subscribe if moved > 500m or > 2 minutes elapsed
    const now = Date.now();
    if (this.lastSubscribedCoords && now - this.lastSubscribedAt < 120000) {
      const movedM = calculateDistanceM(
        this.lastSubscribedCoords.lat,
        this.lastSubscribedCoords.lng,
        lat,
        lng
      );
      if (movedM < 500) {
        return; // Suppress redundant subscription
      }
    }

    if (this.isAuthenticated && this.ws?.readyState === WebSocket.OPEN) {
      this.sendSubscribe();
    }
  }

  public subscribeArea(lat: number, lng: number, radiusM = 5000): void {
    this.subscribe(lat, lng, radiusM);
  }

  private sendSubscribe(): void {
    if (this.subLat === null || this.subLng === null) return;
    this.sendJson({
      type: 'subscribe',
      lat: this.subLat,
      lng: this.subLng,
      radius_m: this.subRadiusM,
    });
    this.lastSubscribedAt = Date.now();
    this.lastSubscribedCoords = { lat: this.subLat, lng: this.subLng };
  }

  private handleOpen(): void {
    // First message after open MUST be auth; token is never sent in URL
    this.sendJson({
      type: 'auth',
      token: this.token,
    });
    this.startHeartbeat();
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const msg: WsServerMessage = JSON.parse(event.data);

      // Notify generic observers and listeners
      this.onAnyMessage?.(msg);
      this.listeners.forEach((listener) => {
        try {
          listener(msg);
        } catch {}
      });

      if (msg.type === 'auth.success') {
        this.isAuthenticated = true;
        this.reconnectAttempts = 0;
        this.setStatus('live');

        // Immediately send spatial subscription
        if (this.subLat !== null && this.subLng !== null) {
          this.sendSubscribe();
        }

        // If this was a reconnection, notify caller to refetch missed incidents
        if (this.isReconnecting) {
          this.isReconnecting = false;
          this.onReconnect?.();
        }
      } else if (msg.type === 'pong') {
        this.clearPongTimeout();
      } else if (
        msg.type === 'incident.created' ||
        msg.type === 'incident.updated' ||
        msg.type === 'incident.validated' ||
        msg.type === 'incident.resolved' ||
        msg.type === 'incident.expired'
      ) {
        this.onIncidentEvent?.(msg as WsIncidentEventMessage);
      } else if (msg.type === 'ambulance.nearby') {
        this.onAmbulanceNearby?.(msg);
      } else if (msg.type === 'ambulance.clear') {
        this.onAmbulanceClear?.(msg);
      } else if (msg.type === 'dispatch.offer' || (msg.type as string) === 'dispatch.offered') {
        this.onDispatchOffer?.(msg as WsDispatchOfferMessage);
      } else if (msg.type === 'dispatch.updated') {
        this.onDispatchUpdated?.(msg);
      } else if (msg.type === 'dispatch.cancelled') {
        this.onDispatchCancelled?.(msg);
      } else if (msg.type === 'hospital.prealert') {
        this.onHospitalPrealert?.(msg);
      }
    } catch {
      // Ignore malformed JSON messages
    }
  }

  private handleError(): void {
    // Errors bubble to onclose
  }

  private handleClose(event: CloseEvent): void {
    this.isAuthenticated = false;
    this.clearHeartbeat();

    // Close code 4401: Unauthorized token / auth failure -> stop retrying and logout
    if (event.code === 4401) {
      this.setStatus('offline');
      this.onAuthFailed?.();
      return;
    }

    if (!this.isExplicitlyClosed) {
      this.isReconnecting = true;
      this.scheduleReconnect();
    } else {
      this.setStatus('offline');
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimeout();
    this.setStatus('reconnecting');

    // Exponential backoff with jitter: min 1s, doubling up to max 30s
    this.reconnectAttempts += 1;
    const baseDelay = Math.min(30000, 1000 * Math.pow(2, this.reconnectAttempts - 1));
    const jitter = Math.random() * 1000;
    const delay = Math.min(30000, baseDelay + jitter);

    this.reconnectTimeoutId = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private startHeartbeat(): void {
    this.clearHeartbeat();
    this.pingIntervalId = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.sendJson({ type: 'ping' });
        // Set a 10-second deadline for pong; treat absence as dead connection
        this.pongTimeoutId = setTimeout(() => {
          if (this.ws) {
            this.ws.close();
          }
        }, 10000);
      }
    }, 25000);
  }

  private clearPongTimeout(): void {
    if (this.pongTimeoutId) {
      clearTimeout(this.pongTimeoutId);
      this.pongTimeoutId = null;
    }
  }

  private clearHeartbeat(): void {
    if (this.pingIntervalId) {
      clearInterval(this.pingIntervalId);
      this.pingIntervalId = null;
    }
    this.clearPongTimeout();
  }

  private clearReconnectTimeout(): void {
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }
  }

  private sendJson(msg: WsClientMessage): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  private setStatus(newStatus: RealtimeConnectionStatus): void {
    if (this.status !== newStatus) {
      this.status = newStatus;
      this.onStatusChange?.(newStatus);
    }
  }

  public getStatus(): RealtimeConnectionStatus {
    return this.status;
  }

  public disconnect(): void {
    this.isExplicitlyClosed = true;
    this.clearHeartbeat();
    this.clearReconnectTimeout();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setStatus('offline');
  }
}
