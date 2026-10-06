self.addEventListener('push', event => {
  const payload = event.data ? event.data.json() : { title: 'Herramientas JG', body: 'Tienes una nueva notificación.' };
  event.waitUntil(self.registration.showNotification(payload.title || 'Herramientas JG', { body: payload.body || '', icon: '/favicon.svg', data: { url: payload.url || '/dashboard' } }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow(event.notification.data?.url || '/dashboard'));
});
