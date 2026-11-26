import { linkTo } from "../../lib/router";

type Item = [icon: string, label: string, query: string];

/** Everything the planner understands, grouped. Each chip opens the planner with that request
 * typed in. Queries are checked against the rules parser (backend/tests). */
const GROUPS: { icon: string; title: string; note?: string; tint: string; items: Item[] }[] = [
  {
    icon: "🙏",
    title: "Places of worship",
    note: "Every faith on the map. Muslim prayer times join the plan when you ask for a mosque.",
    tint: "from-amber-300/20",
    items: [
      ["⛪", "Church", "church before 10am"],
      ["🛕", "Hindu temple", "Hindu temple"],
      ["☸️", "Buddhist temple", "Buddhist temple"],
      ["☯️", "Taoist / Chinese temple", "Chinese temple"],
      ["🕌", "Mosque", "mosque at Asr"],
      ["🕌", "Surau / prayer room", "surau"],
      ["☬", "Gurdwara", "gurdwara"],
      ["🕍", "Synagogue", "synagogue"],
      ["🛕", "Any temple", "temple"],
    ],
  },
  {
    icon: "🍽",
    title: "Food by cuisine",
    note: "Restaurants tagged with that cuisine; name-only matches are flagged.",
    tint: "from-orange-300/20",
    items: [
      ["🍝", "Italian", "Italian dinner"],
      ["🍕", "Pizza", "pizza"],
      ["🍣", "Japanese", "sushi"],
      ["🥟", "Chinese", "dim sum"],
      ["🍛", "Indian", "Indian lunch"],
      ["🥩", "Korean", "Korean BBQ"],
      ["🍜", "Thai", "Thai food"],
      ["🍲", "Vietnamese", "pho"],
      ["🍚", "Malay / Indonesian", "nasi padang"],
      ["🍗", "Local", "chicken rice"],
      ["🍔", "Western", "burger"],
      ["🥐", "French", "French bistro"],
      ["🌮", "Mexican", "tacos"],
      ["🥙", "Middle Eastern", "kebab"],
      ["🦀", "Seafood", "seafood dinner"],
      ["🥘", "Spanish", "tapas"],
    ],
  },
  {
    icon: "🥗",
    title: "Any diet",
    note: "Add to any food stop — “halal Korean”, “vegan lunch”.",
    tint: "from-emerald-300/20",
    items: [
      ["✅", "Halal", "halal lunch"],
      ["🥦", "Vegetarian", "vegetarian dinner"],
      ["🌱", "Vegan", "vegan lunch"],
    ],
  },
  {
    icon: "☕",
    title: "Snacks & drinks",
    tint: "from-pink-300/20",
    items: [
      ["☕", "Coffee", "coffee"],
      ["🧋", "Bubble tea", "bubble tea"],
      ["🍨", "Ice cream & dessert", "ice cream"],
      ["🥐", "Bakery", "bakery"],
      ["🥢", "Hawker centre", "hawker centre"],
      ["🏪", "Convenience store", "7-eleven"],
    ],
  },
  {
    icon: "🧾",
    title: "Errands",
    tint: "from-cyan-300/20",
    items: [
      ["⛽", "Petrol", "petrol"],
      ["⚡", "EV charging", "EV charging"],
      ["🏧", "ATM / bank", "ATM"],
      ["💊", "Pharmacy", "pharmacy"],
      ["🩺", "Clinic", "clinic"],
      ["🛒", "Supermarket", "groceries"],
      ["🔌", "Phone charger", "phone charger"],
      ["💐", "Florist", "flowers"],
      ["📚", "Bookshop", "bookshop"],
      ["🚻", "Toilet", "toilet"],
      ["🅿️", "Parking", "parking"],
      ["🌳", "Park", "park"],
      ["🛍️", "Shopping mall", "mall"],
    ],
  },
  {
    icon: "🔎",
    title: "Anything else",
    note: "Not a category? It searches place names instead of giving up.",
    tint: "from-violet-300/20",
    items: [
      ["🍈", "Durian", "durian"],
      ["👕", "Uniqlo", "Uniqlo"],
      ["🚲", "Bike shop", "bike shop"],
    ],
  },
  {
    icon: "⏰",
    title: "…whenever you like",
    note: "Add a time to any stop.",
    tint: "from-sky-300/20",
    items: [
      ["🕐", "around 1pm", "lunch around 1pm"],
      ["⏳", "45 min in", "coffee 45 min in"],
      ["⏱️", "before 6pm", "pharmacy before 6pm"],
      ["🕌", "at a prayer time", "mosque at Asr"],
    ],
  },
];

export const ASK_QUERIES = GROUPS.flatMap((g) => g.items.map((i) => i[2]));

export default function AskAnything() {
  return (
    // CSS columns pack cards of different heights without gaps (masonry)
    <div className="mx-auto max-w-6xl gap-4 md:columns-2 lg:columns-3">
      {GROUPS.map((g, gi) => (
        <section
          key={g.title}
          className={`reveal mb-4 break-inside-avoid rounded-2xl bg-gradient-to-b ${g.tint} to-transparent p-[1px]`}
          style={{ transitionDelay: `${(gi % 3) * 80}ms` }}
        >
          <div className="rounded-2xl bg-ink-900/95 p-5">
            <h3 className="flex items-center gap-2 font-display text-lg font-semibold text-white">
              <span aria-hidden className="text-xl">
                {g.icon}
              </span>
              {g.title}
            </h3>
            {g.note && <p className="mt-1 text-xs text-slate-400">{g.note}</p>}
            <div className="mt-3 flex flex-wrap gap-1.5">
              {g.items.map(([icon, label, q]) => {
                const to = `/plan?q=${encodeURIComponent(q)}`;
                return (
                  <a key={label} href={to} onClick={linkTo(to)} className="chip text-xs" title={`Try “${q}”`}>
                    <span aria-hidden>{icon}</span>
                    {label}
                  </a>
                );
              })}
            </div>
          </div>
        </section>
      ))}
    </div>
  );
}
