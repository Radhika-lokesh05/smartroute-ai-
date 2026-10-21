import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Header } from '@/components/Header';
import { MapView } from '@/components/MapView';
import { RoutePlanner } from '@/components/RoutePlanner';
import { FasterRouteNotice } from '@/components/FasterRouteNotice';
import { IncidentToasts } from '@/components/incidents/IncidentToasts';
import { NearbyIncidentsPanel } from '@/components/incidents/NearbyIncidentsPanel';
import { ReportIncidentModal } from '@/components/incidents/ReportIncidentModal';
import { HospitalListSheet } from '@/components/hospitals/HospitalListSheet';
import { AmbulanceWarningBanner } from '@/components/ambulance/AmbulanceWarningBanner';
import { AdminHintToasts } from '@/components/admin/AdminHintToasts';
import { useGeolocation } from '@/hooks/useGeolocation';
import { useRoutesQuery } from '@/hooks/useRoutesQuery';
import { useNearbyIncidentsQuery } from '@/hooks/useIncidentsQuery';
import { useRealtimeIncidents } from '@/realtime/useRealtimeIncidents';
import { useRouteImpactRefetch } from '@/hooks/useRouteImpactRefetch';
import { useMapAlerts } from '@/hooks/useMapAlerts';
import { useAmbulanceWarnings } from '@/hooks/useAmbulanceWarnings';
import { useAdminHints } from '@/hooks/useAdminHints';
import { WayPoint } from '@/types/routing';
import { fetchReverseGeocode } from '@/api/geocode';
import { ChevronUp, ChevronDown, Hospital as HospitalIcon } from 'lucide-react';

export const MapPage: React.FC = () => {
  const routerLocation = useLocation();
  const [origin, setOrigin] = useState<WayPoint | null>(null);
  const [destination, setDestination] = useState<WayPoint | null>(routerLocation.state?.destination || null);
  const [originText, setOriginText] = useState('');
  const [destinationText, setDestinationText] = useState(routerLocation.state?.destination?.label || '');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(true);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [isIncidentsPanelOpen, setIsIncidentsPanelOpen] = useState(false);
  const [isHospitalSheetOpen, setIsHospitalSheetOpen] = useState(false);
  const [isSoundEnabled, setIsSoundEnabled] = useState(false);
  const [dismissedFasterNotice, setDismissedFasterNotice] = useState(false);
  const [departureTime, setDepartureTime] = useState<string | undefined>(undefined);

  const { location: userLocation, error: gpsError, isLocating, locateMe, isSecureContext } = useGeolocation();
  const { data: routeResponse, isLoading: routesLoading, isError: routesError, error, refetch } = useRoutesQuery({ origin, destination, departureTime });
  const { data: incidents = [], isLoading: incidentsLoading } = useNearbyIncidentsQuery(userLocation);

  const { toasts, focusedLocation, setFocusedLocation, handleAlert, handleDismissToast, handleShowOnMap, addReportToast } = useMapAlerts(userLocation, isSoundEnabled);
  const { handleRouteImpact } = useRouteImpactRefetch({ hasActiveRoute: Boolean(origin && destination), refetchRoutes: refetch });

  const { status: connectionStatus, realtimeClient } = useRealtimeIncidents({ userLocation, onAlert: handleAlert, onRouteImpact: handleRouteImpact });
  const { warning: ambulanceWarning, dismiss: dismissAmbulanceWarning } = useAmbulanceWarnings({ realtimeClient });
  const { toasts: adminToasts, dismissToast: dismissAdminToast } = useAdminHints({ realtimeClient });

  const routes = routeResponse?.routes || [];
  const summary = routeResponse?.summary;
  const traffic = routeResponse?.traffic;
  const provider = routeResponse?.provider || 'ors';

  useEffect(() => {
    setSelectedIndex(0);
    setDismissedFasterNotice(false);
  }, [origin?.lat, origin?.lng, destination?.lat, destination?.lng]);

  const recommendedIdx = summary?.recommended_route_index ?? 0;
  const selectedRoute = routes[selectedIndex];
  const recommendedRoute = routes[recommendedIdx];
  const isFasterAvailable = Boolean(!dismissedFasterNotice && routes.length > 1 && selectedIndex !== recommendedIdx && recommendedRoute && selectedRoute && recommendedRoute.adjusted_duration_s < selectedRoute.adjusted_duration_s);

  const handleMapClick = async (lat: number, lng: number) => {
    setFocusedLocation(null);
    const fallback = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
    setDestination({ lat, lng, label: fallback });
    setDestinationText(fallback);
    try {
      const res = await fetchReverseGeocode(lat, lng);
      if (res.results?.[0]) {
        setDestination({ lat, lng, label: res.results[0].label });
        setDestinationText(res.results[0].label);
      }
    } catch {}
  };

  const renderPlanner = () => (
    <RoutePlanner
      origin={origin} destination={destination} originText={originText} destinationText={destinationText}
      setOriginText={setOriginText} setDestinationText={setDestinationText}
      onSelectOrigin={(i) => { setOrigin({ lat: i.lat, lng: i.lng, label: i.label }); setOriginText(i.label); }}
      onSelectDestination={(i) => { setDestination({ lat: i.lat, lng: i.lng, label: i.label }); setDestinationText(i.label); }}
      onUseMyLocation={() => userLocation ? (setOrigin({ lat: userLocation.lat, lng: userLocation.lng, label: 'My Current Location' }), setOriginText('My Current Location')) : locateMe()}
      onSwap={() => { const p = origin; const t = originText; setOrigin(destination); setOriginText(destinationText); setDestination(p); setDestinationText(t); }}
      routes={routes} summary={summary} traffic={traffic} departureTime={departureTime} onDepartureTimeChange={setDepartureTime}
      selectedIndex={selectedIndex} onSelectRouteIndex={setSelectedIndex}
      provider={provider} isLoading={routesLoading} isError={routesError} error={error} refetchRoutes={refetch}
      isLocating={isLocating} gpsError={gpsError}
    />
  );

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Header connectionStatus={connectionStatus} incidentCount={incidents.length} onToggleIncidents={() => setIsIncidentsPanelOpen((p) => !p)} isSoundEnabled={isSoundEnabled} onToggleSound={() => setIsSoundEnabled((p) => !p)} />
      <AmbulanceWarningBanner warning={ambulanceWarning} onDismiss={dismissAmbulanceWarning} userHeading={userLocation?.heading} />
      <main className="flex-1 relative flex overflow-hidden">
        <div className="hidden md:block w-96 lg:w-[420px] shrink-0 h-full z-10 shadow-2xl">{renderPlanner()}</div>
        <div className="flex-1 h-full relative">
          <MapView origin={origin} destination={destination} routes={routes} selectedIndex={selectedIndex} userLocation={userLocation} incidents={incidents} focusedLocation={focusedLocation} onMapClick={handleMapClick} onLocateMe={locateMe} onOpenReportModal={() => setIsReportModalOpen(true)} isLocating={isLocating} gpsError={gpsError} isSecureContext={isSecureContext} />

          {/* Emergency Hospitals Quick Trigger Button */}
          <div className="absolute top-4 left-4 z-10 pointer-events-auto">
            <button
              type="button"
              onClick={() => setIsHospitalSheetOpen(true)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-rose-950/90 hover:bg-rose-900 text-rose-300 border border-rose-800 shadow-xl backdrop-blur-md text-xs font-semibold active:scale-95 transition-all"
            >
              <HospitalIcon className="w-3.5 h-3.5 text-rose-400" />
              <span>Nearest emergency hospitals</span>
            </button>
          </div>

          {isFasterAvailable && recommendedRoute && selectedRoute && (
            <div className="absolute top-16 left-4 right-16 md:left-6 md:right-auto md:max-w-md z-20 pointer-events-auto">
              <FasterRouteNotice isOpen={isFasterAvailable} savedSeconds={selectedRoute.adjusted_duration_s - recommendedRoute.adjusted_duration_s} onSwitch={() => { setSelectedIndex(recommendedIdx); setDismissedFasterNotice(true); }} onDismiss={() => setDismissedFasterNotice(true)} />
            </div>
          )}

          <IncidentToasts toasts={toasts} onDismiss={handleDismissToast} onShowOnMap={handleShowOnMap} />
          <AdminHintToasts toasts={adminToasts} onDismiss={dismissAdminToast} />
          <NearbyIncidentsPanel isOpen={isIncidentsPanelOpen} onClose={() => setIsIncidentsPanelOpen(false)} incidents={incidents} onSelectIncident={(inc) => { setFocusedLocation([inc.lat, inc.lng]); setIsIncidentsPanelOpen(false); }} isLoading={incidentsLoading} />
          <ReportIncidentModal isOpen={isReportModalOpen} onClose={() => setIsReportModalOpen(false)} userLocation={userLocation} onSuccessToast={(msg) => addReportToast(msg, userLocation?.lat || 0, userLocation?.lng || 0)} />
          <HospitalListSheet isOpen={isHospitalSheetOpen} onClose={() => setIsHospitalSheetOpen(false)} userLocation={userLocation} onSelectHospital={(h) => { setDestination({ lat: h.lat, lng: h.lng, label: h.name }); setDestinationText(h.name); }} onLocateMe={locateMe} />

          <div className={`md:hidden absolute bottom-0 left-0 right-0 z-20 transition-all duration-300 bg-slate-950/95 border-t border-slate-800 shadow-2xl flex flex-col ${isMobileDrawerOpen ? 'max-h-[75vh] h-[65vh]' : 'h-12'}`}>
            <button type="button" onClick={() => setIsMobileDrawerOpen((p) => !p)} className="w-full h-12 flex items-center justify-between px-4 bg-slate-900 border-b border-slate-800 text-xs font-semibold text-slate-300">
              <span>{origin && destination ? 'Route Details' : 'Plan Your Route'}</span>
              {isMobileDrawerOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
            </button>
            <div className="flex-1 overflow-hidden">{renderPlanner()}</div>
          </div>
        </div>
      </main>
    </div>
  );
};
