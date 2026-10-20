# Contratos para el tratamiento de datos clínicos

Preparados el 15 de octubre de 2026 para Richard Andres Marles Bonilla, que opera como NuviaMy desde España. Son propuestas contractuales editables en inglés para clientes profesionales, inicialmente estadounidenses. Requieren completar el cliente y el anexo real de servicios, cerrar los acuerdos de proveedores y revisar su adecuación al ámbito contratado antes de presentarlos como contratos definitivos. No se han firmado, enviado a terceros, publicado en la web ni usado para habilitar datos clínicos.

## Documentos preparados

- `data-processing-agreement.docx`: contrato de tratamiento entre NuviaMy y la consulta, con instrucciones, confidencialidad, seguridad, subencargados, transferencias, incidentes, derechos, auditoría y salida.
- `hipaa-business-associate-agreement.docx`: BAA adicional cuando el cliente sea una entidad cubierta por HIPAA o un business associate que contrata a NuviaMy como subcontratista. No todos los terapeutas ni todas las cuentas estadounidenses tienen automáticamente ese encaje.
- `clinical-processing-schedule.docx`: anexo común obligatorio que concreta alcance, datos, proveedores, ubicaciones, medidas y conservación. Las entidades, planes, regiones y coberturas no verificadas quedan marcadas para completar; su mera inclusión no autoriza PHI.

Los `.md` del mismo nombre son las fuentes editables y mantienen el mismo contenido. Las versiones base son NUVIA DPA 2026 10 15 v1, NUVIA BAA 2026 10 15 v1 y NUVIA SCHEDULE 2026 10 20 v3. No contienen el NIF privado del operador ni firmas simuladas.

## Actualización del 20 de octubre de 2026

El anexo v3 sustituye la descripción antigua de alojamiento por AWS EC2 y S3 en us-east-1, administración desde España y BAA AWS confirmado por el titular. Incluye cifrado de volumen y buckets, acceso en dos pasos por correo, adendas firmadas y recuperación real de DB documentada. Distingue el origen activo de las copias históricas en Contabo/R2 y medios privados; mantiene pendientes la disposición de esas copias, referencias contractuales privadas, revisión de integraciones, retención por cliente y aprobación clínica. No se ha firmado ni activado el uso clínico por esta actualización.

Se conservan las versiones v1 y v2 del anexo en `archive/`. El DPA y el BAA base conservan sus versiones: sus campos de referencia deben completarse con el anexo v3 al preparar un acuerdo concreto. Las instrucciones históricas sobre contratar Contabo que aparecen más abajo no describen la infraestructura productiva actual; AWS es el origen activo.

## Un único anexo compartido

La versión v3 del anexo usa cuatro apartados: qué datos se guardan y para qué; quién los procesa y dónde; protección e incidentes; y salida, exportación y eliminación. Se adjunta el mismo anexo al DPA y, cuando corresponda, al BAA. No se pide rellenar anexos duplicados y los precios siguen en los términos comerciales.

Los campos pendientes se completan con evidencias reales antes de la aprobación clínica. La infraestructura productiva está en AWS US East Northern Virginia; se declara la administración desde España y no se promete acceso exclusivamente estadounidense. Los proveedores citados no quedan autorizados para PHI por aparecer en la lista. La versión v1 anterior se conserva en `archive/` únicamente como historial, sin añadir otro anexo al paquete del cliente.

## Quién firma

| Documento | Parte del cliente | Parte NuviaMy |
| --- | --- | --- |
| Tratamiento de datos y anexo | El profesional autónomo titular o representante autorizado de la entidad contratante | Richard Andres Marles Bonilla |
| BAA y anexo cuando proceda | Representante autorizado de la entidad cubierta o del business associate cliente | Richard Andres Marles Bonilla como business associate o subcontratista |
| Acuerdos con proveedores | Richard Andres Marles Bonilla, en la función real de esa relación | La entidad proveedora correspondiente mediante su acuerdo vinculante |

No se exige que todos los empleados o terapeutas de una clínica firmen por separado el contrato entre empresas. El cliente debe organizar las autorizaciones y deberes de confidencialidad de su personal. Si un terapeuta contrata por su propia consulta independiente, sí será la parte cliente de su propio acuerdo. Un paciente no firma el BAA del proveedor SaaS: sus consentimientos, información y autorizaciones asistenciales constituyen otra relación, que debe gestionar la consulta según la ley aplicable.

## Cómo formalizarlos

Puede utilizarse firma electrónica válida o documento firmado por ambas partes. Para la primera fase puede hacerse de forma manual y guardar el contrato en un archivo privado protegido. Un checkbox genérico de términos, una compra de Stripe o el login de un empleado no deben registrarse como firma de estos contratos.

Identificar la razón social real y comprobar la autoridad del firmante; completar y adjuntar la versión exacta del anexo; facilitar el texto íntegro descargable; obtener una acción expresa de aceptación con intención de firmar y constancia de las dos partes; conservar copia inmutable y entregar copia al cliente. La prueba de firma debe vincular identidad, entidad/consulta, cargo, autoridad, documento y hash, anexos, versión y fecha/hora UTC. IP y agente de navegador pueden ser evidencia auxiliar con minimización y acceso restringido; no sustituyen identidad y autoridad. No inventar ni retrofechar la firma de Richard. Una oferta electrónica previamente autorizada también necesita un mecanismo de ejecución atribuible adecuado a su ley contractual, no simplemente una casilla adicional.

Si después se integra en la aplicación: firma por propietario o representante autorizado, acuerdo por workspace, estados pendiente/firmado/aprobado, descarga de copias, renovación ante cambios materiales y registro de la firma de NuviaMy. La aprobación clínica es un paso distinto: firmar no debe desbloquear automáticamente PHI si faltan contratos de proveedores o controles. El flujo ya está preparado en el código mediante Configuración → Contratos para propietarios y publicación expresa por un operador autorizado en Django admin. Véanse [las instrucciones de contratación](onboarding.md). Esta implementación no acredita despliegue, firmas reales ni aprobación clínica.

## Proveedores y siguiente acción concreta

Contabo ofrece un DPA estándar en su panel de cliente: crear un nuevo Data Processing Agreement, verificar los datos del titular, seleccionar el VPS y demás servicios reales, indicar categorías de datos e interesados, revisar y concluir el acuerdo, y guardar su PDF. No declarar categorías falsas para obtener un contrato. Su documentación pública describe un DPA GDPR; no acredita un BAA HIPAA para el VPS contratado.

Para Contabo y Cloudflare R2, solicitar por escrito si firman un BAA para el plan y producto exactos, entidades, regiones y acceso de soporte. Si no existe cobertura suficiente, ese servicio no puede incluirse en la cadena PHI sujeta a HIPAA; habrá que cambiar de servicio/proveedor o mantener fuera los datos afectados. No basta con que el cliente firme nuestro BAA ni con cifrar sus copias. Para Google, Sentry y demás integraciones evaluar el flujo concreto y retirarlo del alcance clínico hasta tener los contratos y controles requeridos. El soporte en Gmail personal/Brevo/Email Routing se limita a comunicaciones no clínicas.

Texto de consulta listo para adaptar y enviar por el titular, no enviado:

> We operate NuviaMy, a professional practice-management service administered from Spain. We are assessing your exact service [PRODUCT AND PLAN] for storing or processing electronic protected health information for US HIPAA-regulated customers. Please confirm whether your contracting entity will execute a HIPAA Business Associate Agreement covering this product, storage and backup regions, administrative/support access and relevant subcontractors. Please also provide the applicable Data Processing Agreement, transfer safeguards, security responsibilities, incident-notification terms, data-return/deletion process and any plan restrictions. An ordinary GDPR DPA alone does not resolve our HIPAA subcontractor requirements. If this service is not eligible for a BAA, please confirm that in writing. No patient data is included in this request.

## Qué no queda resuelto con los contratos

La firma establece obligaciones; no prueba que estén cumplidas. Continúan pendientes la cobertura contractual real de proveedores, completar el anexo de conservación y ubicaciones, el análisis y tratamiento de riesgos, controles y validación del alcance. Las notas de progreso ordinarias no son automáticamente las psychotherapy notes separadas de HIPAA. Se excluyen estas últimas y los registros sujetos a 42 CFR Part 2 hasta aprobar un alcance y adenda específicos; Part 2 no aplica automáticamente a cualquier referencia a adicciones. No se fija una conservación universal ni se promete almacenamiento indefinido.

Los textos no incorporan SCC de transferencias por simple referencia, no crean una certificación y no sustituyen una revisión jurídica de las condiciones y del estado/profesión del cliente. HHS advierte que sus modelos cubren elementos HIPAA y pueden requerir otros elementos de derecho contractual estatal. No se aplica por defecto una cláusula de arbitraje, jurisdicción exclusiva, indemnización o limitación de responsabilidad no pactada.

## Fuentes oficiales verificadas

- [RGPD publicado en BOE, artículos 3, 28, 32, 33 y capítulo V](https://www.boe.es/doue/2016/119/L00001-00088.pdf): contrato de encargo, seguridad, notificación y transferencias; el artículo 28.9 admite forma escrita electrónica.
- [AEPD, directrices de contratos entre responsables y encargados](https://www.aepd.es/es/documento/guia-directrices-contratos.pdf): concreción del encargo y sus instrucciones.
- [HHS, requisitos y cláusulas modelo de BAA](https://www.hhs.gov/hipaa/for-professionals/covered-entities/sample-business-associate-agreement-provisions/index.html): finalidad, salvaguardas, derechos, subcontratistas, supervisión y fin de la relación.
- [HHS, BAA y firmas electrónicas](https://www.hhs.gov/hipaa/for-professionals/faq/are-business-associate-contracts-in-electronic-form-acceptable/index.html): admite forma electrónica si el contrato es válido conforme a la ley aplicable.
- [HHS, nube y PHI cifrada](https://www.hhs.gov/hipaa/for-professionals/special-topics/health-information-technology/cloud-computing/index.html): el almacenamiento cifrado sin clave no excluye por sí solo la condición de business associate.
- [45 CFR 164.410](https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-D/section-164.410): aviso sin retraso injustificado y límite exterior de 60 días; no se confunde con un SLA de 24 o 72 horas.
- [HHS, 42 CFR Part 2](https://www.hhs.gov/hipaa/part-2/index.html): ámbito específico de confidencialidad de registros de programas de trastorno por consumo de sustancias.
- [Contabo, DPA y formalización en el panel](https://docs.contabo.com/docs/dpa/dpa/): contrato estándar del producto; no evidencia de un BAA firmado.
