import { useState, useEffect, useCallback } from 'react';
import {
  DispatchOfferData,
  DispatchResponse,
  WsDispatchCancelledMessage,
  WsDispatchOfferMessage,
  WsDispatchUpdatedMessage,
  WsServerMessage,
} from '@/types/dispatch';
import {
  acceptDispatch,
  declineDispatch,
  getCurrentDispatch,
  mapDispatchError,
  updateDispatchStatus,
} from '@/api/dispatch';
import { RealtimeClient } from '@/realtime/RealtimeClient';

interface UseAmbulanceDispatchProps {
  realtimeClient?: RealtimeClient | null;
  onDispatchCompletedOrCancelled?: () => void;
}

export function useAmbulanceDispatch({
  realtimeClient,
  onDispatchCompletedOrCancelled,
}: UseAmbulanceDispatchProps) {
  const [activeDispatch, setActiveDispatch] = useState<DispatchResponse | null>(null);
  const [incomingOffer, setIncomingOffer] = useState<DispatchOfferData | null>(null);
  const [cancellationNotice, setCancellationNotice] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Reconnect safe: fetch active dispatch from REST on mount & reconnect
  const loadActiveDispatch = useCallback(async () => {
    setIsLoading(true);
    try {
      const current = await getCurrentDispatch();
      setActiveDispatch(current);
    } catch {
      // Ignore initial lookup errors
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadActiveDispatch();
  }, [loadActiveDispatch]);

  // Handle WebSocket events
  useEffect(() => {
    if (!realtimeClient) return;

    const unsubscribe = realtimeClient.addListener((msg: WsServerMessage) => {
      if (msg.type === 'dispatch.offer' || (msg.type as string) === 'dispatch.offered') {
        const offerData = (msg as WsDispatchOfferMessage).data;
        setIncomingOffer(offerData);
      } else if (msg.type === 'dispatch.updated') {
        const updateData = (msg as WsDispatchUpdatedMessage).data;
        setActiveDispatch((prev) => {
          if (!prev || prev.id !== updateData.dispatch_id) return prev;
          if (updateData.status === 'completed' || updateData.status === 'cancelled') {
            onDispatchCompletedOrCancelled?.();
            return null;
          }
          return {
            ...prev,
            status: updateData.status,
            hospital_id: updateData.hospital_id ?? prev.hospital_id,
          };
        });
      } else if (msg.type === 'dispatch.cancelled') {
        const cancelledData = (msg as WsDispatchCancelledMessage).data;
        setCancellationNotice(
          cancelledData?.reason || 'Active dispatch was cancelled by the system.'
        );
        setActiveDispatch(null);
        setIncomingOffer(null);
        onDispatchCompletedOrCancelled?.();
      }
    });

    return () => {
      unsubscribe();
    };
  }, [realtimeClient, onDispatchCompletedOrCancelled]);

  const handleAccept = async (dispatchId: string) => {
    setIsLoading(true);
    setActionError(null);
    try {
      const disp = await acceptDispatch(dispatchId);
      setActiveDispatch(disp);
      setIncomingOffer(null);
      return disp;
    } catch (err) {
      const friendly = mapDispatchError(err);
      setActionError(friendly);
      setIncomingOffer(null); // Close expired or taken offer
      throw new Error(friendly);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDecline = async (dispatchId: string, reason?: string) => {
    setIsLoading(true);
    setActionError(null);
    try {
      await declineDispatch(dispatchId, reason);
      setIncomingOffer(null);
    } catch (err) {
      const friendly = mapDispatchError(err);
      setActionError(friendly);
      setIncomingOffer(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAdvance = async (nextStatus: string, hospitalId?: string) => {
    if (!activeDispatch) return;
    setIsLoading(true);
    setActionError(null);
    try {
      const updated = await updateDispatchStatus(activeDispatch.id, nextStatus, hospitalId);
      if (nextStatus === 'completed' || nextStatus === 'cancelled') {
        setActiveDispatch(null);
        onDispatchCompletedOrCancelled?.();
      } else {
        setActiveDispatch(updated);
      }
      return updated;
    } catch (err) {
      const friendly = mapDispatchError(err);
      setActionError(friendly);
      throw new Error(friendly);
    } finally {
      setIsLoading(false);
    }
  };

  return {
    activeDispatch,
    incomingOffer,
    cancellationNotice,
    isLoading,
    actionError,
    clearCancellationNotice: () => setCancellationNotice(null),
    dismissOffer: () => setIncomingOffer(null),
    acceptOffer: handleAccept,
    declineOffer: handleDecline,
    advanceStatus: handleAdvance,
    reloadDispatch: loadActiveDispatch,
  };
}
