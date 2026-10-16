# Conservación, corrección y derechos — marco operativo

15 octubre 2026. Propuesta pendiente de aprobación por responsable y profesionales.
No se activa borrado automático ni se inventa un plazo general de expediente clínico.

## Antes de incorporar una práctica

Registrar jurisdicción, profesión, tipos de registros, adultos/menores, financiadores,
reglas específicas y responsable de custodia. El cliente debe indicar las instrucciones
aplicables y NuviaMy debe comprobar que puede ejecutarlas. La matriz aprobada contendrá:
clase de dato, fundamento, evento de inicio, plazo, excepciones, legal hold, destino
al terminar contrato y evidencia de eliminación. No prometer soporte de un plazo que
el producto no puede imponer.

HIPAA no establece un único periodo de conservación de historias clínicas; las reglas
estatales y otras obligaciones pueden hacerlo. Los seis años de documentación de
cumplimiento de la Security Rule no son un plazo universal para las notas clínicas.
Fuentes: [historias clínicas, HHS](https://www.hhs.gov/hipaa/for-professionals/faq/does-hipaa-require-covered-entities-to-keep-medical-records-for-any-period/index.html),
[documentación de seguridad, HHS](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html).

## Operación

- Cancelar una suscripción no autoriza a borrar registros. Acordar devolución/exportación,
  conservación y eliminación con el responsable; separar facturación del expediente.
- Toda solicitud de acceso, corrección, restricción o supresión tiene ticket, identidad
  verificada, alcance, autorización y respuesta documentada. No enviar archivos clínicos
  por correo ordinario. El paciente se dirige a su profesional; no modificar su historia
  por una petición de identidad no verificada al soporte.
- Preservar el original de una nota firmada. Una corrección requiere adenda vinculada,
  autoría, fecha y razón; no desbloquear el original ni cambiar SQL para satisfacerla.
  Las notas firmadas ya tienen un flujo de adendas inmutables revisadas y firmadas;
  la validación clínica y las reglas de corrección de otros tipos de registros siguen pendientes.
- Un legal hold suspende disposición relevante, incluidas copias; registrar quién lo
  impuso y su levantamiento. Todavía no existe un motor integral de legal holds.
- Eliminar solo con autorización y prueba de ausencia de obligación incompatible;
  registrar disposición de DB, objetos y copias. Definir cuándo expiran backups y cómo
  reaplicar supresiones tras una restauración. No declarar borrado instantáneo de copias.
- Distinguir progress notes de psychotherapy notes; no ofrecer tratamiento separado de
  estas últimas hasta tener controles y autorizaciones específicas validados.

Pendiente: matriz de una clínica piloto, controles técnicos integrales de retención, validación clínica de adendas,
pruebas de exportación y eliminación autorizada, reglas fiscales/comerciales separadas.
