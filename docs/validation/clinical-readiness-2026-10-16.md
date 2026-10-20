# Evidencia de entrega — 16 octubre 2026

- PR60: https://github.com/richard9106/django-analytics-dashboard/pull/60
- PR61: https://github.com/richard9106/django-analytics-dashboard/pull/61
- Commit final: `4e98df92301baa030166762fb5422f9264799080`.
- CI final de rama 38881933893: 586 tests, roles y backup/restore correctos.
- CI/despliegue final de main: https://github.com/richard9106/django-analytics-dashboard/actions/runs/38882505046, satisfactorios.
- Comprobación posterior en VPS: migraciones 0008/0009 aplicadas, guards de runtime verificados, digest de todas las firmas existentes válido y formulario de adenda de una nota firmada existente HTTP 200. No se firmaron adendas ni se crearon datos clínicos ficticios en producción.
- Stripe live y precio mensual conservados; MFA sigue desactivado por decisión previa. MIGRATION_REHEARSAL=false. Health público correcto.

## Recuperación y ensayo

- Copia independiente de dos documentos cifrada: 20261016T091508Z; descifrado y hashes correctos, sin escribir/borrar objetos de origen. Archivo privado y SHA256 en el informe de avances.
- Tests ficticios: recuperación después de borrado/corrupción de copia de trabajo, manipulación rechazada, rutas inseguras rechazadas y sobreescritura de destino impedida.
- DB previa a adendas cifrada fuera del VPS: `nuviamy-db-preaddenda-20261016T092645Z.cms`; SHA256 `d0bae301e65603f1ca8b426a85513f6c4e34a47049c25d1fdff0e4f2d54ae537`; descifrado autenticado y cabecera PGDMP verificados a memoria. No se afirma restauración integral de este archivo en otro host.
- Configuración posterior al despliegue: `nuviamy-config-20261016T095119Z.cms`; SHA256 `fed8af3856ab45922440f6435650520ff9d390f9b3756208e3e130b946458ed8`; ocho entradas, campos de claves presentes y manipulación rechazada.
- Archivos privados en `/home/richard/Documents/Personal/NuviaMy-Recovery`, fuera de Git; clave privada solo local. Los puntos de captura no son una instantánea transaccional única de DB + documentos.
- Comando isolate_rehearsal ejecutado satisfactoriamente sobre DB local independiente con sufijo _rehearsal y tokens ficticios; datos/conexiones del proveedor no tocados. DB de ensayo eliminada al terminar. Tests prueban rechazo sobre DB normal antes de escribir.

## Límites

No hay migración ni contratación de nuevo proveedor. Copias manuales pequeñas, sin planificación/alertas/retención automática ni WORM. Pendientes: BAA, ensayo de recuperación en otro host, objetivos RPO/RTO, custodia adicional de claves, revisión clínica y revisión independiente de seguridad. Matriz probada en notas/adendas/documentos; no es un inventario exhaustivo de todos los endpoints. Uso clínico con datos reales sigue sin aprobación.
