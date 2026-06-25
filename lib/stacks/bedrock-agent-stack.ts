import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import { Construct } from 'constructs';
import * as path from 'path';
import { AGENT_SYSTEM_PROMPT } from '../config/agent-system-prompt';

/**
 * Props for the BedrockAgentStack
 */
export interface BedrockAgentStackProps extends cdk.StackProps {
  /** Guardrail ID to associate with the agent */
  guardrailId?: string;
  /** Guardrail version to associate with the agent */
  guardrailVersion?: string;
}

/**
 * Stack principal para el Amazon Bedrock Agent del Asistente de Salud Financiera.
 * 
 * Define:
 * - Bedrock Agent con Claude 3.5 Sonnet
 * - 4 Action Groups (ISF Calculator, Transaction Analyzer, Liquidity Alerter, Session Manager)
 * - Placeholder Lambda functions para cada Action Group
 * - IAM roles y permisos necesarios
 * - Asociación con Guardrails de seguridad
 * 
 * Requirements: 1.1, 6.1, 7.1, 7.3, 7.4
 */
export class BedrockAgentStack extends cdk.Stack {
  public readonly agentId: cdk.CfnOutput;
  public readonly agentAliasId: cdk.CfnOutput;

  constructor(scope: Construct, id: string, props?: BedrockAgentStackProps) {
    super(scope, id, props);

    // ─────────────────────────────────────────────────────────────────────────
    // S3 Bucket for OpenAPI schemas
    // ─────────────────────────────────────────────────────────────────────────
    const schemasBucket = new s3.Bucket(this, 'AgentSchemasBucket', {
      bucketName: `financial-agent-schemas-${this.account}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // Deploy OpenAPI schemas to S3
    new s3deploy.BucketDeployment(this, 'DeploySchemas', {
      sources: [s3deploy.Source.asset(path.join(__dirname, '..', 'schemas'))],
      destinationBucket: schemasBucket,
      destinationKeyPrefix: 'schemas/',
    });

    // ─────────────────────────────────────────────────────────────────────────
    // IAM Role for Bedrock Agent
    // ─────────────────────────────────────────────────────────────────────────
    const agentRole = new iam.Role(this, 'BedrockAgentRole', {
      roleName: 'financial-health-assistant-agent-role',
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      description: 'Role for Financial Health Assistant Bedrock Agent',
    });

    // Allow agent to invoke the foundation model
    agentRole.addToPolicy(new iam.PolicyStatement({
      sid: 'InvokeFoundationModel',
      effect: iam.Effect.ALLOW,
      actions: ['bedrock:InvokeModel'],
      resources: [
        `arn:aws:bedrock:${this.region}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0`,
      ],
    }));

    // Allow agent to read schemas from S3
    agentRole.addToPolicy(new iam.PolicyStatement({
      sid: 'ReadSchemasBucket',
      effect: iam.Effect.ALLOW,
      actions: ['s3:GetObject'],
      resources: [`${schemasBucket.bucketArn}/schemas/*`],
    }));

    // Allow agent to use Guardrails (Requirement 6.1)
    if (props?.guardrailId) {
      agentRole.addToPolicy(new iam.PolicyStatement({
        sid: 'ApplyGuardrails',
        effect: iam.Effect.ALLOW,
        actions: ['bedrock:ApplyGuardrail'],
        resources: [
          `arn:aws:bedrock:${this.region}:${this.account}:guardrail/${props.guardrailId}`,
        ],
      }));
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Lambda Functions for Action Groups (placeholder implementations)
    // ─────────────────────────────────────────────────────────────────────────
    const lambdaRole = new iam.Role(this, 'ActionGroupLambdaRole', {
      roleName: 'financial-agent-lambda-role',
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Grant DynamoDB access for Action Group Lambdas (Requirement 8.3)
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      sid: 'DynamoDBAccess',
      effect: iam.Effect.ALLOW,
      actions: [
        'dynamodb:GetItem',
        'dynamodb:PutItem',
        'dynamodb:UpdateItem',
        'dynamodb:DeleteItem',
        'dynamodb:Query',
        'dynamodb:Scan',
      ],
      resources: [
        `arn:aws:dynamodb:${this.region}:${this.account}:table/financial-assistant-transactions`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/financial-assistant-transactions/index/*`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/financial-assistant-sessions`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/financial-assistant-sessions/index/*`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/financial-assistant-clients`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/financial-assistant-clients/index/*`,
      ],
    }));

    // L1: ISF Calculator Lambda
    const isfCalculatorLambda = new lambda.Function(this, 'ISFCalculatorLambda', {
      functionName: 'isf-calculator',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', '..', 'lambdas', 'isf-calculator')),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      role: lambdaRole,
      description: 'Calcula el Índice de Salud Financiera (ISF) del cliente',
      environment: {
        TRANSACTIONS_TABLE: 'financial-assistant-transactions',
        CLIENTS_TABLE: 'financial-assistant-clients',
      },
    });

    // L2: Transaction Analyzer Lambda
    const transactionAnalyzerLambda = new lambda.Function(this, 'TransactionAnalyzerLambda', {
      functionName: 'transaction-analyzer',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', '..', 'lambdas', 'transaction-analyzer')),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      role: lambdaRole,
      description: 'Analiza transacciones para gastos hormiga y suscripciones',
      environment: {
        TRANSACTIONS_TABLE: 'financial-assistant-transactions',
        CLIENTS_TABLE: 'financial-assistant-clients',
      },
    });

    // L3: Liquidity Alerter Lambda
    const liquidityAlerterLambda = new lambda.Function(this, 'LiquidityAlerterLambda', {
      functionName: 'liquidity-alerter',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', '..', 'lambdas', 'liquidity-alerter')),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      role: lambdaRole,
      description: 'Proyecta liquidez y genera alertas de sobregiro',
      environment: {
        TRANSACTIONS_TABLE: 'financial-assistant-transactions',
        CLIENTS_TABLE: 'financial-assistant-clients',
      },
    });

    // L4: Session Manager Lambda
    const sessionManagerLambda = new lambda.Function(this, 'SessionManagerLambda', {
      functionName: 'session-manager',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', '..', 'lambdas', 'session-manager')),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      role: lambdaRole,
      description: 'Gestiona contexto de conversación y persistencia de sesiones',
      environment: {
        SESSIONS_TABLE: 'financial-assistant-sessions',
      },
    });

    // ─────────────────────────────────────────────────────────────────────────
    // Bedrock Agent (using CfnAgent - L1 construct)
    // ─────────────────────────────────────────────────────────────────────────
    const agent = new cdk.aws_bedrock.CfnAgent(this, 'FinancialHealthAgent', {
      agentName: 'financial-health-assistant-agent',
      foundationModel: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
      instruction: AGENT_SYSTEM_PROMPT,
      agentResourceRoleArn: agentRole.roleArn,
      idleSessionTtlInSeconds: 1800, // 30 minutes session TTL
      description: 'Asistente de Salud Financiera del Banco Bolivariano - Calcula ISF, detecta gastos hormiga, proyecta liquidez',

      // Guardrails association (Requirement 6.1)
      guardrailConfiguration: props?.guardrailId && props?.guardrailVersion ? {
        guardrailIdentifier: props.guardrailId,
        guardrailVersion: props.guardrailVersion,
      } : undefined,

      // Action Groups definition
      actionGroups: [
        // Action Group 1: ISF Calculator
        {
          actionGroupName: 'calculate-isf',
          description: 'Calcula el Índice de Salud Financiera del cliente basado en ingresos, gastos, ahorros y deudas',
          actionGroupExecutor: {
            lambda: isfCalculatorLambda.functionArn,
          },
          apiSchema: {
            s3: {
              s3BucketName: schemasBucket.bucketName,
              s3ObjectKey: 'schemas/isf-calculator-api.json',
            },
          },
        },
        // Action Group 2: Transaction Analyzer
        {
          actionGroupName: 'analyze-transactions',
          description: 'Analiza transacciones para identificar gastos hormiga y suscripciones recurrentes',
          actionGroupExecutor: {
            lambda: transactionAnalyzerLambda.functionArn,
          },
          apiSchema: {
            s3: {
              s3BucketName: schemasBucket.bucketName,
              s3ObjectKey: 'schemas/transaction-analyzer-api.json',
            },
          },
        },
        // Action Group 3: Liquidity Alerter
        {
          actionGroupName: 'check-liquidity',
          description: 'Proyecta saldo futuro y genera alertas de liquidez para prevenir sobregiros',
          actionGroupExecutor: {
            lambda: liquidityAlerterLambda.functionArn,
          },
          apiSchema: {
            s3: {
              s3BucketName: schemasBucket.bucketName,
              s3ObjectKey: 'schemas/liquidity-alerter-api.json',
            },
          },
        },
        // Action Group 4: Session Manager
        {
          actionGroupName: 'manage-session',
          description: 'Gestiona contexto de conversación y persistencia de sesiones',
          actionGroupExecutor: {
            lambda: sessionManagerLambda.functionArn,
          },
          apiSchema: {
            s3: {
              s3BucketName: schemasBucket.bucketName,
              s3ObjectKey: 'schemas/session-manager-api.json',
            },
          },
        },
      ],
    });

    // ─────────────────────────────────────────────────────────────────────────
    // Grant Bedrock Agent permission to invoke Lambda functions
    // ─────────────────────────────────────────────────────────────────────────
    const lambdas = [
      isfCalculatorLambda,
      transactionAnalyzerLambda,
      liquidityAlerterLambda,
      sessionManagerLambda,
    ];

    for (const fn of lambdas) {
      fn.addPermission('AllowBedrockAgentInvoke', {
        principal: new iam.ServicePrincipal('bedrock.amazonaws.com'),
        action: 'lambda:InvokeFunction',
        sourceArn: agent.attrAgentArn,
      });
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Agent Alias (for invoking the agent)
    // ─────────────────────────────────────────────────────────────────────────
    const agentAlias = new cdk.aws_bedrock.CfnAgentAlias(this, 'FinancialHealthAgentAlias', {
      agentId: agent.attrAgentId,
      agentAliasName: 'live',
      description: 'Production alias for the Financial Health Assistant Agent',
    });

    agentAlias.addDependency(agent);

    // ─────────────────────────────────────────────────────────────────────────
    // Outputs
    // ─────────────────────────────────────────────────────────────────────────
    this.agentId = new cdk.CfnOutput(this, 'AgentId', {
      value: agent.attrAgentId,
      description: 'Bedrock Agent ID',
      exportName: 'FinancialHealthAgentId',
    });

    this.agentAliasId = new cdk.CfnOutput(this, 'AgentAliasId', {
      value: agentAlias.attrAgentAliasId,
      description: 'Bedrock Agent Alias ID',
      exportName: 'FinancialHealthAgentAliasId',
    });

    new cdk.CfnOutput(this, 'SchemasBucketName', {
      value: schemasBucket.bucketName,
      description: 'S3 Bucket containing OpenAPI schemas',
    });

    // Tags
    cdk.Tags.of(this).add('Project', 'financial-health-assistant');
    cdk.Tags.of(this).add('Environment', 'hackathon');
    cdk.Tags.of(this).add('Team', 'banco-bolivariano');
  }
}
