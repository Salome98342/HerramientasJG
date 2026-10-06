import { createContext, useContext } from 'react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';
export interface ToastAction { label: string; onClick: () => void }
export interface ToastMessage { type: ToastType; title: string; message: string; action?: ToastAction }

export const ToastContext = createContext<{ push: (toast: ToastMessage) => void }>({ push: () => undefined });
export const useToast = () => useContext(ToastContext);
