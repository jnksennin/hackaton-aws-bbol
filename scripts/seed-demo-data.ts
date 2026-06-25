/**
 * Seed script para insertar datos demo de clientes en DynamoDB.
 *
 * Ejecutar después del deploy:
 *   npx ts-node scripts/seed-demo-data.ts
 *
 * Requirement: 8.4
 */
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, PutCommand } from '@aws-sdk/lib-dynamodb';

const TABLE_NAME = 'financial-assistant-clients';

interface Client {
  client_id: string;
  name: string;
  email: string;
  profile_type: 'healthy' | 'regular' | 'critical';
  monthly_income: number;
  monthly_fixed_expenses: number;
  savings_balance: number;
  debt_balance: number;
  created_at: string;
}

const demoClients: Client[] = [
  {
    client_id: 'client-001',
    name: 'María Profesional',
    email: 'maria@example.com',
    profile_type: 'healthy',
    monthly_income: 1800,
    monthly_fixed_expenses: 900,
    savings_balance: 5000,
    debt_balance: 2000,
    created_at: '2025-01-01T00:00:00Z',
  },
  {
    client_id: 'client-002',
    name: 'Carlos Emprendedor',
    email: 'carlos@example.com',
    profile_type: 'regular',
    monthly_income: 1500,
    monthly_fixed_expenses: 1100,
    savings_balance: 1200,
    debt_balance: 4500,
    created_at: '2025-01-01T00:00:00Z',
  },
  {
    client_id: 'client-003',
    name: 'Ana Estudiante',
    email: 'ana@example.com',
    profile_type: 'critical',
    monthly_income: 600,
    monthly_fixed_expenses: 550,
    savings_balance: 100,
    debt_balance: 1500,
    created_at: '2025-01-01T00:00:00Z',
  },
];

async function seedClients(): Promise<void> {
  const client = new DynamoDBClient({});
  const docClient = DynamoDBDocumentClient.from(client);

  console.log(`Seeding ${demoClients.length} clients into ${TABLE_NAME}...`);

  for (const item of demoClients) {
    await docClient.send(
      new PutCommand({
        TableName: TABLE_NAME,
        Item: item,
      })
    );
    console.log(`  ✓ Inserted ${item.name} (${item.client_id}) - ISF profile: ${item.profile_type}`);
  }

  console.log('\nSeed complete!');
}

seedClients().catch((err) => {
  console.error('Error seeding clients:', err);
  process.exit(1);
});
