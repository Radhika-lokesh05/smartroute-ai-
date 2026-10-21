import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { cancelDispatch, getAdminDispatches } from '@/api/admin';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { DispatchResponse } from '@/types/dispatch';
import { Ban, ChevronLeft, ChevronRight, Filter } from 'lucide-react';

export const AdminDispatchesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [page, setPage] = useState<number>(1);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [cancelTarget, setCancelTarget] = useState<DispatchResponse | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['admin-dispatches', page, statusFilter],
    queryFn: () => getAdminDispatches({ page, page_size: 15, status: statusFilter || undefined }),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => cancelDispatch(id, 'Cancelled from Admin Dispatches Table'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-dispatches'] });
      setCancelTarget(null);
    },
  });

  const totalPages = Math.ceil((data?.total || 0) / 15) || 1;

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-900 border border-slate-800 p-4 rounded-xl">
        <div>
          <h1 className="text-base font-bold text-white tracking-wide">EMERGENCY DISPATCHES</h1>
          <p className="text-xs text-slate-400">Manage vehicle responses and active dispatch lifecycles</p>
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="bg-slate-800 border border-slate-700 text-xs text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-cyan-500 font-mono"
          >
            <option value="">All Statuses</option>
            {['offered', 'accepted', 'en_route_to_scene', 'at_scene', 'to_hospital', 'completed', 'declined', 'expired', 'cancelled'].map((st) => (
              <option key={st} value={st}>{st}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-800/60 text-slate-400 font-mono uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="p-3">Dispatch ID</th>
                <th className="p-3">Status</th>
                <th className="p-3">Emergency Type</th>
                <th className="p-3">ETA Scene</th>
                <th className="p-3">Offered At</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 font-mono text-slate-300">
              {isLoading ? (
                <tr><td colSpan={6} className="p-6 text-center text-slate-500">Loading dispatches...</td></tr>
              ) : data?.items?.length === 0 ? (
                <tr><td colSpan={6} className="p-6 text-center text-slate-500">No dispatches match the selected criteria</td></tr>
              ) : (
                data?.items?.map((d) => (
                  <tr key={d.id} className="hover:bg-slate-800/40 transition">
                    <td className="p-3 text-cyan-400">{d.id.slice(0, 8)}...</td>
                    <td className="p-3"><span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-[11px]">{d.status}</span></td>
                    <td className="p-3 capitalize">{d.emergency_type}</td>
                    <td className="p-3">{d.eta_to_scene_s ? `${d.eta_to_scene_s.toFixed(0)}s` : '—'}</td>
                    <td className="p-3 text-slate-400">{new Date(d.offered_at).toLocaleTimeString()}</td>
                    <td className="p-3 text-right">
                      {['offered', 'accepted', 'en_route_to_scene', 'at_scene', 'to_hospital'].includes(d.status) && (
                        <button
                          onClick={() => setCancelTarget(d)}
                          className="px-2.5 py-1 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 rounded text-[11px] transition flex items-center gap-1 ml-auto"
                        >
                          <Ban className="w-3 h-3" /> Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination controls */}
        <div className="flex items-center justify-between p-3 border-t border-slate-800 bg-slate-900/60 text-xs">
          <span className="text-slate-400 font-mono">Page {page} of {totalPages} ({data?.total || 0} total)</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1 rounded bg-slate-800 border border-slate-700 text-slate-300 disabled:opacity-40"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1 rounded bg-slate-800 border border-slate-700 text-slate-300 disabled:opacity-40"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <ConfirmDialog
        isOpen={cancelTarget !== null}
        title="Cancel Emergency Dispatch"
        message={`Are you sure you want to cancel dispatch ${cancelTarget?.id.slice(0, 8)}? The ambulance will return to available status.`}
        confirmLabel="Cancel Dispatch"
        onConfirm={() => cancelTarget && cancelMutation.mutate(cancelTarget.id)}
        onCancel={() => setCancelTarget(null)}
      />
    </div>
  );
};
