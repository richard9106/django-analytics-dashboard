# Respuesta a incidentes — procedimiento inicial

Versión 1, 15 octubre 2026. Responsable propuesto: Richard; pendiente de aceptación,
contacto alternativo y ejercicio con el operador. Canal inicial: support@nuviamy.com.
El correo es para avisos mínimos: no adjuntar expedientes, contraseñas ni claves.
Guardar la evidencia sensible en un expediente restringido fuera de Git.

1. **Registrar y evaluar.** Asignar INC-fecha-secuencia; anotar hora de descubrimiento
   en UTC, quién informa, sistemas afectados y hechos conocidos. Separar hechos de
   hipótesis. Riesgo de acceso activo, alteración o pérdida de registros se escala
   inmediatamente; no esperar al análisis completo.
2. **Contener preservando evidencia.** Revocar la cuenta/sesiones o integración
   afectada; aislar el servicio concreto si hace falta. Antes de borrar/reconstruir,
   conservar registros y estado con hash, acceso restringido y cadena de custodia.
   No destruir expedientes ni restaurar encima de producción como primer paso.
3. **Determinar alcance.** Fechas, prácticas/personas, datos, destinatario, acceso
   real o posible, medidas de protección y eficacia, exfiltración, integridad y
   disponibilidad. Investigar copias y terceros. Mantener cronología y decisiones.
4. **Notificar.** Cuando NuviaMy actúe como encargado/business associate, informar
   al cliente afectado sin demora injustificada, con hechos disponibles y ampliaciones;
   aplicar plazos más cortos del contrato. No esperar 60 días como objetivo operativo.
   El responsable debe evaluar si corresponde notificar autoridad/interesados.
5. **Recuperar.** Corregir causa, rotar secretos afectados mediante plan seguro,
   restaurar en entorno aislado y validar integridad/permisos/firmas antes de volver.
   Preservar transacciones legítimas posteriores al backup. Registrar aprobación.
6. **Cerrar.** Resumen de causa, impacto, mitigación, comunicaciones, pruebas de
   recuperación, acciones con dueño/fecha y revisión del análisis de riesgos.

## Reglas de notificación que hay que evaluar, sin automatizar conclusiones

HIPAA: el business associate debe informar a la covered entity de una brecha de PHI
no protegida sin demora injustificada y como máximo a los 60 días del descubrimiento.
Documentar la evaluación aplicable; no basta asumir que no se consultaron los datos.
Fuente: [HHS, breach notification](https://www.hhs.gov/hipaa/for-professionals/breach-notification/index.html).

RGPD: un encargado informa al responsable sin dilación indebida. El responsable
valora la notificación a la autoridad, cuando proceda, dentro de 72 horas desde que
consta la brecha; se permiten ampliaciones justificadas. No atribuir automáticamente
ese mismo deber a NuviaMy en todos sus roles.
Fuente: [EDPB](https://www.edpb.europa.eu/sme/assess-the-risks/data-breaches_en).

## Comprobación de escritorio del procedimiento

Escenario ficticio revisado al preparar este documento: credencial de un terapeuta
expuesta y duda sobre lectura de una nota. El flujo exige revocar acceso/sesiones,
preservar auditoría antes de borrar, identificar práctica y periodo, comunicar al
responsable con información inicial, evaluar exposición y validar recuperación.
Resultado: el guion distingue incidente de brecha y no ordena esperar ni borrar datos.
Límite: es una revisión escrita del guion, **no un simulacro ejecutado por Richard**,
no demuestra tiempos de respuesta y no se enviaron notificaciones reales.
