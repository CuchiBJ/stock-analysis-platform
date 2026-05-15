import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      <nav className="border-b border-border">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold">Stock Analysis Platform</h1>
            <div className="flex gap-4">
              <Link href="/dashboard" className="text-muted-foreground hover:text-foreground">
                Dashboard
              </Link>
              <Link href="/scanner" className="text-muted-foreground hover:text-foreground">
                Scanner
              </Link>
              <Link href="/watchlists" className="text-muted-foreground hover:text-foreground">
                Watchlists
              </Link>
            </div>
          </div>
        </div>
      </nav>
      
      <main className="container mx-auto px-4 py-8">
        <div className="text-center py-20">
          <h2 className="text-4xl font-bold mb-4">Stock Momentum Analysis</h2>
          <p className="text-muted-foreground text-lg mb-8">
            Find strong stocks with relative strength, sector rotation, and momentum signals
          </p>
          <div className="flex gap-4 justify-center">
            <Link
              href="/dashboard"
              className="px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90"
            >
              View Dashboard
            </Link>
            <Link
              href="/scanner"
              className="px-6 py-3 bg-secondary text-secondary-foreground rounded-lg hover:opacity-90"
            >
              Run Scanner
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
