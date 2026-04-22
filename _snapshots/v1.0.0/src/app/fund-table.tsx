import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface Fund {
  id: number;
  code: string;
  name: string;
  manager_name: string;
  fund_type: string;
  holding_count: number;
  report_date: string | null;
  stock_pct: number | null;
}

export default function FundTable({ funds }: { funds: Fund[] }) {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-20">Kod</TableHead>
            <TableHead>Fon Adı</TableHead>
            <TableHead className="hidden md:table-cell">Yönetici</TableHead>
            <TableHead className="w-20 text-center">Tür</TableHead>
            <TableHead className="w-24 text-right">Hisse</TableHead>
            <TableHead className="w-28 text-right hidden sm:table-cell">Tarih</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {funds.map((fund) => (
            <TableRow key={fund.id} className="cursor-pointer">
              <TableCell className="font-mono font-semibold">
                <Link href={`/fund/${fund.code}`} className="text-primary hover:underline">
                  {fund.code}
                </Link>
              </TableCell>
              <TableCell className="max-w-[300px] truncate">
                <Link href={`/fund/${fund.code}`} className="hover:underline">
                  {fund.name}
                </Link>
              </TableCell>
              <TableCell className="hidden md:table-cell text-muted-foreground text-sm truncate max-w-[200px]">
                {fund.manager_name}
              </TableCell>
              <TableCell className="text-center">
                <Badge variant="secondary" className="text-xs">
                  {fund.fund_type}
                </Badge>
              </TableCell>
              <TableCell className="text-right font-medium">
                {fund.holding_count > 0 ? (
                  <span>{fund.holding_count}</span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </TableCell>
              <TableCell className="text-right text-muted-foreground text-sm hidden sm:table-cell">
                {fund.report_date || "—"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
