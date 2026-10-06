import { http, HttpResponse } from 'msw';
import { dashboard, notifications } from './data';

let mockSession = false;
const user = { id: '1', name: 'María Fernanda', role: 'ADMIN' as const };

export const handlers = [
  http.get('*/auth/csrf/', () => HttpResponse.json({ token: 'development-only-csrf-token' })),
  http.post('*/auth/login/', async ({ request }) => {
    const input = await request.json() as { username?: string; password?: string };
    if (!input.username || !input.password) return HttpResponse.json({ detail: 'No fue posible iniciar sesión.' }, { status: 400 });
    mockSession = true;
    return HttpResponse.json({ access: 'mock-access-token', user });
  }),
  http.post('*/auth/refresh/', () => mockSession ? HttpResponse.json({ access: 'mock-access-token' }) : HttpResponse.json({ detail: 'No hay una sesión simulada activa.' }, { status: 401 })),
  http.get('*/auth/me/', () => mockSession ? HttpResponse.json(user) : HttpResponse.json({ detail: 'No autorizado.' }, { status: 401 })),
  http.post('*/auth/logout/', () => { mockSession = false; return new HttpResponse(null, { status: 204 }); }),
  http.get('*/dashboard/summary/', () => HttpResponse.json(dashboard)),
  http.get('*/notifications/', () => HttpResponse.json(notifications)),
  http.post('*/notifications/push-subscriptions/', () => HttpResponse.json({ id: 'mock-subscription' }, { status: 201 })),
];
