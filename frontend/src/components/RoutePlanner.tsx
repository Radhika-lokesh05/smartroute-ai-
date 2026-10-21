import React from 'react';
import { WayPoint, RouteItem, RouteSummary, RouteTrafficSummary } from '@/types/routing';
import { GeocodeResult } from '@/types/geocode';
import { PlaceSearchInput } from './PlaceSearchInput';
import { LeaveAtPicker } from './LeaveAtPicker';
import { RouteStatusMessages } from './RouteStatusMessages';
import { RouteList } from './RouteList';
import { RouteSteps } from './RouteSteps';
import { RerouteBanner } from './RerouteBanner';
import { ArrowUpDown, Navigation2, Loader2, AlertCircle } from 'lucide-react';

interface RoutePlannerProps {
  origin: WayPoint | null;
  destination: WayPoint | null;
  originText: string;
  destinationText: string;
  setOriginText: (val: string) => void;
  setDestinationText: (val: string) => void;
  onSelectOrigin: (item: GeocodeResult) => void;
  onSelectDestination: (item: GeocodeResult) => void;
  onUseMyLocation: () => void;
  onSwap: () => void;
  routes: RouteItem[];
  summary?: RouteSummary | null;
  traffic?: RouteTrafficSummary | null;
  departureTime?: string;
  onDepartureTimeChange?: (val?: string) => void;
  selectedIndex: number;
  onSelectRouteIndex: (idx: number) => void;
  provider: string;
  isLoading: boolean;
  isError: boolean;
  error?: unknown;
  refetchRoutes?: () => void;
  isLocating?: boolean;
  gpsError?: string | null;
}

export const RoutePlanner: React.FC<RoutePlannerProps> = ({
  origin, destination, originText, destinationText, setOriginText, setDestinationText,
  onSelectOrigin, onSelectDestination, onUseMyLocation, onSwap, routes, summary, traffic,
  departureTime, onDepartureTimeChange, selectedIndex, onSelectRouteIndex, provider,
  isLoading, isError, error, refetchRoutes, isLocating, gpsError,
}) => {
  const selectedRoute = routes[selectedIndex];

  return (
    <div className="flex flex-col h-full bg-slate-950/95 backdrop-blur-md border-r border-slate-800 text-slate-100 p-4 overflow-y-auto">
      <div className="space-y-3 pb-3 border-b border-slate-800">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold tracking-tight text-slate-100">Plan Route</h2>
          <button
            type="button"
            onClick={onUseMyLocation}
            disabled={isLocating}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-cyan-950/60 hover:bg-cyan-900/60 text-cyan-300 border border-cyan-800/50 text-[11px] font-semibold transition-colors disabled:opacity-50"
            title="Set origin to your current GPS location"
          >
            {isLocating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Navigation2 className="w-3 h-3" />}
            Use My Location
          </button>
        </div>

        {gpsError && (
          <div className="p-2 rounded-lg bg-amber-950/40 border border-amber-800/40 text-[11px] text-amber-300 flex items-start gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
            <span>{gpsError}</span>
          </div>
        )}

        <div className="relative space-y-2">
          <PlaceSearchInput id="origin-input" label="Origin (Point A)" placeholder="Starting address..." value={originText} onChange={setOriginText} onSelect={onSelectOrigin} focusLat={origin?.lat} focusLng={origin?.lng} />
          <div className="flex justify-center -my-1 z-10 relative">
            <button type="button" onClick={onSwap} title="Swap origin and destination" className="p-1.5 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 shadow-md transition-transform active:scale-90">
              <ArrowUpDown className="w-3.5 h-3.5" />
            </button>
          </div>
          <PlaceSearchInput id="destination-input" label="Destination (Point B)" placeholder="Target address or click map..." value={destinationText} onChange={setDestinationText} onSelect={onSelectDestination} focusLat={destination?.lat} focusLng={destination?.lng} />
        </div>

        <LeaveAtPicker value={departureTime} onChange={onDepartureTimeChange || (() => {})} />
      </div>

      <div className="flex-1 py-3 space-y-3">
        {summary?.rerouted && (
          <RerouteBanner rerouted={true} incidentsCount={summary.incidents_considered} />
        )}

        <RouteStatusMessages isLoading={isLoading} isError={isError} error={error} onRetry={refetchRoutes} />

        {routes.length > 0 && (
          <>
            <RouteList routes={routes} selectedIndex={selectedIndex} onSelect={onSelectRouteIndex} provider={provider} traffic={traffic} />
            {selectedRoute && <RouteSteps steps={selectedRoute.steps} />}
          </>
        )}

        {!isLoading && !isError && routes.length === 0 && (
          <div className="text-center py-8 text-slate-500 text-xs">
            <p>Enter both origin & destination or click the map to select destination.</p>
          </div>
        )}
      </div>
    </div>
  );
};
