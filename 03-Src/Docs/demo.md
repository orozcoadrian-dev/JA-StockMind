# Guion de sustentación / 8 minutos

## 0:00-0:45 / Problema

Explicar que cuatro mayoristas describen el mismo repuesto con nombres y códigos diferentes. El riesgo es contar inventario duplicado como si fueran referencias distintas y comprar al proveedor equivocado.

## 0:45-1:30 / Preparación

Desde la raíz ejecutar:

```bash
python demo/seed.py
```

Mostrar en la consola que los cuatro archivos tienen 85 filas y que el seed deja sugerencias pendientes. Abrir `http://127.0.0.1:5501`.

## 1:30-2:30 / Importación

Abrir **Importar lista**. Señalar el selector de proveedor, la zona de archivo y la barra de progreso. Subir uno de los Excel demo. Mostrar el resumen: filas importadas, rechazadas y el historial con la ruta persistida.

Frase para explicar el diseño: “El sistema guarda el archivo original, pero el producto conserva también el nombre crudo; normalizar no destruye evidencia”.

## 2:30-3:45 / Catálogo

Abrir **Inventario**. Buscar `grip` y expandir una fila. Mostrar nombre canónico, atributos, stock y referencias de proveedores. Explicar que la tabla es densa a propósito: sirve para comparar precios y códigos en una sola lectura.

## 3:45-5:00 / Equivalencias

Abrir **Coincidencias**. Ejecutar recalcular si es necesario. Mostrar el grip rojo de Guerrero y Malusa con score y razones. Comparar mentalmente con el grip azul y el grip rojo de 28 mm: comparten palabras, pero los atributos contradictorios los mantienen separados.

Confirmar solo una coincidencia. Mostrar que el vínculo pasa a catálogo canónico y que la acción queda registrada.

## 5:00-6:15 / Agente

Abrir **Agente** y decir:

> “Dime qué productos se repiten entre Inversiones Guerrero y Malusa y explícame las razones.”

Mostrar las herramientas que el modelo solicita y la respuesta. El agente no fusiona automáticamente porque sugerir y consolidar son acciones diferentes.

Después decir:

> “Si un grip rojo lo provee Inversiones Guerrero y Malusa, es el mismo.”

La herramienta muestra la regla estructurada. Confirmar desde el flujo y mostrar el número de pares afectados y los `ProductLink` creados.

## 6:15-7:15 / Reportes

Abrir **Reportes**. Mostrar productos bajo mínimo y sugerencias de compra. Decir:

> “¿A quién me conviene comprar los frenos este mes?”

La respuesta debe apoyarse en precios persistidos, no en una recomendación inventada.

## 7:15-8:00 / Cierre técnico

Mostrar `/api/docs` y resumir:

- API versionada y paginada;
- errores JSON uniformes;
- reglas y acciones auditables;
- confirmación humana para cambios destructivos;
- pruebas automatizadas y seed reproducible.

## Tres frases listas para decirle al agente

1. “Dime qué productos se repiten entre Inversiones Guerrero y Malusa y explícame las razones.”
2. “Si un grip rojo lo provee Inversiones Guerrero y Malusa, es el mismo.”
3. “¿A quién me conviene comprar los frenos este mes? Compárame los precios reales.”
