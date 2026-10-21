import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/auth/useAuth';
import { RealtimeClient } from '@/realtime/RealtimeClient';
import { WsDispatchUpdatedMessage, WsHospitalPrealertMessage, WsServerMessage } from '@/types/dispatch';

export interface AdminHintToast {
  id: string;
  title: string;
  message: string;
  type: 'prealert' | 'dispatch';
  timestamp: number;
}

interface UseAdminHintsProps {
  realtimeClient?: RealtimeClient | null;
}

export function useAdminHints({ realtimeClient }: UseAdminHintsProps) {
  const { user } = useAuth();
  const [toasts, setToasts] = useState<AdminHintToast[]>([]);

  const addToast = useCallback((title: string, message: string, type: 'prealert' | 'dispatch') => {
    const id = `hint-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`;
    const newToast: AdminHintToast = {
      id,
      title,
      message,
      type,
      timestamp: Date.now(),
    };
    setToasts((prev) => [...prev.slice(-3), newToast]); // keep at most 4 toasts

    // Auto dismiss after 6s
    setTimeout(() => {
      setToasts((current) => current.filter((t) => t.id !== id));
    }, 6000);
  }, []);

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  useEffect(() => {
    if (!realtimeClient || user?.role !== 'admin') return;

    const unsubscribe = realtimeClient.addListener((msg: WsServerMessage) => {
      if (msg.type === 'hospital.prealert') {
        const data = (msg as WsHospitalPrealertMessage).data;
        const etaText = data.eta_s ? `ETA ~${Math.round(data.eta_s / 60)} min` : 'Inbound';
        addToast(
          'Hospital Pre-Alert',
          `Emergency transport underway (${data.emergency_type || 'General'}). ${etaText}`,
          'prealert'
        );
      } else if (msg.type === 'dispatch.updated') {
        const data = (msg as WsDispatchUpdatedMessage).data;
        addToast(
          'Dispatch Status Update',
          `Ambulance dispatch updated to '${data.status}'.`,
          'dispatch'
        );
      }
    });

    return () => {
      unsubscribe();
    };
  }, [realtimeClient, user?.role, addToast]);

  return {
    toasts,
    dismissToast,
  };
}
