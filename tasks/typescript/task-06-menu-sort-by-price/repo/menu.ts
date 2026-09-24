/**
 * A restaurant menu.
 *
 * A menu is a list of items. Each item has a name, a price,
 * and a course such as "starter", "main", or "dessert".
 */

export type MenuItem = {
  name: string;
  price: number;
  course: string;
};

/** Return the item names in menu order. */
export function itemNames(menu: MenuItem[]): string[] {
  return menu.map((item) => item.name);
}

/** Return the cheapest item. Return null if the menu is empty. */
export function cheapest(menu: MenuItem[]): MenuItem | null {
  if (menu.length === 0) {
    return null;
  }
  let best = menu[0];
  for (const item of menu.slice(1)) {
    if (item.price < best.price) {
      best = item;
    }
  }
  return best;
}

/** Return the items of one course, in menu order. */
export function byCourse(menu: MenuItem[], course: string): MenuItem[] {
  return menu.filter((item) => item.course === course);
}

/** Return the items that cost `limit` or less, in menu order. */
export function underPrice(menu: MenuItem[], limit: number): MenuItem[] {
  return menu.filter((item) => item.price <= limit);
}

/** Return one line for the printed menu. */
export function formatItem(item: MenuItem): string {
  return `${item.name} - ${item.price.toFixed(2)}`;
}

/** Return the whole menu as text, one item per line. */
export function formatMenu(menu: MenuItem[]): string {
  return menu.map(formatItem).join("\n");
}
