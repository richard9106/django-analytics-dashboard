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
