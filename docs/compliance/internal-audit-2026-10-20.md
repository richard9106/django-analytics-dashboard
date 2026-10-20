# Auditoría interna de evidencias — 20 octubre 2026

## Dictamen y alcance

El despliegue comercial en AWS y el cobro live cuentan con evidencias. No hay evidencia suficiente para declarar cerrado el cumplimiento HIPAA ni para concluir que solo falta la verificación Google. Esto no demuestra que cada control pendiente sea inexistente: distingue lo acreditado de lo no acreditado.

Revisión documental, inspección selectiva de código y consultas de lectura autenticadas a AWS/GitHub. No se han inspeccionado expedientes de pacientes, contratos privados ni variables de producción; no se ha realizado pentest ni validación clínica. No se han modificado servicios o configuraciones. BAA AWS confirmado por el titular y registrado en aws-foundation-2026-10-20.md; no se ha verificado el documento contractual firmado.

## Evidencias positivas

- Actualización posterior: el titular aportó `/home/richard/Downloads/AWS+Business+Associate+Addendum.pdf`. Leídas sus cuatro páginas: corresponde al AWS Business Associate Addendum, Doc #3256920v3, versión 2023-01-20. El texto establece aceptación electrónica mediante AWS Artifact; el PDF no muestra identificador de cuenta ni fecha de aceptación concreta. Se acredita disponer del texto contractual y se mantiene la confirmación del titular de que fue activado. La comprobación independiente del estado de aceptación en Artifact sigue fuera del alcance realizado. No se copia el contrato confidencial al repositorio. Sus obligaciones de logging, retención y configuración deben incluirse en la verificación técnica pendiente.

- AWS consultado directamente: EC2 running y SSM Online; volumen raíz 60 GiB cifrado; grupo de seguridad expone 80/443 y SSH a una sola IPv4 /32, sin puertos PostgreSQL públicos.
- Ambos buckets S3 de documentos y backups: cuatro bloqueos de acceso público activos, cifrado AES256 y versionado habilitados. Política documental rechaza transporte sin TLS. Política DLM de snapshots diarios habilitada; esto no acredita ejecución reciente ni restaurabilidad por sí solo.
- El informe aws-cutover-2026-10-20.md registra migración completa, cotejo de registros y documentos, protección de notas firmadas, backup cifrado y restauración efectiva en una segunda DB vacía. Registra origen anterior detenido, timers AWS y despliegue real exitoso.
- GitHub: las tres ejecuciones recientes de Test and Deploy son satisfactorias; la última corresponde al HEAD local 84c208654e198e02fca7e79afdfad5923c7d5135.
- Código y evidencias registran permisos por práctica, firmas/adendas protegidas, auditoría, límites de acceso, sesiones y minimización de Sentry/calendario. Alcance parcial: no equivale a revisar todos los endpoints.

## Hallazgos abiertos

| Prioridad | Hallazgo | Evidencia / cierre necesario |
|---|---|---|
| Alta | Aprobación clínica y contractual no acreditada | compliance/README.md y validation.md mantienen requisitos de salida; contracts/README.md describe DPA/BAA/anexo como borradores sin firma. Completar alcance AWS actual y formalizar por cliente cuando corresponda; una firma privada posterior puede cerrar el punto si se aporta su referencia |
| Alta | Destinatarios externos sin cierre documentado | vendors.md deja Google Drive/Calendar, correo y diagnóstico pendientes según flujo. Inventariar PHI real y contratos/productos/cuentas; restringir las salidas no aprobadas. OAuth verificado no acredita cobertura contractual HIPAA |
| Alta | MFA diferido y riesgo de identidad abierto | config/settings.py:216 predetermina MFA_REQUIRED=false; clinical-readiness-us.md documenta decisión del titular. El informe aws-rehearsal-2026-10-20.md registra el segundo paso por correo habilitado; es independiente del TOTP y no corresponde describir el acceso como solo contraseña. Confirmar valores reales en producción y cerrar decisión de riesgo, recuperación y accesos privilegiados. No se afirma que el valor predeterminado pruebe el valor activo |
| Alta | Controles organizativos sin evidencia de ejecución | Designación del responsable, formación, simulacro operativo, control del equipo y aceptación de riesgo siguen pendientes en compliance/README.md, incidents.md y risk-register.md. Documentar ejecución y responsables reales |
| Alta | Revisión de permisos y validación clínica incompletas | readiness-progress-2026-10-16.md limita la matriz probada a notas/adendas/documentos. Completar rutas, admin, soporte y casos clínicos; registrar aceptación y resolver hallazgos |
| Media | Conservación y continuidad sin cierre integral | retention.md no tiene matriz aprobada ni motor integral de legal holds. La restauración AWS reduce el riesgo de recuperación, pero no acredita RPO/RTO aprobados, alertas ensayadas o custodia alternativa de claves |
| Media | Copias históricas fuera de AWS | cutover conserva origen anterior y la documentación describe R2/copias locales. Determinar contenido real, cobertura contractual, plazo y retirada autorizada. No borrar ni reactivar automáticamente |
| Media | Avisos públicos incompatibles con lanzamiento clínico | templates/accounts/signup.html y marketing/terms.html siguen exigiendo datos ficticios; legal_notice.html aún dice que el lanzamiento de pago está pendiente. Actualizar solo al aprobar el alcance real y versionar términos |
| Media | Expediente desactualizado | vendors.md, contracts/README.md y compliance/README.md describen alojamiento previo. Añadir estado actual y cierres fechados, preservando el historial; no marcar controles cerrados solo por migración |

## Graphify

Existe graphify-out con graph.json, graph.html y GRAPH_REPORT.md fechado 30 septiembre, además de un subdirectorio 4 octubre. Útil como mapa histórico; no representa por sí solo los cambios AWS del 20 octubre. No hay una herramienta Graphify callable expuesta en esta sesión. Se usó lectura directa de fuentes actuales para las conclusiones.

## Referencias normativas consultadas

- HHS, Security Rule: https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html
- HHS, análisis de riesgos: https://www.hhs.gov/hipaa/for-professionals/security/guidance/guidance-risk-analysis/index.html
- HHS, cloud: https://www.hhs.gov/hipaa/for-professionals/special-topics/health-information-technology/cloud-computing/index.html
- AWS, alcance HIPAA y responsabilidad compartida: https://aws.amazon.com/compliance/hipaa-compliance/

Las obligaciones se determinan por el rol y flujo reales. Las revisiones clínica e independiente son criterios documentados del proyecto; no se presentan como certificaciones universales exigidas por HIPAA. No se concluye que todos los proveedores necesiten idéntico BAA: depende de su función y datos.
