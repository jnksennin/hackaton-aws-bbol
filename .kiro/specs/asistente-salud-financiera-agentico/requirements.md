# Requirements Document

## Pitch de Una Línea

**"Convierte datos transaccionales en inteligencia financiera proactiva con un agente conversacional que calcula tu Índice de Salud Financiera en tiempo real"**

---

## Introduction

### Problema y Oportunidad

**Problema cuantificado:**
- 70%+ de clientes del Banco Bolivariano consultan su saldo únicamente en crisis de liquidez
- 63% desconoce sus gastos mensuales en suscripciones y gastos hormiga
- Baja tasa de ahorro activo y alta incidencia de alertas de mora temprana

**Oportunidad:**
Transformar datos transaccionales pasivos en inteligencia financiera proactiva mediante un agente conversacional que:
- Calcula un Índice de Salud Financiera (ISF) personalizado (score 0-100)
- Identifica patrones de gasto y oportunidades de ahorro
- Previene crisis de liquidez mediante alertas tempranas
- Se integra nativamente en canales digitales 24Móvil y 24Online

**Impacto esperado:**
- +15% en tasa de ahorro activo
- -20% en alertas de mora temprana
- Mayor NPS en canales digitales

### Hackathon Personas

**Persona 1: María - La Profesional Ocupada**
- **Perfil:** 32 años, ejecutiva de marketing, ingresos $1,800/mes
- **Job-to-be-Done:** "Cuando reviso mi cuenta bancaria, quiero entender mi salud financiera en segundos, para tomar decisiones rápidas sin analizar transacciones manualmente"
- **Pain Points:** No tiene tiempo para revisar extractos, descubre suscripciones olvidadas al final del mes, no sabe si puede permitirse gastos extras

**Persona 2: Carlos - El Emprendedor Digital**
- **Perfil:** 28 años, freelancer tech, ingresos variables $800-$2,500/mes
- **Job-to-be-Done:** "Cuando mis ingresos fluctúan, quiero recibir alertas proactivas sobre mi capacidad de gasto, para evitar sobregiros en meses bajos"
- **Pain Points:** Ingresos irregulares dificultan planificación, no identifica gastos hormiga, ha tenido sobregiros por falta de visibilidad

---

## Glossary

- **Agente_Conversacional**: Sistema de IA basado en Amazon Bedrock Agents que interpreta lenguaje natural y ejecuta acciones financieras
- **ISF (Índice_de_Salud_Financiera)**: Score numérico de 0-100 que evalúa la salud financiera del cliente basado en ingresos, gastos, ahorros y deudas
- **Gasto_Hormiga**: Transacciones pequeñas y frecuentes (< $10) que acumuladas representan un porcentaje significativo del gasto mensual
- **Guardrails**: Mecanismos de Amazon Bedrock Guardrails que filtran contenido inapropiado y validan respuestas del agente
- **Knowledge_Base**: Base de conocimiento vectorial en Amazon Bedrock que contiene información de productos financieros y educación financiera
- **Streaming**: Transmisión progresiva de respuestas del agente para reducir latencia percibida
- **Lambda_Function**: Función serverless de AWS Lambda que ejecuta lógica de negocio (cálculo ISF, análisis transaccional)
- **DynamoDB_Table**: Base de datos NoSQL que almacena datos de clientes, transacciones simuladas y conversaciones
- **S3_Bucket**: Almacenamiento de objetos para documentos de Knowledge Base y logs de auditoría

---

## Requirements

### Requirement 1: Cálculo del Índice de Salud Financiera (ISF)

🏆 **Demo Star** | 🔧 **Tech Showcase**

**User Story:** Como María, quiero que el agente calcule mi Índice de Salud Financiera en tiempo real, para entender mi situación financiera en un solo número sin analizar transacciones manualmente.

#### Acceptance Criteria

1. WHEN el Cliente solicita su ISF mediante lenguaje natural, THE Agente_Conversacional SHALL invocar la Lambda_Function de cálculo de ISF
2. THE Lambda_Function SHALL calcular el ISF basado en cuatro componentes: ratio ingresos/gastos (30%), nivel de ahorro (25%), carga de deuda (25%), y estabilidad de ingresos (20%)
3. THE Lambda_Function SHALL retornar un score numérico entre 0 y 100 con precisión de dos decimales
4. THE Agente_Conversacional SHALL presentar el ISF con interpretación textual: "Excelente" (80-100), "Bueno" (60-79), "Regular" (40-59), "Crítico" (0-39)
5. THE Agente_Conversacional SHALL mostrar el ISF con indicador visual de color: verde para scores ≥60, rojo para scores <60
6. THE Agente_Conversacional SHALL completar el cálculo y presentación del ISF en menos de 3 segundos (P95)

### Requirement 2: Identificación de Gastos Hormiga

🏆 **Demo Star** | 🔧 **Tech Showcase**

**User Story:** Como Carlos, quiero que el agente identifique mis gastos hormiga del último mes, para descubrir oportunidades de ahorro que no veo en mi día a día.

#### Acceptance Criteria

1. WHEN el Cliente pregunta por gastos hormiga, THE Agente_Conversacional SHALL consultar transacciones del último mes en DynamoDB_Table
2. THE Lambda_Function SHALL filtrar transacciones menores a $10 USD y agruparlas por categoría (cafeterías, snacks, transporte, apps)
3. THE Lambda_Function SHALL calcular el total acumulado de Gasto_Hormiga y su porcentaje respecto al ingreso mensual
4. THE Agente_Conversacional SHALL presentar las top 3 categorías de Gasto_Hormiga con monto total y frecuencia
5. IF el Gasto_Hormiga supera el 15% del ingreso mensual, THEN THE Agente_Conversacional SHALL generar una alerta proactiva con recomendaciones de ahorro
6. THE Agente_Conversacional SHALL visualizar los gastos hormiga en un formato de lista agrupada por categoría

### Requirement 3: Detección de Suscripciones Recurrentes

🏆 **Demo Star**

**User Story:** Como María, quiero que el agente detecte todas mis suscripciones activas, para cancelar las que no uso y evitar cargos innecesarios.

#### Acceptance Criteria

1. WHEN el Cliente solicita revisar suscripciones, THE Agente_Conversacional SHALL analizar transacciones recurrentes en los últimos 3 meses
2. THE Lambda_Function SHALL identificar patrones de cobro mensual con mismo monto y comercio (tolerancia ±$2 USD)
3. THE Lambda_Function SHALL clasificar suscripciones por categoría: streaming, software, gimnasio, servicios digitales
4. THE Agente_Conversacional SHALL listar cada suscripción con: nombre del comercio, monto mensual, fecha de último cobro, y total anual proyectado
5. THE Agente_Conversacional SHALL calcular el costo total mensual y anual de todas las suscripciones detectadas
6. THE Agente_Conversacional SHALL presentar las suscripciones en tarjetas visuales con montos destacados

### Requirement 4: Alertas Proactivas de Liquidez

🏆 **Demo Star** | 🔧 **Tech Showcase**

**User Story:** Como Carlos, quiero recibir alertas cuando mi saldo proyectado sea insuficiente para cubrir gastos fijos, para evitar sobregiros antes de que ocurran.

#### Acceptance Criteria

1. WHEN el saldo actual del Cliente es menor al 120% de sus gastos fijos mensuales promedio, THE Agente_Conversacional SHALL generar una alerta de liquidez
2. THE Lambda_Function SHALL proyectar el saldo a 7 días basado en gastos promedio diarios de los últimos 30 días
3. IF el saldo proyectado es negativo, THEN THE Agente_Conversacional SHALL recomendar acciones específicas: reducir gastos variables, diferir compras no esenciales, o considerar transferencia desde ahorros
4. THE Agente_Conversacional SHALL presentar la alerta con badge visual de tipo advertencia
5. THE Agente_Conversacional SHALL incluir en la alerta: saldo actual, gastos fijos pendientes, fecha estimada de déficit, y monto recomendado a reservar
6. WHEN el Cliente pregunta "¿puedo comprar X?", THE Agente_Conversacional SHALL evaluar si el gasto compromete su liquidez y responder con recomendación clara

### Requirement 5: Integración con Knowledge Base de Educación Financiera

🔧 **Tech Showcase** | 🛡️ **Trust & Safety**

**User Story:** Como María, quiero que el agente responda preguntas sobre productos financieros del banco, para tomar decisiones informadas sin salir de la conversación.

#### Acceptance Criteria

1. WHEN el Cliente pregunta sobre productos financieros (cuentas de ahorro, tarjetas de crédito, inversiones), THE Agente_Conversacional SHALL consultar la Knowledge_Base en Amazon Bedrock
2. THE Knowledge_Base SHALL contener documentación oficial de productos del Banco Bolivariano en formato vectorizado
3. THE Agente_Conversacional SHALL citar la fuente de información con badge visual de tipo informativo
4. THE Agente_Conversacional SHALL responder en español ecuatoriano con terminología local (ej: "cuenta de ahorros" no "savings account")
5. IF la Knowledge_Base no contiene información suficiente, THEN THE Agente_Conversacional SHALL indicar claramente que no tiene esa información y sugerir contactar a un asesor
6. THE Agente_Conversacional SHALL incluir enlaces a documentación completa cuando esté disponible en S3_Bucket

### Requirement 6: Guardrails de Seguridad y Cumplimiento

🛡️ **Trust & Safety** | 🏆 **Demo Star**

**User Story:** Como Banco Bolivariano, queremos que el agente rechace consultas inapropiadas y proteja datos sensibles, para cumplir con regulaciones financieras y proteger a nuestros clientes.

#### Acceptance Criteria

1. THE Guardrails SHALL filtrar consultas que soliciten información de otros clientes, datos de tarjetas completos, o PINs
2. WHEN el Cliente intenta una consulta prohibida, THE Agente_Conversacional SHALL responder con mensaje de rechazo cortés y explicación de la política de seguridad
3. THE Guardrails SHALL detectar y bloquear intentos de prompt injection o jailbreak
4. THE Agente_Conversacional SHALL mostrar un badge "Protegido por Guardrails" de tipo advertencia cuando rechace una consulta
5. THE Guardrails SHALL validar que las respuestas del agente no contengan información personal identificable (PII) de otros clientes
6. THE Agente_Conversacional SHALL registrar todos los rechazos de Guardrails en DynamoDB_Table para auditoría

### Requirement 7: Experiencia Conversacional con Streaming

🔧 **Tech Showcase**

**User Story:** Como Carlos, quiero que el agente responda de forma fluida y natural, para sentir que hablo con un asesor financiero real y no con un bot.

#### Acceptance Criteria

1. THE Agente_Conversacional SHALL transmitir respuestas mediante streaming para mostrar progreso en tiempo real
2. THE Agente_Conversacional SHALL completar el 95% de las respuestas en menos de 3 segundos desde el envío del mensaje
3. THE Agente_Conversacional SHALL mantener contexto de la conversación durante toda la sesión del Cliente
4. THE Agente_Conversacional SHALL usar lenguaje natural en español ecuatoriano con tono amigable y profesional
5. THE Agente_Conversacional SHALL aplicar estilos visuales consistentes con la identidad del Banco Bolivariano
6. WHEN el Agente_Conversacional está procesando una consulta compleja, THE interfaz SHALL mostrar un indicador de "pensando" con animación visual

### Requirement 8: Persistencia de Conversaciones y Datos

🔧 **Tech Showcase**

**User Story:** Como María, quiero que el agente recuerde nuestras conversaciones anteriores, para no repetir contexto cada vez que inicio una sesión.

#### Acceptance Criteria

1. THE Agente_Conversacional SHALL almacenar cada mensaje y respuesta en DynamoDB_Table con timestamp y session_id
2. WHEN el Cliente inicia una nueva sesión, THE Agente_Conversacional SHALL recuperar el contexto de las últimas 5 conversaciones
3. THE DynamoDB_Table SHALL almacenar datos de transacciones simuladas con estructura: transaction_id, client_id, amount, category, merchant, date
4. THE Lambda_Function SHALL generar datos transaccionales realistas para demo: 50-80 transacciones por mes con distribución representativa de categorías
5. THE S3_Bucket SHALL almacenar logs de auditoría de todas las interacciones del agente con retención de 90 días
6. THE Agente_Conversacional SHALL permitir al Cliente solicitar "olvidar" conversaciones anteriores para iniciar contexto limpio

---

## Requisitos No Funcionales

### Performance

1. THE Agente_Conversacional SHALL responder al 95% de las consultas en menos de 3 segundos (P95 latency)
2. THE Lambda_Function SHALL ejecutar cálculos de ISF en menos de 500ms
3. THE Agente_Conversacional SHALL soportar streaming de respuestas con latencia inicial menor a 800ms

### Idioma y Localización

1. THE Agente_Conversacional SHALL comunicarse exclusivamente en español ecuatoriano
2. THE Agente_Conversacional SHALL usar formato de moneda ecuatoriano: $1.234,56 USD
3. THE Agente_Conversacional SHALL usar terminología financiera local (ej: "cuenta de ahorros", "tarjeta de débito")

### Seguridad y Cumplimiento

1. THE Guardrails SHALL estar activos en todas las interacciones del Agente_Conversacional
2. THE Agente_Conversacional SHALL registrar todas las interacciones en logs de auditoría en S3_Bucket
3. THE Lambda_Function SHALL validar permisos del Cliente antes de acceder a datos transaccionales en DynamoDB_Table

### Datos de Demostración

1. THE DynamoDB_Table SHALL contener datos simulados de al menos 3 clientes con perfiles financieros diversos
2. THE datos simulados SHALL incluir: transacciones realistas, suscripciones activas, gastos hormiga identificables, y variación de ISF
3. THE Knowledge_Base SHALL contener al menos 5 documentos de productos financieros del Banco Bolivariano

### Responsividad

1. THE interfaz SHALL ser demostrable en dispositivo móvil (responsive design)

### Demostrabilidad (Hackathon)

1. THE demo completo SHALL ejecutarse en 5 minutos o menos
2. THE demo SHALL mostrar al menos 4 de las 6 historias de usuario marcadas como 🏆 Demo Star
3. THE demo SHALL evidenciar visualmente: streaming en acción, Guardrails rechazando consulta, y badge de Knowledge Base
4. THE stack técnico SHALL ser desplegable en una cuenta AWS en menos de 30 minutos usando Infrastructure as Code

---

## Notas de Implementación para Hackathon

### Priorización de Features

**Must Have (Demo Star):**
- Cálculo de ISF con visualización
- Identificación de gastos hormiga
- Detección de suscripciones
- Guardrails activos con rechazo visible
- Streaming de respuestas

**Should Have:**
- Alertas proactivas de liquidez
- Knowledge Base con productos financieros
- Persistencia de conversaciones

**Nice to Have:**
- Análisis de tendencias de gasto
- Comparación con promedios de usuarios similares
- Exportación de reportes

### Stack Técnico Mínimo

- **Frontend:** React
- **Backend:** Amazon Bedrock Agents + Lambda (Python/Node.js)
- **Storage:** DynamoDB (transacciones, conversaciones) + S3 (Knowledge Base, logs)
- **Seguridad:** Bedrock Guardrails (configuración mínima: PII filtering, topic blocking)
- **IaC:** AWS CDK  para despliegue rápido

### Datos Simulados Realistas

Generar 3 perfiles de cliente con:
- Cliente A: ISF 75 (saludable), gastos controlados, ahorro activo
- Cliente B: ISF 45 (regular), gastos hormiga 18%, suscripciones olvidadas
- Cliente C: ISF 28 (crítico), ingresos irregulares, riesgo de sobregiro

Cada perfil debe tener 60-80 transacciones de los últimos 2 meses con distribución realista.
