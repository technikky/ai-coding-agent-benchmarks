# Two defects in cart totalling

`src/cart.ts` computes shopping-cart totals in integer cents. It contains two
**independent** defects: one in `lineTotalCents`, one in `cartTotalCents`. Fixing
either does not fix the other.

## Context

```ts
export interface CartLine {
  sku: string;
  unitPriceCents: number;
  quantity: number;
  percentOff?: number;
}

export function lineTotalCents(line: CartLine): number;
export function cartTotalCents(lines: CartLine[]): number;
```

All money is in integer cents. `percentOff` is a percentage, so `10` means ten per
cent off, and it may be fractional. Every `unitPriceCents` and `quantity` in the tests
is a non-negative integer.

## Requirements

1. **Round the line total once, at the end.** `lineTotalCents` must compute the exact
   value

   ```text
   unitPriceCents * quantity * (100 - percentOff) / 100
   ```

   and round that single result to the nearest integer cent, with an exact half rounded
   **up**. The current implementation instead discards the fraction from each
   *discounted unit price* before multiplying by the quantity, which loses up to one
   cent per unit. A missing `percentOff` counts as `0`.

2. **Total every line.** `cartTotalCents` must return the sum of `lineTotalCents` over
   **all** lines. The current loop stops one line early, so the last line of every cart
   is ignored. An empty cart totals `0`.

## Examples

```ts
// 199 cents, 10% off, 7 units: exact 1253.7, rounded 1254.
// The current code computes floor(179.1) = 179, then 179 * 7 = 1253.
expect(lineTotalCents({ sku: "a", unitPriceCents: 199, quantity: 7, percentOff: 10 }))
  .toBe(1254);

// 101 cents, 50% off, 1 unit: exact 50.5, an exact half, rounded up to 51.
expect(lineTotalCents({ sku: "b", unitPriceCents: 101, quantity: 1, percentOff: 50 }))
  .toBe(51);

// No discount: 250 * 4.
expect(lineTotalCents({ sku: "c", unitPriceCents: 250, quantity: 4 })).toBe(1000);
```

```ts
const lines = [
  { sku: "a", unitPriceCents: 1000, quantity: 2, percentOff: 10 }, // 1800
  { sku: "b", unitPriceCents: 250, quantity: 4 },                  // 1000
];
expect(cartTotalCents(lines)).toBe(2800);   // the current code returns 1800
expect(cartTotalCents([lines[0]])).toBe(1800); // the current code returns 0
expect(cartTotalCents([])).toBe(0);
```

## Behaviour that must not change

- An empty cart totals `0`.
- A line with no discount totals `unitPriceCents * quantity`.
- A discount that divides evenly is unaffected by the rounding change.
- The `CartLine` interface and both function signatures stay as they are.

## Definition of done

`lineTotalCents` rounds the exact line total once with halves going up, and
`cartTotalCents` sums every line.

Change only `src/cart.ts`. Do not edit any file under `tests/`.
