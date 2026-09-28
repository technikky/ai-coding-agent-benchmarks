export interface CartLine {
  sku: string;
  unitPriceCents: number;
  quantity: number;
  percentOff?: number;
}

/**
 * Total for one cart line, in integer cents.
 *
 * The exact value is rounded once, at the end, with an exact half going up. Rounding
 * the discounted unit price first would lose up to a cent on every unit.
 */
export function lineTotalCents(line: CartLine): number {
  const percentOff = line.percentOff ?? 0;
  const exact = (line.unitPriceCents * line.quantity * (100 - percentOff)) / 100;
  return Math.round(exact);
}

/** Total for a whole cart, in integer cents. */
export function cartTotalCents(lines: CartLine[]): number {
  return lines.reduce((total, line) => total + lineTotalCents(line), 0);
}
