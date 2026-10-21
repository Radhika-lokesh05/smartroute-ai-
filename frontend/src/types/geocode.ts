export interface GeocodeResult {
  label: string;
  lat: number;
  lng: number;
  locality?: string | null;
}

export interface GeocodeResponse {
  provider: string;
  warning?: string | null;
  results: GeocodeResult[];
}
