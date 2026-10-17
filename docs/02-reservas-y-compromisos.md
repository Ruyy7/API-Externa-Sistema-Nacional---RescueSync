# Preparación del modelo para reservas y compromisos

Este cambio conserva el alcance HTTP de I-3.2 (catálogo y consulta), pero incorpora al modelo las
piezas que evitan una remodelación cuando se implemente I-3.4.

## Problema

`cantidad_comprometida` por sí sola mezcla dos situaciones diferentes:

- una ONG presentó una oferta y el recurso debe quedar temporalmente reservado;
- el municipio adjudicó la oferta y el recurso quedó efectivamente comprometido.

También `categoria = MATERIAL` no permite saber si un recurso se consume o vuelve al stock. Una
ración y una carpa son materiales, pero su comportamiento al finalizar es distinto.

## Decisión

### Inventario

`inventario_recurso` mantiene tres cantidades:

- `cantidad_total`: stock administrado por la ONG;
- `cantidad_bloqueada`: reserva provisional asociada a ofertas aún no adjudicadas;
- `cantidad_comprometida`: cantidad adjudicada y todavía en ejecución.

La base impide que `bloqueada + comprometida` supere el total.

La disponibilidad pública se calcula como:

```text
cantidad_disponible = cantidad_total - cantidad_bloqueada - cantidad_comprometida
```

### Reutilización

`tipo_recurso.reutilizable` indica si el recurso vuelve a quedar disponible al finalizar la
actividad. El seed marca personal, carpas, frazadas y colchones como reutilizables, y alimentos,
agua, medicamentos e higiene como consumibles.

### Trazabilidad futura

Se agregan, sin endpoints de escritura todavía:

- `convocatoria`: referencia externa, cierre de ofertas y límite de adjudicación;
- `compromiso`: uno por oferta y ONG, con estado;
- `compromiso_item`: cantidades reservadas y comprometidas por recurso.

La referencia de la oferta y de la convocatoria es externa porque la webapp y el Sistema Nacional
usan bases separadas; no se crean FKs entre sistemas.

## Flujo que habilita

1. Presentar una oferta incrementa `cantidad_bloqueada` dentro de una transacción.
2. Modificar o retirar la oferta ajusta/libera esa cantidad.
3. Cerrar la ventana de ofertas no libera automáticamente la reserva; puede mantenerse hasta el
   límite de adjudicación.
4. Adjudicar mueve la cantidad seleccionada de bloqueada a comprometida y libera el resto.
5. Finalizar la actividad libera el compromiso. Si el recurso es consumible, además reduce
   `cantidad_total`; si es reutilizable, el total no cambia.

## Concurrencia

I-3.4 debe realizar cada modificación de inventario con una transacción y `SELECT ... FOR UPDATE`
sobre la fila de `inventario_recurso`. El modelo y los `CHECK` de PostgreSQL complementan ese
locking y evitan estados imposibles aun ante un error de aplicación.

## Alcance actual

Este documento no agrega endpoints de reserva, adjudicación ni liberación. Esas operaciones siguen
perteneciendo al punto I-3.4. Los endpoints de I-3.2 conservan sus rutas y solamente enriquecen la
respuesta con `cantidad_bloqueada` y `reutilizable`.
