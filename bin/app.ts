#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { BedrockAgentStack } from '../lib/stacks/bedrock-agent-stack';
import { KnowledgeBaseStack } from '../lib/stacks/knowledge-base-stack';
import { GuardrailsStack } from '../lib/stacks/guardrails-stack';
import { DataStack } from '../lib/stacks/data-stack';

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
};

// Data stack (DynamoDB tables)
const dataStack = new DataStack(app, 'FinancialHealthAssistantDataStack', {
  env,
  description: 'DynamoDB tables - Transactions, Sessions, Clients',
});

// Guardrails stack (must be created before Agent stack)
const guardrailsStack = new GuardrailsStack(app, 'FinancialHealthAssistantGuardrailsStack', {
  env,
  description: 'Guardrails de seguridad - PII filtering, Topic blocking, Content moderation',
});

// Agent stack with Guardrail association
const agentStack = new BedrockAgentStack(app, 'FinancialHealthAssistantAgentStack', {
  env,
  description: 'Asistente de Salud Financiera Agéntico - Bedrock Agent + Action Groups',
  guardrailId: guardrailsStack.guardrailId,
  guardrailVersion: guardrailsStack.guardrailVersion,
});
agentStack.addDependency(guardrailsStack);
agentStack.addDependency(dataStack);

new KnowledgeBaseStack(app, 'FinancialHealthAssistantKBStack', {
  env,
  description: 'Knowledge Base de productos financieros - OpenSearch Serverless + Titan Embeddings',
});

app.synth();
