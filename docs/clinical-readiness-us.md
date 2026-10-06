# NuviaMy: preparación para uso clínico en Estados Unidos

Fecha: 6 de octubre de 2026. Revisión inicial del repositorio, no auditoría externa ni dictamen legal. Objetivo: producción clínica con cumplimiento HIPAA demostrable.

## Alcance y conclusión

Se revisaron configuración Django, despliegue, autenticación y permisos, modelos clínicos, documentos, auditoría, integraciones Google, pagos del portal, exportación y backups. No se inspeccionaron el VPS, contratos, cuentas de proveedores, claves, datos reales ni controles físicos/organizativos. No se ejecutó un pentest. La presencia de un control en código no acredita su funcionamiento en producción.

La base funcional es amplia: aislamiento por Practice en numerosas vistas, permisos por módulo, descargas autorizadas, tokens OAuth cifrados, HTTPS/cookies seguras en configuración de producción, notas bloqueadas, webhooks Stripe firmados, backups y pruebas automatizadas. Faltan controles que impiden considerar el producto listo para PHI real.

HHS/OCR no certifica productos como HIPAA compliant. El objetivo consiste en cumplir las obligaciones aplicables y conservar evidencia; una evaluación independiente o una certificación privada tiene un alcance distinto. Debe decidirse por separado si se necesita certificación ONC para el mercado objetivo. El uso clínico por sí solo no determina esa necesidad.

## Bloqueos técnicos prioritarios

P0 significa bloqueo antes de introducir PHI real; no significa vulnerabilidad explotada o incumplimiento legal ya demostrado.

| ID | Prioridad | Evidencia | Acción y criterio de cierre |
|---|---|---|---|
| SEC-01 | P0 | requirements.txt fija Django 5.1.15; soporte de 5.1 finalizado | Migrar a una rama soportada, preferentemente LTS compatible. Revisar dependencias y CVE; suite y pruebas PostgreSQL pasan. |
| SEC-02 | P0 | settings.py y docker-compose.yml aceptan secreto de desarrollo; Compose acepta contraseña DB de ejemplo | Arranque de producción falla si faltan secretos válidos, DEBUG está activo o hay configuración insegura. Gestor de secretos, rotación y permisos documentados. |
| SEC-03 | P0 | No se encontró MFA; no hay política explícita de inactividad/expiración de sesión | MFA para personal y administradores, recuperación segura, cierre por inactividad, revocación de sesiones y reautenticación para exportación/acciones críticas. Probar desactivación de cuentas con sesiones existentes. MFA se propone como control de riesgo; no se presenta una regla propuesta como ley vigente. |
| SEC-04 | P0 | apps/rate_limit.py usa django.core.cache sin CACHES compartida; Gunicorn configura 4 workers | Limitación compartida entre procesos, límites por cuenta e IP, política de proxy de confianza y alertas de abuso. Verificar con varios workers; proteger admin y recuperación. |
| CLIN-01 | P0 | SessionNote.save/delete comprueba bloqueo; FKs a paciente, terapeuta y Practice usan CASCADE | Evitar pérdida de historial por QuerySet.delete, acciones masivas y cascadas; QuerySet.update también evita save. Retención, archivo, legal hold y eliminación autorizada con pruebas de todas las rutas. |
| AUD-01 | P0 | AuditLog editable/borrable como modelo normal; Admin solo hace readonly created_at; Practice CASCADE | Auditoría protegida contra modificación y borrado, identidad estable del actor, almacenamiento separado o controles DB, retención y detección de manipulación. Asegurar trazabilidad de lecturas, exportaciones, privilegios y accesos denegados. |
| AUD-02 | P0 | Vistas de notas registran cambios; no se encontró auditoría de lectura en listado clínico ni vistas de pacientes | Definir cobertura de acceso a PHI y registrar lecturas sin contenido clínico. Probar listados, búsquedas, detalle, portal, admin y descargas; evitar que borrar una práctica borre la evidencia. |
| INT-01 | P0 | google_calendar.py envía nombre de paciente en summary/description; Drive exporta archivos; conexión OAuth general | Inventario de datos externos, cuentas Workspace y servicios elegibles bajo BAA, validación contractual y configuración. Desactivar envío de PHI hasta aprobación; minimizar calendario, revisar permisos y enlaces compartidos. OAuth conectado no prueba elegibilidad HIPAA. |
| INT-02 | P0 | Portal Checkout envía email e identificadores a Stripe; Sentry send_default_pii=False, sin filtrado específico observado | Revisar tratamiento y condiciones de cada proveedor. Minimizar datos de pagos; no enviar diagnóstico/notas. Revisar URLs, cuerpos, excepciones y trazas en Sentry/logs; probar con PHI ficticia que no sale información no autorizada. No asumir que todos los proveedores requieren o admiten el mismo BAA: evaluar su función. |
| AUTH-01 | P0 | accounts/views.py y tests envían contraseñas temporales y las muestran como fallback | Sustituir por invitaciones de un solo uso con caducidad y establecimiento de contraseña por el destinatario. No mostrar ni enviar contraseñas; proteger reenviado y recuperación. |
| DATA-01 | P0 | El cifrado de tokens no acredita cifrado DB/discos; backup_postgres.sh conserva dump local sin cifrar y cifra copia R2 | Acreditar cifrado y acceso de DB, volúmenes, documentos y backups. Gestión de claves separada, recuperación y rotación. Revisar también exposición de la passphrase GPG en argumentos de proceso. |
| DR-01 | P0 | Backup de PostgreSQL y verificación de restauración existen; documentos locales/media no quedan incluidos en ese dump | Recuperación integral DB + documentos + claves/configuración, RPO/RTO acordados y simulacro. Copias separadas, protección frente a ransomware y alertas por fallos. Verificar retención remota y recuperación de objetos R2. |
| DOC-01 | P0 | ClientDocumentForm no valida tamaño, tipo real o malware; conserva nombre original en ruta | Límites de subida, tipos permitidos por contenido, cuarentena/escaneo según análisis de riesgo, nombres internos opacos y almacenamiento privado. Revisar también adjuntos Summernote, fotos y URLs media para impedir vías sin autorización. |
| RBAC-01 | P0 | Permisos por módulo y ámbito Practice; terapeutas con acceso clínico predeterminado amplio; Admin estándar | Definir acceso por función y relación asistencial, privilegios mínimos, acceso de soporte y emergencia trazable. Revisar todas las rutas y admin con usuarios de dos prácticas y pacientes distintos. No se afirma una fuga entre tenants sin reproducción. |
| CLIN-02 | P0 si se almacenan psychotherapy notes | SessionNote no separa específicamente psychotherapy notes del expediente habitual | Definir distinción legal y clínica; si se ofrecen, almacenamiento/acceso/divulgación separados y autorizaciones específicas. No confundir progress notes/SOAP con psychotherapy notes. |
| CLIN-03 | P1, previo al piloto según alcance | Hay bloqueo pero no modelo específico de firma/adendas/versiones observado | Autoría, firma/finalización, adendas sin sobrescribir original y cambios concurrentes controlados; validación por clínicos. Retención de planes, diagnósticos y documentos coherente. |
| OPS-01 | P0 | CI prueba SQLite por defecto; check --deploy sin --fail-level WARNING; despliegue tras push main | Ejecutar PostgreSQL en CI, bloquear warnings relevantes, análisis de dependencias/secretos y controles de seguridad. Staging con datos ficticios, migraciones verificadas, rollback y aprobación de releases documentados. |

## Trabajo contractual y organizativo pendiente de acreditar

La revisión no encontró un expediente de cumplimiento suficiente; su ausencia en Git no implica que no exista fuera del repositorio.

1. Determinar estados de lanzamiento, perfil de clínicas y condición de covered entity/business associate. NuviaMy probablemente actuará como business associate para clientes sujetos a HIPAA; validar el modelo contractual.
2. Análisis formal de riesgos HIPAA con inventario ePHI, diagramas de flujo, amenazas, controles, riesgos residuales y responsables. Mantenerlo actualizado.
3. BAA con clínicas y subcontratistas pertinentes. Verificar contrato exacto para VPS, almacenamiento R2, correo, Google Workspace, monitoring, backups y soporte; un proveedor o servicio seguro no acredita automáticamente el contrato adecuado.
4. Responsable de seguridad/privacidad, formación, accesos del equipo, bajas, confidencialidad y revisión periódica de privilegios.
5. Políticas de incidentes y brechas, evaluación, notificaciones, registro y simulacros; continuidad y recuperación verificadas.
6. Flujos para acceso del paciente a su expediente, correcciones/adendas, autorizaciones y revocaciones, restricciones, comunicaciones confidenciales, representantes y menores. El ZIP de toda la práctica para el propietario no sustituye estos procesos.
7. Retención por estado y tipo de documento, menores y legal hold. HIPAA no establece un plazo universal de retención del historial médico; no confundir documentación HIPAA con expediente clínico.
8. Revisar 42 CFR Part 2 si se atienden programas/expedientes de trastornos por uso de sustancias dentro de su ámbito: no aplica automáticamente a toda psicoterapia. La fecha de cumplimiento de la regla de 2024 fue el 16 de febrero de 2026.
9. Avisos y contratos: privacidad del SaaS, DPA/BAA, condiciones, subprocessors y apoyo al Notice of Privacy Practices de clínicas según responsabilidades. Consentimiento asistencial, consentimiento de comunicación y autorización de divulgación son procesos distintos.
10. Pentest independiente tras cerrar bloqueos; registrar correcciones y repetir pruebas relevantes. Decidir después si una evaluación privada, SOC 2 o HITRUST sirve a compradores concretos; no sustituye HIPAA.

## Primera entrega técnica: base de seguridad y despliegue

Trabajo iniciado el 6 de octubre de 2026 para SEC-01, SEC-02 y parte de OPS-01:

- Django 5.2.17 LTS, versión publicada disponible al preparar la entrega.
- Validación obligatoria al arrancar en producción: DEBUG, secreto Django, PostgreSQL, hosts/CSRF, HTTPS/cookies/HSTS y clave Fernet; mensajes sin valores de secretos.
- Compose exige secretos y fija el entorno de producción. Contexto Docker excluye archivos de entorno, configuración de agentes y media local.
- Once pruebas adicionales de configuración, arranque y configuración de Summernote, con escenarios seguros e inseguros.
- Workflow con PostgreSQL 16, checks de despliegue que fallan ante warnings, consistencia de migraciones/dependencias y despliegue del commit exacto probado. Comprobación del candidato antes de reemplazar el servicio.
- Summernote conserva el tipo de clave primaria de sus migraciones publicadas; se desactiva su endpoint de adjuntos sin ámbito Practice. La subida de documentos sigue disponible en Documents.
- README actualizado para reflejar el objetivo clínico real. Esta entrega no cierra MFA, políticas, contratos, auditoría, retención ni el resto de bloqueos.

La inspección por SSH confirmó en el servicio previo: PostgreSQL, DEBUG desactivado, secreto Django que cumple los checks básicos, clave Fernet válida, R2 y controles HTTPS activos. Se detectó un origen CSRF HTTP a retirar antes del nuevo despliegue y permisos 664 del archivo de entorno a restringir a 600, conservando propietario. Se retiró el origen HTTP y se restringió el archivo a 600 con copia protegida, sin cambiar claves. No se imprimieron secretos ni se consultaron expedientes de pacientes.

## Secuencia de ejecución

- Fase 1: fijar estados, alcance asistencial y proveedores; análisis de riesgos y contratos en paralelo con actualización Django, secretos, MFA/sesiones e invitaciones.
- Fase 2: proteger conservación del expediente y auditoría; revisar autorizaciones/tenant/admin; cerrar integraciones y exposición de archivos/logs.
- Fase 3: validar cifrado, backups integrales, restauración, incidentes y derechos del paciente; CI PostgreSQL y procedimientos operativos.
- Fase 4: evaluación independiente de seguridad y cumplimiento, validación clínica y piloto limitado aprobado.

No estimar una fecha de certificación sin conocer contratos, infraestructura, estados, alcance y resultados de evaluación.

## Criterios para permitir un piloto con datos reales

Todos los P0 cerrados con evidencia; análisis de riesgos aceptado; contratos aplicables firmados; accesos y formación completados; recuperación integral ensayada; políticas de retención/incidentes/derechos operativas; revisión clínica completada y evaluación independiente sin riesgos críticos abiertos. Registrar responsables y aceptación formal del riesgo residual. Mantener solo datos ficticios antes de esa decisión.

## Validación técnica de esta revisión

check --deploy --fail-level WARNING pasó con DEBUG=false y secreto temporal de revisión, sin conectarse al VPS. Esto confirma únicamente los checks Django para ese entorno.

Revisión inicial: 334 tests correctos con SQLite. Primera entrega: 345 tests correctos con Django 5.2.17 y PostgreSQL 16 aislado (238,375 segundos); once pruebas adicionales de arranque/configuración, también verificadas en un contenedor limpio. También pasan checks de despliegue, consistencia de migraciones/dependencias, validación Compose y checks en la imagen Docker construida. No valida cumplimiento ni todos los controles de producción.

## Fuentes primarias

- HHS: no certifica personas/productos como Privacy Rule compliant: https://www.hhs.gov/hipaa/for-professionals/privacy/guidance/index.html
- HHS: análisis de riesgos: https://www.hhs.gov/hipaa/for-professionals/security/guidance/final-guidance-risk-analysis/index.html
- HHS: cloud y business associates: https://www.hhs.gov/hipaa/for-professionals/special-topics/health-information-technology/cloud-computing/index.html
- HHS: protección de psychotherapy notes: https://www.hhs.gov/hipaa/for-professionals/faq/does-hipaa-provide-extra-protections-mental-health-information-compared-other-health.html
- HHS: retención de historias clínicas: https://www.hhs.gov/hipaa/for-professionals/faq/does-hipaa-require-covered-entities-to-keep-medical-records-for-any-period/index.html
- HHS: Part 2: https://www.hhs.gov/hipaa/part-2/index.html
- HHS: propuesta Security Rule (distinguir propuesta de requisitos vigentes): https://www.hhs.gov/hipaa/for-professionals/security/hipaa-security-rule-nprm/index.html
- Google: Workspace y BAA: https://knowledge.workspace.google.com/admin/compliance/hipaa-compliance-with-google-workspace-and-cloud-identity
- Cloudflare: propiedades de seguridad R2, no prueba de contrato de este proyecto: https://developers.cloudflare.com/r2/reference/data-security/
- Django: ramas y fechas de soporte: https://www.djangoproject.com/download/

La primera ejecución de CI bloqueó la entrega por una discrepancia de clave primaria en Summernote, oculta por una migración generada localmente dentro de .venv. Se preservó esa migración local en /tmp y se fijó AutoField para Summernote, según su esquema publicado. La imagen limpia ya no genera migraciones pendientes; no se alteró la tabla de producción.

## Segunda entrega técnica: MFA y sesiones

SEC-03 cuenta con controles implementados: MFA TOTP obligatorio para todo el personal
(incluido Django admin), recuperación de un solo uso, cifrado obligatorio del secreto,
revocación por versión de cuenta y al desactivar/reactivar, cierre tras 15 minutos de
inactividad y máximo 8 horas, desafío pendiente de 10 minutos y reautenticación de 5
minutos para exportación/cambios de equipo/perfil. El navegador oculta contenido al
expirar y sincroniza actividad/cierre entre pestañas. Las sesiones anteriores a la
entrega se invalidan; el personal debe iniciar sesión e inscribirse.

SEC-04 tiene límites atómicos de IP en PostgreSQL para login, admin, recuperación y
MFA, más bloqueo MFA por cuenta (5 fallos/15 minutos). Los secretos pendientes y
códigos mostrados una vez también se cifran en la tabla de sesiones. La recuperación
operativa exige verificación independiente y un ticket: consultar DEPLOYMENT.md.
Los tests de dominio existentes aíslan MFA mediante override explícito; los nuevos
tests de seguridad mantienen MFA obligatorio y prueban los límites de acceso.

Pendiente para cerrar estos controles como parte del expediente: validación operativa
con usuarios, procedimiento/registro de soporte, mantenimiento diario de sesiones y
buckets, alertas de abuso y evaluación independiente. TOTP no ofrece resistencia al
phishing. Admins sin práctica carecen de registro en la auditoría actual y necesitan
registro operativo externo. Se desactiva la captura de variables locales en Sentry;
esto no sustituye el filtrado integral de PHI pendiente en INT-02. Se mantienen abiertos
los requisitos de contratos, conservación, auditoría y validación clínica.

Validación de la segunda entrega: 38 pruebas nuevas de límites de autenticación,
recuperación, cifrado, CSRF, inactividad, revocación y concurrencia real con PostgreSQL.
Checks de despliegue en imagen Docker limpia y consistencia de migraciones correctos.
La revisión visual en navegador local quedó pendiente por una denegación de acceso;
los formularios y redirecciones sí se ejercitan mediante el cliente de pruebas Django.

Suite completa final: 383 tests correctos con PostgreSQL 16 (110,707 segundos en
cuatro procesos). Las 38 pruebas de seguridad pasan también dentro de una imagen
Docker limpia con el manifiesto estático generado, sin depender de la .venv local.

La verificación posterior al despliegue detectó que la generación de estáticos en un
contenedor temporal no persistía: Compose no monta un volumen staticfiles. Se
recuperaron los archivos en el contenedor activo y se corrigió Dockerfile para
incluirlos en la imagen. CI comprueba los assets con DEBUG=false en un contenedor
nuevo, sin collectstatic adicional, y el despliegue comprueba el JavaScript de
sesiones además de /health/. La salud HTTP por sí sola no detectaba este fallo.

## Tercera entrega técnica: auditoría y protección del historial

- AuditLog solo admite nuevas entradas en el modelo, operaciones masivas y admin. PostgreSQL rechaza UPDATE, DELETE y TRUNCATE mediante triggers. Se conserva una instantánea del identificador/nombre del actor y se admiten eventos globales sin Practice, incluidos accesos de administradores. La migración histórica captura el nombre actual del usuario; no reconstruye nombres anteriores.
- Las notas finalizadas quedan protegidas también frente a SQL directo, operaciones masivas y objetos desactualizados. Las relaciones de notas, planes y diagnósticos impiden borrar en cascada pacientes, terapeutas o prácticas con historial. Al intentar borrar un paciente con historial se indica archivar; un plan referido por notas tampoco puede borrarse.
- Se registran lecturas y denegaciones en módulos sensibles, accesos del admin y rechazos de credenciales. La metadata usa nombres de vistas e identificadores, sin URL, búsqueda, cuerpo de petición ni contenido clínico. Algunos contextos incluyen identificadores de recursos, con límite de 200 y marca de truncamiento. Esta cobertura no equivale a identificar todos los recursos consultados en todas las rutas; faltan inventario completo, alertas y validación independiente.
- Los triggers se instalan exclusivamente en PostgreSQL. El propietario/superusuario de la base puede deshabilitarlos: no constituyen almacenamiento WORM ni protección contra un administrador comprometido. Quedan pendientes rol de aplicación con privilegios mínimos, copia independiente protegida, detección de manipulación y política de conservación de auditoría.
- Los borradores y otros tipos de registros conservan rutas de eliminación directa; esta entrega no implementa retención legal completa, legal hold, firma ni adendas. CLIN-01, AUD-01 y AUD-02 avanzan parcialmente y siguen abiertos por sus criterios restantes.
- Se propone Pennsylvania para el primer piloto y Massachusetts/California como candidatos posteriores, con métricas y límites documentados en [mercados iniciales](us-launch-markets.md). No se activan plazos ni borrado automático hasta validar las reglas aplicables a estado, profesión, menores y documento.

Las pruebas de transacciones deshabilitan solo los triggers de TRUNCATE durante limpieza de bases cuyo nombre empieza por `test_`, y los restauran después. El código de producción no utiliza esa excepción. La verificación de integridad se realiza con datos ficticios; no se ejecutan intentos de modificación sobre expedientes reales.
