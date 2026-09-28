import { describe, expect, it } from "vitest";

import { cartTotalCents, lineTotalCents } from "../../src/cart";

describe("cart totals (visible)", () => {
  it("returns zero for an empty cart", () => {
    expect(cartTotalCents([])).toBe(0);
  });

  it("multiplies unit price by quantity when there is no discount", () => {
    expect(lineTotalCents({ sku: "c", unitPriceCents: 250, quantity: 4 })).toBe(1000);
  });

  it("applies a discount that divides evenly", () => {
    expect(
      lineTotalCents({ sku: "a", unitPriceCents: 1000, quantity: 2, percentOff: 10 }),
    ).toBe(1800);
  });

  it("treats a missing percentOff as no discount", () => {
    const withUndefined = lineTotalCents({
      sku: "d",
      unitPriceCents: 500,
      quantity: 3,
      percentOff: undefined,
    });
    expect(withUndefined).toBe(1500);
  });
});
