import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import App from '@/app/App';
import '@/styles/index.css';
const client = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });
async function start() { if (import.meta.env.DEV && import.meta.env.VITE_ENABLE_MOCKS === 'true') { const { worker } = await import('@/mocks/browser'); await worker.start({ onUnhandledRequest: 'bypass' }); } ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={client}><BrowserRouter><App /></BrowserRouter></QueryClientProvider></React.StrictMode>); }
void start();
