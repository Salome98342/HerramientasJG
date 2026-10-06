export type Role = 'ADMIN' | 'CAJERO';
export interface SessionUser { id: string; username?: string; name: string; role: Role; business?: { id: number; nombre: string } | null; permissions?: { canViewFinancialReports: boolean; canManageUsers: boolean; canManageSettings: boolean } }
export interface DashboardSummary { salesToday: number; openRegister: boolean; registerAmount: number; investment: number; profit: number; expenses: number; chart: { day: string; sales: number; expenses: number }[]; alerts: { id: string; title: string; detail: string; kind: 'warning' | 'danger' }[] }
export interface AppNotification { id: string; title: string; detail: string; kind: 'warning' | 'danger' | 'info'; createdAt: string; read: boolean }
