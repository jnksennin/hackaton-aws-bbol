import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as opensearchserverless from 'aws-cdk-lib/aws-opensearchserverless';
import { Construct } from 'constructs';
import * as path from 'path';

/**
 * Stack para la Knowledge Base de productos financieros del Banco Bolivariano.
 *
 * Define:
 * - S3 Bucket para documentos de la Knowledge Base
 * - OpenSearch Serverless collection como vector store
 * - Bedrock Knowledge Base con Amazon Titan Embeddings G1
 * - Chunking: 300 tokens, 20% overlap (60 tokens)
 *
 * Requirements: 5.1, 5.2
 */
export class KnowledgeBaseStack extends cdk.Stack {
  public readonly knowledgeBaseId: cdk.CfnOutput;
  public readonly dataSourceId: cdk.CfnOutput;
  public readonly bucketName: cdk.CfnOutput;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ─────────────────────────────────────────────────────────────────────────
    // S3 Bucket for Knowledge Base documents
    // ─────────────────────────────────────────────────────────────────────────
    const kbDocsBucket = new s3.Bucket(this, 'KBDocsBucket', {
      bucketName: `financial-assistant-kb-docs-${this.account}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      versioned: false,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    });

    // Deploy Knowledge Base documents to S3
    new s3deploy.BucketDeployment(this, 'DeployKBDocuments', {
      sources: [s3deploy.Source.asset(path.join(__dirname, '..', '..', 'knowledge-base'))],
      destinationBucket: kbDocsBucket,
      destinationKeyPrefix: 'knowledge-base/',
    });

    // ─────────────────────────────────────────────────────────────────────────
    // OpenSearch Serverless Collection (Vector Store)
    // ─────────────────────────────────────────────────────────────────────────

    // Encryption policy (required for OpenSearch Serverless)
    const encryptionPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'OSSEncryptionPolicy', {
      name: 'financial-kb-encryption',
      type: 'encryption',
      policy: JSON.stringify({
        Rules: [
          {
            ResourceType: 'collection',
            Resource: ['collection/financial-products-kb'],
          },
        ],
        AWSOwnedKey: true,
      }),
    });

    // Network policy (allow public access for Bedrock integration)
    const networkPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'OSSNetworkPolicy', {
      name: 'financial-kb-network',
      type: 'network',
      policy: JSON.stringify([
        {
          Rules: [
            {
              ResourceType: 'collection',
              Resource: ['collection/financial-products-kb'],
            },
            {
              ResourceType: 'dashboard',
              Resource: ['collection/financial-products-kb'],
            },
          ],
          AllowFromPublic: true,
        },
      ]),
    });

    // OpenSearch Serverless Collection
    const ossCollection = new opensearchserverless.CfnCollection(this, 'FinancialProductsCollection', {
      name: 'financial-products-kb',
      type: 'VECTORSEARCH',
      description: 'Vector store para Knowledge Base de productos financieros Banco Bolivariano',
    });

    ossCollection.addDependency(encryptionPolicy);
    ossCollection.addDependency(networkPolicy);

    // ─────────────────────────────────────────────────────────────────────────
    // IAM Role for Bedrock Knowledge Base
    // ─────────────────────────────────────────────────────────────────────────
    const kbRole = new iam.Role(this, 'KnowledgeBaseRole', {
      roleName: 'financial-kb-bedrock-role',
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      description: 'Role for Bedrock Knowledge Base to access S3 and OpenSearch Serverless',
    });

    // Permission to read KB documents from S3
    kbRole.addToPolicy(new iam.PolicyStatement({
      sid: 'ReadKBDocuments',
      effect: iam.Effect.ALLOW,
      actions: ['s3:GetObject', 's3:ListBucket'],
      resources: [
        kbDocsBucket.bucketArn,
        `${kbDocsBucket.bucketArn}/*`,
      ],
    }));

    // Permission to use Amazon Titan Embeddings model
    kbRole.addToPolicy(new iam.PolicyStatement({
      sid: 'InvokeEmbeddingModel',
      effect: iam.Effect.ALLOW,
      actions: ['bedrock:InvokeModel'],
      resources: [
        `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v1`,
      ],
    }));

    // Permission to access OpenSearch Serverless
    kbRole.addToPolicy(new iam.PolicyStatement({
      sid: 'AccessOpenSearchServerless',
      effect: iam.Effect.ALLOW,
      actions: ['aoss:APIAccessAll'],
      resources: [
        `arn:aws:aoss:${this.region}:${this.account}:collection/${ossCollection.attrId}`,
      ],
    }));

    // Data access policy for OpenSearch Serverless (allow KB role to manage indexes)
    const dataAccessPolicy = new opensearchserverless.CfnAccessPolicy(this, 'OSSDataAccessPolicy', {
      name: 'financial-kb-data-access',
      type: 'data',
      policy: JSON.stringify([
        {
          Rules: [
            {
              ResourceType: 'index',
              Resource: ['index/financial-products-kb/*'],
              Permission: [
                'aoss:CreateIndex',
                'aoss:UpdateIndex',
                'aoss:DescribeIndex',
                'aoss:ReadDocument',
                'aoss:WriteDocument',
              ],
            },
            {
              ResourceType: 'collection',
              Resource: ['collection/financial-products-kb'],
              Permission: [
                'aoss:CreateCollectionItems',
                'aoss:DescribeCollectionItems',
                'aoss:UpdateCollectionItems',
              ],
            },
          ],
          Principal: [
            kbRole.roleArn,
            `arn:aws:iam::${this.account}:root`,
          ],
        },
      ]),
    });

    dataAccessPolicy.addDependency(ossCollection);

    // ─────────────────────────────────────────────────────────────────────────
    // Bedrock Knowledge Base
    // ─────────────────────────────────────────────────────────────────────────
    const knowledgeBase = new cdk.aws_bedrock.CfnKnowledgeBase(this, 'FinancialProductsKB', {
      name: 'banco-bolivariano-productos-financieros',
      description: 'Knowledge Base con información de productos financieros del Banco Bolivariano: cuentas, tarjetas, inversiones, créditos y seguros',
      roleArn: kbRole.roleArn,
      knowledgeBaseConfiguration: {
        type: 'VECTOR',
        vectorKnowledgeBaseConfiguration: {
          embeddingModelArn: `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v1`,
        },
      },
      storageConfiguration: {
        type: 'OPENSEARCH_SERVERLESS',
        opensearchServerlessConfiguration: {
          collectionArn: ossCollection.attrArn,
          vectorIndexName: 'financial-products-index',
          fieldMapping: {
            vectorField: 'embedding',
            textField: 'text',
            metadataField: 'metadata',
          },
        },
      },
    });

    knowledgeBase.addDependency(ossCollection);
    knowledgeBase.node.addDependency(kbRole);

    // ─────────────────────────────────────────────────────────────────────────
    // Bedrock Knowledge Base Data Source (S3)
    // ─────────────────────────────────────────────────────────────────────────
    const dataSource = new cdk.aws_bedrock.CfnDataSource(this, 'KBDataSource', {
      name: 'productos-financieros-docs',
      description: 'Documentos de productos financieros Banco Bolivariano en S3',
      knowledgeBaseId: knowledgeBase.attrKnowledgeBaseId,
      dataSourceConfiguration: {
        type: 'S3',
        s3Configuration: {
          bucketArn: kbDocsBucket.bucketArn,
          inclusionPrefixes: ['knowledge-base/'],
        },
      },
      vectorIngestionConfiguration: {
        chunkingConfiguration: {
          chunkingStrategy: 'FIXED_SIZE',
          fixedSizeChunkingConfiguration: {
            maxTokens: 300,
            overlapPercentage: 20,
          },
        },
      },
    });

    dataSource.addDependency(knowledgeBase);

    // ─────────────────────────────────────────────────────────────────────────
    // Outputs
    // ─────────────────────────────────────────────────────────────────────────
    this.knowledgeBaseId = new cdk.CfnOutput(this, 'KnowledgeBaseId', {
      value: knowledgeBase.attrKnowledgeBaseId,
      description: 'Bedrock Knowledge Base ID',
      exportName: 'FinancialKnowledgeBaseId',
    });

    this.dataSourceId = new cdk.CfnOutput(this, 'DataSourceId', {
      value: dataSource.attrDataSourceId,
      description: 'Knowledge Base Data Source ID',
      exportName: 'FinancialKBDataSourceId',
    });

    this.bucketName = new cdk.CfnOutput(this, 'KBDocsBucketName', {
      value: kbDocsBucket.bucketName,
      description: 'S3 Bucket for Knowledge Base documents',
      exportName: 'FinancialKBDocsBucketName',
    });

    new cdk.CfnOutput(this, 'OpenSearchCollectionEndpoint', {
      value: ossCollection.attrCollectionEndpoint,
      description: 'OpenSearch Serverless Collection endpoint',
      exportName: 'FinancialKBCollectionEndpoint',
    });

    new cdk.CfnOutput(this, 'OpenSearchCollectionArn', {
      value: ossCollection.attrArn,
      description: 'OpenSearch Serverless Collection ARN',
      exportName: 'FinancialKBCollectionArn',
    });

    // Tags
    cdk.Tags.of(this).add('Project', 'financial-health-assistant');
    cdk.Tags.of(this).add('Environment', 'hackathon');
    cdk.Tags.of(this).add('Team', 'banco-bolivariano');
    cdk.Tags.of(this).add('Component', 'knowledge-base');
  }
}
