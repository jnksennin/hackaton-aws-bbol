import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Match, Template } from 'aws-cdk-lib/assertions';
import { DataStack } from '../lib/stacks/data-stack';

describe('DataStack - Transactions Table', () => {
  let template: Template;

  beforeAll(() => {
    const app = new cdk.App();
    const stack = new DataStack(app, 'TestDataStack', {
      env: { account: '123456789012', region: 'us-east-1' },
    });
    template = Template.fromStack(stack);
  });

  test('creates transactions table with correct name', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'financial-assistant-transactions',
    });
  });

  test('transactions table has client_id as partition key', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      KeySchema: Match.arrayWith([
        { AttributeName: 'client_id', KeyType: 'HASH' },
      ]),
    });
  });

  test('transactions table has transaction_id as sort key', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      KeySchema: Match.arrayWith([
        { AttributeName: 'transaction_id', KeyType: 'RANGE' },
      ]),
    });
  });

  test('transactions table uses on-demand billing (PAY_PER_REQUEST)', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      BillingMode: 'PAY_PER_REQUEST',
    });
  });

  test('transactions table has date-index GSI', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      GlobalSecondaryIndexes: Match.arrayWith([
        Match.objectLike({
          IndexName: 'date-index',
          KeySchema: [
            { AttributeName: 'client_id', KeyType: 'HASH' },
            { AttributeName: 'date', KeyType: 'RANGE' },
          ],
          Projection: { ProjectionType: 'ALL' },
        }),
      ]),
    });
  });

  test('transactions table has DESTROY removal policy', () => {
    template.hasResource('AWS::DynamoDB::Table', {
      DeletionPolicy: 'Delete',
      UpdateReplacePolicy: 'Delete',
    });
  });

  test('defines attribute definitions for client_id, transaction_id, and date', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      AttributeDefinitions: Match.arrayWith([
        { AttributeName: 'client_id', AttributeType: 'S' },
        { AttributeName: 'transaction_id', AttributeType: 'S' },
        { AttributeName: 'date', AttributeType: 'S' },
      ]),
    });
  });

  test('exports table name as CfnOutput', () => {
    template.hasOutput('TransactionsTableName', {
      Value: Match.objectLike({ Ref: Match.anyValue() }),
      Export: { Name: 'FinancialAssistantTransactionsTableName' },
    });
  });

  test('exports table ARN as CfnOutput', () => {
    template.hasOutput('TransactionsTableArn', {
      Export: { Name: 'FinancialAssistantTransactionsTableArn' },
    });
  });
});

describe('DataStack - Sessions Table', () => {
  let template: Template;

  beforeAll(() => {
    const app = new cdk.App();
    const stack = new DataStack(app, 'TestDataStack2', {
      env: { account: '123456789012', region: 'us-east-1' },
    });
    template = Template.fromStack(stack);
  });

  test('creates sessions table with correct name', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'financial-assistant-sessions',
    });
  });

  test('sessions table has session_id as partition key', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'financial-assistant-sessions',
      KeySchema: Match.arrayWith([
        { AttributeName: 'session_id', KeyType: 'HASH' },
      ]),
    });
  });

  test('sessions table has timestamp as sort key (Number)', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'financial-assistant-sessions',
      KeySchema: Match.arrayWith([
        { AttributeName: 'timestamp', KeyType: 'RANGE' },
      ]),
      AttributeDefinitions: Match.arrayWith([
        { AttributeName: 'timestamp', AttributeType: 'N' },
      ]),
    });
  });

  test('sessions table uses on-demand billing (PAY_PER_REQUEST)', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'financial-assistant-sessions',
      BillingMode: 'PAY_PER_REQUEST',
    });
  });

  test('sessions table has TTL enabled on ttl attribute', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'financial-assistant-sessions',
      TimeToLiveSpecification: {
        AttributeName: 'ttl',
        Enabled: true,
      },
    });
  });

  test('sessions table has DESTROY removal policy', () => {
    template.hasResource('AWS::DynamoDB::Table', {
      Properties: Match.objectLike({
        TableName: 'financial-assistant-sessions',
      }),
      DeletionPolicy: 'Delete',
      UpdateReplacePolicy: 'Delete',
    });
  });

  test('exports sessions table name as CfnOutput', () => {
    template.hasOutput('SessionsTableName', {
      Value: Match.objectLike({ Ref: Match.anyValue() }),
      Export: { Name: 'FinancialAssistantSessionsTableName' },
    });
  });

  test('exports sessions table ARN as CfnOutput', () => {
    template.hasOutput('SessionsTableArn', {
      Export: { Name: 'FinancialAssistantSessionsTableArn' },
    });
  });

  test('sessionsTable is exposed as a public property', () => {
    const app = new cdk.App();
    const stack = new DataStack(app, 'TestDataStackProp', {
      env: { account: '123456789012', region: 'us-east-1' },
    });
    expect(stack.sessionsTable).toBeDefined();
    expect(stack.sessionsTable).toBeInstanceOf(dynamodb.Table);
  });
});


describe('DataStack - Clients Table', () => {
  let template: Template;

  beforeAll(() => {
    const app = new cdk.App();
    const stack = new DataStack(app, 'TestDataStackClients', {
      env: { account: '123456789012', region: 'us-east-1' },
    });
    template = Template.fromStack(stack);
  });

  test('creates clients table with correct name', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'financial-assistant-clients',
    });
  });

  test('clients table has client_id as partition key', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'financial-assistant-clients',
      KeySchema: [{ AttributeName: 'client_id', KeyType: 'HASH' }],
    });
  });

  test('clients table has no sort key (only partition key)', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'financial-assistant-clients',
      KeySchema: [{ AttributeName: 'client_id', KeyType: 'HASH' }],
      AttributeDefinitions: [
        { AttributeName: 'client_id', AttributeType: 'S' },
      ],
    });
  });

  test('clients table uses on-demand billing (PAY_PER_REQUEST)', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'financial-assistant-clients',
      BillingMode: 'PAY_PER_REQUEST',
    });
  });

  test('clients table has DESTROY removal policy', () => {
    template.hasResource('AWS::DynamoDB::Table', {
      Properties: Match.objectLike({
        TableName: 'financial-assistant-clients',
      }),
      DeletionPolicy: 'Delete',
      UpdateReplacePolicy: 'Delete',
    });
  });

  test('exports clients table name as CfnOutput', () => {
    template.hasOutput('ClientsTableName', {
      Value: Match.objectLike({ Ref: Match.anyValue() }),
      Export: { Name: 'FinancialAssistantClientsTableName' },
    });
  });

  test('exports clients table ARN as CfnOutput', () => {
    template.hasOutput('ClientsTableArn', {
      Export: { Name: 'FinancialAssistantClientsTableArn' },
    });
  });

  test('clientsTable is exposed as a public property', () => {
    const app = new cdk.App();
    const stack = new DataStack(app, 'TestDataStackClientsProp', {
      env: { account: '123456789012', region: 'us-east-1' },
    });
    expect(stack.clientsTable).toBeDefined();
    expect(stack.clientsTable).toBeInstanceOf(dynamodb.Table);
  });
});
