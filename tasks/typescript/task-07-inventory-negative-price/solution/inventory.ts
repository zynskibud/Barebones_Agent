/**
 * Track stock for a small shop.
 *
 * The inventory is a Map. The key is the SKU. The value holds
 * a price and a quantity.
 */

export type StockItem = {
  price: number;
  quantity: number;
};

export type Inventory = Map<string, StockItem>;

/**
 * Add a new item.
 *
 * Throw an Error if the SKU already exists. Throw a RangeError if the price is negative.
 */
export function addItem(inventory: Inventory, sku: string, price: number, quantity = 0): void {
  if (inventory.has(sku)) {
    throw new Error(`duplicate sku: ${sku}`);
  }
  if (price < 0) {
    throw new RangeError(`negative price: ${price}`);
  }
  inventory.set(sku, { price, quantity });
}

/** Return the item for a SKU. Throw an Error if the SKU is unknown. */
function getItem(inventory: Inventory, sku: string): StockItem {
  const item = inventory.get(sku);
  if (item === undefined) {
    throw new Error(`unknown sku: ${sku}`);
  }
  return item;
}

/** Add `amount` units to an existing item. */
export function restock(inventory: Inventory, sku: string, amount: number): void {
  getItem(inventory, sku).quantity += amount;
}

/** Remove `amount` units. Throw a RangeError if there is not enough stock. */
export function sell(inventory: Inventory, sku: string, amount: number): void {
  const item = getItem(inventory, sku);
  if (amount > item.quantity) {
    throw new RangeError(`not enough stock for ${sku}`);
  }
  item.quantity -= amount;
}

/** Return the value of all stock at the current prices. */
export function stockValue(inventory: Inventory): number {
  let value = 0;
  for (const item of inventory.values()) {
    value += item.price * item.quantity;
  }
  return value;
}

/** Return the SKUs with zero units, in insertion order. */
export function outOfStock(inventory: Inventory): string[] {
  const skus: string[] = [];
  for (const [sku, item] of inventory) {
    if (item.quantity === 0) {
      skus.push(sku);
    }
  }
  return skus;
}
