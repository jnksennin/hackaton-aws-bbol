/**
 * Seed script para generar datos transaccionales simulados realistas.
 *
 * Genera 60-80 transacciones/mes por cliente durante los últimos 2 meses.
 * Incluye gastos hormiga, suscripciones recurrentes, salarios y gastos fijos.
 *
 * Ejecutar después del deploy:
 *   npx ts-node scripts/seed-transactions.ts
 *
 * Requirement: 8.4
 */
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import {
  DynamoDBDocumentClient,
  BatchWriteCommand,
} from '@aws-sdk/lib-dynamodb';

const TABLE_NAME = 'financial-assistant-transactions';

// ─────────────────────────────────────────────────────────────────────────────
// Seeded Random Number Generator (deterministic for reproducibility)
// ─────────────────────────────────────────────────────────────────────────────
class SeededRandom {
  private seed: number;

  constructor(seed: number) {
    this.seed = seed;
  }

  next(): number {
    this.seed = (this.seed * 1664525 + 1013904223) & 0xffffffff;
    return (this.seed >>> 0) / 0xffffffff;
  }

  nextInt(min: number, max: number): number {
    return Math.floor(this.next() * (max - min + 1)) + min;
  }

  nextFloat(min: number, max: number): number {
    return this.next() * (max - min) + min;
  }

  pick<T>(arr: T[]): T {
    return arr[this.nextInt(0, arr.length - 1)];
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Transaction Interface
// ─────────────────────────────────────────────────────────────────────────────
interface Transaction {
  client_id: string;
  transaction_id: string;
  amount: number;
  category: string;
  merchant: string;
  date: string;
  type: 'income' | 'expense';
  description?: string;
  metadata?: {
    is_recurring?: boolean;
    subscription_id?: string;
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Merchants by Category (Ecuadorian context)
// ─────────────────────────────────────────────────────────────────────────────
const MERCHANTS = {
  groceries: ['Supermaxi', 'Mi Comisariato', 'Megamaxi', 'TIA', 'Coral Hipermercados'],
  restaurants: ['KFC Ecuador', 'McDonald\'s', 'El Español', 'La Canoa', 'Crepes & Waffles'],
  coffee_snacks: ['Sweet & Coffee', 'Juan Valdez', 'Pacari Chocolate', 'Café Galletti', 'El Café de Tere'],
  transport: ['Uber', 'Cabify', 'InDriver', 'Gasolinera Primax', 'Gasolinera PDV'],
  subscriptions: ['Netflix', 'Spotify', 'Amazon Prime', 'Disney+', 'HBO Max', 'SmartFit Gym', 'iCloud', 'Google One'],
  utilities: ['Empresa Eléctrica', 'Interagua', 'Claro', 'CNT', 'Movistar'],
  entertainment: ['Cinemark', 'Supercines', 'Fybeca', 'Marathon Sports'],
  health: ['Fybeca', 'Farmacias SanaSana', 'Medicity', 'Clínica Kennedy'],
  education: ['Udemy', 'Coursera', 'Librería Mr. Books', 'Papelería Nacional'],
  shopping: ['De Prati', 'Etafashion', 'Mercado Libre', 'Amazon'],
};

// ─────────────────────────────────────────────────────────────────────────────
// Subscription definitions (recurring monthly charges)
// ─────────────────────────────────────────────────────────────────────────────
interface SubscriptionDef {
  merchant: string;
  amount: number;
  category: string;
  subscriptionId: string;
}

const SUBSCRIPTIONS: Record<string, SubscriptionDef[]> = {
  'client-001': [
    { merchant: 'Netflix', amount: 15.99, category: 'subscriptions', subscriptionId: 'sub-netflix-001' },
    { merchant: 'Spotify', amount: 9.99, category: 'subscriptions', subscriptionId: 'sub-spotify-001' },
    { merchant: 'SmartFit Gym', amount: 45.00, category: 'subscriptions', subscriptionId: 'sub-gym-001' },
    { merchant: 'iCloud', amount: 2.99, category: 'subscriptions', subscriptionId: 'sub-icloud-001' },
  ],
  'client-002': [
    { merchant: 'Netflix', amount: 15.99, category: 'subscriptions', subscriptionId: 'sub-netflix-002' },
    { merchant: 'Spotify', amount: 9.99, category: 'subscriptions', subscriptionId: 'sub-spotify-002' },
    { merchant: 'SmartFit Gym', amount: 45.00, category: 'subscriptions', subscriptionId: 'sub-gym-002' },
    { merchant: 'Amazon Prime', amount: 7.99, category: 'subscriptions', subscriptionId: 'sub-prime-002' },
    { merchant: 'Disney+', amount: 12.99, category: 'subscriptions', subscriptionId: 'sub-disney-002' },
    { merchant: 'Google One', amount: 2.99, category: 'subscriptions', subscriptionId: 'sub-google-002' },
  ],
  'client-003': [
    { merchant: 'Spotify', amount: 9.99, category: 'subscriptions', subscriptionId: 'sub-spotify-003' },
    { merchant: 'Netflix', amount: 15.99, category: 'subscriptions', subscriptionId: 'sub-netflix-003' },
    { merchant: 'Google One', amount: 2.99, category: 'subscriptions', subscriptionId: 'sub-google-003' },
  ],
};

// ─────────────────────────────────────────────────────────────────────────────
// Client profiles for transaction generation
// ─────────────────────────────────────────────────────────────────────────────
interface ClientProfile {
  clientId: string;
  name: string;
  monthlyIncome: number;
  // Gastos hormiga config
  gastosHormigaDailyFrequency: number; // average small purchases per day
  gastosHormigaMinAmount: number;
  gastosHormigaMaxAmount: number;
  // Regular expenses distribution
  groceriesPerMonth: number;
  groceriesMin: number;
  groceriesMax: number;
  restaurantsPerMonth: number;
  restaurantsMin: number;
  restaurantsMax: number;
  transportPerMonth: number;
  transportMin: number;
  transportMax: number;
  utilitiesPerMonth: number;
  utilitiesAmount: number;
  entertainmentPerMonth: number;
  entertainmentMin: number;
  entertainmentMax: number;
  healthPerMonth: number;
  healthMin: number;
  healthMax: number;
  shoppingPerMonth: number;
  shoppingMin: number;
  shoppingMax: number;
  // Savings & debt
  savingsPerMonth: number;
  savingsAmount: number;
  debtPaymentPerMonth: number;
  debtPaymentAmount: number;
}

const CLIENT_PROFILES: ClientProfile[] = [
  {
    // María: healthy profile, moderate gastos hormiga (<10% income)
    // Income $1800, target gastos hormiga ~$120/month (~6.7% of income)
    // Target txns/month: 1+4+4+30+8+5+8+3+1+2+1+1 = 68
    clientId: 'client-001',
    name: 'María',
    monthlyIncome: 1800,
    gastosHormigaDailyFrequency: 1.0,  // ~30 per month
    gastosHormigaMinAmount: 2.00,
    gastosHormigaMaxAmount: 6.50,
    groceriesPerMonth: 8,
    groceriesMin: 25,
    groceriesMax: 85,
    restaurantsPerMonth: 5,
    restaurantsMin: 12,
    restaurantsMax: 35,
    transportPerMonth: 8,
    transportMin: 3,
    transportMax: 15,
    utilitiesPerMonth: 4,
    utilitiesAmount: 45,
    entertainmentPerMonth: 3,
    entertainmentMin: 10,
    entertainmentMax: 40,
    healthPerMonth: 1,
    healthMin: 15,
    healthMax: 50,
    shoppingPerMonth: 2,
    shoppingMin: 20,
    shoppingMax: 80,
    savingsPerMonth: 1,
    savingsAmount: 300,
    debtPaymentPerMonth: 1,
    debtPaymentAmount: 150,
  },
  {
    // Carlos: regular profile, HIGH gastos hormiga (>15% income = >$225/month)
    // Income $1500, target gastos hormiga ~$270/month (~18% of income)
    // Higher amounts per transaction to reach 18% with fewer txns
    // Target txns/month: 1+6+4+38+6+6+4+3+1+2+1+1 = 73
    clientId: 'client-002',
    name: 'Carlos',
    monthlyIncome: 1500,
    gastosHormigaDailyFrequency: 1.25,  // ~38 per month
    gastosHormigaMinAmount: 4.50,
    gastosHormigaMaxAmount: 9.50,
    groceriesPerMonth: 6,
    groceriesMin: 20,
    groceriesMax: 65,
    restaurantsPerMonth: 6,
    restaurantsMin: 10,
    restaurantsMax: 30,
    transportPerMonth: 4,
    transportMin: 3,
    transportMax: 12,
    utilitiesPerMonth: 4,
    utilitiesAmount: 55,
    entertainmentPerMonth: 3,
    entertainmentMin: 8,
    entertainmentMax: 35,
    healthPerMonth: 1,
    healthMin: 10,
    healthMax: 30,
    shoppingPerMonth: 2,
    shoppingMin: 15,
    shoppingMax: 60,
    savingsPerMonth: 1,
    savingsAmount: 100,
    debtPaymentPerMonth: 1,
    debtPaymentAmount: 200,
  },
  {
    // Ana: critical profile, significant gastos hormiga relative to income
    // Income $600, target gastos hormiga ~$80/month (~13% of income)
    // Target txns/month: 1+3+3+35+6+3+6+2+1+1+0+1 = 62
    clientId: 'client-003',
    name: 'Ana',
    monthlyIncome: 600,
    gastosHormigaDailyFrequency: 1.15,  // ~35 per month
    gastosHormigaMinAmount: 1.00,
    gastosHormigaMaxAmount: 5.50,
    groceriesPerMonth: 6,
    groceriesMin: 10,
    groceriesMax: 40,
    restaurantsPerMonth: 3,
    restaurantsMin: 5,
    restaurantsMax: 15,
    transportPerMonth: 6,
    transportMin: 1.50,
    transportMax: 5,
    utilitiesPerMonth: 3,
    utilitiesAmount: 35,
    entertainmentPerMonth: 2,
    entertainmentMin: 5,
    entertainmentMax: 15,
    healthPerMonth: 1,
    healthMin: 8,
    healthMax: 25,
    shoppingPerMonth: 1,
    shoppingMin: 10,
    shoppingMax: 30,
    savingsPerMonth: 0,
    savingsAmount: 0,
    debtPaymentPerMonth: 1,
    debtPaymentAmount: 75,
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// UUID v4 generator (simple, deterministic from seeded random)
// ─────────────────────────────────────────────────────────────────────────────
function generateUUID(rng: SeededRandom): string {
  const hex = '0123456789abcdef';
  let uuid = '';
  for (let i = 0; i < 36; i++) {
    if (i === 8 || i === 13 || i === 18 || i === 23) {
      uuid += '-';
    } else if (i === 14) {
      uuid += '4';
    } else if (i === 19) {
      uuid += hex[rng.nextInt(8, 11)];
    } else {
      uuid += hex[rng.nextInt(0, 15)];
    }
  }
  return uuid;
}

// ─────────────────────────────────────────────────────────────────────────────
// Date utilities
// ─────────────────────────────────────────────────────────────────────────────
function getDateRange(): { start: Date; end: Date } {
  const end = new Date();
  end.setHours(23, 59, 59, 999);
  const start = new Date(end);
  start.setDate(start.getDate() - 60); // 2 months back
  start.setHours(0, 0, 0, 0);
  return { start, end };
}

function randomDateInMonth(
  year: number,
  month: number,
  day: number,
  rng: SeededRandom
): string {
  const hour = rng.nextInt(7, 22);
  const minute = rng.nextInt(0, 59);
  const second = rng.nextInt(0, 59);
  const d = new Date(year, month, day, hour, minute, second);
  return d.toISOString();
}

function getMonthDays(start: Date, end: Date): Date[][] {
  const months: Date[][] = [];
  let current = new Date(start);
  let currentMonth: Date[] = [];
  let lastMonth = current.getMonth();

  while (current <= end) {
    if (current.getMonth() !== lastMonth) {
      if (currentMonth.length > 0) months.push(currentMonth);
      currentMonth = [];
      lastMonth = current.getMonth();
    }
    currentMonth.push(new Date(current));
    current.setDate(current.getDate() + 1);
  }
  if (currentMonth.length > 0) months.push(currentMonth);
  return months;
}

// ─────────────────────────────────────────────────────────────────────────────
// Transaction generation logic
// ─────────────────────────────────────────────────────────────────────────────
function generateTransactionsForClient(
  profile: ClientProfile,
  rng: SeededRandom
): Transaction[] {
  const transactions: Transaction[] = [];
  const { start, end } = getDateRange();
  const months = getMonthDays(start, end);

  for (const monthDays of months) {
    const year = monthDays[0].getFullYear();
    const month = monthDays[0].getMonth();
    const daysInMonth = monthDays.length;

    // 1. SALARY (income) - deposited on 1st or 15th of month
    const salaryDay = monthDays.find(d => d.getDate() === 1 || d.getDate() === 15) || monthDays[0];
    transactions.push({
      client_id: profile.clientId,
      transaction_id: generateUUID(rng),
      amount: profile.monthlyIncome,
      category: 'salary',
      merchant: 'Banco Bolivariano - Nómina',
      date: randomDateInMonth(year, month, salaryDay.getDate(), rng),
      type: 'income',
      description: 'Depósito de nómina mensual',
      metadata: { is_recurring: true },
    });

    // 2. SUBSCRIPTIONS (recurring, same day each month)
    const clientSubs = SUBSCRIPTIONS[profile.clientId] || [];
    for (const sub of clientSubs) {
      const subDay = Math.min(rng.nextInt(1, 5), daysInMonth);
      const subDayDate = monthDays.find(d => d.getDate() === subDay) || monthDays[0];
      transactions.push({
        client_id: profile.clientId,
        transaction_id: generateUUID(rng),
        amount: sub.amount,
        category: sub.category,
        merchant: sub.merchant,
        date: randomDateInMonth(year, month, subDayDate.getDate(), rng),
        type: 'expense',
        description: `Suscripción mensual ${sub.merchant}`,
        metadata: { is_recurring: true, subscription_id: sub.subscriptionId },
      });
    }

    // 3. UTILITIES (fixed monthly bills)
    for (let i = 0; i < profile.utilitiesPerMonth; i++) {
      const utilDay = monthDays[rng.nextInt(0, Math.min(14, daysInMonth - 1))];
      const utilMerchant = rng.pick(MERCHANTS.utilities);
      const variation = rng.nextFloat(0.9, 1.1);
      transactions.push({
        client_id: profile.clientId,
        transaction_id: generateUUID(rng),
        amount: Math.round(profile.utilitiesAmount * variation * 100) / 100,
        category: 'utilities',
        merchant: utilMerchant,
        date: randomDateInMonth(year, month, utilDay.getDate(), rng),
        type: 'expense',
        description: `Pago servicios ${utilMerchant}`,
        metadata: { is_recurring: true },
      });
    }

    // 4. GASTOS HORMIGA (small, frequent purchases <$10)
    const totalHormiga = Math.round(profile.gastosHormigaDailyFrequency * daysInMonth);
    for (let i = 0; i < totalHormiga; i++) {
      const day = monthDays[rng.nextInt(0, daysInMonth - 1)];
      const isCoffee = rng.next() < 0.5;
      const merchant = isCoffee
        ? rng.pick(MERCHANTS.coffee_snacks)
        : rng.pick([...MERCHANTS.coffee_snacks, ...MERCHANTS.entertainment.slice(0, 2)]);
      const amount = rng.nextFloat(profile.gastosHormigaMinAmount, profile.gastosHormigaMaxAmount);
      const descriptions = isCoffee
        ? ['Café', 'Cappuccino', 'Café con leche', 'Latte', 'Snack', 'Galletas', 'Brownie']
        : ['Snack', 'Bebida', 'Dulce', 'Compra rápida', 'App purchase'];
      transactions.push({
        client_id: profile.clientId,
        transaction_id: generateUUID(rng),
        amount: Math.round(amount * 100) / 100,
        category: 'coffee_snacks',
        merchant,
        date: randomDateInMonth(year, month, day.getDate(), rng),
        type: 'expense',
        description: rng.pick(descriptions),
      });
    }

    // 5. GROCERIES
    for (let i = 0; i < profile.groceriesPerMonth; i++) {
      const day = monthDays[rng.nextInt(0, daysInMonth - 1)];
      transactions.push({
        client_id: profile.clientId,
        transaction_id: generateUUID(rng),
        amount: Math.round(rng.nextFloat(profile.groceriesMin, profile.groceriesMax) * 100) / 100,
        category: 'groceries',
        merchant: rng.pick(MERCHANTS.groceries),
        date: randomDateInMonth(year, month, day.getDate(), rng),
        type: 'expense',
        description: 'Compras de supermercado',
      });
    }

    // 6. RESTAURANTS
    for (let i = 0; i < profile.restaurantsPerMonth; i++) {
      const day = monthDays[rng.nextInt(0, daysInMonth - 1)];
      transactions.push({
        client_id: profile.clientId,
        transaction_id: generateUUID(rng),
        amount: Math.round(rng.nextFloat(profile.restaurantsMin, profile.restaurantsMax) * 100) / 100,
        category: 'restaurants',
        merchant: rng.pick(MERCHANTS.restaurants),
        date: randomDateInMonth(year, month, day.getDate(), rng),
        type: 'expense',
        description: 'Comida en restaurante',
      });
    }

    // 7. TRANSPORT
    for (let i = 0; i < profile.transportPerMonth; i++) {
      const day = monthDays[rng.nextInt(0, daysInMonth - 1)];
      transactions.push({
        client_id: profile.clientId,
        transaction_id: generateUUID(rng),
        amount: Math.round(rng.nextFloat(profile.transportMin, profile.transportMax) * 100) / 100,
        category: 'transport',
        merchant: rng.pick(MERCHANTS.transport),
        date: randomDateInMonth(year, month, day.getDate(), rng),
        type: 'expense',
        description: 'Transporte',
      });
    }

    // 8. ENTERTAINMENT
    for (let i = 0; i < profile.entertainmentPerMonth; i++) {
      const day = monthDays[rng.nextInt(0, daysInMonth - 1)];
      transactions.push({
        client_id: profile.clientId,
        transaction_id: generateUUID(rng),
        amount: Math.round(rng.nextFloat(profile.entertainmentMin, profile.entertainmentMax) * 100) / 100,
        category: 'entertainment',
        merchant: rng.pick(MERCHANTS.entertainment),
        date: randomDateInMonth(year, month, day.getDate(), rng),
        type: 'expense',
        description: 'Entretenimiento',
      });
    }

    // 9. HEALTH
    for (let i = 0; i < profile.healthPerMonth; i++) {
      const day = monthDays[rng.nextInt(0, daysInMonth - 1)];
      transactions.push({
        client_id: profile.clientId,
        transaction_id: generateUUID(rng),
        amount: Math.round(rng.nextFloat(profile.healthMin, profile.healthMax) * 100) / 100,
        category: 'health',
        merchant: rng.pick(MERCHANTS.health),
        date: randomDateInMonth(year, month, day.getDate(), rng),
        type: 'expense',
        description: 'Salud / Farmacia',
      });
    }

    // 10. SHOPPING
    for (let i = 0; i < profile.shoppingPerMonth; i++) {
      const day = monthDays[rng.nextInt(0, daysInMonth - 1)];
      transactions.push({
        client_id: profile.clientId,
        transaction_id: generateUUID(rng),
        amount: Math.round(rng.nextFloat(profile.shoppingMin, profile.shoppingMax) * 100) / 100,
        category: 'shopping',
        merchant: rng.pick(MERCHANTS.shopping),
        date: randomDateInMonth(year, month, day.getDate(), rng),
        type: 'expense',
        description: 'Compras varias',
      });
    }

    // 11. SAVINGS transfer (if applicable)
    if (profile.savingsPerMonth > 0) {
      const savingsDay = monthDays.find(d => d.getDate() === 5) || monthDays[2];
      transactions.push({
        client_id: profile.clientId,
        transaction_id: generateUUID(rng),
        amount: profile.savingsAmount,
        category: 'savings',
        merchant: 'Banco Bolivariano - Ahorro Programado',
        date: randomDateInMonth(year, month, savingsDay.getDate(), rng),
        type: 'expense',
        description: 'Transferencia a cuenta de ahorros',
        metadata: { is_recurring: true },
      });
    }

    // 12. DEBT PAYMENT (if applicable)
    if (profile.debtPaymentPerMonth > 0) {
      const debtDay = monthDays.find(d => d.getDate() === 20) || monthDays[Math.min(19, daysInMonth - 1)];
      transactions.push({
        client_id: profile.clientId,
        transaction_id: generateUUID(rng),
        amount: profile.debtPaymentAmount,
        category: 'debt_payment',
        merchant: 'Banco Bolivariano - Cuota Préstamo',
        date: randomDateInMonth(year, month, debtDay.getDate(), rng),
        type: 'expense',
        description: 'Pago cuota de préstamo',
        metadata: { is_recurring: true },
      });
    }
  }

  return transactions;
}

// ─────────────────────────────────────────────────────────────────────────────
// Batch write to DynamoDB (25 items per batch, DynamoDB limit)
// ─────────────────────────────────────────────────────────────────────────────
async function batchWriteTransactions(
  docClient: DynamoDBDocumentClient,
  transactions: Transaction[]
): Promise<void> {
  const BATCH_SIZE = 25;
  let written = 0;

  for (let i = 0; i < transactions.length; i += BATCH_SIZE) {
    const batch = transactions.slice(i, i + BATCH_SIZE);
    const putRequests = batch.map((item) => ({
      PutRequest: { Item: item },
    }));

    await docClient.send(
      new BatchWriteCommand({
        RequestItems: {
          [TABLE_NAME]: putRequests,
        },
      })
    );

    written += batch.length;
    if (written % 100 === 0 || written === transactions.length) {
      process.stdout.write(`\r  Escritas ${written}/${transactions.length} transacciones...`);
    }
  }
  console.log('');
}

// ─────────────────────────────────────────────────────────────────────────────
// Main execution
// ─────────────────────────────────────────────────────────────────────────────
async function main(): Promise<void> {
  const client = new DynamoDBClient({});
  const docClient = DynamoDBDocumentClient.from(client);

  console.log('╔══════════════════════════════════════════════════════════════╗');
  console.log('║  Seed: Transacciones Simuladas - Asistente Salud Financiera ║');
  console.log('╚══════════════════════════════════════════════════════════════╝');
  console.log(`\nTabla destino: ${TABLE_NAME}`);
  console.log(`Período: últimos 60 días\n`);

  let totalTransactions = 0;

  for (const profile of CLIENT_PROFILES) {
    const seed = profile.clientId.charCodeAt(7) * 1000 + 42;
    const rng = new SeededRandom(seed);

    console.log(`─── ${profile.name} (${profile.clientId}) ───`);
    console.log(`  Ingreso mensual: $${profile.monthlyIncome}`);
    console.log(`  Gastos hormiga freq: ${profile.gastosHormigaDailyFrequency}/día`);

    const transactions = generateTransactionsForClient(profile, rng);

    // Calculate gastos hormiga stats for validation
    const hormigaTransactions = transactions.filter(
      (t) => t.category === 'coffee_snacks' && t.amount < 10
    );
    const hormigaTotal = hormigaTransactions.reduce((sum, t) => sum + t.amount, 0);
    const hormigaPct = (hormigaTotal / (profile.monthlyIncome * 2)) * 100; // 2 months

    console.log(`  Transacciones generadas: ${transactions.length}`);
    console.log(`  Gastos hormiga: ${hormigaTransactions.length} txns, $${hormigaTotal.toFixed(2)} total (${hormigaPct.toFixed(1)}% del ingreso mensual promedio)`);

    // Write to DynamoDB
    await batchWriteTransactions(docClient, transactions);
    totalTransactions += transactions.length;

    console.log(`  ✓ Insertadas correctamente\n`);
  }

  console.log('═══════════════════════════════════════════════════════════════');
  console.log(`Total de transacciones insertadas: ${totalTransactions}`);
  console.log('Seed completado exitosamente! 🎉');
}

main().catch((err) => {
  console.error('\n❌ Error ejecutando seed de transacciones:', err);
  process.exit(1);
});
