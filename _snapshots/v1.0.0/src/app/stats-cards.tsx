import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Stats {
  total: number;
  totalHoldings: number;
  totalManagers: number;
  fundsWithStocks: number;
  uniqueTickers: number;
  topTickers: { ticker: string; count: number }[];
}

export function StatsCards({ stats }: { stats: Stats }) {
  const cards = [
    { label: "Toplam Fon", value: stats.total, suffix: "fon" },
    { label: "Hisse Fonları", value: stats.fundsWithStocks, suffix: "fon" },
    { label: "Yönetici", value: stats.totalManagers, suffix: "şirket" },
    { label: "Toplam Holding", value: stats.totalHoldings, suffix: "kayıt" },
    { label: "Benzersiz Hisse", value: stats.uniqueTickers, suffix: "ticker" },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      {cards.map((c) => (
        <Card key={c.label}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {c.label}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{c.value.toLocaleString("tr-TR")}</div>
            <p className="text-xs text-muted-foreground">{c.suffix}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
