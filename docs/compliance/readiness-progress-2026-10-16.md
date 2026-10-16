# Avances de expediente clínico — 16 octubre 2026

Evaluación interna con datos ficticios; no validación clínica externa ni aprobación HIPAA.

## Adendas

Original firmado intacto, adendas firmadas con motivo, contenido, autor, hora, digest
vinculado a firma original e ID de revisión único. Solo el terapeuta responsable con
permiso de edición puede crearlas. Revisión separada, atestación y vencimiento de 30
minutos; reenvío de la misma revisión no duplica el registro. Modelo y triggers rechazan
cambios/borrados; exportaciones clínicas incluyen adendas. ZIP/JSON conserva el contenido completo;
PDF es un resumen con límites de filas/texto ahora indicados expresamente. No se ofrece edición posterior
ni uso de una adenda para firmar un original pendiente. Correcciones de adendas se añaden
como nuevas entradas preservando las anteriores.

## Matriz de acceso revisada

| Recurso | Terapeuta responsable | Otro terapeuta de la práctica | Admin/owner misma práctica | Otra práctica | Portal |
|---|---|---|---|---|---|
| Revisión de nota de sesión | Sí, con permiso clínico | No | Lectura con permiso | No | No |
| Firmar nota/adenda | Sí, con permiso de edición | No | No suplantar al terapeuta | No | No |
| Documentos misma práctica | Según permiso documental | Según permiso documental | Sí | No | Solo propios marcados visibles |
| Documento oculto al paciente | Según permiso | Según permiso | Sí | No | No |

Las pruebas ejercitan GET y POST de adendas, lectura de nota, descarga documental,
separación de prácticas, visibilidad del portal y su desactivación. El acceso documental
actual es a toda la práctica según permiso: **no se afirma aislamiento por terapeuta
para documentos/clientes**. La matriz completa de todos los módulos y admin sigue
siendo parte de la revisión de seguridad previa al piloto.

## Preparación de migración

Herramienta local de configuración y [plan de corte/retorno](migration-plan.md).
Generación probada con configuración sintética; no provisiona servidores ni activa
integraciones. La prueba de recuperación en otro host espera al destino contratado.

## Documentos históricos

`python -m ops.document_snapshot` captura archivos actuales cifrados con CMS AES-256-GCM
para el certificado de recuperación local. No escribe ni elimina objetos del origen.
El manifiesto queda dentro del cifrado, contiene IDs, claves de almacenamiento,
tamaños y SHA256, sin nombres originales ni contenido en consola.

Primera captura independiente de dos documentos actuales: 20261016T091508Z.
SHA256 cifrado: `ff1dfce8bb3c23c13e085a65958037e608dd294c700d51ce29dcde2e13a919d9`.
Archivo fuera de Git: `~/Documents/Personal/NuviaMy-Recovery/nuviamy-documents-20261016T091508Z.cms`.
Se comprobó su descifrado e integridad en memoria; no se borraron objetos reales ni
se extrajeron expedientes de producción a disco para el ensayo.

Las pruebas con archivos ficticios borran/corrompen una copia de trabajo y recuperan
los bytes originales desde una captura anterior. Rechazan manipulación criptográfica,
rutas inseguras y sobreescritura de destinos existentes. El restore solo escribe en
un directorio NUEVO aislado; no modifica DB ni almacenamiento remoto.

Límites: herramienta manual para capturas pequeñas (200 MiB de contenido, 25 MiB por
archivo), sin programación/alertas ni retención automática. No recupera versiones
anteriores a la primera captura. Una captura independiente no implica por sí sola
inmutabilidad WORM, copia de DB o alta disponibilidad. Custodia adicional de la clave,
frecuencia/retención y recuperación en host independiente siguen pendientes.

## Recorrido automatizado

Registro sin tarjeta y sin Checkout, prueba de 15 días, alta de paciente, consulta
inicial de 15 minutos, sesión, nota, firma, adenda, exportación con historial y lectura/
exportación al vencer la prueba con escritura bloqueada. Solo datos ficticios y correo
locmem, Stripe simulado. La recuperación de contraseña mantiene sus pruebas existentes.
El profesional clínico todavía debe revisar significado, redacción y usabilidad con
casos representativos y registrar su aceptación; tests no sustituyen esa revisión.
