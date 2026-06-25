import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';

/**
 * Stack de datos para el Asistente de Salud Financiera.
 *
 * Define las tablas DynamoDB necesarias:
 * - financial-assistant-transactions (Requirement 8.3)
 * - financial-assistant-sessions (Requirement 8.1, 8.5)
 * - financial-assistant-clients (Requirement 8.4)
 */
export class DataStack extends cdk.Stack {
  /** Tabla de transacciones */
  public readonly transactionsTable: dynamodb.Table;

  /** Tabla de sesiones de conversación */
  public readonly sessionsTable: dynamodb.Table;

  /** Tabla de clientes demo */
  public readonly clientsTable: dynamodb.Table;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ─────────────────────────────────────────────────────────────────────────
    // Table: financial-assistant-transactions
    // PK: client_id, SK: transaction_id
    // Billing: On-Demand (PAY_PER_REQUEST)
    // Requirement: 8.3
    // ─────────────────────────────────────────────────────────────────────────
    this.transactionsTable = new dynamodb.Table(this, 'TransactionsTable', {
      tableName: 'financial-assistant-transactions',
      partitionKey: {
        name: 'client_id',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'transaction_id',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // GSI: date-index (PK: client_id, SK: date, Projection: ALL)
    this.transactionsTable.addGlobalSecondaryIndex({
      indexName: 'date-index',
      partitionKey: {
        name: 'client_id',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'date',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // ─────────────────────────────────────────────────────────────────────────
    // Table: financial-assistant-sessions
    // PK: session_id (String), SK: timestamp (Number)
    // Billing: On-Demand (PAY_PER_REQUEST)
    // TTL: 90 días (attribute: ttl)
    // Requirements: 8.1, 8.5
    // ─────────────────────────────────────────────────────────────────────────
    this.sessionsTable = new dynamodb.Table(this, 'SessionsTable', {
      tableName: 'financial-assistant-sessions',
      partitionKey: {
        name: 'session_id',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'timestamp',
        type: dynamodb.AttributeType.NUMBER,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      timeToLiveAttribute: 'ttl',
    });

    // ─────────────────────────────────────────────────────────────────────────
    // Table: financial-assistant-clients
    // PK: client_id (String), no sort key
    // Billing: On-Demand (PAY_PER_REQUEST)
    // Requirement: 8.4
    // ─────────────────────────────────────────────────────────────────────────
    this.clientsTable = new dynamodb.Table(this, 'ClientsTable', {
      tableName: 'financial-assistant-clients',
      partitionKey: {
        name: 'client_id',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // ─────────────────────────────────────────────────────────────────────────
    // Outputs
    // ─────────────────────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, 'TransactionsTableName', {
      value: this.transactionsTable.tableName,
      description: 'DynamoDB Transactions table name',
      exportName: 'FinancialAssistantTransactionsTableName',
    });

    new cdk.CfnOutput(this, 'TransactionsTableArn', {
      value: this.transactionsTable.tableArn,
      description: 'DynamoDB Transactions table ARN',
      exportName: 'FinancialAssistantTransactionsTableArn',
    });

    new cdk.CfnOutput(this, 'SessionsTableName', {
      value: this.sessionsTable.tableName,
      description: 'DynamoDB Sessions table name',
      exportName: 'FinancialAssistantSessionsTableName',
    });

    new cdk.CfnOutput(this, 'SessionsTableArn', {
      value: this.sessionsTable.tableArn,
      description: 'DynamoDB Sessions table ARN',
      exportName: 'FinancialAssistantSessionsTableArn',
    });

    new cdk.CfnOutput(this, 'ClientsTableName', {
      value: this.clientsTable.tableName,
      description: 'DynamoDB Clients table name',
      exportName: 'FinancialAssistantClientsTableName',
    });

    new cdk.CfnOutput(this, 'ClientsTableArn', {
      value: this.clientsTable.tableArn,
      description: 'DynamoDB Clients table ARN',
      exportName: 'FinancialAssistantClientsTableArn',
    });

    // Tags
    cdk.Tags.of(this).add('Project', 'financial-health-assistant');
    cdk.Tags.of(this).add('Environment', 'hackathon');
    cdk.Tags.of(this).add('Team', 'banco-bolivariano');
  }
}
