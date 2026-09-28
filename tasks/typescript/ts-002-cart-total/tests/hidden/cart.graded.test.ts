import { describe, expect, it } from "vitest";

import { cartTotalCents, lineTotalCents } from "../../src/cart";

describe("cart totals (graded)", () => {
  it("rounds the line total once rather than flooring each unit", () => {
    // Exact: 199 * 7 * 0.9 = 1253.7 -> 1254.
    // Flooring each unit gives floor(179.1) * 7 = 1253.
    expect(
      lineTotalCents({ sku: "a", unitPriceCents: 199, quantity: 7, percentOff: 10 }),
    ).toBe(1254);
  });

  it("rounds a half-cent line total up", () => {
    // Exact: 101 * 1 * 0.5 = 50.5, an exact half, so 51.
    expect(
      lineTotalCents({ sku: "b", unitPriceCents: 101, quantity: 1, percentOff: 50 }),
    ).toBe(51);
  });

  it("includes the final line in the cart total", () => {
    const lines = [
      { sku: "a", unitPriceCents: 1000, quantity: 2, percentOff: 10 },
      { sku: "b", unitPriceCents: 250, quantity: 4 },
    ];
    expect(cartTotalCents(lines)).toBe(2800);
  });

  it("totals a cart that holds a single line", () => {
    expect(
      cartTotalCents([{ sku: "a", unitPriceCents: 1000, quantity: 2, percentOff: 10 }]),
    ).toBe(1800);
  });
});
