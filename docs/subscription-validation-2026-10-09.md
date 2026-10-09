# Validación de suscripciones — 9 de octubre de 2026

Stripe sigue en modo prueba. Precios verificados: USD 39 por usuario/mes y USD 421 por usuario/año. Se limpió la descripción del producto de pruebas, que contenía instrucciones copiadas; los importes no cambiaron.

## Pruebas con Stripe

- Dos suscripciones ficticias, mensual y anual, con cantidad 2 y tarjeta de prueba. Periodo gratuito confirmado de 15 días.
- Con Test Clock se avanzaron 16 días: ambas quedaron activas y las facturas pagadas por USD 78 y USD 842, respectivamente.
- Se verificaron cancelación al final del periodo e inmediata, y se eliminaron reloj/clientes ficticios.
- Checkout alojado se completó desde el navegador con tarjeta 4242 y datos ficticios: retorno a NuviaMy, sesión complete, suscripción trialing, 15 días, importe hoy cero y livemode=false. Después se canceló la suscripción y se eliminó el cliente de prueba.

Los clientes de Stripe no se vincularon a prácticas de producción. Las pruebas de Django usan una base PostgreSQL local aislada y simulan eventos firmados; no constituyen una prueba completa del recorrido de una nueva cuenta real y su webhook en producción. No se realizaron cobros reales ni envíos manuales de correo.

## Política de acceso implementada

| Estado | Acceso |
| --- | --- |
| Sin suscripción / incomplete / incomplete_expired | Pantalla de activación; sin acceso operativo. Permanecen disponibles cuenta, seguridad, soporte, cierre de sesión y exportación autorizada. |
| trialing / active | Acceso habitual según permisos. |
| past_due | Siete días de gracia desde el primer fallo registrado; avisos repetidos no reinician el plazo. |
| past_due sin fecha o gracia agotada / canceled / unpaid / otros estados | Consulta de registros existentes; bloqueo de escrituras de negocio y formularios de creación/edición. Facturas, descargas y exportación conservan sus permisos habituales. |

El portal mantiene consulta; sus operaciones de escritura también quedan sujetas al estado de la práctica. La reserva pública no acepta nuevas solicitudes cuando la práctica está pendiente o suspendida. Los controles de seguridad y los webhooks mantienen sus reglas propias.

Cada alta pública marca `Practice.subscription_required=True`. Iniciar Checkout en una práctica existente también activa esa política. La migración conserva `False` en las prácticas internas/demo previas para no suspenderlas automáticamente; cualquier práctica provisionada manualmente para clientes debe marcarse como requerida. No es una excepción automática para nuevas altas públicas.

El checkout pendiente se reutiliza; al cambiar de periodo se expira el anterior. Un bloqueo de fila evita que solicitudes concurrentes de una práctica creen checkouts paralelos. Una suscripción existente activa o con deuda se gestiona mediante el portal, y la reactivación no obtiene otro periodo gratuito. Eventos de una suscripción o checkout antiguos no sustituyen la suscripción actual.

## Verificación de interfaz

El agente de UX revisó activación, avisos, recuperación y exportación. Se añadieron enlace a tarifas y explicación de permisos; acciones deshabilitadas no abren modales. Navegador local: activación y recuperación a 320 y 390 píxeles sin desbordamiento horizontal; banner visible y acción New client deshabilitada en solo lectura.

Suite local completa: 488 tests satisfactorios en PostgreSQL (301,123 segundos), incluidos 15 nuevos casos de acceso y ciclo de suscripción. `check --deploy --fail-level WARNING`, consistencia de migraciones, dependencias, checks de calendario/diagnóstico, aislamiento de credenciales Compose y collectstatic satisfactorios.

Esta entrega no habilita Stripe real. Siguen pendientes los documentos comerciales, entrega de correo y requisitos de preparación clínica descritos en la auditoría de lanzamiento. El despliegue requiere tests locales, CI del PR y CI/deploy de main.
