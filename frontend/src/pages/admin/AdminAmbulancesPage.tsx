import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getAdminAmbulances, unverifyAmbulance, verifyAmbulance } from '@/api/admin';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { AdminAmbulance } from '@/types/admin';
import { ChevronLeft, ChevronRight, ShieldAlert, ShieldCheck, Truck } from 'lucide-react';

export const AdminAmbulancesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [page, setPage] = useState<number>(1);
  const [unverifyTarget, setUnverifyTarget] = useState<AdminAmbulance | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['admin-ambulances', page],
    queryFn: () => getAdminAmbulances({ page, page_size: 15 }),
  });

  const unverifyMutation = useMutation({
    mutationFn: (id: string) => unverifyAmbulance(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-ambulances'] });
      setUnverifyTarget(null);
    },
  });

  const verifyMutation = useMutation({
    mutationFn: (id: string) => verifyAmbulance(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-ambulances'] }),
  });

  const totalPages = Math.ceil((data?.total || 0) / 15) || 1;

  return (
    <div className="space-y-4">
      <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl flex justify-between items-center">
        <div>
          <h1 className="text-base font-bold text-white tracking-wide">AMBULANCE FLEET</h1>
          <p className="text-xs text-slate-400">Manage vehicle verifications, status, and telemetry staleness</p>
        </div>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-800/60 text-slate-400 font-mono uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="p-3">Plate Number</th>
                <th className="p-3">Operator</th>
                <th className="p-3">Status</th>
                <th className="p-3">Verification</th>
                <th className="p-3">Last Telemetry</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 font-mono text-slate-300">
              {isLoading ? (
                <tr><td colSpan={6} className="p-6 text-center text-slate-500">Loading fleet records...</td></tr>
              ) : data?.items?.length === 0 ? (
                <tr><td colSpan={6} className="p-6 text-center text-slate-500">No ambulances found</td></tr>
              ) : (
                data?.items?.map((amb) => (
                  <tr key={amb.id} className="hover:bg-slate-800/40 transition">
                    <td className="p-3 font-bold text-cyan-400 flex items-center gap-2">
                      <Truck className="w-4 h-4 text-slate-500" />
                      <span>{amb.plate_number}</span>
                    </td>
                    <td className="p-3 text-slate-300 font-sans">{amb.user?.name || 'Unassigned'}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-[11px] ${
                        amb.status === 'available' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                        amb.status === 'busy' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                        'bg-slate-800 text-slate-400 border border-slate-700'
                      }`}>
                        {amb.status}
                      </span>
                    </td>
                    <td className="p-3">
                      {amb.is_verified ? (
                        <span className="flex items-center gap-1 text-emerald-400 text-[11px]">
                          <ShieldCheck className="w-3.5 h-3.5" /> Verified
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-slate-500 text-[11px]">
                          <ShieldAlert className="w-3.5 h-3.5" /> Unverified
                        </span>
                      )}
                    </td>
                    <td className="p-3 text-slate-400">
                      {amb.last_seen_at ? (
                        <span>{new Date(amb.last_seen_at).toLocaleTimeString()} {amb.is_stale && <span className="text-red-400 text-[10px]">(stale)</span>}</span>
                      ) : 'Never'}
                    </td>
                    <td className="p-3 text-right">
                      {amb.is_verified ? (
                        <button
                          onClick={() => setUnverifyTarget(amb)}
                          className="px-2.5 py-1 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 rounded text-[11px] transition"
                        >
                          Unverify
                        </button>
                      ) : (
                        <button
                          onClick={() => verifyMutation.mutate(amb.id)}
                          className="px-2.5 py-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded text-[11px] transition"
                        >
                          Verify
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between p-3 border-t border-slate-800 bg-slate-900/60 text-xs">
          <span className="text-slate-400 font-mono">Page {page} of {totalPages} ({data?.total || 0} total)</span>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="p-1 rounded bg-slate-800 border border-slate-700 text-slate-300 disabled:opacity-40">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="p-1 rounded bg-slate-800 border border-slate-700 text-slate-300 disabled:opacity-40">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <ConfirmDialog
        isOpen={unverifyTarget !== null}
        title="Revoke Ambulance Verification"
        message={`Are you sure you want to unverify ${unverifyTarget?.plate_number}? Unverified ambulances are automatically excluded from the emergency dispatch pool.`}
        confirmLabel="Revoke Verification"
        onConfirm={() => unverifyTarget && unverifyMutation.mutate(unverifyTarget.id)}
        onCancel={() => setUnverifyTarget(null)}
      />
    </div>
  );
};
