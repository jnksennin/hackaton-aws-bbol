# Implementation Plan: Asistente de Salud Financiera Agéntico

## Task Dependency Graph

```mermaid
graph TD
    T1[1. Configurar Bedrock Agent]
    T2[2. Configurar Knowledge Base]
    T3[3. Configurar Guardrails]
    T4[4. Checkpoint Setup Base]
    T5[5. Crear DynamoDB Tables]
    T6[6. Generar Datos Simulados]
    T7[7. Lambda ISF Calculator]
    T8[8. Lambda Transaction Analyzer]
    T9[9. Lambda Liquidity Alerter]
    T10[10. Lambda Session Manager]
    T11[11. Conectar Lambdas al Agent]
    T12[12. Checkpoint Action Groups]
    T13[13. Generar bb-tokens.css]
    T14[14. Configurar Next.js]
    T15[15. BBChatHeader]
    T16[16. Burbujas de Chat]
    T17[17. BBFinancialCard ISF]
    T18[18. BBHealthScoreGauge]
    T19[19. BBGastosHormigaList]
    T20[20. BBSubscriptionCard]
    T21[21. BBGuardrailBadge]
    T22[22. BBKnowledgeBadge]
    T23[23. BBQuickActionChips]
    T24[24. BBChatInput]
    T25[25. Streaming Respuestas]
    T26[26. Integración Bedrock Agent]
    T27[27. QA Fidelidad DS]
    T28[28. Responsividad Móvil]
    T29[29. Checkpoint Frontend]
    T30[30. Script Validación DS]
    T31[31. DS Lint Pre-commit]
    T32[32. Dataset Evaluación]
    T33[33. Script FMEval]
    T34[34. CloudWatch Logs]
    T35[35. CloudWatch Dashboard]
    T36[36. CDK Stacks]
    T37[37. GitHub Actions CI/CD]
    T38[38. Scripts Demo]
    T39[39. Datos Demo Presentación]
    T40[40. Video Backup]
    T41[41. Slide Deck]
    T42[42. Script Presentación]
    T43[43. Ensayo Presentación]

    T1 --> T4
    T2 --> T4
    T3 --> T4
    T5 --> T6
    T6 --> T7
    T6 --> T8
    T6 --> T9
    T5 --> T10
    T4 --> T11
    T7 --> T11
    T8 --> T11
    T9 --> T11
    T10 --> T11
    T11 --> T12
    T13 --> T15
    T14 --> T15
    T14 --> T16
    T16 --> T17
    T16 --> T18
    T16 --> T19
    T16 --> T20
    T16 --> T21
    T16 --> T22
    T16 --> T23
    T16 --> T24
    T17 --> T25
    T24 --> T25
    T12 --> T26
    T25 --> T26
    T26 --> T27
    T27 --> T28
    T28 --> T29
    T13 --> T30
    T30 --> T31
    T12 --> T32
    T32 --> T33
    T12 --> T34
    T34 --> T35
    T36 --> T37
    T12 --> T38
    T29 --> T38
    T38 --> T39
    T39 --> T40
    T35 --> T41
    T33 --> T41
    T40 --> T41
    T41 --> T42
    T42 --> T43
```

## Tasks

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
    - Generar alerta si ≥15% del ingreso (independiente del monto absoluto)
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
    - Test alerta ≥15% independiente del nivel de ingresos
    - _Requirements: 2.2, 2.5, 3.2_
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
  - Operación save: guardar turno de conversación en DynamoDB (non-blocking audit logging: si falla la escritura, continuar sin bloquear)
  - Operación retrieve: recuperar últimas 5 conversaciones del cliente
  - Operación reset: limpiar contexto de conversación
  - _Requirements: 8.1, 8.2, 6.6_
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

- [ ] 13. Generar archivo bb-tokens.css con Design System Bolivariano
  - Crear archivo `styles/bb-tokens.css` con todos los tokens CSS
  - Tokens de color: `--bb-primary-500: #008292`, `--bb-bg-body: #edeef3`, `--bb-bg-primary: #008292`, `--bb-bg-surface: #ffffff`
  - Tokens de estado: `--bb-state-warning-bg`, `--bb-state-warning-border`, `--bb-state-info-bg`, `--bb-state-info-border`
  - Tokens de indicadores: `--bb-green-500`, `--bb-red-600`
  - Tokens de sombra: `--bb-shadow-card: 0 2px 8px rgba(0,0,0,0.1)`
  - Configurar Google Fonts para Lexend (weights: 300, 400, 500, 600, 700)
  - Importar bb-tokens.css globalmente en `_app.tsx` o `layout.tsx`
  - _Requirements: 7.5_
  - _Estimación: 1h_

- [ ] 14. Configurar Next.js project con TypeScript
  - Inicializar proyecto Next.js 14+ con App Router
  - Configurar TypeScript con strict mode
  - Instalar dependencias: `aws-sdk`, `@aws-sdk/client-bedrock-agent-runtime`
  - Configurar variables de entorno para AWS credentials
  - _Requirements: 7.5_
  - _Estimación: 0.5h_

- [ ] 15. Crear componente BBChatHeader
  - Header con logo/nombre del agente
  - Fondo: `var(--bb-bg-primary)` (#008292)
  - Tipografía: Lexend, color blanco
  - Incluir badge "Protegido por Guardrails" con icono 🛡️
  - _Requirements: 7.5_
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
  - Si alerta activa (≥15% ingreso): badge warning con `var(--bb-state-warning-bg)` y `var(--bb-state-warning-border)`
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
  - Solo mostrar cuando la información recuperada es suficiente para responder la consulta
  - Fondo: `var(--bb-state-info-bg)`
  - Border: `var(--bb-state-info-border)`
  - Incluir título del documento y enlace (si disponible)
  - _Requirements: 5.3, 5.6_
  - _Estimación: 0.5h_
