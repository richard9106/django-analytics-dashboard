# Avisos de la prueba profesional

Versión inicial: 13 octubre 2026. Alcance: prueba gratuita con datos ficticios; no autoriza contratación live ni uso clínico con datos reales.

- `/legal/`: identidad y contacto autorizados del operador. NIF desde `OPERATOR_TAX_ID` en configuración privada, nunca en Git. La página escapa el valor y señala la falta de información fiscal si no se ha configurado.
- `/terms/`: alcance, 15 días sin tarjeta/cobro automático, invitaciones privadas, precios informativos, cancelación, acceso durante todo el día UTC y límites de la prueba. Impuestos y condiciones de contratación real siguen pendientes.
- `/privacy/`: cuenta/soporte, finalidades y bases, proveedores conocidos, derechos, cookies, conservación y límites contractuales/regionales todavía no acreditados. No afirma que existan BAA ni que todos los datos estén en EE. UU.
- Footer: acceso permanente a Terms of use y Legal notice junto a Privacy notice y Cookie policy.
- Signup: casilla obligatoria desmarcada; advertencia de datos ficticios junto al formulario y antes del envío. Los enlaces abren otra pestaña indicándolo. La privacidad es información, no una casilla de consentimiento genérico.
- Auditoría append-only: evento `preview_terms_accepted`, actor, fecha de creación y versiones de términos/privacidad. No se inventa aceptación de usuarios existentes.

Cambios materiales de los textos requieren nueva versión en `apps/accounts/legal.py`, conservación de la versión previa e información/reaceptación cuando corresponda. El evento inicial documenta la aceptación del signup actual; no implementa por sí solo un workflow de renovación de consentimiento/contrato para usuarios existentes.

Pendientes antes de pagos reales: situación censal/Seguridad Social aplicable, impuestos y facturación, condiciones definitivas, contratos de proveedores, retención/transferencias, aprobación operativa y clínica correspondiente. Publicar avisos no establece cumplimiento global.


## Condiciones comerciales publicadas — 15 octubre 2026

La página `/terms/#subscription-conditions` publica los precios de USD 39/mes y USD 421/año por usuario interno activo, pago anticipado, inicio voluntario, renovación, ajustes proporcionales, cancelación, acceso hasta final del día UTC, revisión de reembolsos y facturas/soporte. Versión general `2026-10-15-preview-commercial-v2`; versión comercial `2026-10-15-commercial-v1`. El texto anterior se conserva en `docs/legal-versions/terms-2026-10-13-preview-v1.html` y en el historial Git.

El formulario previo a Checkout exige una casilla comercial separada y desmarcada, enlazada al apartado publicado. El servidor rechaza aceptación ausente o una versión obsoleta antes de contactar con Stripe. La auditoría registra actor, práctica, fecha, versión, periodo, cantidad y modo de pruebas; la sesión/suscripción de Stripe recibe la versión comercial en metadata. Un Checkout pendiente de una versión anterior se sustituye. Son eventos de aceptación antes de Checkout, no prueba de un pago realizado. No se inventa aceptación para cuentas existentes.

Stripe continúa en test. El texto no habilita pagos reales ni uso clínico con datos identificables: siguen pendientes los impuestos internacionales, la presentación definitiva de precios con/sin impuestos y los demás requisitos de lanzamiento. Cerrar esas condiciones requiere actualizar la versión, conservar esta y pedir nueva aceptación cuando corresponda.
