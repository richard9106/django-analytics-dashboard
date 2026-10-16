# Análisis inicial de riesgos y plan de tratamiento

Fecha: 15 octubre 2026. Preparado mediante inspección del repositorio, pruebas y
consultas de configuración del VPS. Pendiente de revisión y aprobación del responsable.
Alcance: confidencialidad, integridad y disponibilidad de los datos previstos; no
se inspeccionaron controles físicos del proveedor ni se ejecutó una intrusión externa.

## Activos y flujos

Navegador → HTTPS/Nginx → Django/Gunicorn → PostgreSQL y almacenamiento de documentos.
Los registros incluyen identidad/contacto, consultas iniciales, sesiones, diagnósticos,
planes, notas y firmas. La auditoría contiene identificadores y actividad. Credenciales,
OAuth y claves son activos críticos. R2 conserva objetos/copias; SMTP entrega acceso,
soporte y recuperación; Stripe gestiona la suscripción comercial live. Las integraciones
Google y el sistema de errores son salidas adicionales. El ordenador del operador,
el VPS, las cuentas de proveedores, DNS y CI forman parte del perímetro.

## Método

Probabilidad cualitativa: alta (ruta habitual expuesta sin control suficiente), media
(ruta plausible con controles parciales), indeterminada (falta evidencia). Impacto
alto si puede revelar/modificar expedientes, impedir su recuperación o comprometer
cuentas. Estas son estimaciones conservadoras, no frecuencias medidas. Cada cierre
requiere prueba, decisión y fecha; revisar antes del piloto, tras incidentes, cambios
de proveedor/ubicación o nuevas funciones, y periódicamente según plan aprobado.

| Riesgo / probabilidad / impacto | Evidencia y control | Tratamiento y criterio pendiente |
|---|---|---|
| R01 Robo de credenciales / media / alto | Límites compartidos, revocación, sesiones 1 h/8 h; MFA disponible pero desactivado a petición del propietario | Richard: decidir MFA y recuperación, registrar justificación y validar acceso administrativo/equipo |
| R02 Passwords compartidos / media / alto | Nueva entrega elimina contraseñas elegidas/enviadas por administradores; tokens de un uso hasta 48 h y reenvío revocable | Pruebas y CI; verificar entrega real sin exponer credenciales. Revisar cuentas antiguas de demostración antes del piloto |
| R03 Acceso cruzado o excesivo / media / alto | Ámbito Practice, permisos, auditoría y pruebas existentes; no prueba exhaustiva de todas las rutas | Inventario de rutas y matriz terapeuta/administrador/portal, revisar admin y soporte con dos prácticas |
| R04 Exposición en errores/integraciones / media / alto | Nueva lista permitida de campos en Sentry y calendario neutro; Google Drive sigue siendo salida de documentos | Revisar datos ya exportados, logs Nginx/Gunicorn y URLs con tokens; aprobar o desactivar destinos clínicos |
| R05 Proveedor sin garantías / indeterminada / alto | DPA Contabo aportado; soporte confirma que no ofrece BAA para el VPS (Francia, soporte Alemania/Chequia). BAA de R2 y otros destinatarios pertinentes no acreditado | Migrar el alojamiento clínico previsto a servicio con BAA; verificar por separado alcance de almacenamiento/copias y restantes destinatarios |
| R06 Pérdida o robo del VPS / media / alto | Root ext4 sin mapeo dm-crypt/LUKS observado; cifrado físico del proveedor no acreditado. VPS aloja otros servicios | Documentar cifrado de DB/volumen/archivos y aislamiento; plan de migración si no basta. No cifrar en caliente ni parar aplicaciones ajenas |
| R07 Pérdida de claves/copias / media / alto | Backup DB y ensayo 13/10; nueva copia cifrada de configuración fuera del VPS recuperable | Copia histórica independiente de documentos, custodia externa adicional de clave, alertas y ensayo en otro host con RPO/RTO aprobados |
| R08 Archivo hostil / media / alto | UUID privados previos; nueva validación por contenedor y límite 10 MB. PDF por firma, DOCX sin macros/embebidos, imágenes verificadas | No equivale a antivirus; evaluar cuarentena/escaneo, PDF activo y rutas Summernote/fotos antes del piloto |
| R09 Cambio/pérdida de expediente / media / alto | Firmas, digest, protección ORM/DB, auditoría y roles separados existentes | Completar adendas/correcciones, legal holds, disposición y prueba de todas las rutas de eliminación/exportación |
| R10 Incidente no detectado / media / alto | Logs de auditoría y procedimiento escrito | Ensayar respuesta con operador, alertas y acceso alternativo; demostrar formación y cobertura operativa |
| R11 Equipo/control de operador / indeterminada / alto | Operación por una persona; permisos locales de claves restringidos | Verificar cifrado de disco, bloqueo de pantalla, actualizaciones, gestor de claves, recuperación y sustitución en ausencia |

Responsable propuesto del plan: Richard Andres Marles Bonilla. No se registra su
aceptación por inferencia. Prioridad antes del piloto: contratos, R03–R09 y control
operativo; los cambios de esta entrega reducen exposición, no cierran el conjunto.

Fuente metodológica: [HHS](https://www.hhs.gov/hipaa/for-professionals/security/guidance/guidance-risk-analysis/index.html).
