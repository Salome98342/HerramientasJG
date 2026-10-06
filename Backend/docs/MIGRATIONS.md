# Migraciones

Las migraciones iniciales se deben generar en el entorno con Django instalado:

```bash
python manage.py makemigrations core inventario alquileres ventas cajas finanzas
python manage.py migrate
```

El entorno de generación usado para este entregable no tiene Django instalado ni acceso a PyPI, por lo que no se incluyeron archivos `0001_initial.py` generados artificialmente. Esto evita entregar migraciones no verificadas contra la versión real de Django/PostgreSQL del proyecto.

Después de generar las migraciones, deben versionarse en Git y revisarse antes de aplicar en producción.
