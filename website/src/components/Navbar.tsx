import Link from "next/link";

const links = [
  { href: "/schedule", label: "Schedule" },
  { href: "/rosters", label: "Rosters" },
  { href: "/lineups", label: "Lineups" },
  { href: "/predictions", label: "Predictions" },
];

export default function Navbar() {
  return (
    <nav className="bg-nhl-dark text-white p-3 mb-6">
      <div className="max-w-7xl mx-auto flex gap-6">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="hover:text-nhl-red transition-colors"
          >
            {link.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}