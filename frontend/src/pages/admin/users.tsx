import React, { useState, useMemo } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import { adminApi } from '../../lib/api';
import toast from 'react-hot-toast';
import useSWR from 'swr';
import { RiShieldFill, RiUserAddFill, RiGroupFill, RiArrowDownSFill, RiShieldFlashFill, RiErrorWarningFill, RiCoinsFill, RiEditBoxFill, RiUserFollowFill, RiUserUnfollowFill, RiCloseFill, RiMore2Fill, RiFilter3Fill, RiCheckboxCircleFill, RiLoader4Line, RiVipCrownFill, RiSearchEyeFill, RiLineChartFill } from 'react-icons/ri';

const ROLES = ['student', 'researcher', 'seller', 'admin'];

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-red-100 text-red-700 border-red-200',
  seller: 'bg-purple-100 text-purple-700 border-purple-200',
  researcher: 'bg-blue-100 text-blue-700 border-blue-200',
  student: 'bg-gray-100 text-gray-700 border-gray-200',
};

function StatCard({ icon: Icon, label, value, color }: any) {
  return (
    <div className="card p-5 flex items-center gap-4">
      <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: `${color}18` }}>
        <Icon size={22} style={{ color }} />
      </div>
      <div>
        <p className="text-2xl font-bold" style={{ color: 'var(--text)', margin: 0 }}>{value}</p>
        <p className="text-xs" style={{ color: 'var(--text-3)', margin: 0 }}>{label}</p>
      </div>
    </div>
  );
}

import AdminGuard from '../../components/admin/AdminGuard';

export default function AdminUsersPage() {
  return (
    <AdminGuard>
      <AdminUsersPageContent />
    </AdminGuard>
  );
}

function AdminUsersPageContent() {
  const { data: usersData, error: usersError, mutate: mutateUsers } = useSWR('/admin/users');
  const { data: walletsData, error: walletsError, mutate: mutateWallets } = useSWR('/admin/credits/wallets', { refreshInterval: 30000 });

  const users: any[] = usersData || [];
  const wallets: any[] = walletsData || [];
  const loading = !usersData && !usersError;
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

  // Modals
  const [grantingUser, setGrantingUser] = useState<any>(null);
  const [grantAmount, setGrantAmount] = useState<number | ''>('');
  const [grantDescription, setGrantDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [roleModalUser, setRoleModalUser] = useState<any>(null);
  const [newRole, setNewRole] = useState('');

  const [addAdminModal, setAddAdminModal] = useState(false);
  const [adminEmail, setAdminEmail] = useState('');
  const [adminPrivileges, setAdminPrivileges] = useState({
    manage_users: true,
    kyc_payouts: true,
    manage_credits: true,
    review_datasets: true,
  });

  const [actionMenu, setActionMenu] = useState<string | null>(null);

  // Show error if failed
  if (usersError || walletsError) {
    if (usersError?.response?.status === 403 || walletsError?.response?.status === 403) {
      toast.error("You don't have admin privileges", { id: 'admin-403' });
    }
  }

  const getWallet = (userId: string) => wallets.find(w => w.user_id === userId);

  const filteredUsers = useMemo(() => {
    return users.filter(u => {
      const matchSearch = search === '' ||
        u.full_name?.toLowerCase().includes(search.toLowerCase()) ||
        u.email?.toLowerCase().includes(search.toLowerCase());
      const matchRole = roleFilter === 'all' || u.role === roleFilter;
      const matchStatus = statusFilter === 'all' ||
        (statusFilter === 'active' && u.is_verified) ||
        (statusFilter === 'suspended' && !u.is_verified) ||
        (statusFilter === 'paid' && (getWallet(u.id)?.balance ?? 0) > 0) ||
        (statusFilter === 'unpaid' && (getWallet(u.id)?.balance ?? 0) === 0);
      return matchSearch && matchRole && matchStatus;
    });
  }, [users, wallets, search, roleFilter, statusFilter]);

  const stats = useMemo(() => {
    const paid = users.filter(u => (getWallet(u.id)?.balance ?? 0) > 0).length;
    const suspended = users.filter(u => !u.is_verified).length;
    return {
      total: users.length,
      paid,
      unpaid: users.length - paid,
      suspended,
    };
  }, [users, wallets]);

  const handleGrant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!grantingUser || !grantAmount || !grantDescription) return;
    setIsSubmitting(true);
    try {
      const res = await adminApi.grantCredits(grantingUser.id, Number(grantAmount), grantDescription);
      toast.success(`Credits updated. New balance: ${res.data.balance}`);
      setGrantingUser(null);
      setGrantAmount('');
      setGrantDescription('');
      await mutateWallets();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update credits');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSuspend = async (user: any, suspend: boolean) => {
    try {
      await adminApi.suspendUser(user.id, suspend);
      toast.success(suspend ? `${user.full_name} suspended` : `${user.full_name} reactivated`);
      setActionMenu(null);
      await mutateUsers();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update user status');
    }
  };

  const handleChangeRole = async () => {
    if (!roleModalUser || !newRole) return;
    setIsSubmitting(true);
    try {
      await adminApi.changeRole(roleModalUser.id, newRole);
      toast.success(`Role changed to ${newRole}`);
      setRoleModalUser(null);
      await mutateUsers();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to change role');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AppLayout title="User Management" breadcrumbs={[{ label: 'Admin', href: '/admin/users' }, { label: 'Users' }]}>
      <div style={{ padding: '24px', maxWidth: 1300, margin: '0 auto' }}>

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold" style={{ fontFamily: 'Syne, sans-serif', color: 'var(--text)', margin: 0 }}>User Management</h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-3)' }}>Manage platform users, roles, and access control</p>
          </div>
          <button
            onClick={() => setAddAdminModal(true)}
            className="btn btn-primary flex items-center gap-2"
          >
            <RiVipCrownFill size={16} /> Add Admin
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard icon={RiGroupFill} label="Total Users" value={stats.total} color="#6366f1" />
          <StatCard icon={RiUserFollowFill} label="Paid Users" value={stats.paid} color="#10b981" />
          <StatCard icon={RiUserUnfollowFill} label="Unpaid Users" value={stats.unpaid} color="#f59e0b" />
          <StatCard icon={RiShieldFlashFill} label="Suspended" value={stats.suspended} color="#ef4444" />
        </div>

        {/* Filters */}
        <div className="card p-4 mb-4 flex flex-wrap gap-3 items-center">
          <div className="relative flex-1 min-w-[200px]">
            <RiSearchEyeFill size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-3)' }} />
            <input
              type="text"
              className="input w-full pl-9"
              placeholder="Search by name or email…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            <RiFilter3Fill size={15} style={{ color: 'var(--text-3)' }} />
            <select className="input" value={roleFilter} onChange={e => setRoleFilter(e.target.value)}>
              <option value="all">All Roles</option>
              {ROLES.map(r => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
            </select>
            <select className="input" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
              <option value="all">All Status</option>
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
              <option value="paid">Has Credits</option>
              <option value="unpaid">No Credits</option>
            </select>
          </div>
          <p className="text-xs ml-auto" style={{ color: 'var(--text-3)' }}>
            Showing {filteredUsers.length} of {users.length}
          </p>
        </div>

        {/* Table */}
        {loading ? (
          <div className="flex justify-center p-20"><RiLoader4Line className="animate-spin text-brand" size={32} /></div>
        ) : (
          <div className="card overflow-x-auto">
            <table className="w-full text-left text-sm" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                  <th className="px-4 py-3 font-semibold text-xs uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>User</th>
                  <th className="px-4 py-3 font-semibold text-xs uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>Role</th>
                  <th className="px-4 py-3 font-semibold text-xs uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>Credits</th>
                  <th className="px-4 py-3 font-semibold text-xs uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>Status</th>
                  <th className="px-4 py-3 font-semibold text-xs uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>Joined</th>
                  <th className="px-4 py-3 font-semibold text-xs uppercase tracking-wider text-center" style={{ color: 'var(--text-3)' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map(user => {
                  const wallet = getWallet(user.id);
                  const isSuspended = !user.is_verified;
                  return (
                    <tr key={user.id} className="border-b border-border hover:bg-surface-alt transition-colors relative">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0"
                            style={{ background: `hsl(${(user.full_name?.charCodeAt(0) ?? 65) * 5 % 360}, 60%, 55%)` }}>
                            {user.full_name?.charAt(0) ?? '?'}
                          </div>
                          <div>
                            <p className="font-semibold" style={{ color: 'var(--text)', margin: 0 }}>{user.full_name}</p>
                            <p className="text-xs" style={{ color: 'var(--text-3)', margin: 0 }}>{user.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${ROLE_COLORS[user.role] ?? ROLE_COLORS.student}`}>
                          {user.role}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-bold" style={{ color: 'var(--brand)' }}>
                        {wallet?.balance?.toFixed(2) ?? '0.00'}
                      </td>
                      <td className="px-4 py-3">
                        {isSuspended ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700 border border-red-200">
                            <RiErrorWarningFill size={10} /> Suspended
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700 border border-green-200">
                            <RiCheckboxCircleFill size={10} /> Active
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-3)' }}>
                        {user.created_at ? new Date(user.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-center gap-2">
                          <button
                            className="btn btn-secondary btn-sm flex items-center gap-1"
                            onClick={() => setGrantingUser(user)}
                            title="Adjust Credits"
                          >
                            <RiCoinsFill size={13} /> Credits
                          </button>
                          <div className="relative">
                            <button
                              className="btn btn-ghost btn-icon btn-sm"
                              onClick={(e) => {
                                e.stopPropagation();
                                setActionMenu(actionMenu === user.id ? null : user.id);
                              }}
                            >
                              <RiMore2Fill size={15} />
                            </button>
                            {actionMenu === user.id && (
                              <div
                                className="absolute right-0 z-[9999] card shadow-2xl py-1 min-w-[180px]"
                                style={{
                                  border: '1px solid var(--border)',
                                  bottom: '100%',
                                  marginBottom: 4,
                                }}
                              >
                                <button
                                  className="w-full text-left px-4 py-2 text-sm flex items-center gap-2 hover:bg-surface-alt transition-colors"
                                  onClick={() => { setRoleModalUser(user); setNewRole(user.role); setActionMenu(null); }}
                                >
                                  <RiEditBoxFill size={14} /> Change Role
                                </button>
                                {isSuspended ? (
                                  <button
                                    className="w-full text-left px-4 py-2 text-sm flex items-center gap-2 hover:bg-surface-alt transition-colors"
                                    style={{ color: '#10b981' }}
                                    onClick={() => handleSuspend(user, false)}
                                  >
                                    <RiShieldFill size={14} /> Reactivate User
                                  </button>
                                ) : (
                                  <button
                                    className="w-full text-left px-4 py-2 text-sm flex items-center gap-2 hover:bg-surface-alt transition-colors"
                                    style={{ color: '#ef4444' }}
                                    onClick={() => handleSuspend(user, true)}
                                  >
                                    <RiShieldFlashFill size={14} /> Suspend User
                                  </button>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {filteredUsers.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-12 text-center" style={{ color: 'var(--text-3)' }}>
                    No users match your filters.
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Grant Credits Modal */}
        {grantingUser && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50 backdrop-blur-sm">
            <div className="card p-6 max-w-md w-full shadow-2xl">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold" style={{ color: 'var(--text)', fontFamily: 'Syne,sans-serif' }}>Adjust Credits</h3>
                <button type="button" onClick={() => setGrantingUser(null)} className="btn btn-ghost btn-icon"><RiCloseFill size={16} /></button>
              </div>
              <p className="text-sm mb-6" style={{ color: 'var(--text-2)' }}>
                Adjusting balance for <strong style={{ color: 'var(--text)' }}>{grantingUser.full_name}</strong>. Use a negative amount to deduct.
              </p>
              <form onSubmit={handleGrant} className="flex flex-col gap-4">
                <div>
                  <label className="block text-sm font-semibold mb-1">Amount (positive or negative)</label>
                  <input type="number" step="0.01" className="input w-full" placeholder="e.g. 50 or -10"
                    value={grantAmount} onChange={e => setGrantAmount(e.target.value ? Number(e.target.value) : '')} required />
                </div>
                <div>
                  <label className="block text-sm font-semibold mb-1">Reason</label>
                  <input type="text" className="input w-full" placeholder="e.g. Refund for failed job"
                    value={grantDescription} onChange={e => setGrantDescription(e.target.value)} required />
                </div>
                <div className="flex justify-end gap-2 mt-2">
                  <button type="button" className="btn btn-ghost" onClick={() => setGrantingUser(null)}>Cancel</button>
                  <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                    {isSubmitting ? <RiLoader4Line size={16} className="animate-spin" /> : 'Confirm'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Change Role Modal */}
        {roleModalUser && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50 backdrop-blur-sm">
            <div className="card p-6 max-w-sm w-full shadow-2xl">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold" style={{ color: 'var(--text)', fontFamily: 'Syne,sans-serif' }}>Change Role</h3>
                <button type="button" onClick={() => setRoleModalUser(null)} className="btn btn-ghost btn-icon"><RiCloseFill size={16} /></button>
              </div>
              <p className="text-sm mb-4" style={{ color: 'var(--text-2)' }}>
                Change role for <strong style={{ color: 'var(--text)' }}>{roleModalUser.full_name}</strong>
              </p>
              <div className="flex flex-col gap-2 mb-6">
                {ROLES.map(role => (
                  <button key={role} type="button"
                    onClick={() => setNewRole(role)}
                    className="flex items-center justify-between px-4 py-3 rounded-xl border transition-all text-sm font-medium"
                    style={{
                      border: newRole === role ? '2px solid var(--brand)' : '1px solid var(--border)',
                      background: newRole === role ? 'rgba(var(--brand-rgb, 99,102,241), 0.07)' : 'var(--surface)',
                      color: 'var(--text)',
                    }}>
                    <span>{role.charAt(0).toUpperCase() + role.slice(1)}</span>
                    {newRole === role && <RiCheckboxCircleFill size={16} style={{ color: 'var(--brand)' }} />}
                  </button>
                ))}
              </div>
              <div className="flex justify-end gap-2">
                <button type="button" className="btn btn-ghost" onClick={() => setRoleModalUser(null)}>Cancel</button>
                <button type="button" className="btn btn-primary" onClick={handleChangeRole} disabled={isSubmitting || newRole === roleModalUser.role}>
                  {isSubmitting ? <RiLoader4Line size={16} className="animate-spin" /> : 'Apply Change'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Add Admin Modal */}
        {addAdminModal && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50 backdrop-blur-sm">
            <div className="card p-6 max-w-md w-full shadow-2xl">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold" style={{ color: 'var(--text)', fontFamily: 'Syne,sans-serif' }}>
                  <RiVipCrownFill size={20} className="inline mr-2 text-amber-500" />Promote to Admin
                </h3>
                <button type="button" onClick={() => setAddAdminModal(false)} className="btn btn-ghost btn-icon"><RiCloseFill size={16} /></button>
              </div>
              <p className="text-sm mb-4" style={{ color: 'var(--text-2)' }}>
                Find the user by email and assign them admin privileges.
              </p>
              <div className="mb-4">
                <label className="block text-sm font-semibold mb-1">User Email</label>
                <input type="email" className="input w-full" placeholder="user@example.com"
                  value={adminEmail} onChange={e => setAdminEmail(e.target.value)} />
              </div>
              <div className="mb-5">
                <label className="block text-sm font-semibold mb-2">Assign Privileges</label>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(adminPrivileges).map(([key, val]) => (
                    <label key={key} className="flex items-center gap-2 cursor-pointer text-sm px-3 py-2 rounded-lg border"
                      style={{ border: val ? '1px solid var(--brand)' : '1px solid var(--border)', background: val ? 'rgba(99,102,241,0.06)' : 'var(--surface)' }}>
                      <input type="checkbox" checked={val} onChange={e => setAdminPrivileges(prev => ({ ...prev, [key]: e.target.checked }))} className="accent-indigo-500" />
                      <span>{key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <button type="button" className="btn btn-ghost" onClick={() => setAddAdminModal(false)}>Cancel</button>
                <button type="button" className="btn btn-primary" onClick={() => {
                  const user = users.find(u => u.email.toLowerCase() === adminEmail.toLowerCase());
                  if (!user) { toast.error('User not found'); return; }
                  setRoleModalUser(user);
                  setNewRole('admin');
                  setAddAdminModal(false);
                }}>
                  Find & Promote
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Close dropdown on outside click */}
        {actionMenu && (
          <div className="fixed inset-0 z-40" onClick={() => setActionMenu(null)} />
        )}
      </div>
    </AppLayout>
  );
}
