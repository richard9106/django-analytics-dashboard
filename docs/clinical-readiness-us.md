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
- Nueve pruebas adicionales de configuración y arranque, con escenarios seguros e inseguros.
- Workflow con PostgreSQL 16, checks de despliegue que fallan ante warnings, consistencia de migraciones/dependencias y despliegue del commit exacto probado. Comprobación del candidato antes de reemplazar el servicio.
- README actualizado para reflejar el objetivo clínico real. Esta entrega no cierra MFA, políticas, contratos, auditoría, retención ni el resto de bloqueos.

La inspección por SSH confirmó en el servicio previo: PostgreSQL, DEBUG desactivado, secreto Django que cumple los checks básicos, clave Fernet válida, R2 y controles HTTPS activos. Se detectó un origen CSRF HTTP a retirar antes del nuevo despliegue y permisos 664 del archivo de entorno a restringir a 600, conservando propietario. No se imprimieron secretos ni se consultaron expedientes de pacientes.

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

Revisión inicial: 334 tests correctos con SQLite. Primera entrega: 343 tests correctos con Django 5.2.17 y PostgreSQL 16 aislado (242,702 segundos); nueve pruebas adicionales de arranque/configuración. También pasan checks de despliegue, consistencia de migraciones/dependencias, validación Compose y checks en la imagen Docker construida. No valida cumplimiento ni todos los controles de producción.

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
