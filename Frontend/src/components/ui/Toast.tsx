import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { CheckCircle2, Info, TriangleAlert, X } from 'lucide-react';
import { ToastContext, type ToastMessage } from './ToastContext';

interface ToastItem extends ToastMessage { id: number }
const icon = { success: CheckCircle2, error: TriangleAlert, warning: TriangleAlert, info: Info };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((toast: Omit<ToastItem, 'id'>) => {
    const id = Date.now() + Math.random();
    setItems(current => [...current.slice(-3), { ...toast, id }]);
    window.setTimeout(() => setItems(current => current.filter(item => item.id !== id)), 5000);
  }, []);
  const value = useMemo(() => ({ push }), [push]);
  return <ToastContext.Provider value={value}>{children}<div className="jg-toast" role="status" aria-live="polite">
    {items.map(item => {
      const Icon = icon[item.type];
      return <div className={`jg-toast__item jg-toast__item--${item.type}`} key={item.id}><Icon size={20} /><div><strong>{item.title}</strong><p>{item.message}</p>{item.action && <button className="jg-toast__action" onClick={item.action.onClick}>{item.action.label}</button>}</div><button className="jg-icon-button" aria-label="Cerrar notificación" onClick={() => setItems(current => current.filter(entry => entry.id !== item.id))}><X size={16} /></button></div>;
    })}
  </div></ToastContext.Provider>;
}
