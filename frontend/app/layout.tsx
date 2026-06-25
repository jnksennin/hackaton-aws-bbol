import type { Metadata } from 'next';
import '../styles/bb-tokens.css';

export const metadata: Metadata = {
  title: 'Asistente de Salud Financiera | Banco Bolivariano',
  description:
    'Agente conversacional que calcula tu Índice de Salud Financiera en tiempo real.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
