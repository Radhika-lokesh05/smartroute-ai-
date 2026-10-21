import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getAdminUsers, toggleUserActive } from '@/api/admin';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { AdminUser } from '@/types/admin';
import { ChevronLeft, ChevronRight, Search } from 'lucide-react';

export const AdminUsersPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [page, setPage] = useState<number>(1);
  const [search, setSearch] = useState<string>('');
  const [roleFilter, setRoleFilter] = useState<string>('');
  const [toggleTarget, setToggleTarget] = useState<AdminUser | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['admin-users', page, search, roleFilter],
    queryFn: () => getAdminUsers({ page, page_size: 15, search: search || undefined, role: roleFilter || undefined }),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => toggleUserActive(id, active),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setToggleTarget(null);
    },
  });

  const totalPages = Math.ceil((data?.total || 0) / 15) || 1;

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-900 border border-slate-800 p-4 rounded-xl">
        <div>
          <h1 className="text-base font-bold text-white tracking-wide">USER MANAGEMENT</h1>
          <p className="text-xs text-slate-400">Search users, view system roles, and manage account authorization</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search name or email..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="bg-slate-800 border border-slate-700 text-xs text-slate-200 rounded-lg pl-8 pr-3 py-1.5 focus:outline-none focus:border-cyan-500 font-mono w-48 sm:w-60"
            />
          </div>

          <select
            value={roleFilter}
            onChange={(e) => { setRoleFilter(e.target.value); setPage(1); }}
            className="bg-slate-800 border border-slate-700 text-xs text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-cyan-500 font-mono"
          >
            <option value="">All Roles</option>
            <option value="civilian">Civilian</option>
            <option value="ambulance">Ambulance</option>
            <option value="admin">Admin</option>
          </select>
        </div>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-800/60 text-slate-400 font-mono uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="p-3">Name</th>
                <th className="p-3">Email Address</th>
                <th className="p-3">Role</th>
                <th className="p-3">Status</th>
                <th className="p-3">Registered</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 font-mono text-slate-300">
              {isLoading ? (
                <tr><td colSpan={6} className="p-6 text-center text-slate-500">Loading user directory...</td></tr>
              ) : data?.items?.length === 0 ? (
                <tr><td colSpan={6} className="p-6 text-center text-slate-500">No users match query</td></tr>
              ) : (
                data?.items?.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-800/40 transition">
                    <td className="p-3 font-semibold text-slate-100 font-sans">{u.name}</td>
                    <td className="p-3 text-cyan-400">{u.email}</td>
                    <td className="p-3 capitalize">{u.role}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-[11px] ${
                        u.is_active ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'
                      }`}>
                        {u.is_active ? 'Active' : 'Deactivated'}
                      </span>
                    </td>
                    <td className="p-3 text-slate-400">{new Date(u.created_at).toLocaleDateString()}</td>
                    <td className="p-3 text-right">
                      <button
                        onClick={() => setToggleTarget(u)}
                        className={`px-2.5 py-1 rounded text-[11px] transition border ${
                          u.is_active
                            ? 'bg-red-500/10 hover:bg-red-500/20 text-red-400 border-red-500/30'
                            : 'bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                        }`}
                      >
                        {u.is_active ? 'Deactivate' : 'Reactivate'}
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

      <ConfirmDialog
        isOpen={toggleTarget !== null}
        title={toggleTarget?.is_active ? 'Deactivate User Account' : 'Reactivate User Account'}
        message={
          toggleTarget?.is_active
            ? `Deactivating ${toggleTarget?.email} will immediately invalidate all existing sessions and disconnect open WebSockets.`
            : `Reactivating ${toggleTarget?.email} will allow the user to log in and participate in reporting or dispatching.`
        }
        confirmLabel={toggleTarget?.is_active ? 'Deactivate' : 'Reactivate'}
        isDestructive={toggleTarget?.is_active}
        onConfirm={() => toggleTarget && toggleMutation.mutate({ id: toggleTarget.id, active: !toggleTarget.is_active })}
        onCancel={() => setToggleTarget(null)}
      />
    </div>
  );
};
