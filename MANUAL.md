# MANUAL — cómo funciona el asistente por dentro

Explicación de alto nivel de cómo el asistente gestiona cada cosa. No es
documentación línea a línea: es el modelo mental para entender qué hace el código
y por qué. Se irá ampliando a medida que se añadan skills y más funcionalidades.

> Para instalar y usar, mira el [README](README.md). Para el plan de evolución, el
> [ROADMAP](ROADMAP.md).

---

## Idea central: el modelo no recuerda nada por sí mismo

Lo más importante para entenderlo todo: **el modelo de lenguaje es sin estado**.
Cada vez que le hablas, Ollama recibe una petición independiente y no sabe nada de
las anteriores. La "memoria" y la "personalidad" no viven en el modelo: las
construye nuestro código y se las **reenvía en cada mensaje**.

Es decir, en cada turno le mandamos al modelo un paquete completo:

```
[ prompt de sistema ] + [ historial reciente ] + [ tu mensaje nuevo ]
```

Todo lo demás son detalles de cómo se arma ese paquete.

---

## El recorrido de un mensaje

Cuando escribes algo y pulsas Enter, ocurre esto:

```
Tú escribes
   │
   ▼
main.py  ── bucle de consola: ¿es un comando o un mensaje?
   │        (si es "salir" termina; si no, lo trata como mensaje)
   ▼
Conversation.send(texto)      ── dominio: arma el paquete de contexto
   │
   ▼
LLMProvider.generate(mensajes) ── contrato abstracto
   │
   ▼
OllamaProvider                 ── traduce a una petición HTTP
   │
   ▼
Ollama  →  Gemma 3 1B          ── genera la respuesta
   │
   ▼
la respuesta vuelve por el mismo camino hasta la pantalla
```

Cada capa tiene una sola responsabilidad y no conoce los detalles de la de abajo.
`Conversation` no sabe que hay Ollama; solo conoce "un proveedor que genera texto".

---

## Cómo se gestionan los comandos y la capa de servicio

El bucle de consola (`main.py`) es deliberadamente tonto: solo lee líneas y
escribe respuestas. Toda la decisión de qué hacer con una línea vive en el
**servicio** (`AssistantService`), que es el núcleo reutilizable del asistente y no
sabe nada de la consola. En el futuro, una interfaz web o de voz usaría el mismo
servicio sin cambiarlo.

Ante cada línea, el bucle:

1. Si está vacía o es una palabra de salida (`salir`, `Ctrl+D`...), actúa en
   consecuencia.
2. Le pregunta al servicio si es un **comando** (empieza por `/`). Si lo es, el
   servicio lo ejecuta y devuelve un texto para mostrar (y si hay que salir). El
   mensaje **no** llega al modelo.
3. Si no es un comando, es un mensaje: el servicio genera la respuesta.

Los comandos (`/help`, `/perfil`, `/memoria`, `/olvidar`, `/salir`) son un
**registro simple** `nombre -> función`: cada uno recibe su argumento y devuelve el
texto a mostrar. Añadir uno nuevo es escribir una función y registrarla; no hay
motor de parsing ni jerarquías. Mantener todo en un único registro es lo que hace
trivial ampliarlos.

---

## Cómo se gestiona la memoria de sesión

La memoria la lleva la clase `Conversation` (en `core/conversation.py`), y es
simplemente **una lista de mensajes en RAM**. Funciona así:

- Cada mensaje es un objeto con dos campos: quién habla (`role`: sistema, usuario
  o asistente) y qué dice (`content`).
- En cada `send()`, el código:
  1. Añade tu mensaje a la lista.
  2. Manda la lista entera al modelo.
  3. Añade la respuesta del asistente a la lista.
- Así, en el turno siguiente, la lista ya contiene todo lo hablado y el modelo
  "recuerda" el contexto.

Para no gastar RAM ni inflar el prompt sin límite, la lista se **recorta**: solo
se conservan los últimos `max_turns` turnos (un turno = tu mensaje + la respuesta).
Los más antiguos se descartan. El límite se ajusta en `config.toml`.

Esta memoria de sesión es **volátil**: el historial de la charla vive solo
mientras el programa está abierto. Para lo que debe sobrevivir entre sesiones,
está la memoria persistente (ver más abajo).

---

## Cómo se gestiona la memoria persistente

Además del historial volátil, el asistente puede recordar **hechos entre
sesiones**: tu nombre, qué idioma estudias, tu nivel, etc. Son datos pequeños y
duraderos, no la conversación entera.

El modelo es, de nuevo, deliberadamente simple: **pares clave-valor** guardados en
un fichero SQLite (`data/memory.db`). Nada de embeddings ni búsqueda semántica
todavía; eso sería un paso mucho mayor y aquí no hace falta.

Dos movimientos:

- **Guardar.** Cuando le pides recordar algo ("recuerda que me llamo Alba"), el
  modelo usa la herramienta `recordar`, que escribe el hecho en la base de datos.
  Si el dato ya existía, se actualiza en vez de duplicarse.
- **Recuperar.** Al construir cada mensaje, el asistente lee todos los hechos
  guardados y los coloca en el prompt de sistema, como un bloque "Datos que
  recuerdas del usuario". Así el modelo los tiene presentes desde el primer
  mensaje de cualquier sesión futura.

Como en el resto del proyecto, el almacenamiento vive **detrás de una interfaz**
(`MemoryStore`). Hoy la cumple una implementación con SQLite, pero podría
cambiarse por otra (un fichero JSON, otra base de datos) sin tocar el dominio.

**Que no crezca sin control.** A medida que se acumulan hechos, meterlos todos en
el prompt gastaría memoria y contexto. Por eso solo se inyectan los **N más
recientes** (configurable). En disco se guardan todos; lo que se acota es cuántos
"ve" el modelo en cada turno. Los hechos se pueden **agrupar por categoría** con una
simple convención: una clave como `aleman.nivel` pertenece a la categoría `aleman`.
No hay tablas ni esquemas nuevos, solo nombres de clave con un punto.

Para empezar de cero, se borra el fichero `data/memory.db`.

---

## Cómo funciona el prompt de sistema (¿se manda siempre?)

**Sí, se manda en cada mensaje.** El prompt de sistema es un texto que describe
cómo debe comportarse el asistente (su propósito, tono, idiomas...). Vive en un
fichero editable, `prompts/system.txt`, y se carga una vez al arrancar.

La clave está en cómo lo trata `Conversation`:

- El prompt de sistema se guarda **aparte** del historial, no dentro de la lista
  de la conversación.
- En cada `send()`, se coloca **el primero**, delante del historial, y el conjunto
  completo se envía al modelo.

Esto tiene dos consecuencias importantes:

1. **Siempre está presente.** Como se antepone en cada petición, el modelo nunca
   "olvida" sus instrucciones, por larga que sea la charla.
2. **Nunca se recorta.** Al estar fuera del historial, el mecanismo que descarta
   los turnos antiguos no puede eliminarlo jamás.

Si quieres cambiar la personalidad del asistente, editas ese fichero de texto (o
eliges otro perfil, ver abajo) y reinicias. No hay que tocar código.

---

## Cómo se gestionan los perfiles (personalidades)

Un "perfil" es simplemente **un prompt de sistema con nombre**. En vez de un único
fichero, hay una carpeta (`prompts/`) con un `.txt` por personalidad: el general,
un tutor de alemán, un modo conciso, etc.

El mecanismo es deliberadamente simple:

- En `config.toml` indicas el perfil **activo** por su nombre (`active = "aleman"`).
- Al arrancar, el código traduce ese nombre al fichero `prompts/aleman.txt`, lee
  su contenido y lo usa como prompt de sistema de toda la sesión.
- Si el nombre no corresponde a ningún fichero, el arranque se detiene con un
  mensaje claro que lista los perfiles que sí existen.

No hay nada más: un perfil no es una clase ni una estructura de datos, es texto.
Añadir una personalidad nueva = crear un fichero. Cambiar de perfil = editar una
línea de `config.toml` y reiniciar (un perfil por sesión, por ahora).

Esto reutiliza al 100 % el mecanismo del prompt de sistema: el perfil *es* el
prompt de sistema; lo único que añade esta capa es "elegir cuál por nombre".

---

## Cómo se gestionan las herramientas (tools)

Una herramienta es una capacidad concreta que el modelo puede usar cuando le hace
falta: una calculadora, el reloj, leer un archivo. Como el modelo solo sabe
generar texto, todo el mecanismo se apoya en **un formato de texto acordado**.

**El acuerdo (protocolo).** Al arrancar, se añade al prompt de sistema una lista
de las herramientas disponibles y una instrucción: "si necesitas una, responde con
una línea `[[tool:NOMBRE]] ARGUMENTO`". El modelo, cuando quiere usarla, emite esa
línea en lugar de responder al usuario.

**El bucle.** En cada turno, tras pedir una respuesta al modelo, el código mira si
esa respuesta contiene el marcador:

1. Si **no** hay marcador, es la respuesta final: se muestra al usuario.
2. Si **sí** lo hay, el código ejecuta la herramienta con su argumento, añade el
   resultado a la conversación (como un mensaje más) y vuelve a preguntar al
   modelo. Ahora el modelo ya tiene el dato y responde en lenguaje natural.

Este ciclo se repite por si hicieran falta varias herramientas seguidas, pero con
un **tope de iteraciones** (configurable) para que nunca se quede en bucle.

**Por qué un protocolo de texto propio y no el "tool-calling" nativo.** Con un
modelo pequeño (1B), pedirle JSON estructurado es poco fiable. Un marcador de
texto simple es más robusto, más fácil de depurar (se ve en crudo) y, sobre todo,
**no obliga a cambiar la interfaz del modelo** (`LLMProvider`): toda la lógica de
herramientas vive en el dominio, no en la capa que habla con Ollama. Así, cambiar
de modelo sigue sin afectar a las herramientas.

**Seguridad.** Las herramientas validan su entrada. La calculadora no usa `eval`:
interpreta solo números y operadores. La lectura de archivos está **restringida a
una carpeta** (`notes/`); cualquier ruta que intente salir de ahí se rechaza. Y si
una herramienta falla, devuelve un texto de error que se le pasa al modelo, sin
tumbar la sesión.

**Añadir una herramienta nueva.** Se crea una clase con un `name`, una
`description` (que el modelo leerá) y un método `run(argumento) -> texto`, y se
registra en el arranque. No hay que tocar el bucle ni el resto del asistente.

---

## Cómo funciona el streaming (texto que aparece gradualmente)

El modelo genera la respuesta palabra a palabra. En vez de esperar a tenerla
entera, el asistente la va mostrando según llega, como ChatGPT o Claude.

El contrato del modelo (`LLMProvider`) tiene dos formas de responder: `generate`
(respuesta completa de golpe) y `stream` (fragmentos según se generan). El proveedor
de Ollama implementa el streaming real; cualquier proveedor que no lo soporte usa
una implementación por defecto que entrega la respuesta completa en un solo trozo.
Así se pudo añadir streaming **sin romper** la interfaz existente.

**El detalle sutil: streaming y herramientas.** Cuando el modelo usa una
herramienta, su respuesta contiene marcadores (`[[tool:...]]`) que el usuario no
debe ver. En streaming no sabes si vendrá un marcador hasta que llega, así que el
asistente emite el texto en directo pero, **en cuanto aparece un `[[tool`, deja de
mostrar** desde ahí: los marcadores y lo que venga después quedan ocultos. El modelo
puede pedir **varias herramientas en una misma respuesta** (una por línea); se
ejecutan todas y luego responde en lenguaje natural. Resultado: los marcadores nunca
se muestran; solo la respuesta final se ve fluir.

---

## Cómo funcionan los logs

El asistente deja constancia de lo que hace mediante el sistema de logging estándar
de Python. Lo más útil: **cada vez que se usa una herramienta** se registra una
línea con el nombre, el argumento, el resultado y cuánto tardó. Por ejemplo:

```
17:22:12 INFO assistant.tools.registry: herramienta 'calculadora' arg='149*15' -> '2235' (0 ms)
```

Esto responde a "¿se usó de verdad la herramienta X?" sin tener que abrir la base de
datos ni adivinar. Todos los usos pasan por un único punto (`ToolBox.run`), así que
ahí está toda la instrumentación.

El nivel de detalle se ajusta en `config.toml`: con `INFO` se ven las herramientas;
con `DEBUG`, además, cada petición al modelo. Un único módulo (`logging_setup`)
configura todo esto al arrancar; el resto del código solo emite mensajes.

---

## Dónde se configura todo

Los ajustes viven en `config.toml`, en la raíz del proyecto: el modelo a usar, la
dirección de Ollama, el tiempo máximo de espera, cuántos turnos se recuerdan y qué
fichero de prompt de sistema se carga.

Un único módulo (`config.py`) lee ese fichero y construye un objeto de
configuración; el resto del programa lo recibe ya hecho y **no vuelve a leer el
disco**. Así, si algún día la configuración cambia de formato, solo hay un sitio
que tocar.

---

## Cómo funciona el organizador (listas)

El perfil `asistente` convierte al asistente en un organizador sencillo: listas de
tareas, de la compra, o las que necesites. Por debajo hay un **almacén de ítems**
estructurado, separado de la memoria clave-valor porque un ítem es más rico: tiene
un número, pertenece a una lista y puede estar hecho o pendiente.

El mecanismo reutiliza todo lo anterior:

- Un almacén (`ItemStore`, con implementación SQLite) tras una interfaz, como la
  memoria o el LLM.
- Una familia de **herramientas** (añadir, ver, completar, borrar) que el modelo usa
  cuando le pides organizar algo. Son **genéricas**: en vez de una herramienta por
  lista, reciben el nombre de la lista como argumento (`compra: leche`). Así no se
  infla el prompt.
- Cada ítem tiene un **número** visible al listarlo, que es como se completa o borra
  ("marca hecha la 2").
- Dos **comandos** (`/tareas`, `/compra`) leen las listas directamente, sin pasar por
  el modelo — rápido y fiable.

Es el mismo patrón de siempre: dominio contra una interfaz, implementación concreta
inyectada desde el arranque, y una capacidad nueva que no toca el resto del sistema.

**El horario y "compartir entre perfiles".** El horario es otro almacén
(`ScheduleStore`), y sus herramientas están disponibles en **todos los perfiles**, no
solo en el organizador. Así, aunque crees el horario desde el perfil `asistente`, tu
tutor de alemán puede consultarlo. No es que los perfiles "se hablen": es que **leen
el mismo almacén compartido**.

**Dos tipos de evento, para responder con precisión.** El horario distingue:

- **Recurrentes** (`weekly`): se repiten un día de la semana (gimnasio los miércoles).
- **Puntuales** (`dated`): ocurren en una fecha concreta (una reunión el 29/07).

La clave está en la consulta `on_date(fecha)`: para un día dado, junta las citas de
esa fecha exacta con los recurrentes cuyo día de la semana coincide. Sobre eso se
construye "hoy" y "esta semana" (recorriendo los 7 días). Por eso el asistente puede
decir con exactitud qué toca cada día, sin confundir un evento fijo con uno puntual.
El cambio de modelo trajo una **migración**: las entradas del formato antiguo (solo
día + hora) se convierten en recurrentes al arrancar, para no perder nada.

## Cómo funciona el repaso espaciado

Para memorizar (vocabulario, conceptos), repetir justo antes de olvidar es lo que
funciona. El asistente implementa una versión **mínima**: cada cosa a repasar tiene
una fecha de próximo repaso, que al repasarla se aleja siguiendo intervalos fijos
crecientes (1, 3, 7, 15 días). Nada de algoritmos complejos.

Es otro almacén (`ReviewStore`) con el mismo patrón. El "hoy" se inyecta desde
fuera, lo que hace el cálculo de fechas fácil de probar. Con `/repasar` (o pidiéndolo
al asistente) ves lo que toca hoy; al marcar algo repasado, salta al siguiente
intervalo. La "materia" es solo una etiqueta para agrupar (alemán, física...).

## Cómo funciona el registro de actividad

Los logs de consola sirven para depurar, pero se mezclan con la conversación y no
son cómodos de revisar. El **registro de actividad** es un rastro aparte: cada vez
que se usa una herramienta, se anota una línea en un fichero (`data/activity.log`),
en formato JSON, una por evento. Como es *append-only* y ordenado, "ver qué se ha
usado y en qué orden" es simplemente leer el fichero — con el comando `/actividad`
desde dentro, o con `tail`/`grep` desde fuera.

Se escribe desde el **único punto** por el que pasan todas las herramientas
(`ToolBox.run`), así que no hay que instrumentar nada más. Si por lo que sea no se
puede escribir el fichero, la sesión sigue como si nada: auditar nunca debe estorbar
al asistente.

## Cómo funciona la búsqueda semántica en tus notas

`leer_archivo` necesita el nombre exacto del fichero. La búsqueda semántica va un
paso más allá: encuentra lo relevante **por significado**, aunque no recuerdes en
qué nota está.

La idea, en tres pasos:

1. **Indexar.** Cada `.txt` de `notes/` se trocea en fragmentos y, para cada uno, se
   calcula un *embedding*: un vector de números que representa su significado. Los
   vectores se guardan en una base de datos local (SQLite). Este indexado es
   **incremental**: se guarda una huella (hash) de cada nota y solo se vuelve a
   procesar la que haya cambiado, así que después de la primera vez es casi
   instantáneo.
2. **Buscar.** Cuando preguntas algo, se calcula el embedding de tu consulta y se
   compara (con *similitud coseno*) con el de cada fragmento. Los más parecidos son
   los más relevantes.
3. **Responder.** Los mejores fragmentos se le devuelven al modelo, que redacta la
   respuesta a partir de ellos.

Todo es **local**: los embeddings los calcula un modelo pequeño en tu propio Ollama
(`nomic-embed-text`), no se va nada a la nube. Como el resto del proyecto, vive tras
una interfaz (`Retriever`): hoy usa embeddings + SQLite, pero podría cambiarse por
otra técnica (p. ej. búsqueda por palabras clave) sin tocar el asistente.

## Cómo funciona la interfaz web

El terminal y la web son **dos caras del mismo asistente**. Aquí se ve por qué
mereció la pena construir la capa de servicio en la V2: la web no reimplementa nada,
solo es otro cliente de `AssistantService`.

- El **servidor** usa la librería estándar de Python (`http.server`), sin frameworks.
  Sirve una página de chat y expone un endpoint que devuelve la respuesta en
  *streaming* mediante SSE (Server-Sent Events): el navegador recibe la respuesta
  fragmento a fragmento, igual que el terminal.
- El **frontend** es una única página HTML autocontenida (sin build, sin librerías
  externas), así que funciona sin internet, dentro de tu red local.
- Al ser un asistente de un solo usuario con estado (la conversación), las
  peticiones se **serializan** con un cerrojo: se atiende una cada vez.

Un detalle aprendido: como la web atiende en varios hilos y las bases de datos
SQLite no se pueden compartir entre hilos por defecto, se permite explícitamente el
uso multihilo (es seguro porque el cerrojo garantiza que solo se accede de una en
una).

## Cómo funciona el Home (el panel personal)

El asistente acumula datos valiosos —tareas, horario, repasos, memoria, notas—, pero
si solo se ven preguntando, es como si no existieran. El Home los pone delante nada
más abrir la app.

Tiene dos partes:

- **Las tarjetas** son puro reflejo de los datos: cada una pide su endpoint
  (`/schedule`, `/items`, `/review`, `/notes`, `/memory`) y lo pinta. Cargan al
  instante porque no dependen del modelo.
- **El resumen diario** (arriba) sí usa el modelo: `DailyBrief` reúne lo importante de
  hoy (horario, tareas, repasos) y le pide 1-2 frases de saludo. Se carga aparte, para
  que las tarjetas no esperen a la respuesta del LLM. Si Ollama no está, degrada a un
  saludo neutro. Nunca inventa: solo resume lo que hay en los datos.

La idea de fondo: con un modelo local no se puede ganar a ChatGPT en conocimiento
general, así que el valor está en **mostrarte tu mundo** y ser útil de un vistazo.

## Cómo funcionan los varios chats (SessionManager)

En el terminal hay una sola conversación. En la web puedes tener **varias abiertas a
la vez**, cada una con su perfil: un chat con el organizador, otro con el tutor de
alemán. Lo gestiona el `SessionManager`.

La idea clave es qué se comparte y qué no:

- **Lo persistente es compartido y global**: memoria, notas, tareas, horario. Da
  igual desde qué chat apuntes algo, todos lo ven.
- **Lo que se multiplica es la conversación**: su perfil (prompt de sistema) y su
  historial, que viven en RAM. Cada chat es una `Conversation` distinta.

Por eso el `SessionManager` no reconstruye el asistente entero por chat: reutiliza
las mismas herramientas y almacenes (una fábrica crea conversaciones cambiando solo
el perfil). Siempre existe un chat "por defecto", que es el que usa el endpoint
simple `/api/v1/chat` y clientes como la voz, que no manejan varios chats. Los chats
viven en memoria: se pierden al reiniciar (persistirlos es una mejora futura).

## La API: la costura para todo lo que viene

El mismo servidor expone una **API HTTP versionada** (`/api/v1/...`) que no solo
sirve para conversar: también deja **leer tus datos** (memoria, listas, horario,
repasos, notas, actividad) en JSON. El contrato está en [API.md](API.md).

Por qué importa: es el punto por el que se conectarán **todos** los clientes
futuros — el cliente de voz, la app del móvil — sin tocar el dominio. El asistente
deja de ser "un programa" para ser "un servicio de casa" al que cualquier cosa
puede hablar.

Dos decisiones de diseño detrás:

- **Un token** protege el acceso. Sin él configurado (uso solo local), no molesta;
  con él, puedes abrir el asistente a tu red sin riesgo.
- **Una fachada de solo lectura** (`DataView`) traduce los almacenes internos a
  JSON. Así la API no obliga a engordar el servicio del asistente, y el formato que
  ven los clientes queda desacoplado del modelo interno: se puede cambiar por dentro
  sin romper a nadie fuera.

## Cómo se gestionan los fallos (robustez)

Un asistente que se usa a diario tiene que fallar bien. Dos medidas:

- **Comprobación al arrancar.** Antes de empezar, el asistente le pregunta a Ollama
  si está en marcha y si el modelo configurado está descargado. Si algo falta, no
  arranca con un error críptico: te dice exactamente qué hacer (`ollama serve` o
  `ollama pull <modelo>`).
- **Un reintento.** Si una petición al modelo falla por un problema puntual de
  conexión, se reintenta una vez (con una pequeña espera) antes de rendirse. Nada
  de librerías de resiliencia: un reintento simple cubre los fallos transitorios.

Además, los **mensajes para ti** (errores comprensibles) van por un canal distinto
de los **logs técnicos**: los primeros se imprimen en la conversación; los segundos
salen por el canal de logging. Así un fallo del modelo te da una línea clara sin
enterrarte en trazas.

## Por qué el modelo es "intercambiable"

El resto del código nunca habla directamente con Ollama. Habla con un **contrato**
abstracto (`LLMProvider`) que dice solo: "dame estos mensajes y devuélveme una
respuesta". Hoy ese contrato lo cumple `OllamaProvider`, pero mañana podría
cumplirlo uno para OpenAI, llama.cpp u otro, **sin cambiar nada** del dominio.

Es la razón de que el asistente pueda evolucionar durante años: las piezas que
cambian (el modelo, la interfaz, el almacenamiento) están aisladas detrás de
contratos, y el corazón del asistente no depende de ninguna de ellas en concreto.

---

## Resumen en una frase

El asistente es un bucle que, en cada turno, arma un paquete de contexto
(personalidad + memoria reciente + tu mensaje) y se lo entrega a un modelo sin
estado a través de una capa intercambiable; todo lo demás es mantener ese paquete
ordenado y acotado.
