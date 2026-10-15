# Recuperación de configuración y claves — evidencia 15 octubre 2026

Se ejecutó `ops/offsite_config_backup.py` desde el ordenador del operador. El VPS
cifra con un certificado público RSA-3072 y OpenSSL CMS AES-256-GCM/RSA-OAEP. La
clave privada se genera y conserva localmente; no se envía al VPS. SSH transporta
solo el archivo cifrado. La verificación descifra a memoria, inspecciona entradas,
comprueba claves de configuración presentes y no extrae texto a disco.

## Resultado observado

- Fecha UTC: 20261015T141538Z; ocho entradas regulares: `.env`, Compose, sitio Nginx,
  dos pares servicio/timer y configuración protegida Stripe live.
- Campos de claves Django, cifrado de campos y backups presentes; valores no impresos.
- Descifrado satisfactorio y modificación de un byte del cifrado rechazada.
- SHA256 del archivo cifrado: `80488f38969b46c0c4dcbea06ca0bbfa3ac6472d373ffeb98171e9099e8f3395`.
- Archivo privado: `/home/richard/Documents/Personal/NuviaMy-Recovery/nuviamy-config-20261015T141538Z.cms`.
- Clave privada local: `/home/richard/.local/share/nuviamy-recovery/recovery-private.pem`.
  Directorios 0700 y archivos 0600; no están en Git. No publicar su contenido.

## Repetición y recuperación

Ejecutar desde este ordenador, con SSH autorizado y OpenSSL instalado:

```sh
.venv/bin/python ops/offsite_config_backup.py --host root@193.46.243.105 --output-dir /home/richard/Documents/Personal/NuviaMy-Recovery
```

Conservar archivo, manifiesto y clave en destinos protegidos independientes; la
custodia adicional/offline de la clave sigue pendiente. Una pérdida del portátil con
su única clave impediría descifrar. No enviar clave y archivo por correo ni subirlos
juntos al VPS. Verificar cifrado de disco del equipo; 0600 no lo demuestra.

Para recuperar, autenticar al operador, preparar destino aislado sin correos/cobros,
validar manifiesto y usar `inspect_bundle` del script para verificar descifrado y
seguridad del archivo antes de cualquier extracción. Revisar manualmente las ocho
entradas en un área privada sin logs públicos. Aplicar configuración al destino de
ensayo, restaurar DB/documentos y comprobar permisos, datos cifrados y firmas. Cambiar
DNS o arrancar integraciones reales requiere un plan separado. No restaurar un `.env`
anterior al paso live sin revisar consecuencias de cobros/webhooks.

## Lo que no prueba

Esta copia inicial no está programada automáticamente. No incluye el contenido de DB
ni documentos, versiones históricas de objetos, sistema completo o DNS. Complementa
el ensayo interno documentado del 13/10, realizado en el mismo VPS.
Cierra la carencia de una primera copia independiente recuperable de claves/configuración,
no la recuperación integral ante pérdida del proveedor. Falta aprobar RPO/RTO,
frecuencia, alertas, retención y completar el ensayo en otro host.
