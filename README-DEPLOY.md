# Despliegue en Linux sin contenedores

Esta guía instala PostgreSQL, Django/Gunicorn, el frontend compilado y Nginx mediante servicios del sistema. Usa Ubuntu Server 24.04 LTS como referencia. Ejecuta primero en staging; para producción usa un dominio y secretos propios.

## 1. Instalar dependencias del sistema

```sh
sudo apt update
sudo apt install -y python3 python3-venv python3-pip build-essential libpq-dev \
  postgresql postgresql-contrib nginx certbot python3-certbot-nginx nodejs npm
```

Node.js debe ser 22 LTS o superior compatible con el `package-lock.json`. Si el paquete de la distribución es antiguo, instala Node 22 LTS desde el repositorio oficial aprobado por tu organización.

## 2. Crear la base de datos

Genera una contraseña aleatoria, crea un rol dedicado y limita PostgreSQL a conexiones locales. No uses la contraseña de ejemplo en [Backend/.env.production.example](./Backend/.env.production.example).

```sh
sudo -u postgres psql
```

```sql
CREATE ROLE herramientas_jg LOGIN PASSWORD 'REEMPLAZAR_POR_SECRETO_ALEATORIO';
CREATE DATABASE herramientas_jg OWNER herramientas_jg;
\q
```

Ajusta `pg_hba.conf` a autenticación `scram-sha-256`, conserva la escucha local y reinicia PostgreSQL. No expongas el puerto 5432 a Internet.

## 3. Instalar el backend

Clona/copia el proyecto en `/opt/herramientas-jg`. El usuario de despliegue conserva la propiedad del código; `www-data` recibe acceso de lectura para ejecutar el backend:

```sh
sudo mkdir -p /opt/herramientas-jg
sudo chown "$USER":www-data /opt/herramientas-jg
git clone <URL-PRIVADA-DEL-PROYECTO> /opt/herramientas-jg
sudo chown -R "$USER":www-data /opt/herramientas-jg
sudo chmod -R g+rX /opt/herramientas-jg
cd /opt/herramientas-jg/Backend
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Crea `/etc/herramientas-jg.env` a partir de `Backend/.env.production.example`. Configura `SECRET_KEY` con un valor criptográficamente aleatorio, la contraseña creada, el dominio exacto y los orígenes HTTPS exactos. Protege el archivo, que contiene secretos:

```sh
sudo install -o root -g www-data -m 0640 Backend/.env.production.example /etc/herramientas-jg.env
sudoedit /etc/herramientas-jg.env
```

No habilites wildcard en `ALLOWED_HOSTS`, CORS ni CSRF. Mantén `DEBUG=False` y las cookies Secure activas. `SECURE_PROXY_SSL_HEADER` está fijado en los settings para el proxy Nginx local de esta guía.

## 4. Instalar el frontend y Gunicorn

```sh
cd /opt/herramientas-jg/Frontend
npm ci
npm run build
sudo install -d -o root -g www-data -m 0755 /var/www/herramientas-jg
sudo cp -a dist/. /var/www/herramientas-jg/
sudo chown -R root:www-data /var/www/herramientas-jg
sudo chmod -R u=rwX,g=rX,o=rX /var/www/herramientas-jg
sudo install -d -o www-data -g www-data -m 0755 /opt/herramientas-jg/Backend/staticfiles
```

Instala y activa la unidad de systemd incluida. El servicio aplica migraciones y recopila archivos estáticos antes de iniciar Gunicorn:

```sh
sudo install -m 0644 deploy/herramientas-jg.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now herramientas-jg
sudo systemctl status herramientas-jg
```

Consulta incidencias con `sudo journalctl -u herramientas-jg -n 100 --no-pager`.

## 5. HTTPS con Nginx y certificados

Apunta los registros DNS `A`/`AAAA` a este servidor y permite TCP 80/443 en el firewall. Sustituye `app.example.com` en [deploy/nginx.conf](./deploy/nginx.conf), comprueba el virtual host HTTP, y solicita un certificado real:

```sh
sudo certbot certonly --nginx -d app.example.com
sudo install -m 0644 deploy/nginx.conf /etc/nginx/sites-available/herramientas-jg
sudo ln -s /etc/nginx/sites-available/herramientas-jg /etc/nginx/sites-enabled/herramientas-jg
sudo nginx -t
sudo systemctl reload nginx
sudo certbot renew --dry-run
```

Nginx sirve la SPA y los estáticos de Django y reenvía `/api/` y `/admin/` a Gunicorn por loopback. El puerto de Gunicorn no se publica en la red. Conserva TLS 1.2+, HSTS y cookies Secure; verifica renovación del certificado y acceso desde navegador antes de habilitar HSTS en subdominios.

## 6. Copias automáticas de PostgreSQL

Instala `postgresql-client` si `pg_dump` no está disponible. Crea `/etc/herramientas-jg-backup.env` con `PGHOST=127.0.0.1`, `PGPORT=5432`, `PGDATABASE=herramientas_jg`, `PGUSER=herramientas_jg`, `PGPASSWORD` con la contraseña de la base, `BACKUP_DIR=/var/backups/herramientas-jg` y `BACKUP_RETENTION_DAYS=14`. Usa `root:postgres` y modo `0640` para ese archivo, y limita el directorio de backup a `postgres`.

```sh
sudo install -d -o postgres -g postgres -m 0700 /var/backups/herramientas-jg
sudo install -o root -g postgres -m 0640 /dev/null /etc/herramientas-jg-backup.env
sudoedit /etc/herramientas-jg-backup.env
sudo chmod 0755 deploy/backup-postgres.sh
sudo install -m 0644 deploy/backup-postgres.sh /opt/herramientas-jg/deploy/backup-postgres.sh
sudo install -m 0644 deploy/herramientas-jg-backup.service /etc/systemd/system/
sudo install -m 0644 deploy/herramientas-jg-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now herramientas-jg-backup.timer
sudo systemctl list-timers herramientas-jg-backup.timer
```

El timer genera un dump PostgreSQL custom cada día, protege el archivo con permisos restrictivos y purga los respaldos de más de 14 días. Ejecuta una copia inicial manual y prueba una restauración periódicamente:

```sh
sudo systemctl start herramientas-jg-backup.service
sudo -u postgres pg_restore --list /var/backups/herramientas-jg/*.dump
```

Mantén una copia cifrada externa; el backup local del mismo servidor no protege contra pérdida total o compromiso del host. Supervisa `systemctl status herramientas-jg-backup.service` y `journalctl`.

## 7. Actualizaciones y comprobación final

Realiza primero un backup, actualiza el código, instala dependencias, compila el frontend y reinicia:

```sh
sudo systemctl start herramientas-jg-backup.service
cd /opt/herramientas-jg
git pull --ff-only
Backend/.venv/bin/pip install -r Backend/requirements.txt
cd Frontend && npm ci && npm run build
sudo cp -a dist/. /var/www/herramientas-jg/
sudo systemctl restart herramientas-jg
curl --fail https://app.example.com/api/health/
```

Revisa logs del servicio, inicia sesión como ADMIN y CAJERO en staging y sigue el [checklist de seguridad](./docs/SEGURIDAD-CHECKLIST.md). El sistema no crea usuarios, cajas, ni datos del cliente automáticamente: el administrador debe configurarlos con el procedimiento interno aprobado.

## Variables de entorno

La plantilla de producción está en [Backend/.env.production.example](./Backend/.env.production.example). Define además en el archivo separado del backup:

| Variable | Función |
|---|---|
| `SECRET_KEY` | Firma de Django/JWT; secreto aleatorio, privado y distinto en cada entorno. |
| `DEBUG` | Siempre `False` en producción. |
| `ALLOWED_HOSTS` | Lista explícita de dominios HTTP atendidos. |
| `DATABASE_URL` | Cadena PostgreSQL privada; no publicar ni incluir en logs. |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Orígenes exactos con esquema HTTPS. |
| `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `AUTH_REFRESH_COOKIE_SECURE` | Deben estar activos bajo HTTPS. |
| `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD` | HSTS; valida el dominio y sus subdominios antes de usar preload. |
| `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` | Conexión usada exclusivamente para generar copias PostgreSQL. |
| `BACKUP_DIR`, `BACKUP_RETENTION_DAYS` | Destino local y política de retención de copias. |
