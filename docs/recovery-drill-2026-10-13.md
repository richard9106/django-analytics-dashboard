# Ensayo de recuperación — 13 octubre 2026

Resultado: las comprobaciones ejecutadas pasaron. Es un ensayo interno en una base y roles temporales del mismo servidor, con la imagen de aplicación actual, no un failover a un servidor independiente ni aprobación de recuperación clínica integral.

- Backup recuperado de R2: `backups/postgres/nuviamy-20261013T033646Z.dump.gpg`, subido a las 03:37 UTC.
- Descifrado AES256/GPG y restauración PostgreSQL en base nueva; producción no sobrescrita.
- Configuración recuperada de una copia protegida del `.env` previamente guardada. Correos, Stripe, Google y Sentry desactivados para las comprobaciones de aplicación; acceso S3 usado solo para leer los objetos existentes.
- Migraciones posteriores al backup aplicadas en la copia, checks de despliegue correctos.
- Roles runtime y migración exclusivos del ensayo: privilegios mínimos verificados; siete guards de auditoría/registro clínico habilitados.
- Dos valores cifrados leídos con la FIELD_ENCRYPTION_KEY de la configuración guardada; prueba adicional de cifrado/descifrado ficticio correcta. No se imprimieron valores, claves ni contraseñas.
- Dos archivos referenciados en la DB copiados desde R2, restaurados en almacenamiento local aislado y leídos por sus referencias; igualdad SHA256 verificada, cero ausentes.
- Comprobación de digest de las firmas presentes; adicionalmente se creó y firmó una nota ficticia exclusivamente en la copia. ORM y SQL rechazaron cambios de contenido y borrado de firma.
- Lectura autenticada de listado de clientes y revisión de la nota ficticia: HTTP 200.
- El intento completo satisfactorio tardó 34 segundos. Antes se corrigieron dos problemas del guion de ejecución: stdin del contenedor y ruta de importación; no eran fallos de la copia de datos. No interpretar 34 segundos como RTO contractual ni como tiempo completo de recuperación de servidor.
- Bases, roles, contenedores de ejecución y copias de trabajo se eliminaron. No se enviaron correos, efectuaron cobros ni modificaron datos de negocio de producción.

## Limitaciones pendientes

1. Configuración y claves usadas proceden de una copia **en el propio VPS**. Falta copia cifrada independiente con custodia/recuperación de clave fuera de ese servidor.
2. Los documentos se obtuvieron del R2 actual. No se demostró recuperación de objetos eliminados/corrompidos desde una copia histórica independiente. La igualdad SHA256 corresponde al material capturado para este ensayo; no a un manifiesto histórico previo al incidente.
3. No se recrearon VPS, sistema operativo, Nginx, DNS, certificados ni timers desde un destino completamente independiente. No se simuló pérdida del proveedor completo.
4. El backup era de primera hora del día: cambios posteriores no están incluidos. Falta aprobar RPO/RTO, retención remota, frecuencia y alertas según necesidades del servicio.
5. Las credenciales de integraciones se descifraron para comprobar compatibilidad; no se reutilizaron para enviar información ni se aprobaron contratos/BAA.

Guion usado: [recovery_drill.py](validation/recovery_drill.py). Es una herramienta de ensayo con permisos administrativos y borrado de la base/roles temporales que crea; no ejecutarla sin preparar un destino aislado y los archivos privados esperados. Nunca versionar el `.env`, los dumps, el manifiesto de archivos o las claves.

Siguiente cierre operativo: copia independiente cifrada de configuración/claves y snapshot/versionado independiente de archivos; después ensayar recuperación en otro host con objetivos aprobados. Estos puntos siguen abiertos antes de declarar recuperación integral ante pérdida del VPS.
