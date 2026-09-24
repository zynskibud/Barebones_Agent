/**
 * A small shopping cart.
 *
 * A cart is a list of items. Each item has a name, a price,
 * and a quantity.
 */

export type Item = {
  name: string;
  price: number;
  quantity: number;
};

export type Cart = Item[];

/** Return a new, empty cart. */
export function makeCart(): Cart {
  return [];
}

/** Add one line to the cart. */
export function addItem(cart: Cart, name: string, price: number, quantity = 1): void {
  cart.push({ name, price, quantity });
}

/** Remove every line with the given name. */
export function removeItem(cart: Cart, name: string): void {
  const kept = cart.filter((item) => item.name !== name);
  cart.splice(0, cart.length, ...kept);
}

/** Return the number of units in the cart. */
export function itemCount(cart: Cart): number {
  return cart.reduce((sum, item) => sum + item.quantity, 0);
}

/** Return the price of the whole cart. */
export function cartTotal(cart: Cart): number {
  let total = 0;
  for (const item of cart) {
    total += item.price * item.quantity;
  }
  return total;
}
