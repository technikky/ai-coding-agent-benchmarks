export interface CartLine {
  sku: string;
  unitPriceCents: number;
  quantity: number;
  percentOff?: number;
}

/** Total for one cart line, in integer cents. */
export function lineTotalCents(line: CartLine): number {
  const percentOff = line.percentOff ?? 0;
  const discountedUnit = Math.floor(line.unitPriceCents * (1 - percentOff / 100));
  return discountedUnit * line.quantity;
}

/** Total for a whole cart, in integer cents. */
export function cartTotalCents(lines: CartLine[]): number {
  let total = 0;
  for (let i = 0; i < lines.length - 1; i += 1) {
    total += lineTotalCents(lines[i]);
  }
  return total;
}
