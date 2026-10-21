import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getAuditLogs } from '@/api/admin';
import { ChevronLeft, ChevronRight, Eye, Filter } from 'lucide-react';
import { AuditLogItem } from '@/types/admin';

export const AdminAuditPage: React.FC = () => {
  const [page, setPage] = useState<number>(1);
  const [actionFilter, setActionFilter] = useState<string>('');
  const [selectedLog, setSelectedLog] = useState<AuditLogItem | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['admin-audit', page, actionFilter],
    queryFn: () => getAuditLogs({ page, page_size: 15, action: actionFilter || undefined }),
  });

  const totalPages = Math.ceil((data?.total || 0) / 15) || 1;

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-900 border border-slate-800 p-4 rounded-xl">
        <div>
          <h1 className="text-base font-bold text-white tracking-wide">SYSTEM AUDIT TRAIL</h1>
          <p className="text-xs text-slate-400">Security-compliant ledger of all privileged and administrative events</p>
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={actionFilter}
            onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
            className="bg-slate-800 border border-slate-700 text-xs text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-cyan-500 font-mono"
          >
            <option value="">All Actions</option>
            <option value="ambulance.created">ambulance.created</option>
            <option value="ambulance.verified">ambulance.verified</option>
            <option value="ambulance.unverified">ambulance.unverified</option>
            <option value="user.deactivated">user.deactivated</option>
            <option value="user.reactivated">user.reactivated</option>
            <option value="incident.force_resolved">incident.force_resolved</option>
            <option value="dispatch.manual_assigned">dispatch.manual_assigned</option>
            <option value="dispatch.cancelled">dispatch.cancelled</option>
          </select>
        </div>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-800/60 text-slate-400 font-mono uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="p-3">Timestamp</th>
                <th className="p-3">Action</th>
                <th className="p-3">Target Entity</th>
                <th className="p-3">Actor Admin ID</th>
                <th className="p-3 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 font-mono text-slate-300">
              {isLoading ? (
                <tr><td colSpan={5} className="p-6 text-center text-slate-500">Loading audit records...</td></tr>
              ) : data?.items?.length === 0 ? (
                <tr><td colSpan={5} className="p-6 text-center text-slate-500">No audit events found</td></tr>
              ) : (
                data?.items?.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-800/40 transition">
                    <td className="p-3 text-slate-400">{new Date(item.created_at).toLocaleString()}</td>
                    <td className="p-3 font-semibold text-cyan-400">{item.action}</td>
                    <td className="p-3">{item.entity_type} {item.entity_id ? `(${item.entity_id.slice(0, 8)}...)` : ''}</td>
                    <td className="p-3 text-slate-400">{item.actor_user_id ? `${item.actor_user_id.slice(0, 8)}...` : 'System'}</td>
                    <td className="p-3 text-right">
                      <button
                        onClick={() => setSelectedLog(item)}
                        className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-[11px] border border-slate-700 transition inline-flex items-center gap-1"
                      >
                        <Eye className="w-3 h-3" /> View
                      </button>
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

      {/* Details Modal */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 max-w-lg w-full shadow-2xl space-y-3">
            <h3 className="text-sm font-bold text-white uppercase font-mono">{selectedLog.action} Details</h3>
            <pre className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-cyan-300 overflow-x-auto max-h-64">
              {JSON.stringify(selectedLog.details, null, 2)}
            </pre>
            <div className="flex justify-end">
              <button
                onClick={() => setSelectedLog(null)}
                className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs text-white rounded-lg transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
