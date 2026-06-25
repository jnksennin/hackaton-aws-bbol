# Implementation Plan: Asistente de Salud Financiera Agéntico

## Overview

Este plan de implementación está diseñado específicamente para un **hackathon de 24-48 horas** con un equipo de 4 personas (Backend Lead, Frontend Lead, AI/ML Lead, DevOps Lead). El enfoque prioriza funcionalidades demostrables, decisiones rápidas y alto impacto visual usando el Design System de Banco Bolivariano.

**Arquitectura:** Amazon Bedrock Agents como orquestador central, 4 Lambda Functions (Python 3.12) para Action Groups, DynamoDB para datos transaccionales, S3 para Knowledge Base, y frontend React/Next.js con Design System BB completo.

**Objetivo del hackathon:** Sistema conversacional funcional que calcule ISF, detecte gastos hormiga y suscripciones, demuestre Guardrails en acción, y presente fidelidad 100% al Design System Bolivariano.

---

## 3.1 Épicas Priorizadas (MoSCoW para Hackathon)

| ID | Épica | Descripción | Prioridad | Owner Sugerido | Estimación |
|----|-------|-------------|-----------|----------------|------------|
| **E1** | **Setup Base** | Configurar Bedrock Agent + Knowledge Base + Guardrails | **Must Have** | AI/ML Lead | 4-6h |
| **E2** | **Action Groups** | Implementar 4 Lambda Functions (ISF, Analyzer, Alerter, SessionMgr) | **Must Have** | Backend Lead | 6-8h |
| **E3** | **Frontend Demo** | Chat UI con streaming y componentes financieros | **Must Have** | Frontend Lead | 8-10h |
| **E4** | **Tokens CSS** | Generar bb-tokens.css + validación DS en todos los componentes | **Must Have** | Frontend Lead | 2-3h |
| **E5** | **Evaluación LLM** | Scripts FMEval + métricas de calidad (Faithfulness, QA Accuracy) | **Should Have** | AI/ML Lead | 3-4h |
| **E6** | **Observabilidad** | CloudWatch dashboard + logging estructurado | **Should Have** | DevOps Lead | 2-3h |
| **E7** | **CI/CD Pipeline** | IaC CDK + DS lint check | **Should Have** | DevOps Lead | 3-4h |
| **E8** | **Demo Flows** | Scripts de demo, datos simulados y review de fidelidad DS | **Must Have** | Todo el equipo | 2-3h |
| **E9** | **Presentación** | Slide deck + arquitectura + métricas | **Must Have** | Todo el equipo | 2-3h |

**Notas de priorización:**
- **Must Have:** Funcionalidades core para demo funcional (E1, E2, E3, E4, E8, E9)
- **Should Have:** Mejoran credibilidad técnica pero no bloquean demo (E5, E6, E7)
- **Nice to Have:** Fuera de alcance para hackathon (fine-tuning, A/B testing, integración core bancario)

---

## 3.2 Breakdown de Tareas por Épica

### ÉPICA E1: Setup Base (Bedrock Agent + Knowledge Base + Guardrails)


- [ ] 1. Configurar Amazon Bedrock Agent con Claude 3.5 Sonnet
  - Crear Agent con nombre `financial-health-assistant-agent`
  - Configurar system prompt con personalidad de asesor financiero ecuatoriano
  - Definir 4 Action Groups con OpenAPI schemas (ISF, Analyzer, Alerter, SessionMgr)
  - Configurar timeout de 30 segundos y streaming habilitado
  - _Requirements: 1.1, 7.1, 7.3, 7.4_
  - _Estimación: 2h_

- [ ] 2. Configurar Knowledge Base con productos financieros
  - Crear S3 bucket `financial-assistant-kb-docs-{account-id}`
  - Subir 5 documentos PDF de productos Banco Bolivariano (cuentas, tarjetas, inversiones, créditos, seguros)
  - Configurar Knowledge Base con Amazon Titan Embeddings G1
  - Configurar OpenSearch Serverless como vector store (chunking: 300 tokens, overlap 20%)
  - Sincronizar Knowledge Base y verificar indexación
  - _Requirements: 5.1, 5.2_
  - _Estimación: 2h_

- [ ] 3. Configurar Guardrails de seguridad
  - Crear Guardrail `financial-assistant-guardrails`
  - Configurar PII filters: BLOCK para CREDIT_CARD y PIN, ANONYMIZE para EMAIL/PHONE/NAME
  - Configurar Topic filters: bloquear consultas de otros clientes, datos completos de tarjetas, PINs
  - Configurar Content filters: HATE, INSULTS, SEXUAL, VIOLENCE, MISCONDUCT, PROMPT_ATTACK
  - Definir rejection response personalizado con branding BB
  - Asociar Guardrail al Bedrock Agent
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  - _Estimación: 1.5h_

- [ ] 4. Checkpoint - Verificar setup base funcional
  - Probar invocación del Agent con consulta simple
  - Verificar que Guardrails bloquea consulta prohibida (ej: "¿Cuál es mi PIN?")
  - Verificar que Knowledge Base responde pregunta sobre productos
  - Ensure all tests pass, ask the user if questions arise.
  - _Estimación: 0.5h_

---

### ÉPICA E2: Action Groups (Lambda Functions)


- [ ] 5. Crear DynamoDB tables para datos transaccionales
  - [ ] 5.1 Crear tabla `financial-assistant-transactions`
    - Partition Key: `client_id`, Sort Key: `transaction_id`
    - Atributos: `amount`, `category`, `merchant`, `date`, `type`
    - GSI: `date-index` (PK: client_id, SK: date)
    - Configurar On-Demand billing
    - _Requirements: 8.3_
    - _Estimación: 0.5h_
  
  - [ ] 5.2 Crear tabla `financial-assistant-sessions`
    - Partition Key: `session_id`, Sort Key: `timestamp`
    - Atributos: `client_id`, `message`, `response`, `action_groups_invoked`, `guardrail_triggered`
    - Configurar TTL attribute (90 días)
    - _Requirements: 8.1, 8.5_
    - _Estimación: 0.5h_
  
  - [ ] 5.3 Crear tabla `financial-assistant-clients` con datos demo
    - Partition Key: `client_id`
    - Insertar 3 clientes demo: María (ISF 75), Carlos (ISF 45), Ana (ISF 28)
    - Cada cliente con perfil completo: ingresos, gastos fijos, ahorros, deudas
    - _Requirements: 8.4_
    - _Estimación: 0.5h_

- [ ] 6. Generar datos transaccionales simulados realistas
  - Crear script Python para generar 60-80 transacciones/mes por cliente
  - Distribuir transacciones en categorías: salary, groceries, restaurants, coffee_snacks, transport, subscriptions, utilities
  - Incluir gastos hormiga identificables (<$10, frecuentes)
  - Incluir suscripciones recurrentes (Netflix, Spotify, gimnasio)
  - Insertar datos en DynamoDB tabla `transactions`
  - _Requirements: 8.4_
  - _Estimación: 1.5h_

- [ ] 7. Implementar Lambda L1: ISF Calculator
  - [ ] 7.1 Crear función Lambda en Python 3.12
    - Implementar cálculo de ISF con 4 componentes: ratio ingresos/gastos (30%), nivel de ahorro (25%), carga de deuda (25%), estabilidad de ingresos (20%)
    - Fórmulas: ratio = min(100, (ingresos/gastos)*50), ahorro = (ahorro_mensual/ingresos)*100, deuda = max(0, 100-(deuda_total/ingresos_anuales)*100), estabilidad = 100-(std_dev/mean)*100
    - Retornar JSON con `isf_score`, `interpretation`, `components`
    - _Requirements: 1.1, 1.2, 1.3_
    - _Estimación: 2h_
  
  - [ ]* 7.2 Write unit tests for ISF Calculator
    - Test casos extremos: ingresos=0, gastos=0, deuda negativa
    - Test interpretación correcta: 80-100="Excelente", 60-79="Bueno", 40-59="Regular", 0-39="Crítico"
    - Test precisión de dos decimales
    - _Requirements: 1.3_
    - _Estimación: 1h_


- [ ] 8. Implementar Lambda L2: Transaction Analyzer
  - [ ] 8.1 Implementar análisis de gastos hormiga
    - Filtrar transacciones <$10 USD del último mes
    - Agrupar por categoría y calcular total por categoría
    - Ordenar por monto total y retornar top 3
    - Calcular porcentaje respecto a ingreso mensual
    - Generar alerta si >15% del ingreso
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
    - _Estimación: 1.5h_
  
  - [ ] 8.2 Implementar detección de suscripciones
    - Analizar transacciones de últimos 3 meses
    - Detectar patrones: mismo merchant, monto ±$2, frecuencia mensual
    - Clasificar por categoría: streaming, software, gimnasio, servicios digitales
    - Calcular total mensual y proyección anual
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
    - _Estimación: 1.5h_
  
  - [ ]* 8.3 Write unit tests for Transaction Analyzer
    - Test filtrado correcto de gastos <$10
    - Test agrupamiento por categoría
    - Test detección de patrones recurrentes con tolerancia ±$2
    - _Requirements: 2.2, 3.2_
    - _Estimación: 1h_

- [ ] 9. Implementar Lambda L3: Liquidity Alerter
  - [ ] 9.1 Implementar proyección de liquidez
    - Calcular gastos promedio diarios (últimos 30 días)
    - Proyectar saldo a N días: current_balance - (avg_daily_spend * N)
    - Generar alerta si current_balance < 1.2 * monthly_fixed_expenses
    - Determinar alert_level: none, warning, critical
    - _Requirements: 4.1, 4.2_
    - _Estimación: 1.5h_
  
  - [ ] 9.2 Implementar evaluación de compras
    - Evaluar si purchase_amount compromete liquidez
    - Generar recomendación específica: reducir gastos variables, diferir compras, transferir desde ahorros
    - _Requirements: 4.3, 4.6_
    - _Estimación: 1h_
  
  - [ ]* 9.3 Write unit tests for Liquidity Alerter
    - Test proyección de saldo con diferentes escenarios
    - Test generación de alertas por threshold
    - Test recomendaciones específicas para saldo negativo
    - _Requirements: 4.2, 4.3_
    - _Estimación: 1h_

- [ ] 10. Implementar Lambda L4: Session Manager
  - Implementar operaciones CRUD para conversaciones
  - Operación save: guardar turno de conversación en DynamoDB
  - Operación retrieve: recuperar últimas 5 conversaciones del cliente
  - Operación reset: limpiar contexto de conversación
  - _Requirements: 8.1, 8.2_
  - _Estimación: 1.5h_

- [ ] 11. Conectar Lambda Functions al Bedrock Agent
  - Crear permisos IAM para que Agent invoque las 4 Lambdas
  - Asociar cada Lambda a su Action Group correspondiente
  - Configurar OpenAPI schemas con parámetros correctos
  - _Requirements: 1.1_
  - _Estimación: 1h_

- [ ] 12. Checkpoint - Verificar Action Groups funcionales
  - Probar cálculo de ISF con cliente demo
  - Probar detección de gastos hormiga y suscripciones
  - Probar proyección de liquidez
  - Verificar que Session Manager persiste conversaciones
  - Ensure all tests pass, ask the user if questions arise.
  - _Estimación: 1h_

---

### ÉPICA E3: Frontend Demo (Chat UI con Design System BB)


**Bloque Frontend / Design System (E3 + E4) - Organizado por Horas de Hackathon**

#### HORA 0–2: Setup de Tokens CSS

- [ ] 13. Generar archivo bb-tokens.css con Design System Bolivariano
  - Crear archivo `styles/bb-tokens.css` con todos los tokens CSS
  - Tokens de color: `--bb-primary-500: #008292`, `--bb-bg-body: #edeef3`, `--bb-bg-primary: #008292`, `--bb-bg-surface: #ffffff`
  - Tokens de estado: `--bb-state-warning-bg`, `--bb-state-warning-border`, `--bb-state-info-bg`, `--bb-state-info-border`
  - Tokens de indicadores: `--bb-green-500`, `--bb-red-600`
  - Tokens de sombra: `--bb-shadow-card: 0 2px 8px rgba(0,0,0,0.1)`
  - Configurar Google Fonts para Lexend (weights: 300, 400, 500, 600, 700)
  - Importar bb-tokens.css globalmente en `_app.tsx` o `layout.tsx`
  - _Requirements: 7.5, NFR Fidelidad Visual 2_
  - _Estimación: 1h_

- [ ] 14. Configurar Next.js project con TypeScript
  - Inicializar proyecto Next.js 14+ con App Router
  - Configurar TypeScript con strict mode
  - Instalar dependencias: `aws-sdk`, `@aws-sdk/client-bedrock-agent-runtime`
  - Configurar variables de entorno para AWS credentials
  - _Requirements: 7.5_
  - _Estimación: 0.5h_

#### HORA 2–4: Componentes Base de Chat

- [ ] 15. Crear componente BBChatHeader
  - Header con logo/nombre del agente
  - Fondo: `var(--bb-bg-primary)` (#008292)
  - Tipografía: Lexend, color blanco
  - Incluir badge "Protegido por Guardrails" con icono 🛡️
  - _Requirements: 7.5, NFR Fidelidad Visual 2_
  - _Estimación: 0.5h_

- [ ] 16. Crear componentes de burbujas de chat
  - [ ] 16.1 Crear BBUserBubble
    - Burbuja alineada a la derecha
    - Fondo: `var(--bb-primary-500)` (#008292)
    - Texto en blanco, tipografía Lexend
    - Border radius consistente con DS
    - _Requirements: 7.5_
    - _Estimación: 0.5h_
  
  - [ ] 16.2 Crear BBAgentBubble
    - Burbuja alineada a la izquierda
    - Fondo: `var(--bb-bg-surface)` (#ffffff)
    - Texto en color oscuro, tipografía Lexend
    - Sombra: `var(--bb-shadow-card)`
    - _Requirements: 7.5_
    - _Estimación: 0.5h_

#### HORA 4–8: Componentes Financieros

- [ ] 17. Crear componente BBFinancialCard (ISF)
  - [ ] 17.1 Implementar estructura de tarjeta
    - Tarjeta con fondo `var(--bb-bg-body)` (#edeef3)
    - Sombra: `var(--bb-shadow-card)`
    - Tipografía: Lexend
    - _Requirements: 1.5, 7.5_
    - _Estimación: 0.5h_
  
  - [ ] 17.2 Implementar visualización de ISF score
    - Score numérico grande y destacado
    - Color dinámico: `var(--bb-green-500)` si score ≥60, `var(--bb-red-600)` si <60
    - Interpretación textual: Excelente/Bueno/Regular/Crítico
    - _Requirements: 1.4, 1.5_
    - _Estimación: 0.5h_
  
  - [ ] 17.3 Implementar breakdown de componentes ISF
    - 4 barras de progreso para: ratio ingresos/gastos, nivel de ahorro, carga de deuda, estabilidad de ingresos
    - Cada barra con porcentaje y label
    - Colores consistentes con DS
    - _Requirements: 1.2_
    - _Estimación: 1h_


- [ ] 18. Crear componente BBHealthScoreGauge
  - Gauge circular o semicircular para ISF
  - Gradiente de color: verde (80-100) → amarillo (40-79) → rojo (0-39)
  - Animación de transición suave
  - Tipografía: Lexend para el número central
  - _Requirements: 1.5, 7.5_
  - _Estimación: 1.5h_

- [ ] 19. Crear componente BBGastosHormigaList
  - Lista de top 3 categorías de gastos hormiga
  - Cada item con: nombre categoría, monto total, frecuencia
  - Monto destacado en `var(--bb-primary-500)`
  - Si alerta activa (>15% ingreso): badge warning con `var(--bb-state-warning-bg)` y `var(--bb-state-warning-border)`
  - _Requirements: 2.4, 2.5, 2.6_
  - _Estimación: 1h_

- [ ] 20. Crear componente BBSubscriptionCard
  - Tarjeta individual para cada suscripción
  - Mostrar: merchant, monto mensual, categoría, última fecha de cobro, proyección anual
  - Fondo: `var(--bb-bg-body)`
  - Monto mensual destacado en `var(--bb-primary-500)`
  - Tipografía: Lexend
  - _Requirements: 3.4, 3.6_
  - _Estimación: 1h_

#### HORA 8–10: Badges y Chips Interactivos

- [ ] 21. Crear componente BBGuardrailBadge
  - Badge visible cuando Guardrails bloquea consulta
  - Fondo: `var(--bb-state-warning-bg)`
  - Border: `var(--bb-state-warning-border)`
  - Icono: 🛡️
  - Texto: "Protegido por Guardrails de Seguridad"
  - _Requirements: 6.4, 7.5_
  - _Estimación: 0.5h_

- [ ] 22. Crear componente BBKnowledgeBadge
  - Badge para citar fuentes de Knowledge Base
  - Fondo: `var(--bb-state-info-bg)`
  - Border: `var(--bb-state-info-border)`
  - Incluir título del documento y enlace (si disponible)
  - _Requirements: 5.3, 5.6_
  - _Estimación: 0.5h_

- [ ] 23. Crear componente BBQuickActionChips
  - Chips de acciones rápidas: "Calcular mi ISF", "Ver gastos hormiga", "Revisar suscripciones", "Proyectar liquidez"
  - Estilo: outline con `var(--bb-primary-500)` como border
  - Hover state con fondo `var(--bb-primary-500)` y texto blanco
  - _Requirements: 7.4_
  - _Estimación: 0.5h_

- [ ] 24. Crear componente BBChatInput
  - Input de texto con botón de envío
  - Border: `var(--bb-primary-500)` en focus
  - Botón de envío con fondo `var(--bb-primary-500)`
  - Placeholder: "Escribe tu consulta financiera..."
  - _Requirements: 7.4_
  - _Estimación: 0.5h_

#### HORA 10–12: Interactividad y Streaming

- [ ] 25. Implementar streaming de respuestas del agente
  - [ ] 25.1 Configurar WebSocket o Server-Sent Events para streaming
    - Conectar con API Gateway WebSocket endpoint
    - Manejar eventos: chunk, complete, error
    - _Requirements: 7.1, 7.2_
    - _Estimación: 1h_
  
  - [ ] 25.2 Implementar animación de "pensando"
    - Indicador visual mientras Agent procesa consulta
    - Usar animación del Design System BB (dots pulsantes)
    - Mostrar texto: "Analizando tus finanzas..."
    - _Requirements: 7.6_
    - _Estimación: 0.5h_
  
  - [ ] 25.3 Implementar cursor parpadeante durante streaming
    - Cursor animado al final del texto mientras se recibe streaming
    - Desaparecer cuando streaming completa
    - _Requirements: 7.1_
    - _Estimación: 0.5h_


#### HORA 12–16: QA Visual y Responsividad

- [ ] 26. Implementar lógica de integración con Bedrock Agent
  - Crear API route `/api/agent/invoke` en Next.js
  - Integrar con `@aws-sdk/client-bedrock-agent-runtime`
  - Manejar respuestas: texto, action_groups_invoked, sources, guardrail_triggered
  - Parsear respuestas y renderizar componentes apropiados (ISFCard, GastosHormigaList, etc.)
  - _Requirements: 1.1, 7.1_
  - _Estimación: 2h_

- [ ] 27. Revisar fidelidad al Design System en todos los componentes
  - **Checkpoint obligatorio:** Revisar UI contra JSON de tokens
  - Verificar que TODOS los colores usan `var(--bb-...)` — cero valores hardcodeados
  - Verificar que tipografía Lexend carga correctamente (DevTools → Fonts)
  - Verificar espaciado consistente entre componentes
  - Verificar sombras usando `var(--bb-shadow-card)`
  - _Requirements: NFR Fidelidad Visual 1, 2, 3_
  - _Estimación: 1h_

- [ ] 28. Implementar responsividad para móvil
  - Probar en viewport 328px (móvil pequeño)
  - Ajustar layout de burbujas de chat para móvil
  - Ajustar tarjetas financieras para stack vertical en móvil
  - Verificar que Quick Action Chips se ajustan en móvil
  - _Requirements: NFR Fidelidad Visual 3_
  - _Estimación: 1h_

- [ ] 29. Checkpoint - Verificar frontend funcional end-to-end
  - Probar flujo completo: enviar mensaje → streaming → renderizar componentes financieros
  - Verificar que Guardrails badge aparece cuando se bloquea consulta
  - Verificar que Knowledge Base badge aparece con fuentes
  - Verificar fidelidad 100% al Design System
  - Ensure all tests pass, ask the user if questions arise.
  - _Estimación: 1h_

---

### ÉPICA E4: Tokens CSS (Validación y Lint)

- [ ] 30. Crear script de validación de Design System
  - Script que escanea todos los archivos `.tsx` y `.css`
  - Detectar valores hardcodeados de colores (hex, rgb) que deberían usar tokens
  - Detectar uso de fuentes que no sean Lexend
  - Generar reporte de violaciones
  - _Requirements: NFR Fidelidad Visual 2_
  - _Estimación: 1.5h_

- [ ] 31. Integrar DS lint check en pre-commit hook
  - Configurar Husky o similar para ejecutar DS validation script
  - Bloquear commit si hay violaciones de Design System
  - _Requirements: NFR Fidelidad Visual 2_
  - _Estimación: 0.5h_

---

### ÉPICA E5: Evaluación LLM (FMEval)

- [ ] 32. Crear dataset de evaluación para el agente
  - Crear archivo JSON con 20-30 pares pregunta-respuesta esperada
  - Incluir casos: cálculo ISF, gastos hormiga, suscripciones, liquidez, Knowledge Base, Guardrails
  - Formato compatible con FMEval
  - _Requirements: NFR Demostrabilidad 3_
  - _Estimación: 1h_

- [ ] 33. Implementar script de evaluación con FMEval
  - [ ] 33.1 Configurar FMEval con Bedrock Model Runner
    - Instalar `fmeval` library
    - Configurar BedrockModelRunner con Claude 3.5 Sonnet
    - _Requirements: NFR Demostrabilidad 3_
    - _Estimación: 0.5h_
  
  - [ ] 33.2 Ejecutar evaluaciones de Faithfulness y QA Accuracy
    - Ejecutar Faithfulness eval (respuestas fieles a Knowledge Base)
    - Ejecutar QA Accuracy eval (respuestas correctas a preguntas financieras)
    - Generar reporte con métricas
    - _Requirements: NFR Demostrabilidad 3_
    - _Estimación: 1h_
  
  - [ ] 33.3 Crear visualización de resultados de evaluación
    - Generar gráficos de métricas (Faithfulness score, QA Accuracy)
    - Incluir en slide deck de presentación
    - _Requirements: NFR Demostrabilidad 3_
    - _Estimación: 0.5h_


---

### ÉPICA E6: Observabilidad (CloudWatch)

- [ ] 34. Configurar CloudWatch Logs para Lambda Functions
  - Habilitar logging estructurado en las 4 Lambdas
  - Log format: JSON con campos: timestamp, level, message, client_id, latency_ms
  - Configurar log retention: 7 días para demo
  - _Requirements: 8.5_
  - _Estimación: 0.5h_

- [ ] 35. Crear CloudWatch Dashboard
  - [ ] 35.1 Crear métricas custom
    - Métrica: AgentLatency (P50, P95, P99)
    - Métrica: GuardrailBlockRate (% de consultas bloqueadas)
    - Métrica: TokensPerSession (promedio)
    - Métrica: ErrorRate (por Action Group)
    - _Requirements: NFR Performance 1_
    - _Estimación: 1h_
  
  - [ ] 35.2 Crear dashboard con 6 widgets
    - Widget 1: Latencia del Agent (line chart)
    - Widget 2: Guardrails block rate (gauge)
    - Widget 3: Tokens por sesión (bar chart)
    - Widget 4: Error rate por Lambda (stacked area)
    - Widget 5: Invocaciones por Action Group (pie chart)
    - Widget 6: Costos estimados (number widget)
    - _Requirements: NFR Demostrabilidad 3_
    - _Estimación: 1h_

---

### ÉPICA E7: CI/CD Pipeline (IaC CDK)

- [ ] 36. Crear CDK stacks para infraestructura
  - [ ] 36.1 Crear BedrockStack
    - Definir Bedrock Agent con CDK
    - Definir Knowledge Base con S3 data source
    - Definir Guardrails
    - _Requirements: NFR Demostrabilidad 4_
    - _Estimación: 1.5h_
  
  - [ ] 36.2 Crear LambdaStack
    - Definir 4 Lambda Functions con CDK
    - Configurar IAM roles y permisos
    - Asociar Lambdas a Action Groups
    - _Requirements: NFR Demostrabilidad 4_
    - _Estimación: 1h_
  
  - [ ] 36.3 Crear DataStack
    - Definir 3 DynamoDB tables con CDK
    - Definir S3 bucket para Knowledge Base
    - Configurar lifecycle policies
    - _Requirements: NFR Demostrabilidad 4_
    - _Estimación: 0.5h_

- [ ] 37. Configurar GitHub Actions para CI/CD
  - Pipeline de CI: lint, test, DS validation
  - Pipeline de CD: deploy CDK stacks a AWS
  - Configurar secrets para AWS credentials
  - _Requirements: NFR Demostrabilidad 4_
  - _Estimación: 1h_

---

### ÉPICA E8: Demo Flows (Scripts y Datos)

- [ ] 38. Crear scripts de demo para los 3 flujos principales
  - [ ] 38.1 Script Flujo 1: Diagnóstico de Salud Financiera
    - Input: "Hola, ¿cómo está mi salud financiera este mes?"
    - Verificar: ISF calculado, componentes mostrados, colores correctos
    - _Requirements: 1.1, 1.4, 1.5, NFR Demostrabilidad 2_
    - _Estimación: 0.5h_
  
  - [ ] 38.2 Script Flujo 2: Detección de Gastos Hormiga
    - Input: "¿En qué estoy gastando de más?"
    - Verificar: Top 3 categorías, alerta si >15%, badge warning
    - _Requirements: 2.1, 2.4, 2.5, NFR Demostrabilidad 2_
    - _Estimación: 0.5h_
  
  - [ ] 38.3 Script Flujo 3: Guardrails en Acción
    - Input: "¿Cuál es mi PIN?"
    - Verificar: Consulta bloqueada, badge Guardrails visible, mensaje de rechazo
    - _Requirements: 6.1, 6.2, 6.4, NFR Demostrabilidad 2_
    - _Estimación: 0.5h_

- [ ] 39. Preparar datos demo para presentación
  - Seleccionar cliente demo con perfil interesante (Carlos - ISF 45)
  - Verificar que datos transaccionales generan insights demostrables
  - Preparar respuestas esperadas para cada flujo
  - _Requirements: NFR Datos de Demostración 1, 2_
  - _Estimación: 0.5h_

- [ ] 40. Grabar video de backup de demo funcional
  - Grabar screencast de los 3 flujos principales funcionando
  - Duración: 3-4 minutos
  - Plan B en caso de problemas técnicos durante presentación
  - _Requirements: NFR Demostrabilidad 1_
  - _Estimación: 0.5h_


---

### ÉPICA E9: Presentación al Jurado

- [ ] 41. Crear slide deck de presentación
  - [ ] 41.1 Slides de problema y solución
    - Slide 1: Pitch de una línea
    - Slide 2: Problema cuantificado (70% consultan solo en crisis, 63% desconoce gastos)
    - Slide 3: Solución (Agente conversacional con ISF)
    - _Requirements: NFR Demostrabilidad 2_
    - _Estimación: 0.5h_
  
  - [ ] 41.2 Slides de arquitectura técnica
    - Slide 4: Diagrama de arquitectura (Bedrock Agent + Lambdas + DynamoDB + S3)
    - Slide 5: Stack técnico (Claude 3.5 Sonnet, Guardrails, Knowledge Base, FMEval)
    - Slide 6: Decisiones técnicas clave (Agent vs custom, RAG vs fine-tuning)
    - _Requirements: NFR Demostrabilidad 2_
    - _Estimación: 1h_
  
  - [ ] 41.3 Slides de métricas y resultados
    - Slide 7: Métricas de evaluación (Faithfulness, QA Accuracy)
    - Slide 8: Métricas de performance (P95 latency, Guardrails block rate)
    - Slide 9: Fidelidad al Design System (screenshots comparativos)
    - _Requirements: NFR Demostrabilidad 3_
    - _Estimación: 0.5h_
  
  - [ ] 41.4 Slides de demo y roadmap
    - Slide 10: Demo live (3 flujos principales)
    - Slide 11: Roadmap post-hackathon (fine-tuning, A/B testing, integración core)
    - Slide 12: Impacto esperado (+15% ahorro, -20% mora)
    - _Requirements: NFR Demostrabilidad 2_
    - _Estimación: 0.5h_

- [ ] 42. Preparar script de presentación (5 minutos)
  - Introducción: 30 segundos (problema + solución)
  - Arquitectura: 1 minuto (stack técnico + decisiones clave)
  - Demo live: 2.5 minutos (3 flujos)
  - Métricas: 30 segundos (evaluación + performance)
  - Roadmap: 30 segundos (próximos pasos)
  - _Requirements: NFR Demostrabilidad 1_
  - _Estimación: 0.5h_

- [ ] 43. Ensayar presentación con todo el equipo
  - Practicar transiciones entre slides y demo
  - Verificar timing (5 minutos máximo)
  - Preparar respuestas a preguntas frecuentes del jurado
  - _Requirements: NFR Demostrabilidad 1_
  - _Estimación: 0.5h_

---

## 3.3 Definition of Done — Hackathon

Cada tarea se considera completa cuando cumple TODOS estos criterios:

- [ ] ✅ **Funciona en entorno demo sin intervención manual**
  - La funcionalidad se ejecuta correctamente en la cuenta AWS de demo
  - No requiere configuración manual o pasos adicionales para funcionar

- [ ] ✅ **Tiene al menos un test automatizado o script de evaluación que pasa**
  - Tareas de backend: unit tests en Python
  - Tareas de frontend: tests de componentes o validación visual
  - Tareas de infraestructura: script de validación de despliegue

- [ ] ✅ **Está documentada en README con instrucciones de despliegue**
  - Cada componente tiene sección en README explicando su propósito
  - Instrucciones claras de cómo desplegar o ejecutar
  - Variables de entorno requeridas documentadas

- [ ] ✅ **Ha sido revisada por al menos un miembro del equipo diferente al autor**
  - Code review en GitHub PR
  - Validación funcional por otro miembro del equipo
  - Feedback incorporado antes de merge

- [ ] ✅ **El frontend usa exclusivamente tokens `var(--bb-...)` — cero valores hardcodeados**
  - Todos los colores usan tokens CSS del Design System
  - No hay valores hex (#008292) o rgb() hardcodeados en componentes
  - Script de validación DS pasa sin errores

- [ ] ✅ **Los componentes muestran Lexend como tipografía — verificado en DevTools → Fonts**
  - Inspeccionar elementos en DevTools
  - Verificar que "Lexend" aparece en la pestaña Fonts
  - No hay fallback a fuentes del sistema

- [ ] ✅ **Está incluida en el deck de presentación al jurado**
  - La funcionalidad aparece en al menos un slide
  - Hay screenshot o mención en la presentación
  - Forma parte del script de demo de 5 minutos

---

## 3.4 Cronograma Recomendado (24–48 horas de Hackathon)

### Escenario 1: Hackathon de 24 horas

| Hora | Fase | Tareas | Owner | Checkpoint |
|------|------|--------|-------|------------|
| **0-4** | **Setup Crítico** | E1 (Bedrock Agent + KB + Guardrails) | AI/ML Lead | ✓ Agent responde consulta simple |
| **0-4** | **Setup Crítico** | E2.1-E2.3 (DynamoDB + datos demo) | Backend Lead | ✓ Datos cargados en DynamoDB |
| **0-4** | **Setup Crítico** | E4 (Tokens CSS + Next.js setup) | Frontend Lead | ✓ bb-tokens.css importado |
| **4-8** | **Backend Core** | E2.4-E2.7 (Lambdas ISF + Analyzer) | Backend Lead | ✓ ISF y gastos hormiga funcionan |
| **4-8** | **Frontend Base** | E3.1-E3.4 (Chat UI + burbujas) | Frontend Lead | ✓ Chat UI renderiza mensajes |
| **4-8** | **Infraestructura** | E7.1 (CDK stacks básicos) | DevOps Lead | ✓ IaC despliega recursos |
| **8-12** | **Backend Completo** | E2.8-E2.11 (Lambdas Alerter + SessionMgr) | Backend Lead | ✓ Todas las Lambdas conectadas |
| **8-12** | **Frontend Financiero** | E3.5-E3.8 (Componentes ISF + Gastos) | Frontend Lead | ✓ Componentes financieros renderizan |
| **8-12** | **Observabilidad** | E6 (CloudWatch dashboard) | DevOps Lead | ✓ Dashboard muestra métricas |
| **12-16** | **Frontend Completo** | E3.9-E3.12 (Badges + Streaming) | Frontend Lead | **✓ CHECKPOINT OBLIGATORIO: QA visual DS** |
| **12-16** | **Integración** | E3.13 (Integración Bedrock Agent) | Backend + Frontend | ✓ End-to-end funciona |
| **12-16** | **Evaluación** | E5 (FMEval scripts) | AI/ML Lead | ✓ Métricas de evaluación generadas |
| **16-20** | **QA y Refinamiento** | E3.14-E3.15 (Responsividad + QA) | Frontend Lead | ✓ Fidelidad DS 100% |
| **16-20** | **Demo Prep** | E8 (Scripts de demo + datos) | Todo el equipo | ✓ 3 flujos demo funcionan |
| **20-24** | **Presentación** | E9 (Slide deck + ensayo) | Todo el equipo | ✓ Presentación lista |
| **23-24** | **Pre-Demo Check** | Checklist Pre-Demo (ver sección 3.6) | Todo el equipo | ✓ Todo verificado |

### Escenario 2: Hackathon de 48 horas

| Hora | Fase | Tareas | Owner | Checkpoint |
|------|------|--------|-------|------------|
| **0-8** | **Setup Completo** | E1 + E2.1-E2.3 + E4 | AI/ML + Backend + Frontend | ✓ Infraestructura base lista |
| **8-16** | **Backend Core** | E2.4-E2.11 (Todas las Lambdas) | Backend Lead | ✓ Action Groups completos |
| **8-16** | **Frontend Base** | E3.1-E3.8 (Chat + Componentes base) | Frontend Lead | ✓ UI base funcional |
| **16-24** | **Frontend Avanzado** | E3.9-E3.13 (Badges + Streaming + Integración) | Frontend Lead | ✓ Streaming funciona |
| **16-24** | **Observabilidad** | E6 + E7 (CloudWatch + CI/CD) | DevOps Lead | ✓ Dashboard y pipeline listos |
| **24-32** | **QA Visual** | E3.14-E3.15 + E4.1-E4.2 (Responsividad + DS validation) | Frontend Lead | **✓ CHECKPOINT: Fidelidad DS 100%** |
| **24-32** | **Evaluación** | E5 (FMEval completo) | AI/ML Lead | ✓ Métricas de calidad generadas |
| **32-40** | **Demo Prep** | E8 (Scripts + datos + video backup) | Todo el equipo | ✓ 3 flujos demo + video |
| **40-48** | **Presentación** | E9 (Slide deck + ensayo + refinamiento) | Todo el equipo | ✓ Presentación pulida |
| **47-48** | **Pre-Demo Check** | Checklist Pre-Demo (ver sección 3.6) | Todo el equipo | ✓ Todo verificado |

### Checkpoints Go/No-Go

**Checkpoint Hora 4 (24h) / Hora 8 (48h):**
- ❌ **NO-GO si:** Bedrock Agent no responde o Guardrails no funcionan
- ✅ **GO si:** Agent responde consulta simple y Guardrails bloquea consulta prohibida

**Checkpoint Hora 8 (24h) / Hora 16 (48h):**
- ❌ **NO-GO si:** ISF Calculator no retorna score o frontend no renderiza mensajes
- ✅ **GO si:** ISF se calcula correctamente y chat UI muestra burbujas

**Checkpoint Hora 12-16 (24h) / Hora 24-32 (48h) — CRÍTICO:**
- ❌ **NO-GO si:** Componentes usan colores hardcodeados o Lexend no carga
- ✅ **GO si:** Script de validación DS pasa y DevTools muestra Lexend

**Checkpoint Hora 20 (24h) / Hora 40 (48h):**
- ❌ **NO-GO si:** Menos de 2 flujos demo funcionan end-to-end
- ✅ **GO si:** 3 flujos demo funcionan y video backup grabado

---

