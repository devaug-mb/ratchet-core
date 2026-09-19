# assistant-pi

Asistente personal local para Raspberry Pi 5, llamado ratchet en honor a ratchet & clank, probado con Gemma 3 1B y 4B ejecutado mediante Ollama; sin embargo, la arquitectura es modular, así que el LLM es un componente sustituible.

- **Cómo funciona por dentro:** [MANUAL.md](MANUAL.md)
- **API HTTP:** [API.md](API.md)

## Requisitos

- Python 3.11+
- [Ollama](https://ollama.com) corriendo en local con el modelo descargado:

  ```sh
  ollama pull gemma3:1b
  ```

  o
  `sh
    ollama pull gemma3:4b
    `

## Uso

Instala el paquete en modo editable una sola vez (recomendado):

```sh
python3.13 -m pip install -e .
python3.13 -m assistant.main
```

O, sin instalar nada, apunta `PYTHONPATH` al directorio `src`:

```sh
PYTHONPATH=src python3.13 -m assistant.main
```

Escribe tus mensajes; `salir` termina la sesión. La configuración
(modelo, host, timeout) está en `config.toml`.

### Interfaz web

Además del terminal, puedes usar el asistente desde el navegador:

```sh
python3.13 -m assistant.web       # o PYTHONPATH=src python3.13 -m assistant.web
```

Abre `http://127.0.0.1:8000`. Es una app de chat ligera con streaming y formato
(**negrita**, _cursiva_, `código`), que reutiliza el mismo asistente (comandos
`/...` incluidos). Sin dependencias externas.

- **Home (pantalla de inicio):** al abrir ves un **panel con tu día** — un resumen
  generado por el asistente y tarjetas con tu horario de hoy, tareas pendientes,
  repasos, notas y lo que recuerda de ti. El botón 🏠 vuelve al panel; escribir un
  mensaje salta al chat.
- **Varios chats a la vez:** con el botón ☰ abres la lista de chats; con ＋ creas uno
  nuevo eligiendo perfil (el organizador, el tutor de alemán…). Cada chat mantiene su
  hilo; la memoria y los datos son compartidos.
- **Instalable (PWA):** desde el móvil puedes "Añadir a pantalla de inicio" y se
  comporta como una app.

**Desde el móvil** (misma red wifi):

1. En `config.toml`, sección `[web]`, pon `host = "0.0.0.0"` y un `token` (una
   contraseña cualquiera), p. ej. `token = "loquesea123"`.
2. Averigua la IP de tu equipo en la red local (en macOS: Ajustes → Red, o
   `ipconfig getifaddr en0`).
3. En el móvil, abre `http://ESA-IP:8000`. La primera vez te pedirá el token; se
   guarda en el navegador.

El token protege el acceso cuando la web está abierta a la red. Si dejas `host =
"127.0.0.1"` (solo tu equipo), el token es opcional.

### API HTTP

El mismo servidor expone una API versionada (`/api/v1/...`) para leer tus datos
(memoria, listas, horario, repasos, notas, actividad) y para conversar. Es la
costura por la que se conectarán el cliente de voz y la app móvil. El contrato está
documentado en **[API.md](API.md)**. Ejemplo:

```sh
curl -H "Authorization: Bearer TU_TOKEN" http://127.0.0.1:8000/api/v1/memory
```

### Perfiles (personalidades)

El comportamiento del asistente se define mediante **perfiles**. Cada perfil es un
fichero de texto en `prompts/` (un prompt de sistema con nombre). Los que vienen
de ejemplo:

```
prompts/
  system.txt        # asistente general de aprendizaje (por defecto)
  aleman.txt        # tutor de alemán: practica y corrige en alemán
  conciso.txt       # respuestas muy breves y directas
  asistente.txt     # organizador de listas (tareas, compra)
```

El perfil activo se elige por **nombre** en `config.toml`:

```toml
[profile]
active = "aleman"     # usa prompts/aleman.txt
directory = "prompts" # carpeta donde están los perfiles
```

**Crear un perfil nuevo:** añade un fichero `prompts/<nombre>.txt` con las
instrucciones y pon `active = "<nombre>"`.

Cambiar de perfil requiere **editar `config.toml` y reiniciar** (un perfil por
sesión). Si pones un nombre que no existe, al arrancar verás un error claro con la
lista de perfiles disponibles.

### Herramientas

El asistente puede usar herramientas cuando lo necesita, sin que tú hagas nada
especial: pregunta con naturalidad y el modelo decide si usarlas.

- **calculadora** — evalúa aritmética (p. ej. "¿cuánto es 15% de 240?").
- **reloj** — fecha y hora actuales ("¿qué hora es?").
- **leer_archivo** — lee un `.txt` de la carpeta `notes/` ("lee ejemplo.txt y
  resúmelo"). Por seguridad, solo puede leer dentro de `notes/`.
- **recordar** — guarda un dato para futuras sesiones ("recuerda que me llamo
  Alba"). Ver "Memoria persistente" abajo.
- **buscar_notas** — busca en tus notas por **significado** ("¿qué apunté sobre
  transistores?"). Ver "Búsqueda semántica" abajo.
- **organizador** (`agregar_item`, `ver_lista`, `completar_item`, `borrar_item`) —
  gestiona listas de tareas y de la compra ("apunta comprar pan"). Ver "Organizador"
  abajo. Mejor con el perfil `asistente`.
- **horario** (`agregar_horario_recurrente`, `agregar_cita`, `ver_agenda`,
  `borrar_horario`) — distingue **eventos recurrentes** (gimnasio cada miércoles) de
  **citas puntuales** (reunión el 29/07 de 10 a 14h). Así, "¿qué tengo hoy?" o "¿esta
  semana?" responden con precisión. Disponible en **cualquier perfil**.
- **repaso** (`agregar_repaso`, `repasos_pendientes`, `marcar_repasado`) — repaso
  espaciado: apunta algo (una palabra, un concepto) y el asistente te lo recuerda en
  intervalos crecientes. Ver "Repaso espaciado" abajo.

Coloca tus textos en `notes/`. La carpeta y el número máximo de herramientas
encadenadas por turno se configuran en `config.toml`, sección `[tools]`. Añadir
una herramienta nueva es crear una clase en `src/assistant/tools/` y registrarla;
el detalle está en [MANUAL.md](MANUAL.md).

### Búsqueda semántica en tus notas (RAG local)

El asistente puede buscar en los `.txt` de `notes/` por **significado**, no por
nombre de archivo. Requiere un modelo de embeddings local:

```sh
ollama pull nomic-embed-text
```

Luego pregunta con naturalidad ("¿qué tengo apuntado sobre X?") y usará la
herramienta `buscar_notas`. Las notas se indexan solas (de forma incremental: solo
se re-procesa lo que cambie) en `data/notes_index.db`. Se configura en
`config.toml`, sección `[retrieval]` (modelo, nº de fragmentos, tamaño). Para
desactivarlo, `enabled = false`.

### Organizador (listas de tareas y compra)

El perfil `asistente` (actívalo con `active = "asistente"` en `config.toml`) actúa
como un organizador sencillo: le dices qué apuntar y lo guarda en listas.

- "apunta comprar leche" → lo añade a la lista `compra`.
- "añade estudiar alemán a mis tareas" → lista `tareas`.
- "¿qué tengo pendiente?" → muestra las listas con un número por elemento.
- "marca hecha la 2" / "borra la 3" → por número.

Comandos directos (sin pasar por el modelo): `/tareas` y `/compra`. Las listas se
guardan en `data/organizer.db` (configurable en `[organizer]`).

**Horario de clases/citas.** También puedes organizar un horario:

- "añade clase de alemán el martes a las 18:00" → lo guarda con día y hora.
- "¿qué tengo el lunes?" / "enséñame el horario" → lo muestra ordenado.

El horario es **compartido entre perfiles**: puedes crearlo con el perfil
`asistente` y luego, desde el perfil de alemán, preguntar por tu próxima clase.
Comando directo: `/horario`. Se guarda en el mismo `data/organizer.db`.

### Memoria persistente

El asistente puede recordar datos **entre sesiones** (tu nombre, qué idioma
estudias, tu nivel...). Se guardan como pares clave-valor en un fichero SQLite
(`data/memory.db` por defecto, configurable en `config.toml` sección `[memory]`).

- Para guardar algo: díselo con naturalidad ("recuerda que me llamo Alba"). El
  modelo usará la herramienta `recordar`.
- Los hechos guardados se le muestran automáticamente al inicio de cada sesión,
  así que puede tenerlos en cuenta desde el primer mensaje. Para no inflar el
  prompt, solo se inyectan los `max_facts` más recientes (`config.toml`).
- Puedes **agrupar** hechos por categoría usando un punto en la clave
  (`aleman.nivel`, `perfil.nombre`); `/memoria` los muestra agrupados.
- `/memoria` lista todo; `/memoria <clave>` muestra un dato; `/olvidar <clave>` lo
  borra.

Para empezar de cero, borra el fichero `data/memory.db`.

### Comandos de la conversación

Los comandos empiezan por `/`:

- `/help` — lista todos los comandos.
- `/perfil` — muestra el perfil activo y los disponibles.
- `/memoria` — lista los datos recordados (o uno: `/memoria <clave>`).
- `/olvidar <clave>` — borra un dato recordado.
- `/tareas`, `/compra` — muestran esas listas.
- `/horario` — muestra el horario.
- `/repasar [materia]` — qué toca repasar hoy.
- `/actividad [n]` — últimas herramientas usadas, en orden.
- `/salir` — termina la sesión.

También terminan la sesión las palabras `salir`, `exit`, `quit`, o `Ctrl+D` /
`Ctrl+C`. Todo lo demás que escribas se envía al modelo.

## Desarrollo y pruebas

Instala las dependencias de desarrollo (solo la primera vez):

```sh
python3.13 -m pip install -e ".[dev]"
```

Comandos disponibles vía `make`:

```sh
make test    # ejecuta pytest
make lint    # ruff (estilo e imports)
make type    # mypy (tipos)
make check   # las tres comprobaciones juntas
```

Los tests usan proveedores falsos, así que **no** necesitan Ollama en marcha.

### Logs y registro de actividad

Dos cosas distintas:

- **Logs de consola** (`[logging]`): con `level = "INFO"` ves cada uso de
  herramienta en vivo; con `DEBUG`, además el detalle de las peticiones al modelo.
- **Registro de actividad** (`[audit]`): un rastro **persistente y ordenado** de las
  herramientas usadas, en `data/activity.log` (JSONL). Se consulta con `/actividad`
  dentro de la app, o desde fuera con `tail -f data/activity.log`. Es lo que te
  permite ver "qué herramientas se han usado y en qué orden" sin rebuscar entre los
  logs.

### Repaso espaciado

Apunta cosas que quieras memorizar y el asistente te las recuerda en intervalos
crecientes (1, 3, 7, 15 días). Por ejemplo: "recuérdame repasar _der Tisch = la
mesa_". Con el comando `/repasar` ves lo que toca hoy. Al marcar algo como repasado,
su siguiente repaso se aleja.

## Estructura

```
prompts/               Perfiles: un .txt por personalidad (system, aleman, ...)
notes/                 Textos que la herramienta leer_archivo puede consultar
data/memory.db         Memoria persistente (SQLite), se crea al usarla
src/assistant/
  main.py              CLI: cablea las piezas y hace la entrada/salida
  web/                 Interfaz web local (http.server + SSE + página HTML)
  service.py           Capa de servicio reutilizable (comandos + respuestas)
  commands.py          Framework de comandos (/help, /perfil, /memoria, ...)
  config.py            Carga de config.toml -> objeto Config
  logging_setup.py     Configuración central del logging
  prompts.py           Carga de prompts desde ficheros de texto
  profiles.py          Resuelve y lista perfiles por nombre
  core/conversation.py Dominio: orquesta diálogo + historial + prompt + tools + memoria
  core/tool_protocol.py Formato del marcador de herramientas y su detección
  llm/base.py          Contrato LLMProvider + tipos (Message, Role)
  llm/ollama_provider.py  Implementación para Ollama (streaming, salud, reintentos)
  memory/base.py       Contrato MemoryStore (memoria persistente)
  memory/sqlite_store.py  Implementación con SQLite
  items/               Almacén de ítems en listas (tareas, compra): ItemStore
  schedule/            Almacén del horario (clases/citas): ScheduleStore
  review/              Repaso espaciado: ReviewStore
  audit/               Registro de actividad: AuditLog (JSONL)
  retrieval/           Búsqueda semántica: Embedder/Retriever, índice SQLite
  tools/               Herramientas: calculadora, reloj, archivos, recordar, buscar_notas
```

Regla clave: `core/` depende solo de `llm/base.py` (la interfaz), nunca de una
implementación concreta. `main.py` es el único que conoce `OllamaProvider`.
