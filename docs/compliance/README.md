# Expediente de preparación clínica — 15 octubre 2026

Estado: **preparación en curso; no aprobación para datos reales de pacientes**.
Esta es una evaluación interna del código y de evidencias operativas disponibles,
no una auditoría independiente ni una certificación. El cobro comercial live ya
está autorizado; ello no cambia el límite de uso clínico publicado.

Ver también los [avances del 16 de octubre](readiness-progress-2026-10-16.md): adendas,
matriz de acceso, preparación de migración y copias de documentos.

## Evidencia y trabajo entregado

- Invitaciones de equipo y portal sin contraseñas compartidas: enlace individual,
  caducidad, revocación por reenvío y comprobación bajo bloqueo al establecer clave.
- Minimización de Sentry y calendario, validación de documentos y pruebas de seguridad.
- Copia cifrada de configuración/claves fuera del VPS: descifrado y rechazo de
  manipulación comprobados el 15 de octubre; [alcance](recovery.md).
- [Análisis inicial y plan de riesgos](risk-register.md), [procedimiento de incidentes](incidents.md),
  [conservación y derechos](retention.md), [proveedores](vendors.md) y
  [validación previa al piloto](validation.md).

El código tiene que superar CI y el despliegue antes de considerarse activo. Consultar
el PR y su ejecución para el estado final de entrega; no interpretar un borrador local
como evidencia de producción. Los informes históricos conservan su fecha y alcance.

## Bloqueo confirmado de alojamiento

Contabo ha comunicado que no ofrece BAA para este VPS. Para el objetivo de tratar
ePHI sujeta a HIPAA es necesario migrar a infraestructura cubierta por BAA; trasladar
este VPS a Estados Unidos no resuelve el bloqueo. Ubicación confirmada por soporte:
Francia; acceso de soporte desde Alemania y Chequia. Ver [evidencia y plan](vendors.md).

## Condiciones pendientes antes del piloto con pacientes identificables

| Condición | Evidencia necesaria | Responsable propuesto |
|---|---|---|
| Proveedores que almacenan o procesan ePHI | Confirmación de servicio elegible y BAA firmado cuando corresponda; DPA y transferencias aplicables | Richard + proveedor |
| Infraestructura y recuperación | Cifrado documentado, aislamiento, copia histórica de documentos, recuperación en destino independiente y objetivos aprobados | Richard |
| Identidad, accesos y equipos | Decisión de MFA basada en riesgo, inventario de accesos, equipo cifrado y custodia de claves verificada | Richard |
| Conservación y cambios del expediente | Reglas por jurisdicción/profesión, legal holds, correcciones/adendas y disposición autorizada probadas | Richard + profesional clínico |
| Validación clínica y revisión de seguridad | Resultados fechados, hallazgos resueltos y aceptación de alcance | Profesional clínico + revisor independiente |
| Organización | Responsable de seguridad designado, formación realizada, simulacro operativo y aprobación del riesgo residual | Richard |

Las dos revisiones son criterios de salida de este proyecto; no se presentan como
una certificación externa universal exigida literalmente por HIPAA. No hay constancia
de designaciones, formación o firmas ya realizadas. No se declara cerrado un riesgo
por la mera existencia de este documento.

Fuente: [HHS, análisis de riesgos](https://www.hhs.gov/hipaa/for-professionals/security/guidance/guidance-risk-analysis/index.html).
