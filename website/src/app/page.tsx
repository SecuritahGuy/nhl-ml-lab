import Link from "next/link";

const navItems = [
  { href: "/schedule", label: "Schedule" },
  { href: "/rosters", label: "Rosters" },
  { href: "/lineups", label: "Lineups" },
  { href: "/predictions", label: "Predictions" },
];

export default function Home() {
  return (
    <div className="max-w-4xl mx-auto text-center">
      <h1 className="text-4xl font-bold mb-4 text-nhl-red">NHL ML Lab</h1>
      <p className="text-lg text-gray-600 mb-10">
        Predictions, schedules, rosters, and lineups powered by machine learning.
      </p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="block bg-white rounded-lg p-6 shadow-md hover:shadow-lg hover:bg-nhl-red hover:text-white transition-colors duration-200"
          >
            <span className="text-lg font-semibold">{item.label}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}