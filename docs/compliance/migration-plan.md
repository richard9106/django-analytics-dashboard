# Preparación de migración — 16 octubre 2026

Preparación lista para ensayo; no se ha contratado destino, aceptado BAA, cambiado DNS
ni trasladado producción. El destino debe cubrir aplicación, DB, archivos, copias y
soporte con los acuerdos pertinentes. Contabo permanece sin aprobación para ePHI.

## Inventario y configuración

- Fijar el SHA completo que haya pasado CI; misma imagen/código en ensayo y corte.
- PostgreSQL 16 y roles bootstrap/migración/runtime separados, guards habilitados.
- Conservar DJANGO_SECRET_KEY y FIELD_ENCRYPTION_KEY para recuperar valores existentes;
  una rotación se hace después con un plan específico, no durante una copia ciega.
- Capturar DB cifrada, documentos con manifiesto, configuración y claves por separado.
  Copiar solo mediante canales privados; no adjuntar dumps a tickets ni a GitHub.
- Revisar destinos Google, SMTP, Sentry, Stripe live y las referencias de almacenamiento.
  El ensayo no debe enviar correos, cobrar, sincronizar ni escribir sobre el R2 actual.

Herramienta de preparación local (no conecta con proveedores):

```sh
.venv/bin/python -m ops.prepare_migration --source-env /ruta/privada/source.env --destination /ruta/privada/nuevo-ensayo --revision SHA_COMPLETO_REVISADO
```

Genera directorio 0700 y archivos 0600. `rehearsal.env` conserva claves de lectura
pero desactiva correo real, Stripe, Google, Sentry y credenciales de almacenamiento.
`production-candidate.env` es una copia privada para revisión explícita, nunca activada
por la herramienta. El manifiesto no contiene claves. No ejecutar un ensayo en el
Compose/volumen de producción ni restaurar sobre la DB activa.

## Ensayo en el futuro host

1. Instalar Docker/Compose y Nginx actualizados; SSH por clave y firewall restringido.
   Crear usuario de despliegue, proyecto y volúmenes exclusivos del ensayo.
2. Construir el SHA revisado. Validar configuración y migraciones; usar servicios
   externos desactivados y el almacenamiento local aislado del ensayo.
3. Descifrar backup DB en área privada y restaurar en DB vacía del destino; aplicar
   migraciones y provisionar/verificar roles según DEPLOYMENT.md. No reutilizar
   contraseñas de CI. Preservar IDs del expediente y relaciones de firma/adendas.
4. Descifrar documentos con `ops.document_snapshot`, validar todos los hashes antes
   de escribir. Usar el manifiesto para enlazar cada archivo con su storage_key,
   exclusivamente en almacenamiento de ensayo. No usar rutas no revisadas.
5. Comprobar descifrado de campos, recuentos, referencias, firmas y adendas, permisos,
   exportación, acceso estático, health y recorrido con datos ficticios.
6. Registrar inicio/fin, incidencias, recuentos esperados/obtenidos y hashes; no prometer
   RTO/RPO hasta medir el proceso completo y aprobarlos.

## Corte y vuelta atrás

- Antes del corte: copia independiente comprobada; ensayar DNS/certificados y webhooks
  sin crear cobros. Verificar BAA efectivo y revisión de seguridad pendiente.
- Pausar escrituras durante una ventana anunciada. Capturar delta/final de DB y archivos;
  validar consistencia y tiempos. Una copia de días anteriores no sirve como corte final.
- Activar configuración live revisada y solo un ejecutor de recordatorios/backups.
  Mantener una sola aplicación escritora y comprobar entrega/idempotencia de webhooks.
- Cambiar DNS solo tras comprobación del nuevo servicio. Mantener origen protegido y
  sin trabajos activos durante la ventana de observación.
- Con adendas ya registradas, no revertir las migraciones 0008/0009 ni eliminar su tabla.
  Volver a una versión de código anterior debe conservar esos registros y un camino
  de lectura/exportación del historial.
- Si falla antes de aceptar escrituras nuevas, regresar al origen congelado y registrar
  el resultado. Si ya hay escrituras nuevas, reconciliar/exportar cambios antes de volver;
  no arrancar dos DB divergentes ni descartar expedientes o eventos Stripe.
- Eliminar copias de trabajo con autorización y política de conservación, no automáticamente
  al terminar una prueba. Custodiar la clave offline por separado.

Pendiente: acceso al destino contratado, ensayo en otro host, medición/aprobación RPO/RTO,
cifrado e infraestructura del destino y ejecución del corte. Las pruebas locales validan
la generación de configuración; no sustituyen ese ensayo.
