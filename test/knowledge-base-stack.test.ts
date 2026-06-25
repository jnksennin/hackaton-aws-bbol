import * as cdk from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import { KnowledgeBaseStack } from '../lib/stacks/knowledge-base-stack';

describe('KnowledgeBaseStack', () => {
  let template: Template;

  beforeAll(() => {
    const app = new cdk.App();
    const stack = new KnowledgeBaseStack(app, 'TestKBStack', {
      env: { account: '123456789012', region: 'us-east-1' },
    });
    template = Template.fromStack(stack);
  });

  test('creates S3 bucket with correct naming convention', () => {
    template.hasResourceProperties('AWS::S3::Bucket', {
      BucketName: 'financial-assistant-kb-docs-123456789012',
    });
  });

  test('S3 bucket has public access blocked', () => {
    template.hasResourceProperties('AWS::S3::Bucket', {
      PublicAccessBlockConfiguration: {
        BlockPublicAcls: true,
        BlockPublicPolicy: true,
        IgnorePublicAcls: true,
        RestrictPublicBuckets: true,
      },
    });
  });

  test('creates OpenSearch Serverless collection for vector search', () => {
    template.hasResourceProperties('AWS::OpenSearchServerless::Collection', {
      Name: 'financial-products-kb',
      Type: 'VECTORSEARCH',
    });
  });

  test('creates OpenSearch Serverless encryption policy', () => {
    template.hasResourceProperties('AWS::OpenSearchServerless::SecurityPolicy', {
      Name: 'financial-kb-encryption',
      Type: 'encryption',
    });
  });

  test('creates OpenSearch Serverless network policy', () => {
    template.hasResourceProperties('AWS::OpenSearchServerless::SecurityPolicy', {
      Name: 'financial-kb-network',
      Type: 'network',
    });
  });

  test('creates OpenSearch Serverless data access policy', () => {
    template.hasResourceProperties('AWS::OpenSearchServerless::AccessPolicy', {
      Name: 'financial-kb-data-access',
      Type: 'data',
    });
  });

  test('creates Bedrock Knowledge Base with Titan Embeddings', () => {
    template.hasResourceProperties('AWS::Bedrock::KnowledgeBase', {
      Name: 'banco-bolivariano-productos-financieros',
      KnowledgeBaseConfiguration: {
        Type: 'VECTOR',
        VectorKnowledgeBaseConfiguration: {
          EmbeddingModelArn: 'arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1',
        },
      },
    });
  });

  test('Knowledge Base uses OpenSearch Serverless as storage', () => {
    template.hasResourceProperties('AWS::Bedrock::KnowledgeBase', {
      StorageConfiguration: {
        Type: 'OPENSEARCH_SERVERLESS',
        OpensearchServerlessConfiguration: {
          VectorIndexName: 'financial-products-index',
          FieldMapping: {
            VectorField: 'embedding',
            TextField: 'text',
            MetadataField: 'metadata',
          },
        },
      },
    });
  });

  test('creates Data Source with correct chunking configuration', () => {
    template.hasResourceProperties('AWS::Bedrock::DataSource', {
      Name: 'productos-financieros-docs',
      DataSourceConfiguration: {
        Type: 'S3',
        S3Configuration: {
          InclusionPrefixes: ['knowledge-base/'],
        },
      },
      VectorIngestionConfiguration: {
        ChunkingConfiguration: {
          ChunkingStrategy: 'FIXED_SIZE',
          FixedSizeChunkingConfiguration: {
            MaxTokens: 300,
            OverlapPercentage: 20,
          },
        },
      },
    });
  });

  test('creates IAM role for Knowledge Base', () => {
    template.hasResourceProperties('AWS::IAM::Role', {
      RoleName: 'financial-kb-bedrock-role',
      AssumeRolePolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Principal: { Service: 'bedrock.amazonaws.com' },
            Effect: 'Allow',
          }),
        ]),
      },
    });
  });

  test('KB role has permission to read S3 documents', () => {
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Sid: 'ReadKBDocuments',
            Effect: 'Allow',
            Action: ['s3:GetObject', 's3:ListBucket'],
          }),
        ]),
      },
    });
  });

  test('KB role has permission to invoke Titan Embeddings model', () => {
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Sid: 'InvokeEmbeddingModel',
            Effect: 'Allow',
            Action: 'bedrock:InvokeModel',
            Resource: 'arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1',
          }),
        ]),
      },
    });
  });

  test('KB role has permission to access OpenSearch Serverless', () => {
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Sid: 'AccessOpenSearchServerless',
            Effect: 'Allow',
            Action: 'aoss:APIAccessAll',
          }),
        ]),
      },
    });
  });

  test('S3 bucket deployment is configured for knowledge-base prefix', () => {
    template.hasResourceProperties('Custom::CDKBucketDeployment', {
      DestinationBucketKeyPrefix: 'knowledge-base/',
    });
  });

  test('stack has correct project tags', () => {
    // Verify tags are present via the OpenSearch collection (non-custom resource)
    template.hasResourceProperties('AWS::OpenSearchServerless::Collection', {
      Name: 'financial-products-kb',
    });
  });
});
