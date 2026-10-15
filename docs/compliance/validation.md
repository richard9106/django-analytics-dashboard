# Validación antes de pacientes reales

15 octubre 2026. Plan de pruebas y registro de evidencias; no aprobación firmada.
Los tests automatizados comprueban comportamiento de software, no utilidad clínica.

## Ensayo funcional con datos ficticios

Un profesional autorizado debe ejecutar y registrar resultado, fecha, versión y
hallazgos de: alta sin tarjeta; práctica/roles; consulta inicial 10–15 min; sesión;
nota asociada al paciente y cita correctos; revisión/firma e identidad/hora; bloqueo
del original; corrección mediante adenda cuando exista; permisos del terapeuta,
admin y portal; cancelaciones/ausencias; exportación y continuidad de acceso cuando
venza la prueba o termine la suscripción. Cualquier error de paciente, firma,
autoría o pérdida del registro bloquea el piloto hasta corregirlo y repetir prueba.

## Revisión de seguridad

Validar dos prácticas y dos pacientes, llamadas directas a objetos ajenos, permisos
admin, recuperación/reenvío concurrentes, revocación de cuentas/sesiones, CSRF,
subidas y descargas, enlaces de exportación, logs con marcadores ficticios, webhook
firmado y rechazos, almacenamiento y restauración. Revisar dependencias y secretos,
configuración de red y los otros servicios del VPS. Registrar alcance y límites de
la revisión independiente, hallazgos, correcciones y retest; no afirmar pentest realizado.

## Formación y operación

Responsable y cualquier personal: mínimo acceso necesario, phishing, gestor de
contraseñas, MFA/recuperación, bloqueo y cifrado del equipo, manejo de expedientes,
soporte sin PHI por correo, exportaciones, incidentes, conservación y baja de accesos.
Cada persona confirma fecha y comprensión en registro privado. No hay constancia
de formación completada por la publicación de este material.

## Aprobación pendiente

El responsable debe revisar riesgos residuales, contratos/proveedores, evidencias de
recuperación y resultados clínicos/de seguridad. Registrar quién aprueba qué alcance,
fecha, versión y condiciones de revisión. Si hay bloqueos, mantener uso ficticio;
no sustituir firmas de terceros por checkboxes marcados por el desarrollador.
