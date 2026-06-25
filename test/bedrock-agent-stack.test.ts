import * as cdk from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import { BedrockAgentStack } from '../lib/stacks/bedrock-agent-stack';

describe('BedrockAgentStack', () => {
  let template: Template;

  beforeAll(() => {
    const app = new cdk.App();
    const stack = new BedrockAgentStack(app, 'TestStack', {
      env: { account: '123456789012', region: 'us-east-1' },
    });
    template = Template.fromStack(stack);
  });

  test('creates Bedrock Agent with correct name and model', () => {
    template.hasResourceProperties('AWS::Bedrock::Agent', {
      AgentName: 'financial-health-assistant-agent',
      FoundationModel: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
    });
  });

  test('configures 4 action groups', () => {
    template.hasResourceProperties('AWS::Bedrock::Agent', {
      ActionGroups: [
        { ActionGroupName: 'calculate-isf' },
        { ActionGroupName: 'analyze-transactions' },
        { ActionGroupName: 'check-liquidity' },
        { ActionGroupName: 'manage-session' },
      ],
    });
  });

  test('creates ISF Calculator Lambda function', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      FunctionName: 'isf-calculator',
      Runtime: 'python3.12',
      Timeout: 30,
    });
  });

  test('creates Transaction Analyzer Lambda function', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      FunctionName: 'transaction-analyzer',
      Runtime: 'python3.12',
      Timeout: 30,
    });
  });

  test('creates Liquidity Alerter Lambda function', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      FunctionName: 'liquidity-alerter',
      Runtime: 'python3.12',
      Timeout: 30,
    });
  });

  test('creates Session Manager Lambda function', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      FunctionName: 'session-manager',
      Runtime: 'python3.12',
      Timeout: 30,
    });
  });

  test('creates S3 bucket for schemas', () => {
    template.hasResourceProperties('AWS::S3::Bucket', {
      BucketName: 'financial-agent-schemas-123456789012',
    });
  });

  test('creates Bedrock Agent Alias', () => {
    template.hasResourceProperties('AWS::Bedrock::AgentAlias', {
      AgentAliasName: 'live',
    });
  });

  test('agent has system prompt with financial advisor personality', () => {
    template.hasResourceProperties('AWS::Bedrock::Agent', {
      Instruction: Match.stringLikeRegexp('asesor financiero virtual del Banco Bolivariano'),
    });
  });

  test('agent role allows invoking Claude 3.5 Sonnet model', () => {
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Action: 'bedrock:InvokeModel',
            Effect: 'Allow',
          }),
        ]),
      },
    });
  });

  test('Lambda functions have permission for Bedrock Agent invoke', () => {
    template.hasResourceProperties('AWS::Lambda::Permission', {
      Action: 'lambda:InvokeFunction',
      Principal: 'bedrock.amazonaws.com',
    });
  });
});
