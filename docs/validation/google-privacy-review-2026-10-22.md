# Revisión de privacidad Google — 22 de octubre de 2026

Resultado: cumplimiento parcial. La política pública no describe suficientemente el tratamiento de datos de Google para considerar lista esta parte de la verificación. Revisión de documentación oficial, web pública y código local en e177147; no se ha inspeccionado la configuración privada de Google Cloud Console ni se ha realizado una auditoría integral de seguridad. No se ha cambiado la política ni desplegado nada.

## Evidencias y estado

| Punto | Resultado observado |
| --- | --- |
| Página pública propia, HTML, identidad y enlace desde inicio | Correcto: https://nuviamy.com/privacy/ responde y muestra NuviaMy y el operador. El footer de inicio enlaza la política. Versión publicada 2026-10-20-v3. |
| Dominio verificado y URL configurada en OAuth | Pendiente de comprobar en Google Console; tener HTTPS no prueba la verificación de propiedad. |
| Descripción de Google | Insuficiente: la política se limita a indicar intercambio con Gmail, Calendar y Drive, sin describir las operaciones y categorías específicas que sí existen en el código. |
| Destinatarios y protección | La política identifica proveedores e infraestructura en general, pero no explica específicamente el recorrido, acceso autorizado y protección de datos y credenciales de Google. |
| Conservación y eliminación | Hay reglas generales de registros y backups, pero no instrucciones específicas para datos Google, desconexión, revocación y copias externas. |
| Uso limitado | No se encontró declaración afirmativa de cumplimiento de Limited Use en las plantillas o documentación pública revisadas. No hay declaración específica sobre venta/publicidad, acceso humano o entrenamiento de modelos generalizados con datos de Google. No se encontró evidencia en estos flujos de entrenamiento o publicidad; ausencia de declaración y uso indebido son cuestiones distintas. |
| Aviso contextual | La pantalla Integrations permite elegir funciones, pero no enlaza la política ni presenta una explicación suficiente de acceso, uso, almacenamiento y compartición antes de Connect Google. Hay enlaces en registro/contratos; no sustituyen un aviso contextual en la conexión. |
| Cambios de uso | La política promete una nueva versión; no describe notificación y consentimiento previo para una finalidad nueva de datos Google. |

## Qué hace el código y debe reflejarse con exactitud

- `apps/practices/forms.py`: permisos por capacidad: gmail.send, gmail.readonly, calendar.events y drive.file. Identidad base openid/email en `google_oauth.py`; no se solicita profile.
- `apps/practices/google_oauth.py`: obtiene email de cuenta; Gmail lectura solicita hasta diez mensajes recientes (consulta de 30 días), cabeceras From/Subject/Date y procesa snippet si está presente. La vista los muestra sin guardarlos como un modelo de correo. Envío transmite destinatario, asunto y cuerpo.
- `apps/practices/models.py`: guarda cuenta, permisos, tokens y expiración. Tokens usan EncryptedTextField; `apps/practices/fields.py` permite texto sin cifrar si falta FIELD_ENCRYPTION_KEY. Verificar el entorno y los registros existentes antes de prometer cifrado universal.
- `apps/appointments/google_calendar.py`: crea/actualiza/elimina bloques de ocupación con fechas y título genérico Reserved time; guarda identificador/enlace de evento y estado de sincronización. `list_calendar_events` también lee título y fechas de eventos próximos del calendario principal para la interfaz.
- `apps/documents/google_drive.py`: sube/actualiza contenido y nombre de documentos elegidos, consulta/crea carpeta y guarda identificador/enlace de archivo. No presenta un flujo de borrado remoto en este módulo.
- `ExternalIntegration.disconnect()` y `GoogleOAuthDisconnectView`: borran tokens y cuenta de la integración activa y detienen capacidades. No llaman al endpoint de revocación de Google ni eliminan automáticamente eventos/archivos externos, referencias históricas o backups. Eliminar credenciales locales no equivale a revocar el permiso en Google ni a borrar todas las copias.

## Prioridad de remediación

1. Ampliar la política con sección Google que describa los flujos anteriores, finalidades, destinatarios, protección, conservación y eliminación; añadir compromiso Limited Use enlazado a Google y restricciones de uso y acceso humano acordes con las operaciones reales.
2. Añadir aviso contextual y enlace Privacy junto a la conexión, e instrucciones para desconectar, retirar acceso desde la cuenta Google y solicitar eliminación; explicar límites de copias externas y backups. Decidir e implementar revocación en la desconexión si se va a prometer.
3. Revisar necesidad de lectura de Gmail. gmail.send es sensible; gmail.readonly es restringido. La lectura actual pasa por el backend, por lo que no debe asumirse que no almacenar correos evita requisitos de evaluación de seguridad. Confirmar con Google la ruta aplicable y posibles excepciones; no afirmar aprobación ni exigir evaluación sin revisar el caso concreto. Si se elimina lectura, hacerlo en código, interfaz y scopes solicitados/declarados, no solo en el texto.
4. Comprobar en Console URLs, dominio verificado, permisos declarados, alcance de la verificación y material de demostración. Comprobar también la justificación de Drive: el código se presenta como exportación/almacenamiento; la política Workspace restringe usar Drive como backup de contenido de una app. Esto requiere revisar el caso concreto, no permite concluir automáticamente que cualquier exportación manual esté prohibida.

## Fuentes consultadas

- [App Privacy Policy](https://support.google.com/cloud/answer/13806988?hl=es-419): accesibilidad, identidad y descripción de tratamiento.
- [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy): transparencia y cambios de finalidad.
- [Google Workspace user data and developer policy](https://developers.google.com/workspace/workspace-api-user-data-developer-policy): declaración afirmativa Limited Use, aviso contextual y usos permitidos.
- [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes): clasificación de permisos y evaluación para datos restringidos procesados en servidores.
- [Política publicada](https://nuviamy.com/privacy/) y [web de inicio](https://nuviamy.com/).
