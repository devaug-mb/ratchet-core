# API — assistant-pi

Contrato HTTP del asistente. Es la **costura** por la que se conectan todos los
clientes: la web incluida, y en el futuro el cliente de voz y la app móvil.

- **Base:** `http://<host>:<puerto>/api/v1`
- **Versión actual:** `1`. Si el contrato cambia de forma incompatible, se publicará
  bajo `/api/v2` y `v1` seguirá funcionando durante la transición.
- **Formato:** JSON (UTF-8), salvo el chat, que usa SSE.
- Se levanta con `python -m assistant.web`; se configura en `config.toml`, sección
  `[web]`.

## Autenticación

Si `[web] token` tiene valor, **todos los endpoints requieren token** excepto la
página (`/`) y `GET /api/v1/info`.

```
Authorization: Bearer <token>
```

Sin token válido: `401 No autorizado`. Si `token` está vacío (uso local en
`127.0.0.1`), no se exige nada.

> El token es una clave compartida, sin cifrado. Para acceso desde fuera de casa la
> vía prevista es una **VPN** a tu red, no exponer el puerto a internet.

---

## Endpoints

### `GET /api/v1/info` — descubrimiento (público)

Permite a un cliente saber con qué habla y si necesita token.

```sh
curl http://127.0.0.1:8000/api/v1/info
```
```json
{ "api_version": 1, "profile": "system", "auth_required": true }
```

---

### `POST /api/v1/chat` — conversar (SSE)

Envía un mensaje y recibe la respuesta **en streaming**. Si el mensaje empieza por
`/`, se interpreta como **comando** (`/help`, `/tareas`…) y se devuelve su salida en
un único fragmento.

**Petición**
```json
{ "message": "¿Qué tengo pendiente?" }
```

**Respuesta:** `text/event-stream`, una trama por fragmento:

```
data: {"chunk": "Tienes "}

data: {"chunk": "pan en la compra."}

data: {"done": true}
```

Campos posibles en cada trama: `chunk` (texto), `error` (fallo del modelo),
`done` (fin del stream).

```sh
curl -N -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"hola"}'
```

> Las peticiones se **serializan**: el asistente atiende una conversación a la vez.
> Este endpoint usa el chat **por defecto** (perfil de `config.toml`). Para varios
> chats, ver abajo.

---

## Chats (varias conversaciones)

Puedes tener varias conversaciones abiertas a la vez, cada una con su **perfil**.
Los datos (memoria, notas...) son compartidos; lo propio de cada chat es su perfil e
historial. Los chats viven en memoria (se pierden al reiniciar). Siempre existe uno
"por defecto".

### `GET /api/v1/profiles`
```json
{ "profiles": ["aleman", "asistente", "conciso", "system"] }
```

### `GET /api/v1/chats`
```json
{ "chats": [ { "id": "d0c27d4a", "profile": "system", "title": "hola", "is_default": true } ] }
```

### `POST /api/v1/chats` — abrir un chat
```json
{ "profile": "aleman" }
```
Devuelve el chat creado (`id`, `profile`, `title`, `is_default`). `400` si el perfil
no existe.

### `POST /api/v1/chats/<id>/message` — mensaje a un chat (SSE)
Igual que `POST /chat` pero dirigido a un chat concreto. Mismo formato de respuesta.

### `DELETE /api/v1/chats/<id>` — cerrar un chat
`400` si no existe o si es el chat por defecto (no se puede cerrar).

---

### `GET /api/v1/brief` — resumen del día

Le pide al modelo un saludo breve con lo importante de hoy (horario, tareas,
repasos). Es una llamada al LLM, así que puede tardar unos segundos.

```json
{ "brief": "¡Buenos días! Hoy tienes italiano a las 18:00 y 2 tareas." }
```

---

### `GET /api/v1/memory` — hechos recordados

```json
{ "facts": { "nombre": "Gus", "aleman.nivel": "intermedio" } }
```

---

### `GET /api/v1/items` — listas (tareas, compra…)

Parámetro opcional `list` para filtrar.

```sh
curl -H "Authorization: Bearer TOKEN" \
  "http://127.0.0.1:8000/api/v1/items?list=compra"
```
```json
{ "items": [ { "id": 1, "list": "compra", "text": "pan", "done": false } ] }
```

---

### `GET /api/v1/schedule` — horario

El horario distingue eventos **recurrentes** (`kind: "weekly"`, con `day`) de **citas
puntuales** (`kind: "dated"`, con `date`). Parámetro `when`:

- `?when=today` → lo que hay hoy (citas de hoy + recurrentes de este día), resuelto.
  ```json
  { "events": [ { "id": 2, "title": "reunión", "kind": "dated", "date": "2026-07-29",
                  "start": "10:00", "end": "14:00" } ] }
  ```
- `?when=week` → esta semana, agrupado por día (solo días con eventos).
  ```json
  { "days": [ { "date": "2026-07-22", "weekday": "miércoles",
                "events": [ { "id": 1, "title": "gimnasio", "kind": "weekly",
                              "day": "miércoles", "start": "20:00", "end": null } ] } ] }
  ```
- sin `when` → todas las entradas en crudo (`{ "entries": [...] }`), para listarlas.

---

### `GET /api/v1/review` — repasos pendientes hoy

Parámetro opcional `subject` (materia).

```json
{ "due": [ { "id": 1, "subject": "alemán", "text": "der Tisch", "next_review": "2026-07-21" } ] }
```

---

### `GET /api/v1/notes` — listado de notas

```json
{ "notes": ["fisica.txt", "transistores.txt"] }
```

### `GET /api/v1/notes/<nombre>` — contenido de una nota

```json
{ "name": "fisica.txt", "content": "Apuntes de física cuántica." }
```

`404` si no existe. Las rutas que intenten salir de la carpeta de notas se rechazan.

---

### `GET /api/v1/activity` — registro de actividad

Parámetro opcional `limit` (por defecto 20). Herramientas usadas, en orden.

```json
{ "events": [
    { "timestamp": "2026-07-20T13:27:19", "tool": "reloj", "arg": "",
      "result": "10:00", "ok": true, "ms": 0.4 }
] }
```

---

## Códigos de estado

| Código | Significado |
|--------|-------------|
| 200 | OK |
| 400 | Petición inválida (p. ej. mensaje vacío) |
| 401 | Falta el token o no es válido |
| 404 | Endpoint o recurso inexistente |

## Estado y siguientes pasos

Hoy la API es de **lectura** (más el chat). La **escritura** de datos (crear/editar/
borrar hechos, ítems, horario) llegará con la app móvil de datos — ver
[ROADMAP-V4.md](ROADMAP-V4.md), iteración V4.4.
