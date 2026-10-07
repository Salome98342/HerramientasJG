import { lazy, Suspense, useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { useAppStore } from '@/store/appStore';
import { apiFetch, tokenMemory } from '@/lib/apiClient';
import { ToastProvider } from '@/components/ui/Toast';
import { ProtectedLayout, RoleGuard } from './guards';
const Login = lazy(() => import('@/features/auth/Login'));
const Dashboard = lazy(() => import('@/features/dashboard/Dashboard'));
const Inventario = lazy(() => import('@/features/inventario/Inventario'));
const Compras = lazy(() => import('@/features/inventario/Compras'));
const Cajas = lazy(() => import('@/features/cajas/Cajas'));
const Ventas = lazy(() => import('@/features/ventas/Ventas'));
const CreditosSeparados = lazy(() => import('@/features/ventas/CreditosSeparados'));
const Clientes = lazy(() => import('@/features/ventas/Clientes'));
const Alquileres = lazy(() => import('@/features/alquileres/Alquileres'));
const InventarioAlquiler = lazy(() => import('@/features/alquileres/InventarioAlquilerRoute'));
const Gastos = lazy(() => import('@/features/finanzas/Gastos'));
const Reportes = lazy(() => import('@/features/finanzas/Reportes'));
function SessionBootstrap() { const setUser = useAppStore(s => s.setUser); useEffect(() => { let alive = true; void apiFetch<{ access: string }>('/auth/refresh/', { method: 'POST' }).then(data => { tokenMemory.set(data.access); return apiFetch<{ id: string; name: string; role: 'ADMIN' | 'CAJERO' }>('/auth/me/'); }).then(user => { if (alive) setUser(user); }).catch(() => undefined); return () => { alive = false; }; }, [setUser]); return null; }
export default function App() { return <ToastProvider><SessionBootstrap/><Suspense fallback={<div className="jg-loading">Cargando…</div>}><Routes><Route path="/login" element={<Login/>}/><Route element={<ProtectedLayout/>}><Route path="/" element={<Navigate to="/dashboard" replace/>}/><Route path="/dashboard" element={<Dashboard/>}/><Route path="/ventas" element={<Ventas/>}/><Route path="/creditos" element={<CreditosSeparados/>}/><Route path="/clientes" element={<Clientes/>}/><Route path="/inventario" element={<Inventario/>}/><Route path="/inventario-alquiler" element={<InventarioAlquiler/>}/><Route path="/alquileres" element={<Alquileres/>}/><Route path="/compras" element={<Compras/>}/><Route path="/cajas" element={<Cajas/>}/><Route path="/gastos" element={<Gastos/>}/><Route path="/reportes" element={<RoleGuard roles={['ADMIN']}><Reportes/></RoleGuard>}/><Route path="/configuracion" element={<RoleGuard roles={['ADMIN']}><PageSoon title="Configuración"/></RoleGuard>}/><Route path="/usuarios" element={<RoleGuard roles={['ADMIN']}><PageSoon title="Usuarios"/></RoleGuard>}/><Route path="*" element={<PageSoon title="Módulo en preparación"/>}/></Route></Routes></Suspense></ToastProvider>; }
function PageSoon({ title }: { title: string }) { return <main className="jg-page"><h1>{title}</h1><p>Esta pantalla se incorporará en una fase siguiente.</p></main>; }
