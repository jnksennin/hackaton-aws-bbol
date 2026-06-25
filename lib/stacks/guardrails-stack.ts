import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

/**
 * Stack para Amazon Bedrock Guardrails del Asistente de Salud Financiera.
 *
 * Configura:
 * - PII Filters: BLOCK para tarjetas/PIN, ANONYMIZE para email/phone/name
 * - Topic Filters: bloqueo de consultas de otros clientes, datos de tarjetas, PINs
 * - Content Filters: HATE, INSULTS, SEXUAL, VIOLENCE, MISCONDUCT, PROMPT_ATTACK
 * - Custom rejection response con branding Banco Bolivariano
 *
 * Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
 */
export class GuardrailsStack extends cdk.Stack {
  public readonly guardrailId: string;
  public readonly guardrailVersion: string;
  public readonly guardrailArn: string;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ─────────────────────────────────────────────────────────────────────────
    // Bedrock Guardrail
    // ─────────────────────────────────────────────────────────────────────────
    const guardrail = new cdk.aws_bedrock.CfnGuardrail(this, 'FinancialAssistantGuardrail', {
      name: 'financial-assistant-guardrails',
      description: 'Guardrails de seguridad para el Asistente de Salud Financiera del Banco Bolivariano. Filtra PII, bloquea topics prohibidos y detecta prompt injection.',

      // ─── Custom Rejection Response ──────────────────────────────────────
      blockedInputMessaging: `Lo siento, no puedo procesar esa consulta por razones de seguridad y cumplimiento.\n\n🛡️ Protegido por Guardrails de Seguridad\n\nComo asistente del Banco Bolivariano, estoy diseñado para proteger tu información y la de todos nuestros clientes.\n\nSi necesitas ayuda con información sensible, por favor contacta a nuestro equipo de atención al cliente:\n📞 5505050\n💬 Chat en línea: www.bolivariano.com`,
      blockedOutputsMessaging: `Lo siento, no puedo proporcionar esa información por razones de seguridad y cumplimiento.\n\n🛡️ Protegido por Guardrails de Seguridad\n\nComo asistente del Banco Bolivariano, estoy diseñado para proteger tu información y la de todos nuestros clientes.\n\nSi necesitas ayuda con información sensible, por favor contacta a nuestro equipo de atención al cliente:\n📞 5505050\n💬 Chat en línea: www.bolivariano.com`,

      // ─── Sensitive Information (PII) Filters ────────────────────────────
      sensitiveInformationPolicyConfig: {
        piiEntitiesConfig: [
          {
            type: 'CREDIT_DEBIT_CARD_NUMBER',
            action: 'BLOCK',
          },
          {
            type: 'PIN',
            action: 'BLOCK',
          },
          {
            type: 'EMAIL',
            action: 'ANONYMIZE',
          },
          {
            type: 'PHONE',
            action: 'ANONYMIZE',
          },
          {
            type: 'NAME',
            action: 'ANONYMIZE',
          },
        ],
      },

      // ─── Topic Filters (Denied Topics) ─────────────────────────────────
      topicPolicyConfig: {
        topicsConfig: [
          {
            name: 'InformacionDeOtrosClientes',
            definition: 'Consultas que solicitan datos personales, transacciones o información financiera de clientes que no sean el usuario autenticado',
            examples: [
              '¿Cuánto dinero tiene Juan Pérez en su cuenta?',
              'Muéstrame las transacciones de María García',
              '¿Cuál es el saldo de la cuenta 1234567890?',
            ],
            type: 'DENY',
          },
          {
            name: 'DatosCompletosDeTarjetas',
            definition: 'Solicitudes de números completos de tarjetas de crédito o débito, CVV, o fechas de expiración',
            examples: [
              '¿Cuál es mi número de tarjeta completo?',
              'Dame el CVV de mi tarjeta',
              'Necesito los 16 dígitos de mi tarjeta',
            ],
            type: 'DENY',
          },
          {
            name: 'PINsYContraseñas',
            definition: 'Solicitudes de PINs, contraseñas, o credenciales de acceso',
            examples: [
              '¿Cuál es mi PIN?',
              'Dame mi contraseña del banco',
              'Necesito mi clave de acceso',
            ],
            type: 'DENY',
          },
        ],
      },

      // ─── Content Filters ────────────────────────────────────────────────
      contentPolicyConfig: {
        filtersConfig: [
          {
            type: 'HATE',
            inputStrength: 'MEDIUM',
            outputStrength: 'MEDIUM',
          },
          {
            type: 'INSULTS',
            inputStrength: 'MEDIUM',
            outputStrength: 'MEDIUM',
          },
          {
            type: 'SEXUAL',
            inputStrength: 'HIGH',
            outputStrength: 'HIGH',
          },
          {
            type: 'VIOLENCE',
            inputStrength: 'HIGH',
            outputStrength: 'HIGH',
          },
          {
            type: 'MISCONDUCT',
            inputStrength: 'MEDIUM',
            outputStrength: 'MEDIUM',
          },
          {
            type: 'PROMPT_ATTACK',
            inputStrength: 'HIGH',
            outputStrength: 'NONE',
          },
        ],
      },
    });

    // ─────────────────────────────────────────────────────────────────────────
    // Guardrail Version (required to associate with an agent)
    // ─────────────────────────────────────────────────────────────────────────
    const guardrailVersion = new cdk.aws_bedrock.CfnGuardrailVersion(this, 'GuardrailVersion', {
      guardrailIdentifier: guardrail.attrGuardrailId,
      description: 'Initial version with PII, Topic, and Content filters',
    });

    guardrailVersion.addDependency(guardrail);

    // ─────────────────────────────────────────────────────────────────────────
    // Expose properties for cross-stack references
    // ─────────────────────────────────────────────────────────────────────────
    this.guardrailId = guardrail.attrGuardrailId;
    this.guardrailVersion = guardrailVersion.attrVersion;
    this.guardrailArn = guardrail.attrGuardrailArn;

    // ─────────────────────────────────────────────────────────────────────────
    // Outputs
    // ─────────────────────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, 'GuardrailId', {
      value: guardrail.attrGuardrailId,
      description: 'Bedrock Guardrail ID',
      exportName: 'FinancialAssistantGuardrailId',
    });

    new cdk.CfnOutput(this, 'GuardrailVersionOutput', {
      value: guardrailVersion.attrVersion,
      description: 'Bedrock Guardrail Version',
      exportName: 'FinancialAssistantGuardrailVersion',
    });

    new cdk.CfnOutput(this, 'GuardrailArn', {
      value: guardrail.attrGuardrailArn,
      description: 'Bedrock Guardrail ARN',
      exportName: 'FinancialAssistantGuardrailArn',
    });

    // Tags
    cdk.Tags.of(this).add('Project', 'financial-health-assistant');
    cdk.Tags.of(this).add('Environment', 'hackathon');
    cdk.Tags.of(this).add('Team', 'banco-bolivariano');
    cdk.Tags.of(this).add('Component', 'guardrails');
  }
}
