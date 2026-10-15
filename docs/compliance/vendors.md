# Inventario inicial de proveedores y contratos

15 octubre 2026. Las funciones y garantías se revisan por producto, cuenta y región;
un logotipo o un DPA no acredita por sí mismo un BAA ni autoriza datos clínicos.
No guardar contratos privados, credenciales o datos de pacientes en este repositorio.

| Destino | Tratamiento previsto/actual | Evidencia y condición pendiente |
|---|---|---|
| Contabo VPS | Aplicación, DB, configuración y copias locales | DPA privado aportado por usuario, electrónico 15/10; Contabo GmbH y servicio VPS identificados. Anexo incluye Contabo France SAS; confirmar ubicación real y alcance como subencargado. BAA no acreditado; consulta pendiente al proveedor |
| Cloudflare R2 | Documentos y backup cifrado PostgreSQL | Recuperación de objetos actuales y dump probada 13/10; contrato, elegibilidad BAA, región/transferencias y recuperación histórica pendientes |
| Brevo SMTP | Acceso y recuperación, avisos y soporte | Entrega real confirmada por usuario. Invitaciones nuevas sin nombres ni contenido clínico. Revisar otros cuerpos y condiciones; no usar para expedientes |
| Cloudflare Email Routing/Gmail | Recepción de soporte | Reenvío confirmado por usuario; buzón administrativo sin PHI en el alcance permitido. Revisar contratos si se amplía el uso |
| Stripe live | Suscripción de la práctica y datos comerciales | Checkout/webhook/portal ya probados; no incluir notas/diagnósticos en metadata o factura. Evaluar separadamente pagos clínicos del portal y flujos ya existentes |
| Sentry | Diagnóstico técnico estructural | Nueva sanitización por lista permitida y descarte de trazas/breadcrumbs/mensajes; comprobar retención de eventos antiguos en proveedor |
| Google Calendar | Horarios de agenda | Nuevas sincronizaciones sin nombres, enlaces o ubicación. Aun horarios pueden ser sensibles; revisar cuenta/contrato y exportaciones previas |
| Google Drive | Exportación opcional de documentos | Capacidad existente, sin aprobación contractual acreditada. No aprobar destino para PHI hasta revisar cuenta/BAA/controles y consentimiento/instrucción pertinentes |
| GitHub/CI | Código y despliegue | Secretos protegidos; sin expedientes ni dumps en artefactos. Revisar accesos y rotación del deploy |

El DPA Contabo aportado contiene categorías especiales más amplias que el alcance
actual y al operador en la casilla DPO. Pedir corrección/confirmación si no existe
nombramiento formal; no se ha modificado ni sustituido el contrato privado.

## Solicitud pendiente para cada destinatario de ePHI

Confirmar por escrito producto y región, rol contractual, BAA cuando proceda,
subcontratistas, acceso administrativo, cifrado, incidentes, devolución/eliminación y
fin del servicio. Archivar aceptación y versión fuera de Git; registrar su referencia
sin secretos. Si el servicio no permite cubrir la función, elegir alternativa antes
de introducir ePHI. No interpretar falta de respuesta como aceptación.

Los borradores DPA/BAA para clientes se han preparado por separado, sin firmas ni
aprobación clínica. Deben concordar con este inventario real y los controles probados.
