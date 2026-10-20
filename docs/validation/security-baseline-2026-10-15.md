# Evidencia de entrega de seguridad — 15 octubre 2026

- PR integrado: https://github.com/richard9106/django-analytics-dashboard/pull/59
- Commit main y VPS: `54090f6c82a77dd562ae02bf2e0b0fbe9920b57c`.
- CI de rama: ejecución 38751774864, satisfactoria.
- CI y despliegue de main: https://github.com/richard9106/django-analytics-dashboard/actions/runs/38752484959, satisfactorios.
- Suite local: 571 tests PostgreSQL en 324,374 segundos; main CI: 571 en 171,263 segundos.
- Comprobaciones de migraciones y despliegue sin incidencias; CI comprueba imagen, estáticos, interacciones, roles y restauración.
- Comprobación posterior en contenedor: health, recuperación y enlace inválido de invitación HTTP 200; páginas de acceso con no-store y no-referrer. HEAD público de recuperación confirma cabeceras seguras.
- Sentry: callback de privacidad activo, logs deshabilitados y muestreo 0; mensaje ficticio descartado.
- Stripe: clave restringida live, clave pública live y webhook configurado; precios mensual/anual correctos. El primer guion comprobaba solo prefijo sk_live y se corrigió para admitir también rk_live; no hubo cambio de credencial ni regreso a pruebas.
- MFA continúa desactivado, inactividad 3600 segundos y máximo de sesión 28800.
- No se enviaron invitaciones reales ni se crearon cobros o cuentas de negocio para verificar esta entrega.

## Copia posterior al despliegue

Captura: `20261015T144009Z`, ocho entradas, campos de claves presentes, descifrado a memoria correcto, manipulación rechazada. Archivo privado fuera de Git:
`/home/richard/Documents/Personal/NuviaMy-Recovery/nuviamy-config-20261015T144009Z.cms`.
SHA256 cifrado: `1799bf0825fb46d32bfb8c34695b564a0eb711362b34ee06a35f6e0ff69a8e23`.
La clave privada sigue solo en el ordenador del operador; necesita custodia adicional segura. No es backup de DB/documentos ni ensayo de nuevo host.

## Alcance

El expediente de preparación está en `docs/compliance`. Permanecen abiertos contratos BAA/proveedores, acreditación de cifrado/aislamiento, documentos históricos y ensayo independiente de recuperación, conservación/adendas, formación y revisiones clínica y de seguridad. Esta entrega no autoriza PHI ni declara cumplimiento HIPAA completo.
